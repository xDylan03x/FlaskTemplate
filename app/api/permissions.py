from ..extensions.flask_permissions import PermissionSpec


permissions = [
    PermissionSpec(action='Read', group='API Keys', description='Inspect the calling API key', scope='api'),
    PermissionSpec(action='Read', group='Application Settings', description='Read application branding settings', scope='api'),
    PermissionSpec(action='Read', group='User Preferences', description='Read user appearance and notification preferences', scope='api'),
    PermissionSpec(action='Update', group='User Preferences', description='Update user appearance and notification preferences', scope='api'),
    PermissionSpec(action='Read', group='User Permissions', description='Inspect effective user permissions', scope='api'),
    PermissionSpec(action='Read', group='Users', description='List and look up users', scope='api'),
    PermissionSpec(action='Create', group='Users', description='Provision unverified user accounts with optional welcome emails', scope='api'),
    PermissionSpec(action='Update', group='Users', description='Update user names and phone numbers', scope='api'),
    PermissionSpec(action='Enable', group='Users', description='Enable non-deleted accounts', scope='api'),
    PermissionSpec(action='Disable', group='Users', description='Disable accounts and invalidate their access', scope='api'),
    PermissionSpec(action='Delete', group='Users', description='Soft-delete accounts and invalidate their access', scope='api'),
    PermissionSpec(action='Recover', group='Users', description='Recover deleted accounts as disabled', scope='api'),
    PermissionSpec(action='Read', group='Groups', description='List and inspect group metadata', scope='api'),
    PermissionSpec(action='Create', group='Groups', description='Create groups without permission grants', scope='api'),
    PermissionSpec(action='Update', group='Groups', description='Update group names and descriptions', scope='api'),
    PermissionSpec(action='Delete', group='Groups', description='Delete groups and their inherited permission definitions', scope='api'),
    PermissionSpec(action='Read Members', group='Groups', description='List group member IDs', scope='api'),
    PermissionSpec(action='Add Members', group='Groups', description='Add users to groups, including their inherited permissions', scope='api'),
    PermissionSpec(action='Remove Members', group='Groups', description='Remove users from groups and their inherited permissions', scope='api'),
    PermissionSpec(action='Send', group='Notifications', description='Send notifications using the target user\'s delivery preferences', scope='api'),
    PermissionSpec(action='Send Mass', group='Notifications', description='Send mass notifications to user groups over selected channels', scope='api'),
]
