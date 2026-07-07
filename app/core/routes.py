from flask import render_template, request, flash, redirect, url_for, current_app, abort, session, \
    render_template_string
from flask_login import login_required, current_user, login_user, logout_user
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core import core
from app import db, twilio_client, audit
from .forms import ChangePasswordForm, ProfileSettingsForm, NotificationSettingsForm, SecuritySettingsForm, \
    SetupAccountForm, NewUserForm, TOTPVerifyForm, CreateAccountForm, DeviceManagerForm, \
    build_edit_user_form, ApplicationSettingsForm, SystemSettingsForm
import phonenumbers
from app.model_managers import UserManager, UserDeviceManager, FileManager, NotificationManager, SystemManager
from .helper import send_sms, parse_device, get_routes, get_blueprints, get_extensions, get_database_status, \
    get_platform_info, is_safe_read_query, modify_query
from ..model_managers import LoginTokenManager
from ..extensions.flask_permissions import require_permission
from app import pm
from ..models import NotificationCategory, UserNotification, User


@core.route('/')
def index():
    return render_template('index.html')


@core.route('/setup-account', methods=['GET', 'POST'])
@login_required
def setup_account():
    if current_user.status != 'pending':
        abort(403)
    form = SetupAccountForm()
    if form.validate_on_submit():
        with audit.track(current_user, actor=current_user, message="User setting up account"):
            current_user.name = form.name.data.strip()
            current_user.set_password(form.password.data)
            current_user.status = 'active'
            current_user.set_setting('security.two_factor_auth', form.two_factor_auth.data)
        db.session.commit()
        flash('Your account has been set up. You can now login using email and password or social logins.', 'success')
        flash('You can change account settings such as your profile information, notification preferences, and security options here.', 'info')
        LoginTokenManager.invalidate_create_account_token(current_user.id)
        return redirect(url_for('core.profile_settings'))
    form.name.data = current_user.name
    form.two_factor_auth.data = current_user.get_setting('security.two_factor_auth')
    return render_template('setup-account.html', title="Setup Account", form=form)


@core.route('/create-account', methods=['GET', 'POST'])
def create_account():
    if not SystemManager.get_setting('allow_account_creation'):
        flash('Account creation is not enabled. Please contact an administrator for an account.', 'error')
        abort(403)
    form = CreateAccountForm()
    if form.validate_on_submit():
        if UserManager.get_user_by_email(form.email.data.lower().strip()):
            flash('An account with that email already exists. Please login or reset your password to continue.', 'error')
            return redirect(url_for('auth.login'))
        UserManager.create_user(name=form.name.data.strip(), email=form.email.data.strip().lower(), send_welcome_email=True, status='pending')
        flash('Your account has been created. Please check your email to finish setting up your account.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('create-account.html', title="Create Account", form=form)


@core.route('/account-settings/profile', methods=['GET', 'POST'])
@login_required
def profile_settings():
    form = ProfileSettingsForm()

    if form.validate_on_submit():
        with audit.track(current_user, actor=current_user, message="User updating profile settings"):
            current_user.name = form.name.data.strip()
            if form.profile_picture_url.data:
                if not form.profile_picture_url.data.startswith('http'):
                    file = FileManager.get_file_by_uuid36(form.profile_picture_url.data)
                    if file is not None:
                        current_user.profile_picture_url = file.url
                    else:
                        flash("Error uploading profile picture", "error")
            else:
                current_user.profile_picture_url = f'https://api.dicebear.com/9.x/initials/svg?seed={current_user.name}&radius=50&backgroundColor=00897b,039be5,3949ab,5e35b1,8e24aa,43a047,d81b60,f4511e,fb8c00,fdd835&backgroundType=gradientLinear&fontFamily=Arial&fontSize=41'
            # Get the user entered phone number and country code
            raw_phone = form.phone_number.data.strip()
            region = form.country_code.data or "US"
            # If the user hasn't entered an empty value
            if raw_phone:
                try:
                    parsed = phonenumbers.parse(raw_phone, region)
                    # If the phone number has changed
                    if phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164) != current_user.phone_number:
                        # Validate the phone number
                        if phonenumbers.is_valid_number(parsed):
                            current_user.phone_number = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                            current_user.phone_number_verified = False
                            # Send text to verify phone number.
                            new_token_obj, new_token = LoginTokenManager.create_login_token(expiration_minutes=30, user_id=current_user.id, auth_source='phone number verification')
                            new_token_obj.verify_phone_number = True
                            db.session.commit()
                            verify_url = url_for('auth.login_with_token', raw_token=new_token, _external=True)
                            message = f'Click the following link to verify the phone number in your {current_app.config["APP_NAME"]} account: {verify_url}\n\nIf you did not request this link, please ignore this text.'
                            send_sms(body=message, recipient=current_user.phone_number)
                            flash('A link has been sent to your phone via text. Please click this link to verify your phone number.', 'info')
                        else:
                            flash("Phone number is not valid", "error")
                except phonenumbers.NumberParseException:
                    flash("Error validating phone number", "error")
            else:
                current_user.phone_number = None
                current_user.phone_number_verified = False
        db.session.commit()
        flash('Your profile has been updated.', 'success')
        return redirect(url_for('core.profile_settings'))

    form.name.data = current_user.name
    form.profile_picture_url.data = current_user.profile_picture_url

    # If stored as E.164, phonenumbers can infer region when possible; fallback to US
    if current_user.phone_number:
        try:
            parsed = phonenumbers.parse(current_user.phone_number, None)
            region = phonenumbers.region_code_for_number(parsed) or "US"
            if any(code == region for code, _ in form.country_code.choices):
                form.country_code.data = region
            form.phone_number.data = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        except phonenumbers.NumberParseException:
            form.country_code.data = "US"
            form.phone_number.data = current_user.phone_number
    else:
        form.country_code.data = "US"
        form.phone_number.data = ""

    return render_template('account-settings/profile.html', title="Profile Settings", tab='profile', form=form)


@core.route('/account-settings/application', methods=['GET', 'POST'])
@login_required
def application_settings():
    form = ApplicationSettingsForm()
    if form.validate_on_submit():
        with audit.track(current_user, actor=current_user, message="User updating application settings"):
            current_user.set_setting('preferences.theme', form.theme.data)
            session['theme'] = form.theme.data
        db.session.commit()
        flash('Your notification settings have been updated.', 'success')
        return redirect(url_for('core.application_settings'))
    form.theme.data = current_user.get_setting('preferences.theme')
    return render_template('account-settings/application.html', title="Application Settings", tab='application', form=form)


@core.route('/account-settings/profile/verify-phone-number', methods=['POST'])
@login_required
def send_phone_number_verification():
    if 'HX-Request' not in request.headers:
        return abort(404)
    audit.log("User requested phone number verification", actor=current_user)
    new_token_obj, new_token = LoginTokenManager.create_login_token(expiration_minutes=30, user_id=current_user.id, auth_source='phone number verification')
    new_token_obj.verify_phone_number = True
    db.session.commit()
    verify_url = url_for('auth.login_with_token', raw_token=new_token, _external=True)
    message = f'Click the following link to verify the phone number in your {current_app.config["APP_NAME"]} account: {verify_url}\n\nIf you did not request this link, please ignore this text.'
    send_sms(body=message, recipient=current_user.phone_number)
    return '''<button type="button" class="btn btn-neutral join-item" disabled>Link Sent</button>'''


@core.route('/account-settings/notifications', methods=['GET', 'POST'])
@login_required
def notification_settings():
    form = NotificationSettingsForm()
    if form.validate_on_submit():
        with audit.track(current_user, actor=current_user, message="User updating notification settings"):
            current_user.set_setting('notifications.security_alerts_via_email', form.security_alerts_email.data)
            current_user.set_setting('notifications.security_alerts_via_text', form.security_alerts_text.data)
        db.session.commit()
        flash('Your notification settings have been updated.', 'success')
        return redirect(url_for('core.notification_settings'))
    form.security_alerts_email.data = current_user.get_setting('notifications.security_alerts_via_email')
    form.security_alerts_text.data = current_user.get_setting('notifications.security_alerts_via_text')
    return render_template('account-settings/notifications.html', title="Notification Settings", tab='notifications', form=form)


@core.route('/account-settings/notifications/all')
@login_required
def all_notifications():
    page = request.args.get('page', 1, type=int)
    query = request.args.get("query", "").strip()
    htmx = request.headers.get('HX-Request', False)
    np = NotificationManager.get_web_notifications(current_user, page=page, recent_only=False, include_read=True, query=query)
    return render_template('account-settings/all-notifications.html', title="Notifications", tab='notifications', htmx=htmx, notifications=np)


@core.route("/account-settings/notifications/<uuid36>/read", methods=["POST"])
@login_required
def mark_notification_read(uuid36):
    notification = NotificationManager.mark_notification_as_read(uuid36)
    template_string = """
    {% from 'account-settings/macros.html' import notification_row %}
    {{ notification_row(notification) }}
    """
    return render_template_string(template_string, notification=notification)


@core.route('/account-settings/security', methods=['GET', 'POST'])
@login_required
def security_settings():
    form = SecuritySettingsForm()
    if form.validate_on_submit():
        with audit.track(current_user, actor=current_user, message="User updating security settings"):
            current_user.set_setting('security.two_factor_auth', form.two_factor_auth.data)
            current_user.set_setting('security.password_breach_check', form.password_breach_check.data)
        db.session.commit()
        flash('Your security settings have been updated.', 'success')
        return redirect(url_for('core.security_settings'))
    form.two_factor_auth.data = current_user.get_setting('security.two_factor_auth')
    form.password_breach_check.data = current_user.get_setting('security.password_breach_check')
    return render_template('account-settings/security.html', title="Security Settings", tab='security', form=form)


@core.route('/account-settings/security/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('account-settings/change-password.html', title="Change Password", form=form), 401
        audit.log("User changed their password", actor=current_user)
        current_user.set_password(form.new_password.data)
        current_user.refresh_uuid36()
        db.session.commit()
        message = 'You password has been changed. If you did not make this change, please take action to secure your account'
        NotificationManager.send_notification(current_user, 'Password Changed', message, NotificationCategory.PASSWORD_CHANGE)
        login_user(current_user)
        flash('Your password has been updated.', 'success')
        return redirect(url_for('core.security_settings'))
    return render_template('account-settings/change-password.html', title="Change Password", tab="security", form=form)


@core.route('/account-settings/security/enable-totp', methods=['GET', 'POST'])
@login_required
def enable_totp():
    if current_user.totp_verified:
        flash('TOTP is already enabled for your account.', 'info')
        return redirect(url_for('core.security_settings'))
    verify = request.args.get('verify', False)
    sid = current_app.config["TWILIO_SERVICE_SID"]
    if not verify:
        new_factor = (
            twilio_client.verify.v2.services(sid)
            .entities(current_user.totp_entity)
            .new_factors.create(friendly_name=current_app.config["APP_NAME"], factor_type="totp")
        )
        current_user.totp_factor = new_factor.sid
        db.session.commit()
        return render_template('account-settings/enable-totp.html', title="Enable TOTP", binding_url=new_factor.binding['uri'])
    form = TOTPVerifyForm()
    if form.validate_on_submit():
        factor = (
            twilio_client.verify.v2.services(sid)
            .entities(current_user.totp_entity)
            .factors(current_user.totp_factor)
            .update(form.code.data.strip())
        )
        if factor.status == 'verified':
            audit.log("User enabled TOTP", actor=current_user)
            current_user.totp_verified = True
            db.session.commit()
            flash('TOTP has been enabled for your account.', 'success')
            return redirect(url_for('core.security_settings'))
        else:
            flash('The code you entered is incorrect. Please try again.', 'error')
    return render_template('account-settings/verify-totp.html', title="Verify TOTP", form=form)


@core.route('/account-settings/security/disable-totp')
@login_required
def disable_totp():
    audit.log("User disabled TOTP", actor=current_user)
    current_user.totp_verified = False
    current_user.refresh_totp_entity()
    current_user.totp_factor = None
    db.session.commit()
    flash('Your TOTP method has been disabled.', 'info')
    return redirect(url_for('core.security_settings'))


@core.route('/account-settings/security/login-history')
@login_required
def login_history():
    page = request.args.get('page', 1, type=int)
    records = UserManager.get_logins(current_user.id, page=page)
    return render_template('account-settings/login-history.html', title="Login History", tab="security", records=records)


@core.route('/account-settings/security/manage-device/<string:uuid36>', methods=['GET', 'POST'])
@login_required
def manage_device(uuid36):
    device = UserDeviceManager.get_device_by_uuid36(uuid36)
    user = UserManager.get_user_by_id(device.user_id)

    form = DeviceManagerForm()
    if form.validate_on_submit():
        with audit.track(device, actor=user, message="User managing new device"):
            device.device_trusted = form.device_trusted.data
        db.session.commit()
        flash('Device trust status has been updated.', 'success')
        return redirect(url_for('core.login_history'))
    form.device_trusted.data = device.device_trusted
    parsed_device = parse_device(device.user_agent)
    return render_template('account-settings/manage-device.html', title="Manage Device", tab="security", device=device, parsed_device=parsed_device, user_ip=request.remote_addr, form=form)


@core.route('/account-settings/security/lockdown/<string:uuid36>')
@core.route('/account-settings/security/lockdown')
@login_required
def lockdown(uuid36: str = None):
    if uuid36 is None:
        user = current_user
    else:
        user = UserManager.get_user_by_uuid36(uuid36)
        if user is None:
            abort(404)
    UserManager.lockdown_user(user)
    if uuid36 is None:
        flash('Your account has been locked down.', 'success')
        logout_user()
        session.clear()
        return redirect(url_for('auth.login'))
    flash('User has been locked down.', 'success')
    return redirect(url_for('core.user_settings'))


@core.route('/system-settings/users')
@login_required
@require_permission('users')
def user_settings():
    page = request.args.get('page', 1, type=int)
    users = UserManager.get_all_users(page=page)
    return render_template('system-settings/users.html', title="User Management", tab='users', users=users)


@core.route('/system-settings/users/new', methods=['GET', 'POST'])
@login_required
@require_permission('users.create')
def new_user():
    form = NewUserForm()
    if form.validate_on_submit():
        if UserManager.get_user_by_email(form.email.data.lower().strip()):
            flash('An account with that email already exists.', 'error')
            return render_template('system-settings/new-user.html', title="New User", form=form)
        UserManager.create_user(form.name.data.strip(), form.email.data.strip(), send_welcome_email=True, status='pending')
        flash('New user has been created and a welcome email has been sent.', 'success')
        return redirect(url_for('core.user_settings'))
    return render_template('system-settings/new-user.html', title="New User", tab='users', form=form)


@core.route('/system-settings/users/<string:uuid36>', methods=['GET', 'POST'])
@login_required
@require_permission('users.update')
def edit_user(uuid36):
    user = UserManager.get_user_by_uuid36(uuid36)
    if not user:
        abort(404)

    EditUserForm = build_edit_user_form(pm)
    form = EditUserForm()

    if form.validate_on_submit():
        with audit.track(user, actor=current_user, message="User updating other user's settings"):
            user.name = form.name.data.strip()
            user.status = form.status.data.strip()

            if form.password.data:
                user.set_password(form.password.data)
                user.refresh_uuid36()

            for field_name, permission_key in form.permission_field_map.items():
                field = getattr(form, field_name)
                user.set_permission(permission_key, field.data)

        db.session.commit()

        flash('Your changes have been saved.', 'success')
        return redirect(url_for('core.user_settings'))

    form.name.data = user.name
    form.status.data = user.status

    for field_name, permission_key in form.permission_field_map.items():
        field = getattr(form, field_name)
        field.data = user.can(permission_key)

    return render_template('system-settings/edit-user.html', title="Edit User", tab="users", form=form, user=user, permission_groups=pm.grouped())


@core.route('/system-settings/users/delete/<string:uuid36>')
@login_required
@require_permission('users.delete')
def delete_user(uuid36):
    user = UserManager.get_user_by_uuid36(uuid36)
    if not user:
        abort(404)
    UserManager.delete_user(user)
    flash('User has been deleted.', 'success')
    return redirect(url_for('core.user_settings'))


@core.route('/system-settings/system', methods=['GET', 'POST'])
@login_required
@require_permission('system')
def system_settings():
    form = SystemSettingsForm()
    if form.validate_on_submit():
        audit.log("User updated system settings", actor=current_user)
        SystemManager.set_setting('allow_account_creation', form.allow_account_creation.data)
        SystemManager.set_setting('strict_login', form.strict_login.data)
        flash('Your changes have been saved.', 'success')
    form.allow_account_creation.data = SystemManager.get_setting('allow_account_creation')
    form.strict_login.data = SystemManager.get_setting('strict_login')
    return render_template('system-settings/system.html', title="System Settings", tab='system', form=form)


@core.route('/system-settings/admin')
@login_required
@require_permission('system.admin')
def admin():
    if not current_app.config.get('ADMIN_PANEL', False):
        flash('Admin panel is disabled.', 'error')
        abort(403)
    audit.log("User accessed admin page", actor=current_user)
    num_users = db.session.query(User).count()
    platform = get_platform_info()
    config = current_app.config
    routes = get_routes()
    blueprints = get_blueprints()
    extensions = get_extensions()
    db_status = get_database_status()
    return render_template('system-settings/admin.html', title="Admin", tab='system', num_users=num_users, platform=platform, config=config, routes=routes, blueprints=blueprints, extensions=extensions, db_status=db_status)


@core.route('/system-settings/admin/sql-console', methods=["POST"])
@login_required
@require_permission('system.admin')
def admin_sql_console():
    if not current_app.config.get('ADMIN_PANEL', False):
        flash('Admin panel is disabled.', 'error')
        abort(403)
    query = request.form.get("query", "").strip()
    is_safe, error = is_safe_read_query(query)
    if not is_safe:
        audit.log("Blocked admin SQL console query", actor=current_user)
        return render_template("system-settings/sql-results.html", error=error, query=query, columns=[], rows=[], row_count=0)
    query = modify_query(query)
    try:
        result = db.session.execute(text(query))

        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchall()]

        audit.log("User executed admin SQL console query", actor=current_user)
        return render_template("system-settings/sql-results.html", error=None, query=query, columns=columns, rows=rows, row_count=len(rows))

    except SQLAlchemyError as e:
        db.session.rollback()

        audit.log("Admin SQL console query failed", actor=current_user)
        return render_template("system-settings/sql-results.html", error=str(e), query=query, columns=[], rows=[], row_count=0)


@core.route("/external-redirect")
def external_redirect():
    next_url = request.args.get("next", None)
    return render_template("external-redirect.html", url=next_url)


@core.route('/test')
def test():
    for x in range(5):
        body = f"This is a test notification {x}. This content is really long and may even wrap multiple lines. No one may ever know..."
        n = UserNotification(title=f"Test Notification {x}", body=body, sender="System", category="Test", channel="web", user_id=current_user.id, link='/account-settings/profile')
        db.session.add(n)
    db.session.commit()
    return "ok"
