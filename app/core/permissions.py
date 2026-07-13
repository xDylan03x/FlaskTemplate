from ..extensions.flask_permissions import PermissionSpec

permissions = [
    PermissionSpec(action="Create", group="Users", description="Create new users"),
    PermissionSpec(action="Update", group="Users", description="Edit existing users"),
    PermissionSpec(action="Delete", group="Users", description="Delete existing users"),
    PermissionSpec(action="Impersonate", group="Users", description="Impersonate users for troubleshooting"),
    PermissionSpec(action="Create", group="Groups", description="Create new groups"),
    PermissionSpec(action="Update", group="Groups", description="Edit existing groups"),
    PermissionSpec(action="Delete", group="Groups", description="Delete existing groups"),
    PermissionSpec(action="Admin", group="System", description="View admin dashboard"),
    PermissionSpec(action="Update", group="System", description="Edit system settings"),
]
