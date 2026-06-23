from app.extensions import PermissionSpec

permissions = [
    PermissionSpec(action="Create", group="Users", description="Create new users"),
    PermissionSpec(action="Update", group="Users", description="Edit existing users"),
    PermissionSpec(action="Delete", group="Users", description="Delete existing users"),
]
