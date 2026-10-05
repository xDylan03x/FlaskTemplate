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
| Permission                 | Description                                      |
|----------------------------|--------------------------------------------------|
| Groups - Create            | Create groups                                    |
| Groups - Update            | Modify group details and membership              |
| Groups - Delete            | Delete groups                                    |
| Users - Update Permissions | Change permission definitions on users or groups |

# Instructions
Open **Group Management** from the system settings menu to view groups, their member counts, and their permission counts.

## Creating Groups
1. Click **New Group**.
2. Enter a title and optional description.
3. If you have **Users - Update Permissions**, choose permission definitions in the **Permissions** section.
4. Click **Create Group**.

## Editing Groups
1. Click **Edit group** beside the group.
2. Update its title, description, or selected members.
3. If you have **Users - Update Permissions**, update permission definitions.
4. Click **Save**.

Group managers without **Users - Update Permissions** can still manage membership and group details. Permission controls are locked, and submitted changes to those definitions are ignored.

## Permission Inheritance
Each registered permission supports three group definitions:

- **Not defined**: This group does not define the permission. If no other group defines it, the user's individual value applies.
- **Allow**: Members receive the permission, overriding their individual value.
- **Deny**: Members do not receive the permission, overriding their individual value unless another group allows it.

When groups disagree, **Allow wins**. For example, if one group denies **Create Users** and another allows it, a member of both groups can create users. Saving memberships or definitions that produce conflicting permissions shows a warning explaining this rule.

On the individual user editor, inherited permissions show the effective value, are locked, and list all source groups with their Allow or Deny definitions. Conflicts are identified beside the permission. The user's individual value remains stored underneath and applies again when no membership group defines the permission.

Broad permission checks also use inherited definitions. For example, access to the user management area requires at least one effective permission in the Users category.

## Deleting Groups
1. Click **Edit group** beside the group.
2. Click **Delete Group** and confirm.

Deleting a group removes its memberships and permission definitions. Users keep their individual permissions and definitions inherited from other groups. Group deletion cannot be undone.
