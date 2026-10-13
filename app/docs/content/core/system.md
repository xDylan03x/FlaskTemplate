---
title: System Settings
description: How to view and edit system settings.
group: Core
visibility: private
topics: [system, administration]
order: 22
---
[TOC]

---
# Related Permissions
| Permission      | Description                                   |
|-----------------|-----------------------------------------------|
| System - Admin  | Able to view the admin dashboard (if enabled) |
| System - Update | Able to edit system settings                  |

# Instructions
To view and modify system settings, click on the "System" tab in the system settings menu (you must have the "System - Update" permission to see this option).

## Editing Settings
1. From the system settings page, review the info alert and edit the settings you want to change.
2. Click the "Save" button.

Any changes made to the system settings will take effect immediately.

## Viewing the Admin Panel
1. From the system settings page, click the "Admin Panel" button next to the page title. This button appears only when the `ADMIN_PANEL` configuration option is enabled and you have the "System - Admin" permission.

If you have the "System - Admin" permission but not the "System - Update" permission, you will not see the "System" tab in the system settings menu. Instead, access the admin panel [here]({{ url_for('core.admin') }}).
From here you can view system platform info, GIT repository info, application configuration info, and all of the registered routes, blueprints, and extensions.
You can also query the database directly from this page (read-only commands).  
If you'd like to connect to the database from another tool, you can use the `SQLALCHEMY_DATABASE_URI` config option for reference.  

_Note: If the `ADMIN_PANEL` configuration option is disabled, the button is hidden and the admin panel cannot be accessed._
