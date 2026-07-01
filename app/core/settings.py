from ..extensions.flask_settings import SettingSpec

settings = [
    SettingSpec(key="Two Factor Authentication", group="Security", description="Enable two factor authentication", default=False),
    SettingSpec(key="Password Breach Check", group="Security", description="Check for password breaches", default=True),
    SettingSpec(key="Security Alerts via Email", group="Notifications", description="Receive security alerts via email", default=True),
    SettingSpec(key="Security Alerts via Text", group="Notifications", description="Receive security alerts via text", default=False),
    SettingSpec(key="Theme", group="Preferences", description="Appearance of the application", default="light"),
]
