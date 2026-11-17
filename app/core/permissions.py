from ..extensions.flask_permissions import PermissionSpec

permissions = [
    PermissionSpec(action="Manage", group="API Keys", description="Manage service API keys and browse their audit logs"),
    PermissionSpec(action="Create", group="Users", description="Create new users"),
    PermissionSpec(action="Update", group="Users", description="Edit existing users"),
    PermissionSpec(action="Delete", group="Users", description="Delete existing users"),
    PermissionSpec(action="Update Permissions", group="Users", description="Update user permissions"),
    PermissionSpec(action="Update Authentication Policies", group="Users", description="Update authentication policies on users and groups"),
    PermissionSpec(action="Impersonate", group="Users", description="Impersonate users for troubleshooting"),
    PermissionSpec(action="Create", group="Groups", description="Create new groups"),
    PermissionSpec(action="Update", group="Groups", description="Edit existing groups"),
    PermissionSpec(action="Delete", group="Groups", description="Delete existing groups"),
    PermissionSpec(action="Admin", group="System", description="View admin dashboard"),
    PermissionSpec(action="Update", group="System", description="Edit system settings"),
    PermissionSpec(action="2FA Required", group="Authentication Policies", description="Require 2FA for every password login. When disabled, users choose their own 2FA preference."),
    PermissionSpec(action="Unknown Device Requires 2FA", group="Authentication Policies", description="Require the unknown-device 2FA setting. When disabled, users choose their own preference."),
    PermissionSpec(action="2FA Applies to Alternative Login Methods", group="Authentication Policies", description="Require the alternative-login 2FA setting. When disabled, users choose their own preference."),
    PermissionSpec(action="Password Breach Checking", group="Authentication Policies", description="Require password breach checking on password logins. When disabled, users choose their own preference."),
]
