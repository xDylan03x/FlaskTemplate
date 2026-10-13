from dataclasses import dataclass, field
from typing import Literal
from flask import Blueprint
from flask_login import current_user


@dataclass
class SettingSpec:
    key: str  # The individual setting key
    group: str  # The group the action belongs to
    description: str = ""  # A description of the setting
    default: str | bool = ""  # The default setting value for new users
    order: int = -1
    scope: Literal["user", "system"] = "user"
    storage_key: str | None = None  # Optional existing database key for compatibility
    # When printed out, the setting will be shown as Key (Group) (i.e. Theme (Preferences))

    @property
    def setting(self):
        """
        Returns <group>.<key> for both user and system settings.
        """
        return f"{self.group.lower().replace(' ', '_')}.{self.key.lower().replace(' ', '_')}"

    @property
    def database_key(self) -> str:
        return self.storage_key or self.setting

    @property
    def label(self):
        """
        Returns the setting in a user-friendly format
        """
        return f"{self.key} ({self.group})"

    @property
    def setting_field_name(self) -> str:
        return "setting__" + self.setting.replace(".", "__")


@dataclass
class ModuleSpec:
    name: str
    description: str = ""
    settings: list[SettingSpec] = field(default_factory=list)
    version: str | None = None


class SettingsManager:
    def __init__(self, app=None):
        self.app = app
        self._registry = {"user": {}, "system": {}}
        self._modules = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions["settings"] = self

        app.add_template_global(self.user_setting, name="user_setting")
        app.add_template_global(self.system_setting, name="system_setting")

    def register_module(self, module: ModuleSpec, blueprint: Blueprint | None = None):
        if module.name in self._modules:
            raise ValueError(f"Module already registered: {module.name}")
        self.register_many(module.settings)
        self._modules[module.name] = module
        if blueprint is not None:
            blueprint.module_spec = module

    def get_module(self, name: str) -> ModuleSpec | None:
        return self._modules.get(name)

    def all_modules(self) -> list[ModuleSpec]:
        return sorted(self._modules.values(), key=lambda module: module.name.lower())

    def register(self, *settings: SettingSpec):
        keys = set()
        for setting in settings:
            if setting.scope not in self._registry:
                raise ValueError(f"Invalid setting scope: {setting.scope}")
            if not isinstance(setting.default, (str, bool)):
                raise ValueError("Setting defaults must be strings or booleans")
            identity = (setting.scope, setting.setting)
            stored_identity = (setting.scope, setting.database_key)
            if identity in keys or self.get(setting.setting, scope=setting.scope):
                raise ValueError(f"Setting already registered: {setting.setting}")
            if stored_identity in keys or self.get(setting.database_key, scope=setting.scope):
                raise ValueError(f"Setting database key already registered: {setting.database_key}")
            keys.update((identity, stored_identity))

        for setting in settings:
            # If the setting has an order of -1, assign the order as the next available in the group
            if setting.order < 0:
                setting.order = self._group_next_order(setting.group, setting.scope)
            else:
                # If the order is available, allow the setting to keep it, otherwise, assign the next available order in the group
                if setting.order in [s.order for s in self.grouped(setting.scope).get(setting.group, [])]:
                    setting.order = self._group_next_order(setting.group, setting.scope)
            self._registry[setting.scope][setting.setting] = setting

    def register_many(self, settings: list[SettingSpec]):
        self.register(*settings)

    def get(self, setting: str, scope: str = "user") -> SettingSpec | None:
        spec = self._registry[scope].get(setting)
        if spec is None and scope == "system":
            spec = next((s for s in self._registry[scope].values() if s.database_key == setting), None)
        return spec

    def all(self, scope: str = "user") -> list[SettingSpec]:
        return sorted(
            self._registry[scope].values(),
            key=lambda p: (p.group.lower(), p.key.lower())
        )

    def grouped(self, scope: str = "user") -> dict[str, list[SettingSpec]]:
        groups = {}

        for setting in self.all(scope):
            groups.setdefault(setting.group, []).append(setting)
        for group in groups:
            groups[group] = sorted(groups[group], key=lambda s: s.order)

        return groups

    def user_setting(self, setting: str) -> str | bool:
        if not current_user or not current_user.is_authenticated:
            return False
        return current_user.get_setting(setting)

    def system_setting(self, setting: str) -> str | bool | None:
        from ..model_managers import SystemManager
        return SystemManager.get_setting(setting)

    def set_system_setting(self, setting: str, value: str | bool) -> None:
        from ..model_managers import SystemManager
        SystemManager.set_setting(setting, value)

    def _group_next_order(self, group: str, scope: str = "user") -> int:
        groups = self.grouped(scope)
        if group not in groups:
            return 0
        return max(s.order for s in groups[group]) + 1
