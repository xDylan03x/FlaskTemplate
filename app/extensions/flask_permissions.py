from dataclasses import dataclass
from functools import wraps
from flask import abort, current_app
from flask_login import current_user


@dataclass(frozen=True)
class PermissionSpec:
    action: str  # The Create, Read, Update, or Delete action (or others) to be performed
    group: str  # The group the action belongs to
    description: str = ""  # A description of the action/permission
    default: bool = False  # The default permission value for new users
    # When printed out, the permission will be shown as Action Group (i.e. Create Users)

    @property
    def permission(self):
        """
        Returns the permission in the format of <group>.<action> (all lowercase)
        """
        return f"{self.group.lower()}.{self.action.lower()}"

    @property
    def label(self):
        """
        Returns the permission in a user-friendly format (i.e. Create Users)
        """
        return f"{self.action} {self.group}"

    @property
    def permission_field_name(self) -> str:
        return "perm__" + self.permission.replace(".", "__")


class PermissionManager:
    def __init__(self, app=None):
        self.app = None
        self._registry = {}

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions["permissions"] = self

        app.add_template_global(self.can, name="can")

    def register(self, *permissions: PermissionSpec):
        for permission in permissions:
            if permission.permission in self._registry:
                raise ValueError(f"Permission already registered: {permission.permission}")

            self._registry[permission.permission] = permission

    def register_many(self, permissions: list[PermissionSpec]):
        self.register(*permissions)

    def get(self, permission: str) -> PermissionSpec | None:
        return self._registry.get(permission)

    def all(self) -> list[PermissionSpec]:
        return sorted(
            self._registry.values(),
            key=lambda p: (p.group.lower(), p.action.lower())
        )

    def grouped(self) -> dict[str, list[PermissionSpec]]:
        groups = {}

        for permission in self.all():
            groups.setdefault(permission.group, []).append(permission)

        return groups

    def can(self, permission: str) -> bool:
        if not current_user or not current_user.is_authenticated:
            return False

        return current_user.can(permission)


def require_permission(permission: str):
    """
    Determine if the current user has the permissions required to access the resource.
    Pass in a full permission (like 'users.create') to make sure the user has that specific permission.
    Pass in a group (like 'users') to make sure the user has any permission in that group.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if not current_user or not current_user.is_authenticated:
                abort(403)
            if not current_user.can(permission):
                abort(403)
            return current_app.ensure_sync(view_func)(*args, **kwargs)
        return wrapper
    return decorator
