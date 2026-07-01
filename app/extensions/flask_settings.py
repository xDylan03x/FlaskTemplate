from dataclasses import dataclass
from flask_login import current_user


@dataclass
class SettingSpec:
    key: str  # The individual setting key
    group: str  # The group the action belongs to
    description: str = ""  # A description of the setting
    default: str | bool = ""  # The default setting value for new users
    order: int = -1
    # When printed out, the setting will be shown as Key (Group) (i.e. Theme (Preferences))

    @property
    def setting(self):
        """
        Returns the setting in the format of <group>.<key> (all lowercase)
        """
        return f"{self.group.lower().replace(' ', '_')}.{self.key.lower().replace(' ', '_')}"

    @property
    def label(self):
        """
        Returns the setting in a user-friendly format
        """
        return f"{self.key} ({self.group})"

    @property
    def setting_field_name(self) -> str:
        return "setting__" + self.setting.replace(".", "__")


class SettingsManager:
    def __init__(self, app=None):
        self.app = app
        self._registry = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions["settings"] = self

        app.add_template_global(self.user_setting, name="user_setting")

    def register(self, *settings: SettingSpec):
        for setting in settings:
            if setting.setting in self._registry:
                raise ValueError(f"Setting already registered: {setting.setting}")
            # If the setting has an order of -1, assign the order as the next available in the group
            if setting.order < 0:
                setting.order = self._group_next_order(setting.group)
            else:
                # If the order is available, allow the setting to keep it, otherwise, assign the next available order in the group
                if setting.order in [s.order for s in self.grouped().get(setting.group, [])]:
                    setting.order = self._group_next_order(setting.group)
            self._registry[setting.setting] = setting

    def register_many(self, settings: list[SettingSpec]):
        self.register(*settings)

    def get(self, setting: str) -> SettingSpec | None:
        return self._registry.get(setting)

    def all(self) -> list[SettingSpec]:
        return sorted(
            self._registry.values(),
            key=lambda p: (p.group.lower(), p.key.lower())
        )

    def grouped(self) -> dict[str, list[SettingSpec]]:
        groups = {}

        for setting in self.all():
            groups.setdefault(setting.group, []).append(setting)
        for group in groups:
            groups[group] = sorted(groups[group], key=lambda s: s.order)

        return groups

    def user_setting(self, setting: str) -> bool:
        if not current_user or not current_user.is_authenticated:
            return False
        return current_user.get_setting(setting)

    def _group_next_order(self, group: str) -> int:
        groups = self.grouped()
        if group not in groups:
            return 0
        return max(s.order for s in groups[group]) + 1
