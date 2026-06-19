from app import sendgrid_client, twilio_client
from sendgrid.helpers.mail import Mail, From
from flask import current_app
from device_detector import DeviceDetector


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
    device_type = device.device_type().value
    return {"user_agent": user_agent, "is_bot": is_bot, "device_os": device_os, "device_brand": device_brand, "device_model": device_model, "device_type": device_type}
