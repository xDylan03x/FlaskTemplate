import secrets

import click

from app.model_managers import UserManager
from .helpers import echo_table, get_user, invalidate_access, save_changes, show_help, valid_email, valid_name


@click.group(invoke_without_command=True)
def users():
    """Inspect and manage accounts by numeric ID or email."""
    show_help()


@users.command('list')
@click.option('--include-deleted', is_flag=True, help='Include soft-deleted accounts.')
def list_users(include_deleted):
    """List accounts with stable IDs."""
    accounts = UserManager.get_all_users(include_deleted=include_deleted, paginate=False)
    echo_table(['ID', 'Name', 'Email', 'Status', 'Deleted'],
               [(user.id, user.name, user.email, user.status, user.deleted) for user in accounts])


@users.command('show')
@click.argument('user')
def show_user(user):
    """Show an account, including deleted accounts."""
    account = get_user(user, include_deleted=True)
    echo_table(['Field', 'Value'], [
        ('ID', account.id), ('Name', account.name), ('Email', account.email),
        ('Status', account.status), ('Deleted', account.deleted),
        ('Email verified', account.email_verified), ('Phone', account.phone_number or ''),
        ('Phone verified', account.phone_number_verified),
        ('Groups', ', '.join(f'{group.title} ({group.id})' for group in account.groups)),
    ])


@users.command('update')
@click.argument('user')
@click.option('--name', help='New account name.')
@click.option('--email', help='New email; preserves verification.')
def update_user(user, name, email):
    """Change supplied fields; prompt for both when neither is supplied."""
    account = get_user(user)
    if name is None and email is None:
        name = click.prompt('Name', default=account.name)
        email = click.prompt('Email', default=account.email)
    name = valid_name(name) if name is not None else account.name
    email = valid_email(email) if email is not None else account.email
    other = UserManager.get_user_by_email(email)
    if other is not None and other.id != account.id:
        raise click.ClickException('An account with that email already exists, including deleted accounts.')
    if name == account.name and email == account.email:
        click.echo('No changes.')
        return
    changed_email = email != account.email
    account.name = name
    account.email = email
    if changed_email:
        invalidate_access(account)
    save_changes(f'Updated user {account.id}.', target=account)


@users.command('reset-password')
@click.argument('user')
@click.option('--prompt', 'prompt_password', is_flag=True, help='Enter a hidden password instead of generating one.')
def reset_password(user, prompt_password):
    """Reset the password and invalidate sessions and login tokens."""
    account = get_user(user)
    password = (click.prompt('New password', hide_input=True, confirmation_prompt=True)
                if prompt_password else secrets.token_urlsafe(12))
    if not password.strip():
        raise click.ClickException('Password cannot be blank.')
    account.set_password(password)
    invalidate_access(account)
    save_changes(f'Reset password for user {account.id}.', target=account,
                 generated_password=None if prompt_password else password)


@users.command('enable')
@click.argument('user')
def enable_user(user):
    """Set a non-deleted account active; verification is unchanged."""
    account = get_user(user)
    account.status = 'active'
    save_changes(f'Enabled user {account.id}.', target=account)


@users.command('disable')
@click.argument('user')
def disable_user(user):
    """Disable an account without clearing permissions or verification."""
    account = get_user(user)
    account.status = 'disabled'
    invalidate_access(account)
    save_changes(f'Disabled user {account.id}.', target=account)


@users.command('verify')
@click.argument('user')
def verify_user(user):
    """Verify email and any existing phone number; keep account status."""
    account = get_user(user)
    account.email_verified = True
    if account.phone_number:
        account.phone_number_verified = True
    save_changes(f'Verified user {account.id}.', target=account)


@users.command('delete')
@click.argument('user')
def delete_user(user):
    """Soft-delete an account, retaining its settings and memberships."""
    account = get_user(user, include_deleted=True)
    if account.deleted:
        click.echo('User is already deleted.')
        return
    invalidate_access(account, rotate_session=False)
    UserManager.delete_user(account)
    save_changes(f'Deleted user {account.id}.', target=account, commit=False)


@users.command('recover')
@click.argument('user')
def recover_user(user):
    """Recover a deleted account as disabled without reviving old access."""
    account = get_user(user, include_deleted=True)
    if not account.deleted:
        raise click.ClickException('This account is not deleted.')
    account.deleted = False
    account.deleted_at = None
    account.status = 'disabled'
    invalidate_access(account)
    save_changes(f'Recovered user {account.id} as disabled.', target=account)
