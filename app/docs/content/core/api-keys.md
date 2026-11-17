---
title: API Keys
description: Create and manage shared credentials for external applications.
group: Core
visibility: private
topics: [api, security, permissions, administration]
order: 22
---
[TOC]

# Managing keys

Open **API Keys** from System Settings. Access requires **API Keys – Manage**
(`api_keys.manage`), which also grants access to the API key audit explorer.
The explorer works even when the diagnostic admin panel is disabled.

Create a key with a name and optional expiration date.
Expiration includes the selected day in UTC. Keys belong to the service;
the creator is recorded for reference, and disabling that account does not
invalidate its keys. Keys created through the CLI identify the creator as CLI.

Copy the full key when it is created. Afterwards only its last four characters
are displayed. If the credential is lost, rotate the key.

# Permissions

Keys start with no permissions selected. Choose individual API permissions or
use **Full Control** to select them all. Click it again to clear all permissions;
you can adjust individual checkboxes at any time. Grants are saved explicitly, so new permissions do not apply to
existing keys automatically. If no API permissions are registered, keys receive
no grants. User permissions and group membership do not apply to API keys.

# Rotation, expiration, and revocation

**Rotate Key** generates a new credential and shows it once. The immediately
previous credential remains usable for seven days, unless expiration or revocation
ends access sooner. Both versions share the current permission selection.
Rotating again immediately replaces the previous credential.

The list shows each key's status, creator, creation time, and last-used time.
The detail page also shows expiration, revocation, and rotation information.
Valid authentication updates last-used time even if permissions later deny the
request. Expired keys can be renewed by editing their expiration date, then rotated.

**Revoke Key** permanently disables the current and previous credential. Revoked
records remain available for audit history. Create a new key to restore access.

# Audit log

Select **Audit Log** to browse management events and service request outcomes.
Filter by actor and event type; expand an event for details. Requests record
the method, route template, response status, source IP, authentication result,
and key identity when known. Secrets and request content are excluded.
