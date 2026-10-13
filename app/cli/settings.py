import click

from app import db, sm
from app.models import SystemSetting
from .helpers import display_value, echo_table, get_setting, save_changes, show_help


@click.group(invoke_without_command=True)
def settings():
    """List and change registered application settings."""
    show_help()


def setting_rows(specs):
    stored = set(db.session.scalars(db.select(SystemSetting.key)))
    return [(spec.setting, display_value(sm.system_setting(spec.setting)),
             'saved' if spec.database_key in stored else 'default') for spec in specs]


@settings.command('list')
def list_settings():
    """Show effective values and whether they are saved or defaults."""
    echo_table(['Key', 'Value', 'Source'], setting_rows(sm.all(scope='system')))


@settings.command('get')
@click.argument('key')
def get_value(key):
    """Show one setting; existing storage aliases are accepted."""
    spec = get_setting(key)
    echo_table(['Key', 'Value', 'Source'], setting_rows([spec]))
    if spec.description:
        click.echo(spec.description)


@settings.command('set')
@click.argument('key')
@click.argument('value', required=False)
def set_value(key, value):
    """Set a value, prompting when VALUE is omitted."""
    spec = get_setting(key)
    value_type = click.BOOL if isinstance(spec.default, bool) else click.STRING
    if value is None:
        value = click.prompt(spec.label, default=sm.system_setting(spec.setting), type=value_type)
    else:
        value = value_type.convert(value, None, click.get_current_context())
    if isinstance(value, str) and len(value) > 2048:
        raise click.ClickException('Setting values cannot exceed 2048 characters.')
    sm.set_system_setting(spec.setting, value)
    save_changes(f'Updated setting {spec.setting}.', commit=False)
