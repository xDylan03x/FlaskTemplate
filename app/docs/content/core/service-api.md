---
title: Service API
description: Use shared API keys to work with users, groups, preferences, and notifications.
group: Core
visibility: private
topics: [api, permissions, users, groups, notifications]
order: 23
---
[TOC]

# Authentication and permissions

All routes below start with `/api/v1` and require `Authorization: Bearer <key>`.
Browser sessions do not authenticate these routes. Grant the required **API**
permissions when creating or editing the key; matching user permissions are separate.
Existing keys do not gain these permissions automatically, including keys previously
created with Full Control. Use `flask --app app tools permissions list --scope api`
to inspect the catalog.

Missing, invalid, expired, and revoked credentials return JSON `401`. A valid key
without the required grant returns JSON `403`. Invalid JSON, unknown fields, or
invalid values return `400`; missing records return `404`; duplicate contacts and
conflicting changes return `409`. Unexpected service errors return generic JSON `500`.
Service responses use `Cache-Control: no-store`. Request outcomes and successful
mutations appear in the API key audit log without request content or credentials.

# Routes and grants

User and group IDs are numeric database IDs, returned by the corresponding lookup
and creation routes. User UUIDs are session credentials that rotate on security
changes, so they are excluded from API responses.

| Method | Route | Required API permission |
| --- | --- | --- |
| GET | `/key` | `api_keys.read` |
| GET | `/settings/application` | `application_settings.read` |
| GET | `/users` | `users.read` |
| GET | `/users/<user_id>` | `users.read` |
| POST | `/users` | `users.create` |
| PATCH | `/users/<user_id>` | `users.update` |
| POST | `/users/<user_id>/enable` | `users.enable` |
| POST | `/users/<user_id>/disable` | `users.disable` |
| DELETE | `/users/<user_id>` | `users.delete` |
| POST | `/users/<user_id>/recover` | `users.recover` |
| GET | `/users/<user_id>/preferences` | `user_preferences.read` |
| PATCH | `/users/<user_id>/preferences` | `user_preferences.update` |
| GET | `/users/<user_id>/permissions` | `user_permissions.read` |
| GET | `/groups` | `groups.read` |
| GET | `/groups/<group_id>` | `groups.read` |
| POST | `/groups` | `groups.create` |
| PATCH | `/groups/<group_id>` | `groups.update` |
| DELETE | `/groups/<group_id>` | `groups.delete` |
| GET | `/groups/<group_id>/members` | `groups.read_members` |
| PUT | `/groups/<group_id>/members/<user_id>` | `groups.add_members` |
| DELETE | `/groups/<group_id>/members/<user_id>` | `groups.remove_members` |
| POST | `/users/<user_id>/notifications` | `notifications.send` |
| POST | `/notifications/mass` | `notifications.send_mass` |

Directory and membership lists accept `?page=1` (positive integers) and return
ten items per page with `total` and `has_more`. Collections are named `users`,
`groups`, and `members`. The users directory also accepts an exact `?email=...`
lookup, normalized the same way as account creation. Deleted accounts are excluded
from user lookups. Member lists contain IDs only; reading profiles requires `users.read`.

# Key and application information

`GET /key` returns a `key` object containing the calling key's UUID, name, last
four characters, status, creation/expiration/last-used timestamps, and registered
grants. It never returns the credential or its hashes. It does not inspect other keys.

`GET /settings/application` returns a `settings` object with only
`application.name`, `application.abbreviation`, and `application.default_theme`.
Contact details and authentication settings are excluded.

# User provisioning and updates

`POST /users` accepts JSON `name`, `email`, optional `phone_number`, and optional
`send_welcome_email` (a JSON boolean, default `true`). It returns `201` with a
`user` object. Accounts start pending and unverified, with the existing default
settings and user permissions. The existing welcome email lets the recipient
verify their address and finish setup. Setting `send_welcome_email` to `false`
creates the record without an invitation or login token.

`PATCH /users/<user_id>` accepts `name` and `phone_number`, following the existing
profile page. The login email is read-only after creation; changing it requires
an email-change verification flow that the application does not currently provide. Include a
country calling code for phone numbers; `null` or an empty string clears one.
Phone changes clear phone verification and invalidate browser
sessions, trusted-device credentials, and outstanding login tokens. The new contact
can be verified through the existing account settings phone verification flow. Name-only
changes preserve sessions. Passwords, verification flags, permission definitions,
groups, and authentication policies are not writable through these routes.

Enable and disable have distinct grants. Disabling also invalidates access.
Delete performs the existing soft deletion; recovery restores a disabled account.
Deleted records are available only to delete/recover actions. Reviving a user does
not restore their old sessions or login tokens. API keys remain independent of their creator.

Read and create responses include profile/contact details, status, verification
flags, and creation/update timestamps. Updates and lifecycle actions return
`{"status": "success", "user_id": 1}`; deletion returns `204`. Write grants alone
do not allow reading existing profiles.

# Preferences and effective permissions

Preference reads return `user_id` and a `preferences` object containing registered
user settings in the Preferences and Notifications groups, with defaults for missing
records. Security and system settings are excluded. Preference updates accept a
flat JSON object of those keys, for example:

```json
{"preferences.theme": "dark", "notifications.security_alerts_via_email": false}
```

Booleans must be JSON booleans; themes must match the application's theme choices.
The entire payload is validated before saving. Updates return `{"status": "success"}`.

Effective permission reads return `user_id` and a `permissions` object mapping
registered user permission names to boolean results from the existing permission
checks, including live group inheritance. API permission grants are excluded.

# Groups and membership

Create groups with `title` and optional `description`. Update either field with
PATCH. Creation returns `201` and a `group` object; reads return group metadata
without members or permission definitions. Updates return
`{"status": "success", "group_id": 1}`; deletion returns `204`.

New groups have no members or permission grants. Membership PUT/DELETE operations
are idempotent and return `204`; removed users can be added again unless deleted.
Deleted users can still be removed. Adding/removing membership changes the user's
effective permissions and authentication policies through existing group inheritance.
Grant membership and group deletion permissions only to integrations trusted to make
those changes. These routes do not edit a group's permission definitions.

# Notifications

Send JSON with `title`, `body`, `category`, and optional `link`. Category must be a
registered `NotificationCategory` value: `notifications.security_alerts` or `notifications.user_sent`.
Titles are limited to 512 characters and bodies to 10,000 characters. Links may be
root-relative paths or HTTP(S) URLs; external links use the existing redirect flow.

Notifications use the existing manager and the recipient's delivery preferences
for web, email, and text. The sender identifies the API key; callers cannot override
the sender, recipient, or delivery channels. Success returns `201` with
`{"status": "success"}`. This records the manager completing its work rather than
confirming provider delivery. A provider error may occur after another channel
has already been processed; retries can create duplicate notifications.

## Mass Notifications

Send `POST /api/v1/notifications/mass` with the **Notifications - Send Mass** API permission:

```json
{
  "title": "Office update",
  "body": "Please review the latest announcement.",
  "link": "https://example.com/announcements",
  "channel": "email",
  "group_ids": [1, 2]
}
```

`link` is optional. Choose `web` for Web or `email` for Email and Web. The selected
channel applies directly without recipient preference settings. `group_ids` must
be a non-empty list of existing group IDs; invalid groups reject the entire request
before delivery. Deleted users are excluded, and overlapping memberships receive
one notification per channel. Groups with no eligible users return `400`.

The category is always `notifications.user_sent`. Since service keys do not have
a current user, the sender identifies the API key, matching single-user API notifications.
The response is `201` with `{"status": "success", "recipient_count": 2}`. The existing
`notifications.send` permission does not grant mass notification access. Delivery uses
the same manager as the web form; retrying can create duplicate notifications.

Existing browser upload, file, and notification routes retain their authentication
and response formats.
