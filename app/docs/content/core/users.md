---
title: User Management
description: How to create, edit, and delete users.
group: Core
visibility: private
topics: [users, administration]
order: 20
---
[TOC]

---
# Related Permissions
| Permission                 | Description                                                               |
|----------------------------|---------------------------------------------------------------------------|
| Users - Create             | Able to create uses via the dashboard                                     |
| Users - Update             | Able to modify user information, their permissions, and lockdown the user |
| Users - Delete             | Able to delete users                                                      |
| Users - Update Permissions | Able to impersonate other users for troubleshooting                       |
| Users - Impersonate        | Able to impersonate other users for troubleshooting                       |

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

## Updating User Permissions
1. From the user management page, click the "Edit User" button beside the user you'd like to edit.
2. From this page, check or uncheck the permissions you want to grant or revoke from the user.
3. Click the "Save" button.

_Note: You must have the "Update Permissions" permission to see or change the permission options._

## Impersonating Users
1. From the user management page, click the "Edit User" button beside the user you'd like to impersonate.
2. From this page, click on the "Impersonate User" button and continue through the dialog.

_Note: You must have the "Update Users" permission to view the "Edit User" page/button._

Impersonating a user will sign you in as that user for the duration of the session. In this state, you will be able to
interact with the application as if you were that user, without having to request their credentials.  
Upon starting the session, the user will receive a notification that you are impersonating them, and you will have a banner at the top of the screen indicating that you are impersonating them.  
To end the session, click the "End Session" button in the banner at the top of the screen. This will sign you out of their account, and back into yours.

## User Groups
To learn about managing user groups and assign users to them, [click here]({{ doc_link_article("core/group-management") }}).