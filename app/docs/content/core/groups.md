---
title: Group Management
description: How to create, edit, and delete user groups.
group: Core
visibility: private
topics: [users, groups, administration]
order: 21
---
[TOC]

---
# Related Permissions
| Permission     | Description                                       |
|----------------|---------------------------------------------------|
| Create Groups  | Able to create groups via the dashboard           |
| Update Groups  | Able to modify group information and assign users |
| Delete Groups  | Able to delete groups                             |

# Instructions
To view and modify users, click on the "Group Management" tab in the system settings menu (you must have one of the above permissions to see this option).

## Creating Group
1. From the group management page, click the "New Group" button.
2. Enter the title of the group.
3. Click the "Create Group" button.

## Editing Group
1. From the group management page, click the "Edit Group" button beside the group you'd like to edit.
2. Click the "Save" button.

From this page you can edit the title of the group. 

## Deleting Users
1. From the user management page, click the "Edit User" button beside the user you'd like to delete.
2. From this page, click on the "Delete User" button and continue through the dialog.

This will delete the user, preventing them from interacting with the system.
This action can only be undone through the database via the `deleted` column.

## Impersonating Users
1. From the user management page, click the "Edit User" button beside the user you'd like to impersonate.
2. From this page, click on the "Impersonate User" button and continue through the dialog.

_Note: You must have the "Update Users" permission to view the "Edit User" page/button._

Impersonating a user will sign you in as that user for the duration of the session. In this state, you will be able to
interact with the application as if you were that user, without having to request their credentials.  
Upon starting the session, the user will receive a notification that you are impersonating them, and you will have a banner at the top of the screen indicating that you are impersonating them.  
To end the session, click the "End Session" button in the banner at the top of the screen. This will sign you out of their account, and back into yours.