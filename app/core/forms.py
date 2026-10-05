from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, StringField, SelectField, BooleanField, EmailField, SelectMultipleField
from wtforms.fields.simple import TelField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Optional, Length, ValidationError
import phonenumbers
from app import db
from app.models import User
from .helper import normalize_phone_number

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

THEME_CHOICES = {
    "Core Themes": [
        ("light", "Light"),
        ("dark", "Dark"),
    ],
    "Other Themes": [
        ("cupcake", "Cupcake"),
        ("bumblebee", "Bumblebee"),
        ("emerald", "Emerald"),
        ("corporate", "Corporate"),
        ("synthwave", "Synthwave"),
        ("retro", "Retro"),
        ("cyberpunk", "Cyberpunk"),
        ("valentine", "Valentine"),
        ("halloween", "Halloween"),
        ("garden", "Garden"),
        ("forest", "Forest"),
        ("aqua", "Aqua"),
        ("lofi", "Lofi"),
        ("pastel", "Pastel"),
        ("fantasy", "Fantasy"),
        ("wireframe", "Wireframe"),
        ("black", "Black"),
        ("luxury", "Luxury"),
        ("dracula", "Dracula"),
        ("cmyk", "Cmyk"),
        ("autumn", "Autumn"),
        ("business", "Business"),
        ("acid", "Acid"),
        ("lemonade", "Lemonade"),
        ("night", "Night"),
        ("coffee", "Coffee"),
        ("winter", "Winter"),
        ("dim", "Dim"),
        ("nord", "Nord"),
        ("sunset", "Sunset"),
        ("caramellatte", "Caramellatte"),
        ("abyss", "Abyss"),
        ("silk", "Silk"),
    ],
    "Custom Themes": [
        ("compactlight", "Compact Light"),
        ("compactdark", "Compact Dark"),
        ("bluepastel", "Blue Pastel"),
    ]
}


class SetupAccountForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm New Password', validators=[DataRequired(), EqualTo('password')])
    two_factor_auth = BooleanField('Two-Factor Authentication')
    submit = SubmitField('Setup Account')


class PhoneNumberForm(FlaskForm):
    country_code = SelectField("Country Code", choices=COUNTRY_CODE_CHOICES, default="US", validators=[DataRequired()])
    phone_number = TelField('Phone Number')

    def __init__(self, *args, phone_user_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.phone_user_id = phone_user_id
        self.normalized_phone_number = None

    def validate_phone_number(self, field):
        raw_phone = (field.data or '').strip()
        self.normalized_phone_number = None
        if not raw_phone:
            return
        try:
            normalized_phone = normalize_phone_number(raw_phone, self.country_code.data or "US")
        except phonenumbers.NumberParseException:
            raise ValidationError("Error validating phone number")
        except ValueError:
            raise ValidationError("Phone number is not valid")
        user = db.session.scalar(db.select(User).where(User.phone_number == normalized_phone))
        if user and user.id != self.phone_user_id:
            raise ValidationError("An account with that phone number already exists.")
        self.normalized_phone_number = normalized_phone


class CreateAccountForm(PhoneNumberForm):
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


class ProfileSettingsForm(PhoneNumberForm):
    name = StringField('Name', validators=[DataRequired()])
    profile_picture_url = HiddenField('Profile Picture')
    submit = SubmitField('Save')


class ApplicationSettingsForm(FlaskForm):
    theme = SelectField("Visual Theme", choices=THEME_CHOICES, default="light", validators=[DataRequired()])
    submit = SubmitField('Save')


class NotificationSettingsForm(FlaskForm):
    security_alerts_email = BooleanField('Email')
    security_alerts_text = BooleanField('Text')
    submit = SubmitField('Save')


class SecuritySettingsForm(FlaskForm):
    two_factor_auth = BooleanField('Two-Factor Authentication')
    password_breach_check = BooleanField('Password Breach Checking')
    submit = SubmitField('Save')


class NewUserForm(PhoneNumberForm):
    name = StringField('Name', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired()])
    submit = SubmitField('Create User')


class BasicEditUserForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    status = SelectField('Status', choices=[('active', 'Active'), ('disabled', 'Disabled'), ('pending', 'Pending')], validators=[DataRequired()])
    password = PasswordField('Password')
    user_manager = BooleanField('User Manager')
    submit = SubmitField('Save')


class TOTPVerifyForm(FlaskForm):
    code = StringField('Authentication Code', validators=[DataRequired()])
    submit = SubmitField('Submit')


class SystemSettingsForm(FlaskForm):
    allow_account_creation = BooleanField('Allow Account Creation')
    strict_login = BooleanField('Strict Login')
    restrict_docs = BooleanField('Restrict Docs')
    submit = SubmitField('Save')


class NewGroupForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = StringField('Description', validators=[Length(max=256)])
    submit = SubmitField('Create Group')


class EditGroupForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    description = StringField('Description', validators=[Length(max=256)])
    users = SelectMultipleField('Users', coerce=lambda v: int(v) if v else None, validators=[Optional()])
    submit = SubmitField('Save')


class BugReportForm(FlaskForm):
    subject = StringField('Subject', validators=[DataRequired()])
    message = TextAreaField('Message', validators=[DataRequired()])
    submit = SubmitField('Submit Report')


def build_edit_user_form(permission_manager):
    fields = {}
    permission_field_map = {}
    permission_specs = []

    for permission in permission_manager.all():
        field_name = permission.permission_field_name

        fields[field_name] = BooleanField(
            label=permission.label,
            description=permission.description,
        )

        permission_field_map[field_name] = permission.permission
        permission_specs.append(permission)

    DynamicEditUserForm = type(
        "DynamicEditUserForm",
        (BasicEditUserForm,),
        fields,
    )

    DynamicEditUserForm.permission_field_map = permission_field_map
    DynamicEditUserForm.permission_specs = permission_specs

    return DynamicEditUserForm


def build_group_form(permission_manager, editing=False, manage_permissions=True):
    fields = {}
    permission_field_map = {}
    for permission in permission_manager.all():
        field_name = permission.permission_field_name
        fields[field_name] = SelectField(
            label=permission.label,
            description=permission.description,
            choices=[('', 'Not defined'), ('allow', 'Allow'), ('deny', 'Deny')],
            default='',
        )
        permission_field_map[field_name] = permission.permission

    class GroupForm(EditGroupForm if editing else NewGroupForm):
        def validate(self, extra_validators=None):
            if not manage_permissions:
                # Ignore submitted definitions, including invalid values, for membership managers.
                for field_name in self.permission_field_map:
                    self[field_name].data = ''
            return super().validate(extra_validators=extra_validators)

    DynamicGroupForm = type('DynamicGroupForm', (GroupForm,), fields)
    DynamicGroupForm.permission_field_map = permission_field_map
    return DynamicGroupForm
