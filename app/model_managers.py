import hashlib
import sqlalchemy as sa
from flask import current_app, url_for
from app.core.helper import send_email, send_sms
from app.models import User, LoginToken, LoginRecord, UserNotification, NotificationCategory, UserDevice
from app import db, pm
from datetime import datetime, timedelta, timezone


class UserManager:
    @staticmethod
    def create_user(name: str,
                    email: str,
                    send_welcome_email: bool = False,
                    phone_number: str = None,
                    email_verified: bool = False,
                    phone_number_verified: bool = False,
                    status: str = 'active',
                    profile_picture_url: str = None) -> User:
        user = User(name=name, email=email.lower(), phone_number=phone_number,
                    email_verified=email_verified, phone_number_verified=phone_number_verified,
                    status=status)
        if not profile_picture_url:
            profile_picture_url = f'https://api.dicebear.com/9.x/initials/svg?seed={user.name}&radius=50&backgroundColor=00897b,039be5,3949ab,5e35b1,8e24aa,43a047,d81b60,f4511e,fb8c00,fdd835&backgroundType=gradientLinear&fontFamily=Arial&fontSize=41'
        user.profile_picture_url = profile_picture_url
        db.session.add(user)
        db.session.commit()
        # Default settings
        user.set_setting('security.two_factor_auth', False)
        user.set_setting('security.password_breach_check', True)
        user.set_setting('notifications.security_alerts_email', True)
        user.set_setting('notifications.security_alerts_text', False)
        # Default permissions
        for perm in pm.all():
            user.set_permission(perm.permission, perm.default)
        db.session.commit()
        if send_welcome_email:
            _, raw_token = LoginTokenManager.create_login_token(expiration_minutes=86400, user_id=user.id, next_url=url_for('core.setup_account'), immediate_login=True, create_account=True, auth_source='welcome email')
            welcome_url = url_for('auth.login_with_token', raw_token=raw_token, _external=True)
            send_email(
                f'Your {current_app.config["APP_NAME"]} Account Has Been Created',
                f'Welcome to {current_app.config["APP_NAME"]}!\nTo set up your account, please vising the link below:\n{welcome_url}',
                user.email,
                preheader='Follow the link within 60 days to setup your account.'
            )
        return user

    @staticmethod
    def get_user_by_id(id: int) -> User | None:
        user = db.session.get(User, id)
        return user

    @staticmethod
    def get_user_by_uuid36(uuid36: str) -> User | None:
        user = db.session.scalar(sa.select(User).where(User.uuid36 == uuid36))
        return user

    @staticmethod
    def get_user_by_email(email: str) -> User | None:
        user = db.session.scalar(sa.select(User).where(User.email == email.lower()))
        return user

    @staticmethod
    def get_all_users(include_deleted: bool = False) -> list[User]:
        if include_deleted:
            users = db.session.scalars(sa.select(User)).all()
        else:
            users = db.session.scalars(sa.select(User).where(User.deleted == False)).all()
        return users

    @staticmethod
    def delete_user(user: User) -> None:
        user.refresh_uuid36()
        user.status = 'deleted'
        user.deleted = True
        user.deleted_at = datetime.now(tz=timezone.utc)
        db.session.commit()

    @staticmethod
    def send_notification(title: str,
                          body: str,
                          user: User,
                          category: NotificationCategory,
                          link: str = None,
                          sender: str = "System") -> list[UserNotification]:
        notifications = []
        channels_to_send = []
        if user.get_setting(f"{category.value}_email"):
            channels_to_send.append('email')
        if user.get_setting(f"{category.value}_text"):
            channels_to_send.append('text')

        for channel in channels_to_send:
            notification = UserNotification(
                title=title,
                body=body,
                channel=channel,
                link=link,
                sender=sender,
                category=category.value if category else None,
                user_id=user.id
            )
            db.session.add(notification)
            db.session.commit()

            message_body = f'From: {notification.sender}\n\n{notification.title}\n{notification.body}'
            if link:
                message_body += f'\n\nView on Website: {link}'
            if notification.channel == 'email' and user.email:
                notification.external_id = send_email(notification.title, message_body, user.email)
            elif notification.channel == 'text' and user.phone_number:
                notification.external_id = send_sms(message_body, user.phone_number)

            if notification.external_id:
                notification.sent_timestamp = datetime.now(tz=timezone.utc)
                notification.read = True

            db.session.commit()
            notifications.append(notification)

        return notifications


class LoginTokenManager:
    @staticmethod
    def create_login_token(expiration_minutes: int = 5,
                           immediate_login: bool = False,
                           next_url: str = "/",
                           remember_login: bool = False,
                           reset_password: bool = False,
                           create_account: bool = False,
                           risk_score: int = 40,
                           auth_source: str = None,
                           user_id: int = None) -> (LoginToken, str):
        """
        Generate and store a new login token.

        :param expiration_minutes: How long until the token expires
        :param immediate_login: Whether the token allows immediate login or requires some other step before
        :param next_url: Where the user is directed once logged in
        :param remember_login: Whether the login session should be persistent
        :param reset_password: Whether this token is for password reset
        :param create_account: Whether this token is for account creation
        :param risk_score: How risky the login attempt is, lower is less risky
        :param auth_source: Source of authentication
        :param user_id
        :returns LoginToken, str: The login token record and raw token string
        """
        if next_url is None:
            next_url = "/"
        token = LoginToken(
            expiration=datetime.now(tz=timezone.utc) + timedelta(minutes=expiration_minutes),
            immediate_login=immediate_login,
            next_url=next_url,
            remember_login=remember_login,
            reset_password=reset_password,
            create_account=create_account,
            risk_score=risk_score,
            auth_source=auth_source,
            user_id=user_id
        )
        raw_token = token.set_secure_token()
        db.session.add(token)
        db.session.commit()
        return token, raw_token

    @staticmethod
    def create_login_token_from_existing(existing_token: LoginToken, expiration_minutes: int = 5) -> (LoginToken, str):
        token, raw_token = LoginTokenManager.create_login_token(
            expiration_minutes=expiration_minutes,
            immediate_login=existing_token.immediate_login,
            next_url=existing_token.next_url,
            remember_login=existing_token.remember_login,
            reset_password=existing_token.reset_password,
            risk_score=existing_token.risk_score,
            user_id=existing_token.user_id,
            auth_source=existing_token.auth_source
        )
        token.risk_assessment = existing_token.risk_assessment
        db.session.commit()
        return token, raw_token

    @staticmethod
    def get_login_token(raw_token: str) -> LoginToken | None:
        hashed_token = hashlib.sha1(raw_token.encode('utf-8')).hexdigest()
        token = db.session.scalar(sa.select(LoginToken).where(LoginToken.hashed_token == hashed_token))
        return token

    @staticmethod
    def invalidate_login_token(login_token: LoginToken):
        """
        Mark a login token as used/invalid.

        :param login_token: The LoginToken object to invalidate
        """
        login_token.used = True
        login_token.used_at = datetime.now(tz=timezone.utc)
        db.session.commit()

    @staticmethod
    def invalidate_create_account_token(user_id: int):
        """
        Mark the account creation token as used/invalid.
        """
        token = db.session.scalar(sa.select(LoginToken).where(LoginToken.user_id == user_id, LoginToken.create_account == True))
        if token:
            LoginTokenManager.invalidate_login_token(token)

    @staticmethod
    def cleanup_login_tokens():
        """
        Remove expired or used tokens from the database.
        """
        now = datetime.now(tz=timezone.utc)
        db.session.execute(sa.delete(LoginToken).where(sa.or_(LoginToken.used == True, LoginToken.expiration < now)))
        db.session.commit()


class LoginRecordManager:
    @staticmethod
    def create_login_record(user_id: int, ip_address: str, user_agent: str, login_token: LoginToken) -> LoginRecord:
        login_record = LoginRecord(
            user_id=user_id,
            ip_address=ip_address,
            login_token_id=login_token.id
        )
        db.session.add(login_record)
        device_record = UserDeviceManager.find_device(user_id, user_agent)
        if device_record:
            device_record.logins.append(login_record)
            device_record.last_login = datetime.now(tz=timezone.utc)
        db.session.commit()
        return login_record


class UserDeviceManager:
    @staticmethod
    def create_user_device(user_id: int, user_agent: str) -> UserDevice:
        """
        Creates a device for the user for login tracking.

        Returns:
            device: The created device record
            device_identifier: The device identifier for the device to be stored in a cookie
        """
        device = UserDevice(
            user_agent=user_agent,
            user_id=user_id
        )
        db.session.add(device)
        db.session.commit()
        return device

    @staticmethod
    def find_device(user_id: int, user_agent: str) -> UserDevice | None:
        device = db.session.scalar(sa.select(UserDevice).where(UserDevice.user_id == user_id, UserDevice.user_agent == user_agent))
        return device

    @staticmethod
    def get_device_by_uuid36(uuid36: str) -> UserDevice | None:
        device = db.session.scalar(sa.select(UserDevice).where(UserDevice.uuid36 == uuid36))
        return device
