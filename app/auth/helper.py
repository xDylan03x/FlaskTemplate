from urllib.parse import urlparse
from flask import request, current_app
from app import twilio_client
import hashlib
import requests


def get_ip_from_request(request_object: request) -> str:
    """Extract the client's IP address from a Flask request object."""
    if request_object.headers.get('X-Forwarded-For'):
        ip = request_object.headers.get('X-Forwarded-For').split(',')[0].strip()
    else:
        ip = request_object.remote_addr
    return ip


def twilio_verify_send(to: str, channel: str) -> None:
    """Send a verification code to the user's chosen method."""
    sid = current_app.config["TWILIO_SERVICE_SID"]
    if channel in ['sms', 'text']:
        twilio_client.verify.v2.services(sid).verifications.create(channel="sms", to=to)
    elif channel == 'email':
        twilio_client.verify.v2.services(sid).verifications.create(channel="email", to=to)
    elif channel in ['voice', 'call', 'phone']:
        twilio_client.verify.v2.services(sid).verifications.create(channel="call", to=to)


def twilio_verify_check(to: str, code: str, totp_entity: str = False, totp_factor: str = None) -> bool:
    """Check the verification code provided by the user."""
    sid = current_app.config["TWILIO_SERVICE_SID"]

    # If submitting a TOTP code
    if totp_entity and totp_factor:
        challenge = (
            twilio_client.verify.v2.services(sid)
            .entities(totp_entity)
            .challenges.create(auth_payload=code, factor_sid=totp_factor)
        )
        if challenge.status == 'approved':
            return True
        else:
            return False
    # If submitting a standard verification code
    verify = twilio_client.verify.v2.services(sid).verification_checks.create(to=to, code=code)
    if verify.status == "approved":
        return True
    else:
        return False


def hibp_password_check(password: str) -> bool:
    """
    Checks if a password has been compromised in any known data breaches
    using the Have I Been Pwned (HIBP) Pwned Passwords API.

    This function uses the k-Anonymity method to securely check the password
    without exposing the full password or its hash to the server.

    View more at https://haveibeenpwned.com/API/v3#BreachesForHashRange

    Args:
        password: The raw password string to check.

    Returns:
        True if the password was found in a breach (should not be used),
        False otherwise.
    """
    # TODO: Modify the function to only check once per x week period (something like 2 weeks). Will require a last checked and check result attribute on the user class
    if not password:
        return False

    # Encode the password and get the prefix and suffix
    sha1_password = hashlib.sha1(password.encode('utf-8')).hexdigest().upper()
    prefix = sha1_password[:5]
    suffix = sha1_password[5:]

    # Make the API request
    api_url = f'https://api.pwnedpasswords.com/range/{prefix}'

    response = requests.get(api_url, timeout=5)
    if response.status_code != 200:
        return False

    pwned_hashes = response.text.splitlines()

    # Check if the full hash suffix is present in the response
    for line in pwned_hashes:
        # The suffix in the response is followed by a colon and the count
        response_suffix = line.split(':')[0]

        # Password found in a breach
        if response_suffix == suffix:
            return True

    # If the loop completes without finding a match, the password is not breached.
    return False
