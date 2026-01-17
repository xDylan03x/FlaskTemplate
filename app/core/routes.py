from flask import render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required, current_user, login_user
from app.core import core
from app import db
from .forms import ChangePasswordForm, ProfileSettingsForm, NotificationSettingsForm, SecuritySettingsForm
import phonenumbers
from .helper import send_sms
from ..model_managers import LoginTokenManager


@core.route('/')
def index():
    return render_template('index.html')


@core.route('/account-settings/profile', methods=['GET', 'POST'])
@login_required
def profile_settings():
    form = ProfileSettingsForm()

    if form.validate_on_submit():
        current_user.name = form.name.data.strip()

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
                        new_token_obj, new_token = LoginTokenManager.create_login_token(expiration_minutes=30, user_id=current_user.id)
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

    form.name.data = current_user.name or ""

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

    return render_template('account-settings/profile.html', title="Profile Settings", page='profile', form=form)


@core.route('/account-settings/profile/verify-phone-number', methods=['POST'])
@login_required
def send_phone_number_verification():
    if 'HX-Request' not in request.headers:
        return abort(404)
    new_token_obj, new_token = LoginTokenManager.create_login_token(expiration_minutes=30, user_id=current_user.id)
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
        current_user.set_setting('notifications.security_alerts_email', form.security_alerts_email.data)
        current_user.set_setting('notifications.security_alerts_text', form.security_alerts_text.data)
        db.session.commit()
        flash('Your notification settings have been updated.', 'success')
        return redirect(url_for('core.notification_settings'))
    form.security_alerts_email.data = current_user.get_setting('notifications.security_alerts_email')
    form.security_alerts_text.data = current_user.get_setting('notifications.security_alerts_text')
    return render_template('account-settings/notifications.html', title="Notification Settings", page='notifications', form=form)


@core.route('/account-settings/security', methods=['GET', 'POST'])
@login_required
def security_settings():
    form = SecuritySettingsForm()
    if form.validate_on_submit():
        current_user.set_setting('security.two_factor_auth', form.two_factor_auth.data)
        current_user.set_setting('security.password_breach_check', form.password_breach_check.data)
        db.session.commit()
        flash('Your security settings have been updated.', 'success')
        return redirect(url_for('core.security_settings'))
    form.two_factor_auth.data = current_user.get_setting('security.two_factor_auth')
    form.password_breach_check.data = current_user.get_setting('security.password_breach_check')
    return render_template('account-settings/security.html', title="Security Settings", page='security', form=form)


@core.route('/account-settings/security/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect.', 'error')
            return render_template('account-settings/change-password.html', title="Change Password", form=form), 401
        current_user.set_password(form.new_password.data)
        current_user.refresh_uuid36()
        db.session.commit()
        login_user(current_user)
        flash('Your password has been updated.', 'success')
        return redirect(url_for('core.security_settings'))
    return render_template('account-settings/change-password.html', title="Change Password", form=form)


@core.route("/external-redirect")
def external_redirect():
    next_url = request.args.get("next", None)
    return render_template("external-redirect.html", url=next_url)
