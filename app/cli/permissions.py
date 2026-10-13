import click

from app import pm
from .helpers import echo_table, get_permission, get_user, save_changes, show_help


@click.group(invoke_without_command=True)
def permissions():
    """Inspect registered permissions and change direct user definitions."""
    show_help()


def permission_state(value):
    return 'allow' if value else 'deny'


def permission_rows(account):
    direct = {record.key: record.value for record in account.permissions}
    inherited = account.inherited_permissions()
    rows = []
    for spec in pm.all():
        definition = inherited.get(spec.permission)
        sources = ''
        if definition:
            sources = '; '.join(
                f'{label}: {group.title} ({group.id})'
                for key, label in [('allow_groups', 'allow'), ('deny_groups', 'deny')]
                for group in definition[key]
            )
            if definition['conflict']:
                sources += '; conflict: allow wins'
        rows.append((
            spec.permission, permission_state(direct[spec.permission]) if spec.permission in direct else 'missing',
            permission_state(definition['value']) if definition else 'unset',
            permission_state(account.can(spec.permission)), sources,
        ))
    return rows


@permissions.command('list')
@click.argument('user', required=False)
def list_permissions(user):
    """List definitions, or direct/inherited/effective permissions for USER."""
    if user is None:
        echo_table(['Key', 'Default', 'Description'],
                   [(spec.permission, permission_state(spec.default), spec.description) for spec in pm.all()])
    else:
        echo_table(['Key', 'Direct', 'Inherited', 'Effective', 'Groups'],
                   permission_rows(get_user(user, include_deleted=True)))


@permissions.command('set')
@click.argument('user')
@click.argument('key')
@click.argument('value', type=click.Choice(['allow', 'deny'], case_sensitive=False))
def set_permission(user, key, value):
    """Change a direct permission; group inheritance remains authoritative."""
    account = get_user(user)
    spec = get_permission(key)
    account.set_permission(spec.permission, value == 'allow')
    save_changes(f'Set {spec.permission} to {value} for user {account.id}.', target=account)
    if spec.permission in account.inherited_permissions():
        click.echo(f'Group inheritance controls this permission; effective value: {permission_state(account.can(spec.permission))}.')
