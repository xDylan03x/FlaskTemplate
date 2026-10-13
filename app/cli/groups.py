import click

from app import pm
from app.model_managers import UserManager
from .helpers import echo_table, get_group, get_permission, get_user, save_changes, show_help, valid_name
from .permissions import permission_state


@click.group(invoke_without_command=True)
def groups():
    """Manage groups by numeric ID or an unambiguous exact name."""
    show_help()


@groups.command('list')
def list_groups():
    """List groups and membership counts."""
    echo_table(['ID', 'Name', 'Description', 'Members'],
               [(group.id, group.title, group.description or '', len(group.users))
                for group in UserManager.get_all_user_groups(paginate=False)])


@groups.command('show')
@click.argument('group')
def show_group(group):
    """Show a group; use its subcommands to inspect members and permissions."""
    selected = get_group(group)
    echo_table(['Field', 'Value'], [('ID', selected.id), ('Name', selected.title),
                                  ('Description', selected.description or ''), ('Members', len(selected.users))])


@groups.command('update')
@click.argument('group')
@click.option('--name', help='New group name.')
@click.option('--description', help='New description; an empty string clears it.')
def update_group(group, name, description):
    """Change supplied fields; prompt when neither option is supplied."""
    selected = get_group(group)
    if name is None and description is None:
        name = click.prompt('Name', default=selected.title)
        description = click.prompt('Description', default=selected.description or '')
    name = valid_name(name, 'Group name') if name is not None else selected.title
    description = description.strip() if description is not None else selected.description
    if description is not None and len(description) > 256:
        raise click.ClickException('Group descriptions cannot exceed 256 characters.')
    if name == selected.title and description == selected.description:
        click.echo('No changes.')
        return
    selected.title = name
    selected.description = description
    save_changes(f'Updated group {selected.id}.', target=selected)


@groups.group('permissions', invoke_without_command=True)
def group_permissions():
    """Manage live inherited group permissions."""
    show_help()


@group_permissions.command('list')
@click.argument('group')
def list_permissions(group):
    selected = get_group(group)
    definitions = {record.key: record.value for record in selected.permissions}
    echo_table(['Key', 'Definition'], [(spec.permission,
               permission_state(definitions[spec.permission]) if spec.permission in definitions else 'unset')
               for spec in pm.all()])


@group_permissions.command('set')
@click.argument('group')
@click.argument('key')
@click.argument('value', type=click.Choice(['allow', 'deny', 'unset'], case_sensitive=False))
def set_permission(group, key, value):
    selected = get_group(group)
    spec = get_permission(key)
    selected.set_permission(spec.permission, None if value == 'unset' else value == 'allow')
    save_changes(f'Set {spec.permission} to {value} for group {selected.id}.', target=selected)


@groups.group('members', invoke_without_command=True)
def members():
    """List, add, and remove group members."""
    show_help()


@members.command('list')
@click.argument('group')
def list_members(group):
    selected = get_group(group)
    echo_table(['ID', 'Name', 'Email', 'Status', 'Deleted'],
               [(user.id, user.name, user.email, user.status, user.deleted)
                for user in sorted(selected.users, key=lambda user: (user.name, user.id))])


@members.command('add')
@click.argument('group')
@click.argument('user')
def add_member(group, user):
    selected = get_group(group)
    account = get_user(user)
    if account in selected.users:
        click.echo('User is already a member.')
        return
    selected.users.append(account)
    save_changes(f'Added user {account.id} to group {selected.id}.', target=selected)


@members.command('remove')
@click.argument('group')
@click.argument('user')
def remove_member(group, user):
    selected = get_group(group)
    account = get_user(user, include_deleted=True)
    if account not in selected.users:
        click.echo('User is not a member; no changes.')
        return
    selected.users.remove(account)
    save_changes(f'Removed user {account.id} from group {selected.id}.', target=selected)
