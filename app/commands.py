# app/commands.py
import click
from flask.cli import with_appcontext


@click.command(name='create_admin')
@with_appcontext
def create_admin():
    """Creates the admin user from .env values."""
    from flask import current_app
    from . import db
    from .model_managers import UserManager
    from .models import User

    name = current_app.config.get('ADMIN_NAME')
    email = current_app.config.get('ADMIN_EMAIL')
    password = current_app.config.get('ADMIN_PASSWORD')

    if not all([name, email, password]):
        click.echo('Admin credentials not found in your .env file.')
        return

    if User.query.filter_by(email=email).first():
        click.echo('Admin user with that email already exists.')
        return

    user = UserManager.create_user(email=email, name=name, email_verified=True)
    user.set_password(password)
    user.set_setting('security.two_factor_auth', True)  # If you do not have an email service set up, disable this.
    user.set_setting('security.password_breach_check', True)
    db.session.commit()
    click.echo('Admin user created.')
