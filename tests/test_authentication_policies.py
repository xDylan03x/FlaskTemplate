import hashlib
import itertools
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.orm.attributes import set_committed_value

from app import create_app, db, pm
from app.models import AuditEvent, LoginRecord, LoginToken, UserGroup


REQUIRED = 'authentication_policies.2fa_required'
UNKNOWN = 'authentication_policies.unknown_device_requires_2fa'
ALTERNATIVE = 'authentication_policies.2fa_applies_to_alternative_login_methods'
BREACH = 'authentication_policies.password_breach_checking'
MANAGE = 'users.update_authentication_policies'


def sqlite_token_timezone(token, context, attrs=None):
    # SQLite drops timezone information; production uses PostgreSQL timestamptz.
    expiration = token.__dict__.get('expiration')
    if expiration is not None and expiration.tzinfo is None:
        set_committed_value(token, 'expiration', expiration.replace(tzinfo=timezone.utc))


class AuthenticationPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global UserManager, LoginTokenManager, UserDeviceManager
        cls.directory = tempfile.TemporaryDirectory()
        cls.app = create_app(SimpleNamespace(
            TESTING=True, SECRET_KEY='test-key', WTF_CSRF_ENABLED=False,
            SQLALCHEMY_DATABASE_URI='sqlite:///' + str(Path(cls.directory.name) / 'tests.db'),
            SQLALCHEMY_TRACK_MODIFICATIONS=False, BYPASS_AUTHENTICATION=False,
            OAUTH2_PROVIDERS={}, STATIC_FOLDER=str(Path(__file__).resolve().parents[1] / 'app/core/static'),
        ))
        from app.model_managers import UserManager, LoginTokenManager, UserDeviceManager
        sa.event.listen(LoginToken, 'load', sqlite_token_timezone)
        sa.event.listen(LoginToken, 'refresh', sqlite_token_timezone)

    @classmethod
    def tearDownClass(cls):
        sa.event.remove(LoginToken, 'load', sqlite_token_timezone)
        sa.event.remove(LoginToken, 'refresh', sqlite_token_timezone)
        with cls.app.app_context():
            db.engine.dispose()
        cls.directory.cleanup()

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.addCleanup(self.cleanup_database)
        self.app.config.update(BYPASS_AUTHENTICATION=False, OAUTH2_PROVIDERS={})
        for target in ('app.model_managers.NotificationManager.send_notification',
                       'app.auth.routes.send_email', 'app.auth.routes.send_sms',
                       'app.auth.routes.twilio_verify_send'):
            mock = self.enterContext(patch(target))
            setattr(self, target.rsplit('.', 1)[1], mock)
        self.verify = self.enterContext(patch('app.auth.routes.twilio_verify_check', return_value=True))
        self.user = UserManager.create_user('Test User', 'user@example.com', email_verified=True)
        self.user.set_password('test-password')
        self.user.set_setting('security.password_breach_check', False)
        db.session.commit()
        self.client = self.app.test_client()

    def cleanup_database(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def policy(self, key, enabled=True):
        self.user.set_permission(key, enabled)
        db.session.commit()

    def token(self, source='traditional login', channel=None, **kwargs):
        token, raw = LoginTokenManager.create_login_token(
            user_id=self.user.id, auth_source=source, immediate_login=True, **kwargs)
        token.magic_link_channel = channel
        db.session.commit()
        return token, raw

    def sign_in(self, user=None):
        with self.client.session_transaction() as session:
            session['_user_id'] = (user or self.user).uuid36
            session['_fresh'] = True

    def field(self, key):
        return pm.get(key).permission_field_name

    def input_attributes(self, response, field):
        from html.parser import HTMLParser

        class Inputs(HTMLParser):
            attributes = None

            def handle_starttag(parser, tag, attrs):
                values = dict(attrs)
                if tag in ('input', 'select') and values.get('name') == field:
                    parser.attributes = values

        parser = Inputs()
        parser.feed(response.get_data(as_text=True))
        self.assertIsNotNone(parser.attributes)
        return parser.attributes

    def test_policy_matrix(self):
        self.user.phone_number = '+12025550123'
        self.user.phone_number_verified = True
        device = UserDeviceManager.create_user_device(self.user.id, 'Policy Test Browser')
        for source, trusted, required, unknown, alternative, preference in itertools.product(
                ('traditional login', 'magic link', 'oauth authorization state'),
                (False, True), (False, True), (False, True), (False, True), (False, True)):
            with self.subTest(source=source, trusted=trusted, required=required,
                              unknown=unknown, alternative=alternative, preference=preference):
                for key, value in ((REQUIRED, required), (UNKNOWN, unknown), (ALTERNATIVE, alternative)):
                    self.user.set_permission(key, value)
                self.user.set_setting('security.two_factor_auth', preference)
                device.device_trusted = trusted
                db.session.commit()
                token, raw = self.token(source, 'email' if source == 'magic link' else None)
                client = self.app.test_client()
                response = client.get('/auth/' + raw, headers={'User-Agent': device.user_agent})
                expected = (unknown and not trusted) or ((source == 'traditional login' or alternative) and (required or preference))
                self.assertEqual(response.location, '/auth/2fa/' + raw if expected else '/')
                self.assertEqual(token.used, not expected)

    def test_new_device_and_password_login_use_shared_flow(self):
        self.policy(UNKNOWN)
        response = self.client.post('/auth/login', data={'email': self.user.email, 'password': 'test-password', 'remember_me': 'y'})
        self.assertNotIn('/2fa/', response.location)
        token = LoginTokenManager.get_login_token(response.location.rsplit('/', 1)[1])
        self.assertTrue(token.remember_login)
        response = self.client.get(response.location)
        self.assertIn('/auth/2fa/', response.location)
        self.send_notification.assert_called_once()

    def test_verification_finishes_once_and_can_trust_device(self):
        self.policy(REQUIRED)
        token, raw = self.token()
        challenge = self.client.get('/auth/' + raw)
        self.assertEqual(challenge.location, '/auth/2fa/' + raw)
        self.client.post(challenge.location, data={'method': 'Email'})
        self.twilio_verify_send.assert_called_once_with(to=self.user.email, channel='email')
        self.verify.return_value = False
        code_url = challenge.location + '?code_sent=True&verification_method=email'
        self.client.post(code_url, data={'code': 'wrong', 'trust_device': 'y'})
        self.assertFalse(token.two_factor_verified)
        self.verify.return_value = True
        response = self.client.post(code_url, data={'code': '123456', 'trust_device': 'y'})
        self.assertTrue(token.two_factor_verified)
        self.assertTrue(self.user.devices.first().device_trusted)
        self.assertEqual(self.client.get(response.location).location, '/')
        self.assertEqual(db.session.scalar(sa.select(sa.func.count()).select_from(LoginRecord)), 1)
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/login')

    def test_untrusted_device_stays_untrusted_without_checkbox(self):
        self.policy(UNKNOWN)
        token, raw = self.token()
        self.client.get('/auth/' + raw)
        self.client.post('/auth/2fa/' + raw + '?code_sent=True&verification_method=email', data={'code': '123456'})
        self.assertTrue(token.two_factor_verified)
        self.assertFalse(self.user.devices.first().device_trusted)
        self.assertEqual(self.client.get('/auth/' + raw).location, '/')

    def test_oauth_callback_obeys_policies(self):
        self.policy(REQUIRED)
        self.policy(ALTERNATIVE)
        self.app.config['OAUTH2_PROVIDERS'] = {'test': {
            'client_id': 'id', 'client_secret': 'secret', 'token_url': 'https://provider.example/token',
            'userinfo': {'url': 'https://provider.example/user', 'email': lambda data: data['email']},
        }}
        token, raw = LoginTokenManager.create_login_token(auth_source='oauth authorization state')
        with self.client.session_transaction() as session:
            session['oauth2_state'] = raw
        with patch('app.auth.routes.requests.post', return_value=Mock(status_code=200, json=lambda: {'access_token': 'access'})), \
                patch('app.auth.routes.requests.get', return_value=Mock(status_code=200, json=lambda: {'email': self.user.email, 'email_verified': True})):
            response = self.client.get('/auth/oauth/callback/test?state=' + raw + '&code=code')
        self.assertEqual(token.user_id, self.user.id)
        self.assertEqual(self.client.get(response.location).location, '/auth/2fa/' + raw)

    def magic_request(self):
        token, raw = LoginTokenManager.create_login_token(user_id=self.user.id, auth_source='magic link')
        return token, '/auth/magic-link/' + raw

    def test_magic_preflight_blocks_unusable_links_and_forged_options(self):
        self.policy(REQUIRED)
        self.policy(ALTERNATIVE)
        token, url = self.magic_request()
        response = self.client.post(url, data={'method': 'Email'})
        self.assertEqual(response.location, '/auth/login')
        self.send_email.assert_not_called()
        self.send_sms.assert_not_called()
        self.assertIn('another login method', self.client.get(response.location).get_data(as_text=True))
        self.user.totp_verified = True
        db.session.commit()
        response = self.client.post(url, data={'method': 'Text'})
        self.assertEqual(response.status_code, 200)
        self.send_sms.assert_not_called()
        response = self.client.post(url, data={'method': 'Email'})
        self.assertEqual(response.location, '/auth/login')
        issued = db.session.scalars(sa.select(LoginToken).where(LoginToken.immediate_login.is_(True))).one()
        self.assertEqual(issued.magic_link_channel, 'email')
        self.assertFalse(issued.two_factor_verified)
        self.assertEqual(issued.auth_source, 'magic link')
        self.assertEqual(issued.hashed_token, hashlib.sha1(self.send_email.call_args.kwargs['body'].split('/auth/')[1].split('<')[0].encode()).hexdigest())

    def test_text_magic_link_delivery_keeps_email_as_second_factor(self):
        self.policy(REQUIRED)
        self.policy(ALTERNATIVE)
        self.user.phone_number = '+12025550123'
        self.user.phone_number_verified = True
        db.session.commit()
        request_token, url = self.magic_request()
        response = self.client.get(url)
        html = response.get_data(as_text=True)
        self.assertIn('value="Text"', html)
        self.assertIn('value="Email"', html)
        response = self.client.post(url, data={'method': 'Text'})
        self.assertEqual(response.location, '/auth/login')
        body = self.send_sms.call_args.kwargs['body']
        raw = body.split('/auth/')[1].split()[0]
        token = LoginTokenManager.get_login_token(raw)
        self.assertEqual(token.magic_link_channel, 'text')
        self.assertFalse(request_token.immediate_login)
        response = self.client.get('/auth/' + raw)
        self.assertEqual(response.location, '/auth/2fa/' + raw)
        html = self.client.get(response.location).get_data(as_text=True)
        self.assertIn('value="Email"', html)
        self.assertNotIn('value="Text"', html)
        self.assertNotIn('value="Call"', html)
        response = self.client.post(response.location + '?code_sent=True&verification_method=email', data={'code': '123456'})
        self.assertTrue(token.two_factor_verified)
        self.assertEqual(self.client.get(response.location).location, '/')

    def test_magic_link_exclusions_apply_to_selection_and_code_submission(self):
        self.user.phone_number = '+12025550123'
        self.user.phone_number_verified = True
        self.user.totp_verified = True
        db.session.commit()
        for channel, excluded in (('email', ('Email',)), ('text', ('Text', 'Call'))):
            token, raw = self.token('magic link', channel)
            url = '/auth/2fa/' + raw
            response = self.client.get(url)
            for method in excluded:
                with self.subTest(channel=channel, method=method):
                    self.assertNotIn('value="' + method + '"', response.get_data(as_text=True))
                    self.client.post(url, data={'method': method})
                    rejected = self.client.post(url + '?code_sent=True&verification_method=' + method.lower(), data={'code': '123456'})
                    self.assertEqual(rejected.location, '/auth/login')
                    self.assertFalse(token.two_factor_verified)
            self.verify.assert_not_called()
            self.twilio_verify_send.assert_not_called()
            response = self.client.post(url + '?code_sent=True&verification_method=authenticator_app', data={'code': '123456'})
            self.assertEqual(response.location, '/auth/' + raw)
            self.assertTrue(token.two_factor_verified)
            self.verify.reset_mock()

    def test_magic_request_and_legacy_links_cannot_bypass_primary_authentication(self):
        token, url = self.magic_request()
        raw = url.rsplit('/', 1)[1]
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/login')
        self.assertEqual(self.client.post('/auth/2fa/' + raw + '?code_sent=True&verification_method=email', data={'code': '123456'}).location, '/auth/login')
        self.assertFalse(token.two_factor_verified)
        self.verify.assert_not_called()
        token.immediate_login = True
        db.session.commit()
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/login')
        self.assertEqual(self.client.post('/auth/2fa/' + raw + '?code_sent=True&verification_method=email', data={'code': '123456'}).location, '/auth/login')
        self.assertEqual(self.client.get(url).location, '/auth/login')

    def test_magic_rechecks_changed_policies_methods_and_device(self):
        token, raw = self.token('magic link', 'email')
        self.policy(UNKNOWN)
        # A new device now requires a factor other than the link's email.
        response = self.client.get('/auth/' + raw)
        self.assertEqual(response.location, '/auth/login')
        self.assertFalse(token.used)
        self.user.totp_verified = True
        db.session.commit()
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/2fa/' + raw)
        self.user.totp_verified = False
        db.session.commit()
        self.assertEqual(self.client.post('/auth/2fa/' + raw + '?code_sent=True&verification_method=authenticator_app', data={'code': '123456'}).location, '/auth/login')
        self.verify.assert_not_called()

    def test_group_inheritance_conflicts_and_individual_restoration(self):
        self.policy(REQUIRED)
        disabled = UserGroup(title='Disabled')
        enabled = UserGroup(title='Enabled')
        db.session.add_all([disabled, enabled])
        disabled.set_permission(REQUIRED, False)
        enabled.set_permission(REQUIRED, True)
        self.user.groups = [disabled]
        db.session.commit()
        self.assertFalse(self.user.can(REQUIRED))
        self.user.groups.append(enabled)
        db.session.commit()
        self.assertTrue(self.user.can(REQUIRED))
        self.assertTrue(self.user.inherited_permissions()[REQUIRED]['conflict'])
        self.user.set_permission('users.update', True)
        self.user.set_permission(MANAGE, True)
        db.session.commit()
        self.sign_in()
        url = '/system-settings/users/' + self.user.uuid36
        response = self.client.get(url)
        attrs = self.input_attributes(response, self.field(REQUIRED))
        self.assertIn('checked', attrs)
        self.assertIn('disabled', attrs)
        self.assertIn('Enabled wins over Disabled', response.get_data(as_text=True))
        self.client.post(url, data={'name': self.user.name, 'status': 'active'})
        self.assertTrue(self.user.permissions.filter_by(key=REQUIRED).one().value)
        self.user.groups.clear()
        db.session.commit()
        self.assertTrue(self.user.can(REQUIRED))

    def manager(self, policies=False, permissions=False):
        manager = UserManager.create_user('Manager', 'manager@example.com', email_verified=True)
        for key in ('users.update', 'groups.create', 'groups.update'):
            manager.set_permission(key, True)
        manager.set_permission(MANAGE, policies)
        manager.set_permission('users.update_permissions', permissions)
        db.session.commit()
        self.sign_in(manager)
        return manager

    def test_individual_policy_and_permission_management_are_independent(self):
        manager = self.manager(policies=True)
        self.user.set_permission('users.create', True)
        db.session.commit()
        url = '/system-settings/users/' + self.user.uuid36
        response = self.client.get(url)
        self.assertNotIn('disabled', self.input_attributes(response, self.field(REQUIRED)))
        self.assertIn('disabled', self.input_attributes(response, self.field('users.create')))
        self.client.post(url, data={'name': self.user.name, 'status': 'active', self.field(REQUIRED): 'y'})
        self.assertTrue(self.user.can(REQUIRED))
        self.assertTrue(self.user.can('users.create'))
        manager.set_permission(MANAGE, False)
        manager.set_permission('users.update_permissions', True)
        db.session.commit()
        self.client.post(url, data={'name': self.user.name, 'status': 'active', self.field('users.create'): 'y'})
        self.assertTrue(self.user.can(REQUIRED))
        self.assertTrue(any(REQUIRED in event.message for event in db.session.scalars(sa.select(AuditEvent))))

    def test_self_grant_cannot_edit_policies_in_same_request(self):
        manager = self.manager(permissions=True)
        data = {'name': manager.name, 'status': 'active', self.field(REQUIRED): 'y'}
        for spec in pm.all():
            if manager.can(spec.permission):
                data[spec.permission_field_name] = 'y'
        data[self.field(MANAGE)] = 'y'
        self.client.post('/system-settings/users/' + manager.uuid36, data=data)
        self.assertTrue(manager.can(MANAGE))
        self.assertFalse(manager.can(REQUIRED))

    def test_group_policy_and_permission_management_are_independent(self):
        manager = self.manager(policies=True)
        response = self.client.post('/system-settings/groups/new', data={
            'title': 'Policy Group', self.field(REQUIRED): 'allow', self.field('users.create'): 'invalid',
        })
        self.assertEqual(response.location, '/system-settings/groups')
        group = db.session.scalar(sa.select(UserGroup).where(UserGroup.title == 'Policy Group'))
        self.assertEqual({record.key: record.value for record in group.permissions}, {REQUIRED: True})
        url = '/system-settings/groups/' + group.uuid36
        response = self.client.get(url)
        self.assertNotIn('disabled', self.input_attributes(response, self.field(REQUIRED)))
        self.assertIn('>Enabled<', response.get_data(as_text=True))
        manager.set_permission(MANAGE, False)
        manager.set_permission('users.update_permissions', True)
        db.session.commit()
        response = self.client.post(url, data={
            'title': group.title, 'users': [str(self.user.id)],
            self.field(REQUIRED): 'invalid', self.field('users.create'): 'allow',
        })
        self.assertEqual(response.location, '/system-settings/groups')
        self.assertTrue(self.user.can(REQUIRED))
        self.assertTrue(self.user.can('users.create'))
        manager.set_permission(MANAGE, True)
        db.session.commit()
        self.client.post(url, data={'title': group.title, 'users': [str(self.user.id)], self.field('users.create'): 'allow'})
        self.assertFalse(self.user.can(REQUIRED))
        self.assertFalse(any(record.key == REQUIRED for record in group.permissions))

    def test_required_locks_preference_without_overwriting_it(self):
        self.policy(REQUIRED)
        self.sign_in()
        url = '/account-settings/security'
        attrs = self.input_attributes(self.client.get(url), 'two_factor_auth')
        self.assertIn('checked', attrs)
        self.assertIn('disabled', attrs)
        self.client.post(url, data={'two_factor_auth': 'y'})
        self.assertFalse(self.user.get_setting('security.two_factor_auth'))
        self.policy(REQUIRED, False)
        attrs = self.input_attributes(self.client.get(url), 'two_factor_auth')
        self.assertNotIn('checked', attrs)
        self.assertNotIn('disabled', attrs)
        self.client.post(url, data={'two_factor_auth': 'y'})
        self.assertTrue(self.user.get_setting('security.two_factor_auth'))
        self.policy(REQUIRED)
        self.client.post(url, data={})
        self.assertTrue(self.user.get_setting('security.two_factor_auth'))

    def test_setup_account_preserves_preference_under_required_policy(self):
        self.user.status = 'pending'
        self.policy(REQUIRED)
        self.sign_in()
        attrs = self.input_attributes(self.client.get('/setup-account'), 'two_factor_auth')
        self.assertIn('checked', attrs)
        self.assertIn('disabled', attrs)
        response = self.client.post('/setup-account', data={
            'name': 'Updated', 'password': 'new-password', 'confirm_password': 'new-password', 'two_factor_auth': 'y',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.user.status, 'active')
        self.assertTrue(self.user.check_password('new-password'))
        self.assertFalse(self.user.get_setting('security.two_factor_auth'))

    def test_defaults_update_users_lockdown_and_manual_grant(self):
        for key in (REQUIRED, UNKNOWN, ALTERNATIVE, MANAGE):
            self.assertFalse(self.user.can(key))
            self.assertFalse(self.user.permissions.filter_by(key=key).one().value)
        db.session.delete(self.user.permissions.filter_by(key=UNKNOWN).one())
        self.user.set_permission('users.update_permissions', True)
        self.user.set_setting('security.two_factor_auth', True)
        db.session.commit()
        result = self.app.test_cli_runner().invoke(args=['update_users'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertFalse(self.user.can(UNKNOWN))
        self.assertFalse(self.user.can(MANAGE))
        self.assertTrue(self.user.get_setting('security.two_factor_auth'))
        result = self.app.test_cli_runner().invoke(args=['tools', 'permissions', 'set', self.user.email, MANAGE, 'allow'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(self.user.can(MANAGE))
        for key in (REQUIRED, UNKNOWN, ALTERNATIVE):
            self.policy(key)
        UserManager.lockdown_user(self.user)
        for key in (REQUIRED, UNKNOWN, ALTERNATIVE):
            self.assertTrue(self.user.can(key))
        self.assertFalse(self.user.can(MANAGE))
        self.assertEqual(self.user.status, 'disabled')

    def test_initial_admin_and_cli_group_policies(self):
        result = self.app.test_cli_runner().invoke(args=['create_admin'], input='Admin\nadmin@example.com\n')
        self.assertEqual(result.exit_code, 0)
        admin = UserManager.get_user_by_email('admin@example.com')
        self.assertTrue(admin.can(MANAGE))
        self.assertFalse(admin.can(REQUIRED))
        group = UserGroup(title='CLI Policies')
        group.users.append(self.user)
        db.session.add(group)
        db.session.commit()
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['tools', 'groups', 'permissions', 'set', str(group.id), REQUIRED, 'allow'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(self.user.can(REQUIRED))
        result = runner.invoke(args=['tools', 'permissions', 'list', self.user.email])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn(REQUIRED, result.output)
        self.assertIn('CLI Policies', result.output)
        runner.invoke(args=['tools', 'groups', 'permissions', 'set', str(group.id), REQUIRED, 'unset'])
        self.assertFalse(self.user.can(REQUIRED))

    def test_all_disabled_accepts_new_devices_and_bypass_skips_preflight(self):
        token, raw = self.token()
        self.assertEqual(self.client.get('/auth/' + raw, headers={'User-Agent': 'New Device'}).location, '/')
        self.assertFalse(token.two_factor_verified)
        for key in (REQUIRED, UNKNOWN, ALTERNATIVE):
            self.policy(key)
        self.app.config['BYPASS_AUTHENTICATION'] = True
        request_token, url = self.magic_request()
        response = self.client.post(url, data={'method': 'Email'})
        self.assertEqual(response.location, '/auth/login')
        self.send_email.assert_called_once()

    def test_special_flows_and_development_bypass(self):
        for key in (REQUIRED, UNKNOWN, ALTERNATIVE):
            self.policy(key)
        for source, flags in (
                ('welcome email', {'create_account': True}),
                ('starting impersonation session', {'for_impersonation': True})):
            with self.subTest(source=source):
                token, raw = self.token(source, **flags)
                self.assertEqual(self.app.test_client().get('/auth/' + raw).location, '/')
        token, raw = self.token(reset_password=True)
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/login')
        self.assertEqual(self.client.post('/auth/2fa/' + raw + '?code_sent=True&verification_method=email', data={'code': '123456'}).location, '/auth/login')
        token, raw = self.token('restoring from impersonation session')
        self.assertEqual(self.client.get('/auth/' + raw, headers={'User-Agent': 'Restored Browser'}).location, '/auth/2fa/' + raw)
        token, raw = self.token('phone number verification')
        token.immediate_login = False
        token.verify_phone_number = True
        db.session.commit()
        response = self.client.get('/auth/' + raw, headers={'User-Agent': 'Untrusted Phone Browser'})
        self.assertEqual(response.location, '/auth/2fa/' + raw)
        self.assertFalse(self.user.phone_number_verified)
        response = self.client.post(response.location + '?code_sent=True&verification_method=email', data={'code': '123456'})
        self.assertEqual(self.client.get(response.location).location, '/')
        self.assertTrue(self.user.phone_number_verified)
        self.app.config['BYPASS_AUTHENTICATION'] = True
        token, raw = self.token()
        self.assertEqual(self.app.test_client().get('/auth/' + raw).location, '/')

    def test_personal_unknown_device_setting_applies_to_all_login_methods(self):
        self.user.set_setting('security.unknown_device_requires_2fa', True)
        self.user.phone_number = '+12025550123'
        self.user.phone_number_verified = True
        db.session.commit()
        for source in ('traditional login', 'magic link', 'oauth authorization state'):
            token, raw = self.token(source, 'email' if source == 'magic link' else None)
            response = self.app.test_client().get('/auth/' + raw)
            self.assertEqual(response.location, '/auth/2fa/' + raw)
            self.assertFalse(token.used)

    def test_personal_alternative_setting_extends_enabled_2fa(self):
        self.user.set_setting('security.2fa_applies_to_alternative_login_methods', True)
        db.session.commit()
        for preference in (False, True):
            self.user.set_setting('security.two_factor_auth', preference)
            db.session.commit()
            token, raw = self.token('oauth authorization state')
            response = self.app.test_client().get('/auth/' + raw)
            self.assertEqual(response.location, '/auth/2fa/' + raw if preference else '/')

    def test_new_security_settings_save_and_policy_locks_preserve_preferences(self):
        self.sign_in()
        url = '/account-settings/security'
        self.client.post(url, data={'two_factor_auth': 'y', 'unknown_device_requires_2fa': 'y', 'two_factor_alternative_logins': 'y'})
        self.assertTrue(self.user.get_setting('security.unknown_device_requires_2fa'))
        self.assertTrue(self.user.get_setting('security.2fa_applies_to_alternative_login_methods'))
        # Turning 2FA off hides its alternative-login control without clearing that preference.
        self.client.post(url, data={})
        self.assertFalse(self.user.get_setting('security.two_factor_auth'))
        self.assertTrue(self.user.get_setting('security.2fa_applies_to_alternative_login_methods'))
        for policy, setting, field in (
                (UNKNOWN, 'security.unknown_device_requires_2fa', 'unknown_device_requires_2fa'),
                (ALTERNATIVE, 'security.2fa_applies_to_alternative_login_methods', 'two_factor_alternative_logins'),
                (BREACH, 'security.password_breach_check', 'password_breach_check')):
            with self.subTest(policy=policy):
                self.user.set_setting(setting, False)
                self.policy(policy)
                attrs = self.input_attributes(self.client.get(url), field)
                self.assertIn('checked', attrs)
                self.assertIn('disabled', attrs)
                self.client.post(url, data={field: 'y'})
                self.assertFalse(self.user.get_setting(setting))
                self.policy(policy, False)
                attrs = self.input_attributes(self.client.get(url), field)
                self.assertNotIn('disabled', attrs)
                self.assertNotIn('checked', attrs)

    def test_alternative_control_visibility_follows_2fa_or_policy(self):
        self.sign_in()
        html = self.client.get('/account-settings/security').get_data(as_text=True)
        self.assertIn('x-show="twoFactor || false"', html)
        self.assertIn('"twoFactor": false', html)
        self.assertIn('x-model="twoFactor"', html)
        self.policy(REQUIRED)
        html = self.client.get('/account-settings/security').get_data(as_text=True)
        self.assertIn('"twoFactor": true', html)
        self.policy(REQUIRED, False)
        self.policy(ALTERNATIVE)
        html = self.client.get('/account-settings/security').get_data(as_text=True)
        self.assertIn('x-show="twoFactor || true"', html)

    def test_disabled_group_policy_leaves_personal_choice(self):
        self.policy(REQUIRED)
        self.policy(UNKNOWN)
        self.policy(ALTERNATIVE)
        self.policy(BREACH)
        group = UserGroup(title='Optional Security')
        db.session.add(group)
        for policy in (REQUIRED, UNKNOWN, ALTERNATIVE, BREACH):
            group.set_permission(policy, False)
        self.user.groups.append(group)
        db.session.commit()
        self.sign_in()
        for field in ('two_factor_auth', 'unknown_device_requires_2fa', 'two_factor_alternative_logins', 'password_breach_check'):
            self.assertNotIn('disabled', self.input_attributes(self.client.get('/account-settings/security'), field))
        token, raw = self.token()
        self.assertEqual(self.app.test_client().get('/auth/' + raw).location, '/')
        self.user.set_setting('security.two_factor_auth', True)
        db.session.commit()
        token, raw = self.token()
        self.assertEqual(self.app.test_client().get('/auth/' + raw).location, '/auth/2fa/' + raw)

    def test_password_breach_policy_and_personal_choice(self):
        group = UserGroup(title='Breach Policy')
        db.session.add(group)
        self.user.groups.append(group)
        db.session.commit()
        with patch('app.auth.routes.hibp_password_check', return_value=True) as check:
            for group_value, preference in itertools.product((None, False, True), (False, True)):
                with self.subTest(group_value=group_value, preference=preference):
                    group.set_permission(BREACH, group_value)
                    self.user.set_setting('security.password_breach_check', preference)
                    db.session.commit()
                    check.reset_mock()
                    response = self.app.test_client().post('/auth/login', data={'email': self.user.email, 'password': 'test-password'})
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(check.called, bool(group_value or preference))
            self.policy(BREACH)
            group.set_permission(BREACH, None)
            self.user.set_setting('security.password_breach_check', False)
            db.session.commit()
            check.reset_mock()
            response = self.client.post('/auth/login', data={'email': self.user.email, 'password': 'test-password'})
            check.assert_called_once_with('test-password')
            with self.client.session_transaction() as session:
                self.assertTrue(any('data breach' in message for _, message in session['_flashes']))
            self.app.config['BYPASS_AUTHENTICATION'] = True
            check.reset_mock()
            self.client.post('/auth/login', data={'email': self.user.email})
            check.assert_not_called()

    def test_expired_and_invalid_tokens_still_fail(self):
        token, raw = self.token()
        token.expiration = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        self.assertEqual(self.client.get('/auth/' + raw).location, '/auth/login')
        self.assertEqual(self.client.get('/auth/2fa/' + raw).location, '/auth/login')
        self.assertEqual(self.client.get('/auth/not-a-token').location, '/auth/login')
        self.verify.assert_not_called()


if __name__ == '__main__':
    unittest.main()
