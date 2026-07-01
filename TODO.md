# TODO
## Planned Features
A list of planned features to be implemented. See more information for each feature below.
- [x] Permissions and Authorizations
- [x] Audit Logging
  - [ ] Need to enhance logging and make sure it works reliably.
- [x] File System
- [ ] Notifications

---
# Notifications
Notifications currently are implemented as such:
1. Program calls the UserManager.send_notification() method with information about the notification.
2. The program checks the user's setting to determine which method(s) they want to be notified with (email/sms)
3. The program calls the appropriate helper function to deliver the notification
The system does not track notification sent to the user at all.

To address these issues and make the system more robust, the following changes are planned:
- Provide functions that take in a single or multiple users through the NotificationManager class.
- Provide a cleaner way to expose notification categories (similar to the Permission/Settings extensions)
- Keep up with notifications sent to users, the methods used to send them, and the status of delivery.
- Provide a real-time notification system through the interface using SSE.