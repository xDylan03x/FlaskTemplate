from app import sendgrid_client, twilio_client
from sendgrid.helpers.mail import Mail, From
from flask import current_app


def send_email(subject: str, body: str, recipients: list[str], preheader="", sender=None, sender_name=None, template_id=None):
    if sender is None:
        sender = current_app.config["FROM_EMAIL"]
    if sender_name is None:
        sender_name = current_app.config["APP_NAME"]
    if template_id is None:
        template_id = current_app.config["SENDGRID_EMAIL_TEMPLATE_ID"]

    message = Mail(from_email=From(sender, sender_name), to_emails=recipients)
    message.dynamic_template_data = {
        'body': body,
        'subject': subject,
        'preheader': preheader
    }
    message.template_id = template_id
    try:
        sendgrid_client.send(message)
    except Exception as e:
        print(f"Error: {e}")


def send_sms(body: str, recipients: list[str], sender=None):
    if sender is None:
        sender = current_app.config["FROM_PHONE_NUMBER"]

    for recipient in recipients:
        twilio_client.messages.create(body=body, from_=sender, to=recipient)
