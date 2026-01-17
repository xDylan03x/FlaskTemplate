from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, StringField, SelectField, BooleanField
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


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Change Password')


class ProfileSettingsForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
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

