import click

from app.model_managers import APIKeyManager
from .helpers import echo_table, get_api_key, show_help


@click.group('api-keys', invoke_without_command=True)
def api_keys():
    """Manage shared service credentials by numeric ID or UUID."""
    show_help()


def key_change(operation, *args, **kwargs):
    """Report manager validation errors using the CLI's normal error output."""
    try:
        return operation(*args, **kwargs)
    except ValueError as error:
        raise click.ClickException(str(error)) from error


@api_keys.command('create')
@click.option('--name', required=True, help='Key name.')
@click.option('--expires', type=click.DateTime(formats=['%Y-%m-%d']), help='Inclusive expiration date (UTC).')
@click.option('--preset', type=click.Choice(['custom', 'full-control']), default='custom', show_default=True)
@click.option('--permission', multiple=True, help='API permission to grant with Custom; repeat as needed.')
def create_key(name, expires, preset, permission):
    """Create a credential and print its full value once."""
    key, raw_key = key_change(APIKeyManager.create, name, expires=expires.date() if expires else None,
                             preset=preset, permissions=permission)
    click.echo(f'Created API key {key.id} ({key.uuid36}). Copy this key now; it will not be shown again.')
    click.echo(f'Key: {raw_key}')


@api_keys.command('list')
def list_keys():
    """List keys with masked credentials and lifecycle metadata."""
    keys = APIKeyManager.get_all_api_keys(paginate=False)
    echo_table(['ID', 'UUID', 'Name', 'Key', 'Status', 'Creator', 'Created', 'Last used'],
               [(key.id, key.uuid36, key.name, key.masked_key, key.status,
                 key.creator.email if key.creator else 'CLI', key.created_at, key.last_used_at or 'Never') for key in keys])


@api_keys.command('show')
@click.argument('key')
def show_key(key):
    """Show a key's metadata and explicit permission grants."""
    selected = get_api_key(key)
    echo_table(['Field', 'Value'], [
        ('ID', selected.id), ('UUID', selected.uuid36), ('Name', selected.name),
        ('Key', selected.masked_key), ('Status', selected.status),
        ('Creator', selected.creator.email if selected.creator else 'CLI'),
        ('Created', selected.created_at), ('Updated', selected.updated_at), ('Expires (exclusive UTC)', selected.expires_at or 'Never'),
        ('Last used', selected.last_used_at or 'Never'), ('Revoked', selected.revoked_at or ''),
        ('Rotated', selected.rotated_at or ''), ('Previous key cutoff', selected.previous_valid_until or ''),
        ('Permissions', ', '.join(record.key for record in selected.permissions if record.value)),
    ])


@api_keys.command('rotate')
@click.argument('key')
def rotate_key(key):
    """Rotate a valid key and print its replacement credential once."""
    raw_key = key_change(APIKeyManager.rotate, get_api_key(key))
    click.echo('Rotated API key. Copy this key now; it will not be shown again.')
    click.echo(f'Key: {raw_key}')


@api_keys.command('revoke')
@click.argument('key')
def revoke_key(key):
    """Permanently revoke both versions of a key, retaining its history."""
    key_change(APIKeyManager.revoke, get_api_key(key))
    click.echo('API key revoked.')
