from ..extensions.flask_settings import SettingSpec

settings = [
    SettingSpec(key="Restrict Docs", group="Documentation", description="Block users viewing documentation without signing in.", default=False, scope="system", storage_key="restrict_docs"),
]
