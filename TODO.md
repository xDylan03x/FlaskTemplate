# TODO
## Planned Features
A list of planned features to be implemented. See more information for each feature below.
- [x] Permissions and Authorizations
- [ ] Audit Logging
- [ ] File System
- [ ] Notifications

---

### Permissions and Authorizations
CRUD operations make up most of the operations in this kind of app. As such, it's important to have an easy way of defining
and managing permissions for developers and users. Currently, the appliaction supports basic `role.user_manager` style permissions.
To make the system more modular, this will be replaced to support more granular `users.create` style permissions. 
This will allow for more flexibility in defining permissions and roles, as well as making it easier to manage permissions for different users and groups.
On top of this, adding a permission matrix interface will allow users to easily manage permissions for others.
To make it easier for developers to define permissions, an interface will be created so that for each module in the system,
developers can define each permission they need and what the default values are for new users.

**Summary Features:**
- Make it easier to get permissions with more granularity.
- Add support for jinja `{% if current_user.can(users.create) %}` style syntax.
- Add support for route permission decorators.
- Add a developer interface for easily defining permissions.

### Audit Logging
- Add support for detailed audit logging of user actions and system events.
- Add support for developer functions to audit events automatically.

### File System
- Add support for cloud-based file storage and delivery.

### Notifications
- Add support for sending notifications to users in the app