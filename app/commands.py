import json
from dataclasses import dataclass
import click
from flask import current_app
from flask.cli import with_appcontext


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def _config_state(name: str, required_keys: tuple[str, ...]) -> DoctorCheck | None:
    configured = [
        key for key in required_keys
        if current_app.config.get(key) not in (None, "")
    ]

    if not configured:
        return DoctorCheck(name, "skip", "not configured")

    missing = [key for key in required_keys if key not in configured]
    if missing:
        return DoctorCheck(
            name,
            "fail",
            f"incomplete configuration; missing {', '.join(missing)}",
        )

    return None


def _exception_detail(exception: Exception) -> str:
    message = " ".join(str(exception).split())
    detail = f"{type(exception).__name__}: {message}" if message else type(exception).__name__
    return detail[:300]


def _check_database() -> DoctorCheck:
    from .core.helper import get_database_status

    result = get_database_status()
    if result.get("connected"):
        return DoctorCheck("Database", "ok", "connected")

    error = result.get("error") or "connection failed"
    return DoctorCheck("Database", "fail", str(error)[:300])


def _check_twilio(timeout: float) -> DoctorCheck:
    name = "Twilio"
    required_keys = (
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_SERVICE_SID",
        "FROM_PHONE_NUMBER",
    )
    config_result = _config_state(name, required_keys)
    if config_result:
        return config_result

    try:
        from twilio.http.http_client import TwilioHttpClient
        from twilio.rest import Client

        client = Client(
            current_app.config["TWILIO_ACCOUNT_SID"],
            current_app.config["TWILIO_AUTH_TOKEN"],
            http_client=TwilioHttpClient(timeout=timeout, max_retries=0),
        )
        account = client.api.accounts(
            current_app.config["TWILIO_ACCOUNT_SID"]
        ).fetch()

        if account.status != "active":
            return DoctorCheck(
                name,
                "fail",
                f"credentials are valid, but the account is {account.status}",
            )

        service = client.verify.v2.services(
            current_app.config["TWILIO_SERVICE_SID"]
        ).fetch()
        return DoctorCheck(
            name,
            "ok",
            f"account active; Verify service available ({service.friendly_name})",
        )
    except Exception as exception:
        return DoctorCheck(name, "fail", _exception_detail(exception))


def _check_sendgrid(timeout: float) -> DoctorCheck:
    name = "SendGrid"
    required_keys = (
        "SENDGRID_API_KEY",
        "SENDGRID_EMAIL_TEMPLATE_ID",
        "FROM_EMAIL",
    )
    config_result = _config_state(name, required_keys)
    if config_result:
        return config_result

    try:
        from sendgrid import SendGridAPIClient

        client = SendGridAPIClient(current_app.config["SENDGRID_API_KEY"])
        response = client.client.scopes.get(timeout=timeout)
        if response.status_code != 200:
            return DoctorCheck(
                name,
                "fail",
                f"scope lookup returned HTTP {response.status_code}",
            )

        body = response.body.decode() if isinstance(response.body, bytes) else response.body
        scopes = set(json.loads(body).get("scopes", []))
        if "mail.send" not in scopes:
            return DoctorCheck(
                name,
                "fail",
                "API key is valid but does not have the mail.send scope",
            )

        if "templates.read" not in scopes:
            return DoctorCheck(
                name,
                "warn",
                "API key is valid and can send mail; template ID was not checked "
                "because templates.read is not granted",
            )

        template_response = client.client.templates._(
            current_app.config["SENDGRID_EMAIL_TEMPLATE_ID"]
        ).get(timeout=timeout)
        if template_response.status_code != 200:
            return DoctorCheck(
                name,
                "fail",
                f"API key is valid, but template lookup returned "
                f"HTTP {template_response.status_code}",
            )

        return DoctorCheck(name, "ok", "API key and email template are valid")
    except Exception as exception:
        return DoctorCheck(name, "fail", _exception_detail(exception))


def _check_s3(timeout: float) -> DoctorCheck:
    name = "S3"
    required_keys = ("S3_UPLOAD_ENDPOINT_URL", "S3_BUCKET_NAME")
    config_result = _config_state(name, required_keys)
    if config_result:
        return config_result

    try:
        import boto3
        from botocore.config import Config as BotoConfig

        client = boto3.client(
            service_name="s3",
            endpoint_url=current_app.config["S3_UPLOAD_ENDPOINT_URL"],
            region_name="auto",
            config=BotoConfig(
                connect_timeout=timeout,
                read_timeout=timeout,
                retries={"max_attempts": 0},
            ),
        )
        client.head_bucket(Bucket=current_app.config["S3_BUCKET_NAME"])
        return DoctorCheck(name, "ok", "credentials can access the configured bucket")
    except Exception as exception:
        return DoctorCheck(name, "fail", _exception_detail(exception))


def _check_oauth() -> list[DoctorCheck]:
    checks = []

    for provider_name, provider in current_app.config.get("OAUTH2_PROVIDERS", {}).items():
        name = f"OAuth ({provider_name})"
        client_id = provider.get("client_id")
        client_secret = provider.get("client_secret")

        if not client_id and not client_secret:
            checks.append(DoctorCheck(name, "skip", "not configured"))
        elif not client_id or not client_secret:
            missing = "client_id" if not client_id else "client_secret"
            checks.append(
                DoctorCheck(name, "fail", f"incomplete configuration; missing {missing}")
            )
        else:
            checks.append(
                DoctorCheck(
                    name,
                    "warn",
                    "configured; credentials can only be verified through an OAuth "
                    "authorization-code flow",
                )
            )

    return checks


def _check_sentry() -> DoctorCheck:
    if not current_app.config.get("SENTRY_DSN"):
        return DoctorCheck("Sentry", "skip", "not configured")

    try:
        import sentry_sdk

        if not sentry_sdk.get_client().is_active():
            return DoctorCheck("Sentry", "fail", "DSN is configured but the SDK is inactive")

        return DoctorCheck(
            "Sentry",
            "warn",
            "SDK active; remote ingestion was not tested because that would create an event",
        )
    except Exception as exception:
        return DoctorCheck("Sentry", "fail", _exception_detail(exception))


def _run_doctor_checks(timeout: float) -> list[DoctorCheck]:
    return [
        _check_database(),
        _check_twilio(timeout),
        _check_sendgrid(timeout),
        _check_s3(timeout),
        *_check_oauth(),
        _check_sentry(),
    ]


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


@click.command(name='update_app')
@with_appcontext
def update_app():
    from .model_managers import SystemManager

    if SystemManager.get_setting('strict_login') is None:
        SystemManager.set_setting('strict_login', True)
    if SystemManager.get_setting('allow_account_creation') is None:
        SystemManager.set_setting('allow_account_creation', True)
    if SystemManager.get_setting('restrict_docs') is None:
        SystemManager.set_setting('restrict_docs', False)

    click.echo('Application settings updated.')


@click.command(name='doctor')
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1),
    default=5.0,
    show_default=True,
    help="Network timeout for each provider request, in seconds.",
)
@with_appcontext
def doctor(timeout: float):
    """Check the health of the application and configured providers."""
    checks = _run_doctor_checks(timeout)
    name_width = max(len(check.name) for check in checks)
    labels = {
        "ok": "OK",
        "warn": "WARN",
        "skip": "SKIP",
        "fail": "FAIL",
    }

    for check in checks:
        click.echo(
            f"[{labels[check.status]:4}] "
            f"{check.name:<{name_width}}  {check.detail}"
        )

    failures = [check for check in checks if check.status == "fail"]
    if failures:
        raise click.ClickException(
            f"{len(failures)} health check{'s' if len(failures) != 1 else ''} failed."
        )
