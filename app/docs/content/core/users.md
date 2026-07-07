---
title: User Management
description: How to create, edit, and delete users.
group: Core
visibility: private
topics: [users, administration]
---
[TOC]

---
# Related Permissions
| Permission   | Description                                                               |
|--------------|---------------------------------------------------------------------------|
| Create Users | Able to create uses via the dashboard                                     |
| Update Users | Able to modify user information, their permissions, and lockdown the user |
| Delete Users | Able to delete users                                                      |

# Instructions
To view and modify users, click on the "User Management" tab in the system settings menu (you must have one of the above permissions to see this option).

## Creating Users
1. From the user management page, click the "New User" button.
2. Enter the name and email address of the user.
3. Click the "Create User" button.

_Note: An email address is required to create a user. Make sure the email address is correct and that the user has access to it._

Once you create the user, a welcome email will be sent to the email address you provided.
To activate their account, the user must follow the link in their email. This will allow them to set their password.

## Editing Users
1. From the user management page, click the "Edit User" button beside the user you'd like to edit.
2. Click the "Save" button.

From this page you can edit the name, status, password, and permissions of the user. If you don't want to edit the user's
password, just leave the password field blank.  
Setting a user's status to pending has no real effect, but setting it to disabled will not allow them to log in.

To lock down a user's account, click on the "Lockdown Account" button and continue through the dialog.
This will set the status of the user to disabled and disable all the user's permissions.

## Deleting Users
1. From the user management page, click the "Edit User" button beside the user you'd like to delete. 
2. From this page, click on the "Delete User" button and continue through the dialog.

This will delete the user, preventing them from interacting with the system.
This action can only be undone through the database via the `deleted` column.