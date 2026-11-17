from dataclasses import dataclass
from functools import wraps
from typing import Literal
from flask import abort, current_app, jsonify
from flask_login import current_user


@dataclass
class PermissionSpec:
    action: str  # The Create, Read, Update, or Delete action (or others) to be performed
    group: str  # The group the action belongs to
    description: str = ""  # A description of the action/permission
    default: bool = False  # The default permission value for new users
    order: int = -1  # The order in which the permission should be displayed in the UI
    scope: Literal["user", "api"] = "user"
    # When printed out, the permission will be shown as Action Group (i.e. Create Users)

    @property
    def permission(self):
        """
        Returns the permission in the format of <group>.<action> (all lowercase)
        """
        return f"{self.group.lower().replace(' ', '_')}.{self.action.lower().replace(' ', '_')}"

    @property
    def label(self):
        """
        Returns the permission in a user-friendly format (i.e. Create Users)
        """
        return f"{self.action}".title()

    @property
    def permission_field_name(self) -> str:
        return "perm__" + self.permission.replace(".", "__")

    @property
    def is_authentication_policy(self) -> bool:
        return self.permission.startswith('authentication_policies.')

    @property
    def management_permission(self) -> str:
        return 'users.update_authentication_policies' if self.is_authentication_policy else 'users.update_permissions'


class PermissionManager:
    def __init__(self, app=None):
        self.app = app
        self._registry = {"user": {}, "api": {}}

        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.app = app
        app.extensions["permissions"] = self

        app.add_template_global(self.can, name="can")

    def register(self, *permissions: PermissionSpec):
        for permission in permissions:
            if permission.scope not in self._registry:
                raise ValueError(f"Invalid permission scope: {permission.scope}")
            if permission.permission in self._registry[permission.scope]:
                raise ValueError(f"Permission already registered: {permission.permission}")
            # If the permission has an order of -1, assign the order as the next available in the group
            if permission.order < 0:
                permission.order = self._group_next_order(permission.group, permission.scope)
            else:
                # If the order is available, allow the permission to keep it, otherwise, assign the next available order in the group
                if permission.order in [p.order for p in self.grouped(permission.scope).get(permission.group, [])]:
                    permission.order = self._group_next_order(permission.group, permission.scope)
            self._registry[permission.scope][permission.permission] = permission

    def register_many(self, permissions: list[PermissionSpec]):
        self.register(*permissions)

    def get(self, permission: str, scope: str = "user") -> PermissionSpec | None:
        return self._registry[scope].get(permission)

    def all(self, scope: str = "user") -> list[PermissionSpec]:
        return sorted(
            self._registry[scope].values(),
            key=lambda p: (p.group.lower(), p.action.lower())
        )

    def grouped(self, scope: str = "user") -> dict[str, list[PermissionSpec]]:
        groups = {}

        for permission in self.all(scope):
            groups.setdefault(permission.group, []).append(permission)
        for group in groups:
            groups[group] = sorted(groups[group], key=lambda p: p.order)

        return groups

    def can(self, permission: str, scope: str = "user") -> bool:
        if scope == "api":
            from ..api.helper import current_api_key
            return bool(current_api_key and current_api_key.can(permission))
        if scope != "user":
            raise ValueError(f"Invalid permission scope: {scope}")
        if not current_user or not current_user.is_authenticated:
            return False

        return current_user.can(permission)

    def _group_next_order(self, group: str, scope: str = "user") -> int:
        groups = self.grouped(scope)
        if group not in groups:
            return 0
        return max(p.order for p in groups[group]) + 1


def require_permission(permission: str, scope: str = "user"):
    """
    Determine if the current user has the permissions required to access the resource.
    Pass in a full permission (like 'users.create') to make sure the user has that specific permission.
    Pass in a group (like 'users') to make sure the user has any permission in that group.
    """
    if scope not in ("user", "api"):
        raise ValueError(f"Invalid permission scope: {scope}")

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            if scope == "api":
                from ..api.helper import current_api_key
                if not current_api_key:
                    return jsonify(error="Invalid or missing API key."), 401, {"WWW-Authenticate": "Bearer"}
                if not current_api_key.can(permission):
                    return jsonify(error="Insufficient API permissions."), 403
                return current_app.ensure_sync(view_func)(*args, **kwargs)
            if not current_user or not current_user.is_authenticated:
                abort(403)
            if not current_user.can(permission):
                abort(403)
            return current_app.ensure_sync(view_func)(*args, **kwargs)
        return wrapper
    return decorator
