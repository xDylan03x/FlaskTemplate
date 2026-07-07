import os
import logging
from dotenv import load_dotenv
from git import Repo


class Config:
    def __init__(self):
        cwd = os.getcwd()
        basedir = os.path.abspath(os.path.dirname(__file__))
        repo = Repo(search_parent_directories=True)
        # After creating a .env file (you can use .env.example as a template), this will load it
        load_dotenv(os.path.join(basedir, '.env'))

        # Site Basics
        self.APP_NAME = os.environ.get("APP_NAME") or "Unnamed App"
        self.APP_ABBR = os.environ.get("APP_ABBR") or "UA"
        self.SITE_THEME = os.environ.get("SITE_THEME") or "light"
        self.APP_VERSION = os.environ.get("APP_VERSION") or "N/A"

        self.ADMIN_PANEL = True  # Allow users to access the admin panel (given the proper permissions)
        self.MAIN_REPO_URL = None
        self.TEMPLATE_REPO_URL = None
        try:
            self.MAIN_REPO_URL = repo.remotes['origin'].url or None
            self.TEMPLATE_REPO_URL = repo.remotes['template'].url or None
        except:
            pass

        # File uploads
        self.S3_UPLOAD_ENDPOINT_URL = os.environ.get("S3_UPLOAD_ENDPOINT_URL") or None
        self.S3_PUBLIC_ENDPOINT_URL = os.environ.get("S3_PUBLIC_ENDPOINT_URL") or None
        self.S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME") or None
        self.MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB
        self.ALLOWED_CONTENT_TYPES = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "application/pdf",
            "text/csv",
        }

        # Admin credentials
        self.ADMIN_NAME = os.environ.get('ADMIN_NAME', None)
        self.ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', None)
        self.ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', None)

        self.SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or f"postgresql://localhost/{self.APP_ABBR.lower()}_dev"
        self.SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev_secret'

        self.SSL_REDIRECT = False
        self.SQLALCHEMY_TRACK_MODIFICATIONS = False
        self.SQLALCHEMY_RECORD_QUERIES = True

        self.TEMPLATE_FOLDER = os.path.join(cwd, "app", "core", "templates")
        self.STATIC_FOLDER = os.path.join(cwd, "app", "core", "static")

        # For each OAuth2 provider, set up the necessary configuration below.
        self.OAUTH2_PROVIDERS = {
            "google": {
                "client_id": os.environ.get("OAUTH2_GOOGLE_CLIENT_ID"),
                "client_secret": os.environ.get("OAUTH2_GOOGLE_CLIENT_SECRET"),
                "authorize_url": "https://accounts.google.com/o/oauth2/auth",
                "token_url": "https://accounts.google.com/o/oauth2/token",
                "userinfo": {
                    "url": "https://www.googleapis.com/oauth2/v3/userinfo",
                    "email": lambda json: json["email"],
                },
                "scopes": ["https://www.googleapis.com/auth/userinfo.email"],
            },
        }

        # Twilio configuration - to use another provider, modify accordingly and
        # update the core/helper.py files and auth/helper.py files
        self.TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", None)
        self.TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", None)
        self.TWILIO_SERVICE_SID = os.environ.get("TWILIO_SERVICE_SID", None)
        self.FROM_PHONE_NUMBER = os.environ.get("FROM_PHONE_NUMBER", None)

        # Sendgrid configuration - to use another provider, modify accordingly and update the core/helper.py
        self.FROM_EMAIL = os.environ.get("FROM_EMAIL", None)
        self.SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", None)
        self.SENDGRID_EMAIL_TEMPLATE_ID = os.environ.get("SENDGRID_EMAIL_TEMPLATE_ID", None)

        # Sentry configuration
        self.SENTRY_DSN = os.environ.get("SENTRY_DSN", None)

        # Checks
        if self.SECRET_KEY == "dev_secret":
            logging.warning("Using default secret key. This is insecure and should be changed in production.")
        if not self.TWILIO_ACCOUNT_SID or not self.TWILIO_AUTH_TOKEN or not self.TWILIO_SERVICE_SID or not self.FROM_PHONE_NUMBER:
            logging.fatal("Twilio configuration is incomplete.")
        if not self.FROM_EMAIL or not self.SENDGRID_API_KEY or not self.SENDGRID_EMAIL_TEMPLATE_ID:
            logging.fatal("Sendgrid configuration is incomplete.")
        if not self.ADMIN_NAME or not self.ADMIN_EMAIL or not self.ADMIN_PASSWORD:
            logging.warning("Admin user configuration is incomplete. Set this up to enable default admin user creation.")
