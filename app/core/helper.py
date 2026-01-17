from app import sendgrid_client, twilio_client
from sendgrid.helpers.mail import Mail, From
from flask import current_app


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

