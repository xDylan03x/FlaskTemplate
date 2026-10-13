from ..extensions.flask_settings import SettingSpec

settings = [
    SettingSpec(key="Two Factor Auth", group="Security", description="Enable two factor authentication", default=False),
    SettingSpec(key="Password Breach Check", group="Security", description="Check for password breaches", default=True),
    SettingSpec(key="Security Alerts via Email", group="Notifications", description="Receive security alerts via email", default=True),
    SettingSpec(key="Security Alerts via Text", group="Notifications", description="Receive security alerts via text", default=False),
    SettingSpec(key="Theme", group="Preferences", description="Appearance of the application", default="light"),
    SettingSpec(key="Allow Account Creation", group="Authentication", description="Allow users to create an account (does not affect account creation in the user management tab).", default=True, scope="system", storage_key="allow_account_creation"),
    SettingSpec(key="Strict Login", group="Authentication", description="Block users from signing in with suspicious user agents.", default=True, scope="system", storage_key="strict_login"),
]
