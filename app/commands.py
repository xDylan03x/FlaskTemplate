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
    user.set_permission('users.create', True)
    user.set_permission('users.update', True)
    user.set_permission('users.delete', True)
    user.set_setting('security.two_factor_auth', True)  # Disable this if you do not have a way to send emails
    user.set_setting('security.password_breach_check', False)
    user.set_setting('notifications.security_alerts_via_email', True)
    db.session.commit()
    click.echo('Admin user created.')


@click.command(name='update_users')
@with_appcontext
def update_users():
    from . import db
    from .model_managers import UserManager
    from .models import User

    user_count = 0
    users_updated = []
    for user in db.session.query(User).all():
        user_count += 1
        UserManager.update_permissions(user)
        UserManager.update_settings(user)
        users_updated.append(user.email)

    click.echo(f'All users updated.\nFound {user_count} users.\nUpdated: {', '.join(users_updated)}')
