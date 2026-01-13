from flask_wtf import FlaskForm
from wtforms import SubmitField, PasswordField, BooleanField, EmailField, SelectField, StringField
from wtforms.validators import DataRequired, Length, Email, EqualTo


class LoginForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(""), Length(1, 64), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Log In')


class TwoFactorAuthSelectForm(FlaskForm):
    method = SelectField('Authentication Method', validators=[DataRequired()])
    submit = SubmitField('Continue')


class TwoFactorAuthCodeForm(FlaskForm):
    code = StringField('Authentication Code', validators=[DataRequired()])
    submit = SubmitField('Submit')


class MagicLinkEmailForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(""), Length(1, 64), Email()])
    submit = SubmitField('Continue')


class MagicLinkSelectForm(FlaskForm):
    method = SelectField('Delivery Method', validators=[DataRequired()])
    submit = SubmitField('Send Link')


class ForgotPasswordEmailForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(""), Length(1, 64), Email()])
    submit = SubmitField('Continue')


class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Reset Password')
