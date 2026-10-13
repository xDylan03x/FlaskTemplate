import click
from flask.cli import with_appcontext

from .helpers import ToolsGroup, show_help
from .settings import settings
from .users import users
from .permissions import permissions
from .groups import groups


@click.group(cls=ToolsGroup, invoke_without_command=True)
@with_appcontext
def tools():
    """Manage application settings, accounts, permissions, and groups."""
    show_help()


for command in (settings, users, permissions, groups):
    tools.add_command(command)
