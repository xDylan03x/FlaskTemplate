import inspect
import logging
from twilio.rest import Client
from sendgrid import SendGridAPIClient
from flask_qrcode import QRcode
from config import Config
from flask import Flask
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_compress import Compress
import sentry_sdk
from .commands import create_admin
from .extensions.flask_permissions import PermissionManager
from .extensions.flask_settings import SettingsManager
from .extensions.flask_audit import AuditManager

# Create global instances of extensions
db = SQLAlchemy(add_models_to_shell=True)
migrate = Migrate()
login = LoginManager()
twilio_client = Client()
sendgrid_client = SendGridAPIClient()
qr = QRcode()
compress = Compress()
pm = PermissionManager()
sm = SettingsManager()
audit = AuditManager()


def create_app(cfg: Config = Config) -> Flask:
    # If the config has not been instantiated, do so
    if inspect.isclass(cfg):
        cfg = cfg()
        logging.info("Manually instantiated config class.")

    app = Flask(__name__, template_folder=getattr(cfg, "TEMPLATE_FOLDER", None), static_folder=getattr(cfg, "STATIC_FOLDER", None))

    app.config.from_object(cfg)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'auth.login'
    twilio_client.username = app.config.get('TWILIO_ACCOUNT_SID')
    twilio_client.password = app.config.get('TWILIO_AUTH_TOKEN')
    sendgrid_client.api_key = app.config.get('SENDGRID_API_KEY')
    qr.init_app(app)
    compress.init_app(app)
    pm.init_app(app)
    sm.init_app(app)
    audit.init_app(app, db)
    if app.config.get('SENTRY_DSN'):
        sentry_sdk.init(
            dsn=app.config.get('SENTRY_DSN'),
            send_default_pii=True,
            traces_sample_rate=1.0,
            environment=app.config.get('FLASK_ENV'),
        )

    # Context processors
    @app.context_processor
    def app_name():
        return dict(app_name=app.config["APP_NAME"])

    @app.context_processor
    def app_abbr():
        return dict(app_abbr=app.config["APP_ABBR"])

    @app.context_processor
    def site_theme():
        return dict(site_theme=app.config["SITE_THEME"])

    # Register CLI commands
    app.cli.add_command(create_admin)

    from . import models

    from .core import core as core_blueprint
    app.register_blueprint(core_blueprint)

    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    # from .api import apiV1 as api_blueprint
    # app.register_blueprint(api_blueprint, url_prefix='/api/v1')

    from .errors import errors
    app.register_blueprint(errors)

    return app
