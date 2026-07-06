from ..extensions.flask_permissions import PermissionSpec

permissions = [
    PermissionSpec(action="Create", group="Users", description="Create new users"),
    PermissionSpec(action="Update", group="Users", description="Edit existing users"),
    PermissionSpec(action="Delete", group="Users", description="Delete existing users"),
    PermissionSpec(action="Admin", group="System", description="View admin dashboard"),
    PermissionSpec(action="Update", group="System", description="Edit system settings"),
]
