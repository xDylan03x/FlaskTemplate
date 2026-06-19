from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, StringField, SelectField, BooleanField, EmailField
from wtforms.fields.simple import TelField
from wtforms.validators import DataRequired, EqualTo

COUNTRY_CODE_CHOICES = [
    ("US", "US +1"),
    ("CA", "CA +1"),
    ("GB", "GB +44"),
    ("AU", "AU +61"),
    ("DE", "DE +49"),
    ("FR", "FR +33"),
    ("ES", "ES +34"),
    ("IT", "IT +39"),
    ("JP", "JP +81"),
    ("KR", "KR +82"),
    ("IN", "IN +91"),
    ("CN", "CN +86"),
    ("MX", "MX +52"),
    ("BR", "BR +55"),
]


class SetupAccountForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    two_factor_auth = BooleanField('Two-Factor Authentication')
    submit = SubmitField('Setup Account')


class CreateAccountForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired()])
    submit = SubmitField('Create Account')


class DeviceManagerForm(FlaskForm):
    device_trusted = BooleanField('Trust This Device')
    submit = SubmitField('Save')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')


class ProfileSettingsForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    profile_picture_url = StringField('Profile Picture URL')
    country_code = SelectField("Country Code", choices=COUNTRY_CODE_CHOICES, default="US", validators=[DataRequired()])
    phone_number = TelField('Phone Number')
    submit = SubmitField('Save')


class NotificationSettingsForm(FlaskForm):
    security_alerts_email = BooleanField('Text')
    security_alerts_text = BooleanField('Text')
    submit = SubmitField('Save')


class SecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('Two-Factor Authentication')
    password_breach_check = BooleanField('Password Breach Checking')
    submit = SubmitField('Save')


class NewUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired()])
    submit = SubmitField('Create User')


class EditUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    status = SelectField('Status', choices=[('active', 'Active'), ('disabled', 'Disabled'), ('pending', 'Pending')], validators=[DataRequired()])
    password = PasswordField('Password')
    user_manager = BooleanField('User Manager')
    submit = SubmitField('Save')


class TOTPVerifyForm(FlaskForm):
    code = StringField('Authentication Code', validators=[DataRequired()])
    submit = SubmitField('Submit')
