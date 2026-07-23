from urllib.parse import urlencode
import requests
from app.auth.helper import get_ip_from_request, twilio_verify_send, twilio_verify_check, hibp_password_check, \
    is_internal_url
from app.models import NotificationCategory, RiskAction
from app.model_managers import UserManager, LoginTokenManager, LoginRecordManager, UserDeviceManager, \
    NotificationManager, SystemManager
from flask_login import login_user, logout_user
from flask import flash, request, redirect, render_template, url_for, current_app, session
from app.auth import auth
from .forms import LoginForm, TwoFactorAuthSelectForm, TwoFactorAuthCodeForm, MagicLinkEmailForm, MagicLinkSelectForm, \
    ForgotPasswordEmailForm, ResetPasswordForm
from app import db
from ..core.helper import send_email, send_sms, parse_user_agent

LOGIN_RISK_SCORE_THRESHOLD = 50
CONTACT_ADMINISTRATOR_MESSAGE = 'There was an error logging you in. Please contact an administrator.'
TOKEN_EXPIRED_MESSAGE = 'The link or token you used has expired. Please try again.'
REQUIRES_2FA_MESSAGE = 'For security, please complete the two-factor authentication process to log in.'
WRONG_EMAIL_PASSWORD_MESSAGE = 'Incorrect email or password.'


@auth.route('/login', methods=['GET', 'POST'])
def login():
    """The actual login form page"""
    next_url = request.args.get('next', None)
    form = LoginForm()
    create_accounts = SystemManager.get_setting('allow_account_creation')
    if form.validate_on_submit():
        user = UserManager.get_user_by_email(form.email.data.lower().strip())

        # If the user isn't found
        if not user:
            flash(WRONG_EMAIL_PASSWORD_MESSAGE, 'error')
            return render_template('login.html', title='Log In', form=form), 401

        # If the user cannot log in
        if not user.can_login():
            flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
            return render_template('login.html', title='Log In', form=form), 401

        # If the password is incorrect
        if not user.check_password(form.password.data):
            flash(WRONG_EMAIL_PASSWORD_MESSAGE, 'error')
            return render_template('login.html', title='Log In', form=form), 401

        # If the user has enabled password breach checking
        if user.get_setting('security.password_breach_check'):
            # If their password has been found in a data breach, alert them and require 2FA
            if hibp_password_check(form.password.data):
                flash('Your password has been found in a data breach, consider changing it immediately.', 'warning')

        # If the user has 2FA enabled
        if user.get_setting('security.two_factor_auth'):
            flash(REQUIRES_2FA_MESSAGE, 'info')
            _, raw_token = LoginTokenManager.create_login_token(next_url=next_url, remember_login=form.remember_me.data, user_id=user.id, auth_source='traditional login needing 2fa')
            return redirect(url_for('auth.two_factor_auth', raw_token=raw_token))

        _, raw_token = LoginTokenManager.create_login_token(immediate_login=True, next_url=next_url, remember_login=form.remember_me.data, user_id=user.id, auth_source='traditional login')
        return redirect(url_for('auth.login_with_token', raw_token=raw_token))
    return render_template('login.html', title='Log In', form=form, next_url=next_url, create_accounts=create_accounts)


@auth.route('/forgot-password', methods=['GET', 'POST'])
@auth.route('/forgot-password/<string:raw_token>', methods=['GET', 'POST'])
def forgot_password(raw_token: str = None):
    """The forgot password page"""
    # If the user has not entered their email
    if raw_token is None:
        form = ForgotPasswordEmailForm()
        if form.validate_on_submit():
            user = UserManager.get_user_by_email(form.email.data)

            # If the user isn't found
            if not user:
                flash('A login link has been sent to your email.', 'info')
                return redirect(url_for('auth.login', next=request.args.get('next', None)))

            # If the user cannot log in
            if not user.can_login():
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return render_template('forgot_password_email.html', title='Forgot Password', form=form)

            # Create a token and email it to them
            _, raw_token = LoginTokenManager.create_login_token(user_id=user.id, next_url=request.args.get('next', None), reset_password=True, auth_source='forgot password')
            login_url = url_for('auth.forgot_password', raw_token=raw_token, _external=True)
            message = f'Click the following link to reset your password: {login_url}<br><br>If you did not request this link, please ignore this email.'
            send_email(subject=f'Your {current_app.config["APP_NAME"]} Password Reset Link', body=message, recipient=user.email)
            flash('A login link has been sent to your email.', 'info')
            return redirect(url_for('auth.login', next=request.args.get('next', None)))
        return render_template('forgot_password_email.html', title='Forgot Password', form=form)

    login_token = LoginTokenManager.get_login_token(raw_token)

    # If the hashed token is not found
    if not login_token:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token was found, but not valid
    if not login_token.is_valid(raw_token):
        flash(TOKEN_EXPIRED_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token is not for password reset
    if not login_token.reset_password:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the user isn't found or cannot log in
    user = UserManager.get_user_by_id(login_token.user_id)
    if not user or not user.can_login():
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        message = 'You password has been reset. If you did not make this change, please take action to secure your account'
        NotificationManager.send_notification(user, 'Password Reset', message, NotificationCategory.PASSWORD_RESET)
        LoginTokenManager.invalidate_login_token(login_token)
        user.refresh_uuid36()
        db.session.commit()
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset. You can now log in with your new password.', 'success')
        return redirect(url_for('auth.login', next=login_token.next_url))
    return render_template('reset_password.html', title='Reset Password', form=form)


@auth.route('/magic-link', methods=['GET', 'POST'])
@auth.route('/magic-link/<string:raw_token>', methods=['GET', 'POST'])
def magic_link(raw_token: str = None):
    """Page to generate and verify magic links"""
    # If the user has not entered their email
    if raw_token is None:
        form = MagicLinkEmailForm()
        if form.validate_on_submit():
            user = UserManager.get_user_by_email(form.email.data)

            # If the user isn't found
            if not user:
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return render_template('magic_link_email.html', title='Login with Magic Link', form=form)

            # If the user cannot log in
            if not user.can_login():
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return render_template('magic_link_email.html', title='Login with Magic Link', form=form)

            _, raw_token = LoginTokenManager.create_login_token(user_id=user.id, next_url=request.args.get('next', None), auth_source='magic link')
            return redirect(url_for('auth.magic_link', raw_token=raw_token))
        return render_template('magic_link_email.html', title='Login with Magic Link', form=form)

    login_token = LoginTokenManager.get_login_token(raw_token)

    # If the hashed token is not found
    if not login_token:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token was found, but not valid
    if not login_token.is_valid(raw_token):
        flash(TOKEN_EXPIRED_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the user isn't found or cannot log in
    user = UserManager.get_user_by_id(login_token.user_id)
    if not user or not user.can_login():
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    form = MagicLinkSelectForm()
    form.method.choices = []
    if user.email_verified:
        form.method.choices.append('Email')
    if user.phone_number_verified:
        form.method.choices.append('Text')

    # Send the login link when submitting
    if form.validate_on_submit():
        new_token_obj, new_token = LoginTokenManager.create_login_token_from_existing(login_token)
        new_token_obj.immediate_login = True
        new_token_obj.update_risk_score(RiskAction.MAGIC_LINK_LOGIN)
        db.session.commit()
        login_url = url_for('auth.login_with_token', raw_token=new_token, _external=True)
        if form.method.data == 'Email':
            # Make sure the user's email is verified
            if not user.email_verified:
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return redirect(url_for('auth.login'))
            message = f'Click the following link to log in to your account: {login_url}<br><br>If you did not request this link, please ignore this email.'
            send_email(subject=f'Your {current_app.config["APP_NAME"]} Login Link', body=message, recipient=user.email)
            flash('A login link has been sent to your email.', 'info')
            return redirect(url_for('auth.login'))
        if form.method.data == 'Text':
            # Make sure the user's phone number is verified
            if not user.phone_number_verified:
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return redirect(url_for('auth.login'))
            message = f'Click the following link to log in to your {current_app.config["APP_NAME"]} account: {login_url}\n\nIf you did not request this link, please ignore this text.'
            send_sms(body=message, recipient=user.phone_number)
            flash('A login link has been sent to your phone via text.', 'info')
            return redirect(url_for('auth.login'))

    return render_template('magic_link_select_method.html', title='Login with Magic Link', form=form)


@auth.route('/oauth/authorize/<string:provider>')
def oauth_authorize(provider: str):
    """Page to generate and direct to oauth verification"""
    provider_data = current_app.config['OAUTH2_PROVIDERS'].get(provider)
    next_url = request.args.get('next', None)

    # If the provider isn't supported
    if provider_data is None:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # Save the OAuth2 state parameter in the session for later verification
    _, raw_token = LoginTokenManager.create_login_token(next_url=next_url, auth_source='oauth authorization state')
    session['oauth2_state'] = raw_token

    # Create a query string with all the OAuth2 parameters
    query_string = urlencode({
        'client_id': provider_data['client_id'],
        'redirect_uri': url_for('auth.oauth_callback', provider=provider, _external=True),
        'response_type': 'code',
        'scope': ' '.join(provider_data['scopes']),
        'state': session['oauth2_state'],
    })

    # Redirect the user to the OAuth2 provider authorization URL
    return redirect(provider_data['authorize_url'] + '?' + query_string)


@auth.route('/oauth/callback/<string:provider>')
def oauth_callback(provider: str):
    """Page to verify and sign the user in from an oauth attempt"""
    provider_data = current_app.config['OAUTH2_PROVIDERS'].get(provider)

    # If the provider isn't supported
    if provider_data is None:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If there was an authentication error, flash the error messages and exit
    if 'error' in request.args:
        for k, v in request.args.items():
            if k.startswith('error'):
                flash(f'{k}: {v}', 'error')
        return redirect(url_for('auth.login'))

    # Make sure that the state parameter matches the one we created in the authorization request
    if request.args['state'] != session.get('oauth2_state'):
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # Make sure that the authorization code is present
    if 'code' not in request.args:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # Exchange the authorization code for an access token
    response = requests.post(provider_data['token_url'], data={
        'client_id': provider_data['client_id'],
        'client_secret': provider_data['client_secret'],
        'code': request.args['code'],
        'grant_type': 'authorization_code',
        'redirect_uri': url_for('auth.oauth_callback', provider=provider,
                                _external=True),
    }, headers={'Accept': 'application/json'})
    if response.status_code != 200:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))
    oauth2_token = response.json().get('access_token')
    if not oauth2_token:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # Use the access token to get the user's email address
    response = requests.get(provider_data['userinfo']['url'], headers={
        'Authorization': 'Bearer ' + oauth2_token,
        'Accept': 'application/json',
    })
    if response.status_code != 200:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))
    email = provider_data['userinfo']['email'](response.json())

    # Make sure the email is verified by the OAuth provider
    if response.json().get("email_verified", False) is not True:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        flash("Provider does not support email verification. Use another form of authentication to log in.", 'info')
        return redirect(url_for('auth.login'))

    # Find the user in the database
    user = UserManager.get_user_by_email(email)
    if user is None:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # Get the login token and make sure we can log the user in
    login_token = LoginTokenManager.get_login_token(session['oauth2_state'])
    if not login_token or not user.can_login():
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))
    login_token.user_id = user.id
    login_token.immediate_login = True
    db.session.commit()
    return redirect(url_for('auth.login_with_token', raw_token=session['oauth2_state']))


@auth.route('/2fa/<string:raw_token>', methods=['GET', 'POST'])
def two_factor_auth(raw_token: str):
    """Page to generate and verify a two-factor authentication code."""
    login_token = LoginTokenManager.get_login_token(raw_token)
    verification_method = request.args.get('verification_method', None)
    code_sent = request.args.get('code_sent', False)

    # If the hashed token is not found
    if not login_token:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token was found, but not valid
    if not login_token.is_valid(raw_token):
        flash(TOKEN_EXPIRED_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the user isn't found or cannot log in
    user = UserManager.get_user_by_id(login_token.user_id)
    if not user or not user.can_login():
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If no verification method has been sent, show the selection page
    if not code_sent:
        form = TwoFactorAuthSelectForm()
        form.method.choices = []
        if user.email_verified:
            form.method.choices.append('Email')
        if user.phone_number_verified:
            form.method.choices.append('Text')
            form.method.choices.append('Call')
        if user.totp_verified:
            form.method.choices.append('Authenticator App')

        if form.validate_on_submit():
            # If the user chose email verification
            if form.method.data == 'Email' and user.email_verified:
                twilio_verify_send(to=user.email, channel='email')
            # If the user chose SMS or call verification
            elif form.method.data in ['Text', 'Call'] and user.phone_number_verified:
                # If the user chose SMS verification
                if form.method.data == 'Text':
                    twilio_verify_send(to=user.phone_number, channel='sms')
                # If the user chose call verification
                elif form.method.data == 'Call':
                    twilio_verify_send(to=user.phone_number, channel='call')
            elif form.method.data == 'Authenticator App' and user.totp_verified:
                pass  # No need to send anything for authenticator apps
            else:
                flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
                return redirect(url_for('auth.login'))
            return redirect(url_for('auth.two_factor_auth', raw_token=raw_token, code_sent=True, verification_method=form.method.data.lower().replace(' ', '_')))
        return render_template('2fa_select_method.html', title='Two-Factor Authentication', form=form)

    # If a code has been sent, show the appropriate form
    form = TwoFactorAuthCodeForm()

    # If the user chose email verification
    if verification_method == 'email':
        # Make sure the user's email is verified
        if not user.email_verified:
            flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
            return redirect(url_for('auth.login'))
        # If submitting, check the code
        if form.validate_on_submit():
            if twilio_verify_check(to=user.email, code=form.code.data):
                login_token.immediate_login = True
                login_token.update_risk_score(RiskAction.TWO_FACTOR_AUTH)
                db.session.commit()
                return redirect(url_for('auth.login_with_token', raw_token=raw_token))
            else:
                flash('The code you entered is incorrect. Please try again.', 'warning')

    # If the user chose SMS verification
    if verification_method == 'text':
        # Make sure the user's phone number is verified
        if not user.phone_number_verified:
            flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
            return redirect(url_for('auth.login'))
        # If submitting, check the code
        if form.validate_on_submit():
            if twilio_verify_check(to=user.phone_number, code=form.code.data):
                login_token.immediate_login = True
                login_token.update_risk_score(RiskAction.TWO_FACTOR_AUTH)
                db.session.commit()
                return redirect(url_for('auth.login_with_token', raw_token=raw_token))
            else:
                flash('The code you entered is incorrect. Please try again.', 'warning')

    # If the user chose call verification
    if verification_method == 'call':
        # Make sure the user's phone number is verified
        if not user.phone_number_verified:
            flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
            return redirect(url_for('auth.login'))
        # If submitting, check the code
        if form.validate_on_submit():
            if twilio_verify_check(to=user.phone_number, code=form.code.data):
                login_token.immediate_login = True
                login_token.update_risk_score(RiskAction.TWO_FACTOR_AUTH)
                db.session.commit()
                return redirect(url_for('auth.login_with_token', raw_token=raw_token))
            else:
                flash('The code you entered is incorrect. Please try again.', 'warning')

    # If the user chose to use an authenticator app
    if verification_method == 'authenticator_app':
        # Make sure the user has set up TOTP
        if not user.totp_verified:
            flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
            return redirect(url_for('auth.login'))
        # If submitting, check the code
        if form.validate_on_submit():
            if twilio_verify_check(to=user.email, code=form.code.data, totp_entity=user.totp_entity, totp_factor=user.totp_factor):
                login_token.immediate_login = True
                login_token.update_risk_score(RiskAction.TWO_FACTOR_AUTH)
                db.session.commit()
                return redirect(url_for('auth.login_with_token', raw_token=raw_token))
            else:
                flash('The code you entered is incorrect. Please try again.', 'warning')
    return render_template('2fa_enter_code.html', title='Two-Factor Authentication', raw_token=raw_token, method=verification_method, form=form)


@auth.route('/<string:raw_token>')
def login_with_token(raw_token: str):
    """The actual route that logs the user in. All other authentication routes eventually end up here."""
    login_token = LoginTokenManager.get_login_token(raw_token)
    user_agent = request.headers.get('User-Agent', '')

    # If suspicious user agents are not allowed to log in
    if SystemManager.get_setting('strict_login') and parse_user_agent(user_agent)["is_bot"]:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the hashed token is not found
    if not login_token:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token was found, but not valid
    if not login_token.is_valid(raw_token):
        flash(TOKEN_EXPIRED_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the login token does not allow immediate login and is not for phone number verification
    if (not login_token.immediate_login) and (not login_token.verify_phone_number):
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If the token is for password reset
    if login_token.reset_password:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    user = UserManager.get_user_by_id(login_token.user_id)

    # If the user does not exist
    if not user:
        flash(CONTACT_ADMINISTRATOR_MESSAGE, 'error')
        return redirect(url_for('auth.login'))

    # If impersonating another user
    if login_token.for_impersonation:
        login_token.update_risk_score(RiskAction.ACCOUNT_IMPERSONATION)

    # For create-account tokens
    if login_token.create_account:
        if user and not user.email_verified:
            user.email_verified = True
            db.session.commit()

    # Determine if the user is using a new device
    user_device = UserDeviceManager.find_device(user.id, user_agent)
    if user_device and user_device.device_trusted:
        login_token.update_risk_score(RiskAction.EXISTING_DEVICE)
    elif user_device and not user_device.device_trusted:
        pass
    else:
        user_device = UserDeviceManager.create_user_device(user_id=user.id, user_agent=user_agent)
        # If this is an account creation token
        if login_token.create_account:
            user_device.device_trusted = True
            login_token.update_risk_score(RiskAction.EXISTING_DEVICE)
        else:
            login_token.update_risk_score(RiskAction.NEW_DEVICE)
        manage_url = url_for('core.manage_device', uuid36=user_device.uuid36, _external=True)
        NotificationManager.send_notification(user, "New Device Login", "A new device has logged in to your account. Please use the link below to manage it.", NotificationCategory.NEW_DEVICE_LOGIN, link=manage_url)
    db.session.commit()

    # If the token was found and valid
    if login_token.risk_score < LOGIN_RISK_SCORE_THRESHOLD:
        login_token.immediate_login = False
        db.session.commit()
        flash(REQUIRES_2FA_MESSAGE, 'info')
        return redirect(url_for('auth.two_factor_auth', raw_token=raw_token))

    # If the token is to be used to verify a phone number, mark it as verified
    if login_token.verify_phone_number:
        user.phone_number_verified = True
        db.session.commit()
        flash('Your phone number has been successfully verified.', 'success')
        body = f'The phone number ({user.phone_number}) associated with your {current_app.config["APP_NAME"]} account has just been verified.\n\nIf you did not perform this action, please secure your account immediately.'
        NotificationManager.send_notification(user, 'Phone Number Verified', body, NotificationCategory.PHONE_NUMBER_CHANGE)
    # Otherwise, log the user in
    else:
        LoginRecordManager.create_login_record(user.id, get_ip_from_request(request), user_agent, login_token)
        login_user(user, remember=login_token.remember_login)
        session['theme'] = user.get_setting('preferences.theme') or 'light'
    # Invalidate the token if it's not to be used for account creation
    if not login_token.create_account:
        LoginTokenManager.invalidate_login_token(login_token)

    next_url = login_token.next_url
    if user.status == 'pending':
        next_url = url_for('core.setup_account')
    elif next_url is None:
        next_url = '/'

    if is_internal_url(next_url):
        return redirect(next_url)
    return redirect((url_for('core.external_redirect', next=next_url)))


@auth.route('/logout')
def logout():
    """Page to log the user out"""
    next_url = request.args.get('next')
    preserve_user = request.args.get('preserve_user', '').lower() in ('1', 'true', 'yes')
    actual_user = session.get('actual_user')

    logout_user()
    # Clear the cookies (except the _remember cookie as it will keep a user signed in)
    session.clear()
    session['_remember'] = 'clear'

    # If preserving the user (for an impersonation session)
    if preserve_user and actual_user is not None:
        session['actual_user'] = actual_user

    if next_url and is_internal_url(next_url):
        return redirect(next_url)
    return redirect(url_for('auth.login'))
