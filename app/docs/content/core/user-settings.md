---
title: User Settings
description: How to view and manage your settings.
group: Core
visibility: private
topics: [user, settings]
order: 10
---
[TOC]

---
# Instructions
To view and modify your settings, click on the "Settings" button in the profile menu (click on your profile picture).

## Profile Settings
1. Once on the user settings page, click on the "Profile" tab.
2. Modify your profile information.
3. Click on the "Save" button.

From this page you can edit your name, profile picture, and phone number.  
You can click the "Remove Image" button to remove your profile picture and use a default one.
You can also click the "Upload Image" button to upload a new profile picture. This will open up a dialog window allowing
you to upload or take an image from your device.  
You can see the status of your phone number beside the field lable (either "Verified" or "Not Verified").
You can not use text or call as a two-factor authentication method until you have verified your phone number.
Once you enter or edit your phone number and hit save, you will receive a text message with a link to verify it.
You can also click the "verify" button beside this field to send another text message.

_Note: You can not edit your email address once your account has been created._

## Application Settings
1. Once on the user settings page, click on the "Application" tab.
2. Modify your application settings.
3. Click on the "Save" button.

From this page you can edit your visual theme. This just changes how the application looks for you.

## Notifications Settings
1. Once on the user settings page, click on the "Notifications" tab.
2. Modify your notification settings.
3. Click on the "Save" button.

From this page you can change how you receive notifications. All notifications are sent to the web portal
(learn more about that [here]({{ doc_link_article("core/user-notifications") }})), but some can be sent to you
via email and/or text message as well.

## Security Settings
1. Once on the user settings page, click on the "Security" tab.
2. Modify your security settings.
3. Click on the "Save" button.

From this page you can change your two-factor authentication preference, password breach alert preference, and perform other actions.  
Enabling two-factor authentication requires a verification code from your email, phone call,
text message, or TOTP app (depending on what you have enabled) when you log in via password.
The **Unknown Device Requires Two-Factor Authentication** preference independently
requires 2FA on untrusted devices for password, magic-link, and OAuth logins.
**Two-Factor Authentication Applies to Alternative Login Methods** extends your main
2FA setting to magic-link and OAuth logins. It appears when your main 2FA setting is
enabled or the alternative-login policy requires it. Its saved value is retained when
hidden. Both new preferences default to off.

Your authentication policies may require 2FA for every password login, extend the same
rule to magic-link and OAuth logins, or require 2FA on any untrusted device regardless
of login method. Enabled policies check and lock their matching security settings, including Password
Breach Checking. Disabled policies leave personal choice available. Your saved preferences
apply again when the policy requirements are removed.

For magic-link logins, the channel delivering the link cannot also verify 2FA: Email is
excluded for email links, and both Text and Call are excluded for text links. If no eligible
second factor is available, that delivery option is unavailable. Use another login method
or contact an administrator. Eligibility is checked again when the link is used.

If password breach checking is enabled, you will receive an alert if your password has been found in a data breach when logging in with a password.
This does not prevent you from logging in and will only appear when logging in with a password.

_Note: All users are recommended to enable two-factor authentication._

### Changing Your Password
1. From the user settings page, click on the "Change Password" button.
2. Enter your current password, new password, and confirm your new password.
3. Click on the "Change Password" button.

### Viewing Login History
1. From the user settings page, click on the "Login History" button.

This page will display a list of all the times someone has logged in to the system with your account.  
Login attempts with a checkmark are from a trusted device, and those with an exclamation mark are from an untrusted device.
You can click on the IP button to view more information about the IP address (such as likely location), view the source
of the login attempt, and view the device that was used to make the login attempt.  
By clicking on the device button, you can view more information about the device (such as browser, device, and a list of logins).
You can also manage the device's trust status by clicking the "Trust This Device" field and clicking the "Save" button.  
When logging in from an untrusted device, you can also select **Trust This Device** while submitting your two-factor authentication code. The device is trusted only after the code is verified. Leaving it unchecked keeps the device untrusted. Trusting a device does not disable two-factor authentication if you have enabled it in your security settings.

Each login has an authorization source which describes how the login was attepmted. These include:

- traditional login: login with email and password
- traditional login needing 2fa: login with email and password that requires a second factor of authentication
- oauth authorization state: login with an external authentication provider
- magic link: login with a magic link sent to email or phone
- impersonation session: another user logged in as you via the impersonation feature
- restoring from impersonation session: you were logged back in to your account after impersonating another user
- welcome email: login from the welcome email link

### TOTP Authentication
TOTP authentication is a two-factor authentication method that uses a time-based one-time password (TOTP) generated by an application on your device.
This is a more secure method of authentication than a password, and is recommended to be used in place of email, phone call, or text message authentication.

**Enabling TOTP**

1. From the user settings page, click on the "Enable TOPT" button.
2. If prompted, click "Start Setup", then scan the QR code with your TOTP app and click "Next".
3. Enter the code from your TOTP app and click the "Submit" button

**Disabling TOTP**

1. From the user settings page, click on the "Disable TOPT" button and follow the dialog.

### Lockdown Your Account
1. From the user settings page, click on the "Lockdown Account" button and follow the dialog.

This will disable your account, preventing you from logging in, and disable your permissions.
An administrator can re-enable your account at any time.