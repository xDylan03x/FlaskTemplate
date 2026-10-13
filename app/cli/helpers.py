from datetime import datetime, timezone
import json

import click
from email_validator import EmailNotValidError, validate_email
from flask import has_app_context
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import audit, db, pm, sm
from app.model_managers import UserManager
from app.models import LoginToken, UserGroup


class ToolsGroup(click.Group):
    def invoke(self, ctx):
        try:
            return super().invoke(ctx)
        except (click.ClickException, click.Abort, SQLAlchemyError) as error:
            if has_app_context():
                db.session.rollback()
            if isinstance(error, IntegrityError):
                raise click.ClickException('The update conflicts with an existing record.') from error
            if isinstance(error, SQLAlchemyError):
                raise click.ClickException('Database operation failed.') from error
            raise


def show_help():
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def echo_table(headers, rows):
    rows = [[str(value).replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t') for value in row] for row in rows]
    widths = [max([len(header)] + [len(row[index]) for row in rows]) for index, header in enumerate(headers)]
    for row in [headers, *rows]:
        click.echo('  '.join(value.ljust(width) for value, width in zip(row, widths)).rstrip())
    if not rows:
        click.echo('(none)')


def display_value(value):
    return json.dumps(value, ensure_ascii=False)


def valid_name(value, label='Name'):
    value = value.strip()
    if not value or len(value) > 256:
        raise click.ClickException(f'{label} must contain between 1 and 256 characters.')
    return value


def valid_email(value):
    try:
        email = validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise click.ClickException('Enter a valid email address.')
    if len(email) > 120:
        raise click.ClickException('Email addresses cannot exceed 120 characters.')
    return email


def get_user(identifier, include_deleted=False):
    identifier = identifier.strip()
    user = (UserManager.get_user_by_id(int(identifier)) if identifier.isdigit()
            else UserManager.get_user_by_email(identifier))
    if user is None:
        raise click.ClickException('User not found; use a numeric ID or exact email address.')
    if user.deleted and not include_deleted:
        raise click.ClickException('This user is deleted; recover the account first.')
    return user


def get_group(identifier):
    identifier = identifier.strip()
    if identifier.isdigit():
        group = db.session.get(UserGroup, int(identifier))
    else:
        matches = db.session.scalars(db.select(UserGroup).where(UserGroup.title == identifier)).all()
        if len(matches) > 1:
            raise click.ClickException('Group name is ambiguous; use its numeric ID.')
        group = matches[0] if matches else None
    if group is None:
        raise click.ClickException('Group not found; use a numeric ID or exact group name.')
    return group


def get_setting(key):
    spec = sm.get(key.lower(), scope='system')
    if spec is None:
        raise click.ClickException('Unknown system setting; use tools settings list to find its key.')
    return spec


def get_permission(key):
    spec = pm.get(key.lower())
    if spec is None:
        raise click.ClickException('Unknown permission; use tools permissions list to find its key.')
    return spec


def invalidate_access(user, rotate_session=True):
    if rotate_session:
        user.refresh_uuid36()
    db.session.execute(db.update(LoginToken).where(
        LoginToken.user_id == user.id, LoginToken.used.is_(False),
    ).values(used=True, used_at=datetime.now(timezone.utc)))


def save_changes(message, target=None, generated_password=None, commit=True):
    if commit:
        db.session.commit()
    click.echo(message)
    if generated_password is not None:
        click.echo(f'Password: {generated_password}')
    try:
        # Do not snapshot model state: it could include password hashes.
        audit.log(message, target=target, actor='CLI')
    except SQLAlchemyError as error:
        raise click.ClickException('Changes saved, but audit logging failed.') from error
