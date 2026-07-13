import re

from sqlalchemy import text
import os
import platform
import sys
from app import sendgrid_client, twilio_client, db
from sendgrid.helpers.mail import Mail, From
from flask import current_app
from device_detector import DeviceDetector
import boto3


READ_ONLY_PREFIXES = ("select", "show", "describe", "explain", "pragma")
BLOCKED_SQL_WORDS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "create",
    "truncate",
    "replace",
    "merge",
    "grant",
    "revoke",
    "commit",
    "rollback",
    "vacuum",
    "attach",
    "detach",
    "copy",
)


def send_email(subject: str, body: str, recipient: str, preheader="", sender=None, sender_name=None, template_id=None) -> str:
    if sender is None:
        sender = current_app.config["FROM_EMAIL"]
    if sender_name is None:
        sender_name = current_app.config["APP_NAME"]
    if template_id is None:
        template_id = current_app.config["SENDGRID_EMAIL_TEMPLATE_ID"]

    message = Mail(from_email=From(sender, sender_name), to_emails=recipient)
    message.dynamic_template_data = {
        'body': body.replace('\n', '<br>'),
        'subject': subject,
        'preheader': preheader
    }
    message.template_id = template_id
    try:
        response = sendgrid_client.send(message)
        # Get the Message-ID from the response headers
        message_id = response.headers.get('X-Message-Id') or response.headers.get('X-Message-ID')
        return message_id
    except Exception:
        return None


def send_sms(body: str, recipient: str, sender=None) -> str:
    if sender is None:
        sender = current_app.config["FROM_PHONE_NUMBER"]

    message = twilio_client.messages.create(body=body, from_=sender, to=recipient)
    return message.sid


def parse_device(user_agent: str):
    """
    Parses a user agent string to extract device information and determine if it is a bot.

    :param user_agent:
    Returns:
        A dictionary containing:
            - user_agent: The original user agent string.
            - is_bot: Whether the user agent is identified as a bot.
            - device_os: The detected operating system name, if available.
            - device_brand: The detected device brand, if available.
            - device_model: The detected device model, if available.
            - device_type: The detected device type, if available.
    """
    device = DeviceDetector(user_agent).parse()
    is_bot = device.is_bot()
    device_os = device.os_name()
    device_brand = device.device_brand()
    device_model = device.device_model()
    device_type = device.device_type()
    browser = device.client_name()
    return {"user_agent": user_agent, "is_bot": is_bot, "device_os": device_os, "device_brand": device_brand, "device_model": device_model, "device_type": device_type, "browser": browser}


def get_s3_client():
    return boto3.client(
        service_name="s3",
        endpoint_url=current_app.config["S3_UPLOAD_ENDPOINT_URL"],
        region_name="auto",
    )


def get_routes():
    routes = []
    for rule in current_app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": sorted(rule.methods - {"HEAD", "OPTIONS"}),
            "rule": str(rule),
            "arguments": sorted(rule.arguments),
        })
    return sorted(routes, key=lambda r: r["endpoint"])


def get_blueprints():
    blueprints = []
    for name, blueprint in current_app.blueprints.items():
        blueprints.append({
            "name": name,
            "url_prefix": blueprint.url_prefix,
            "import_name": blueprint.import_name,
        })
    return sorted(blueprints, key=lambda b: b["name"])


def get_extensions():
    extensions = []
    for name, extension in current_app.extensions.items():
        extensions.append({
            "name": name,
            "instance": extension,
        })
    return sorted(extensions, key=lambda e: e["name"])


def get_database_status():
    try:
        db.session.execute(text("SELECT 1"))
        return {
            "connected": True,
            "error": None,
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
        }


def get_platform_info():
    info = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "pid": os.getpid(),
        "cwd": os.getcwd(),
    }
    return info


def is_safe_read_query(query: str) -> tuple[bool, str | None]:
    cleaned = query.strip().lower()

    if not cleaned:
        return False, "Query is empty."

    if ";" in cleaned:
        return False, "Multiple statements are not allowed."

    if not cleaned.startswith(READ_ONLY_PREFIXES):
        return False, "Only read-only SELECT-style queries are allowed."

    for word in BLOCKED_SQL_WORDS:
        if word in cleaned.split():
            return False, f"Blocked SQL keyword: {word}"

    return True, None


def modify_query(query: str) -> str:
    strict_pattern = r"\buser\b"
    return re.sub(strict_pattern, '"user"', query)
