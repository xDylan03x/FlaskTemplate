---
title: Getting Started
description: Getting started with the application.
group: Core
visibility: public
order: -1
---

# Welcome
Welcome to {{ app_name }}{% if current_user.is_authenticated %}, {{ current_user.name }}{% endif %}!
Below, you can find some information to help you get started.  
{% set admin_email = get_system_setting('application.admin_email') %}
{% if current_user.is_authenticated and admin_email %}If you have any questions, please reach out to [{{ admin_email }}](mailto:{{ admin_email }}).{% endif %}

## Next Steps
{% if get_system_setting('authentication.allow_account_creation') %}1. If you need an account, visit the [account creation page]({{ url_for("core.create_account") }}).{% else %}1. If you need an account, please contact an administrator.{% endif %}
2. Once you've set up your account from the welcome email, you can edit your profile as needed on the [profile settings page]({{ url_for("core.profile_settings") }}).
3. Learn how to manage your notifications, preferences, and other settings on the [user settings documentation page]({{ doc_link_article("core/user-settings") }}).
4. Explore other documentation using the [documentation page]({{ url_for("docs.articles") }}).
