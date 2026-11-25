import hashlib
import re
import secrets
import uuid
import sqlalchemy as sa
from sqlalchemy import orm as so
from flask import url_for, request, current_app
from flask_sqlalchemy.pagination import Pagination
from app.core.helper import send_email, send_sms, format_notification_sms
from app.models import User, LoginToken, LoginRecord, UserNotification, NotificationCategory, UserDevice, File, \
    SystemSetting, UserPermission, UserSetting, UserGroup, APIKey, APIKeyPermission
from app import audit, db, pm, sm
from datetime import date, datetime, time, timedelta, timezone


class SystemManager:
    @staticmethod
    def get_all_settings() -> list[SystemSetting]:
        return db.session.scalars(sa.select(SystemSetting).order_by(SystemSetting.key)).all()

    @staticmethod
    def get_setting_by_uuid36(uuid36: str) -> SystemSetting | None:
        return db.session.scalar(sa.select(SystemSetting).where(SystemSetting.uuid36 == uuid36))

    @staticmethod
    def get_setting(key: str) -> str | bool | None:
        spec = sm.get(key, scope="system")
        key = spec.database_key if spec is not None else key
        setting_record = db.session.scalar(sa.select(SystemSetting).where(SystemSetting.key == key))
        if setting_record:
            if spec is not None and isinstance(spec.default, str):
                return setting_record.value
            if setting_record.value in ["true", "True"]:
                return True
            elif setting_record.value in ["false", "False"]:
                return False
            return setting_record.value
        else:
            return spec.default if spec is not None else None

    @staticmethod
    def set_setting(key: str, value: str | bool) -> None:
        spec = sm.get(key, scope="system")
        key = spec.database_key if spec is not None else key
        setting_record = db.session.scalar(sa.select(SystemSetting).where(SystemSetting.key == key))
        if setting_record:
            setting_record.value = str(value)
        else:
            setting_record = SystemSetting(key=key, value=str(value))
            db.session.add(setting_record)
        db.session.commit()


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
            profile_picture_url = f'https://api.dicebear.com/10.x/initials/svg?size=50&initialsVariant=alt:1&lettersVariant=double:1&seed={user.name}'
        user.profile_picture_url = profile_picture_url
        db.session.add(user)
        db.session.commit()
        # Default settings
        for setting in sm.all(include_hidden=True):
            user.set_setting(setting.setting, setting.default)
        # Default permissions
        for perm in pm.all(include_hidden=True):
            user.set_permission(perm.permission, perm.default)
        db.session.commit()
        if send_welcome_email:
            _, raw_token = LoginTokenManager.create_login_token(expiration_minutes=86400, user_id=user.id, next_url=url_for('core.setup_account'), immediate_login=True, create_account=True, auth_source='welcome email')
            welcome_url = url_for('auth.login_with_token', raw_token=raw_token, _external=True)
            send_email(
                f'Your {sm.system_setting("application.name")} Account Has Been Created',
                f'Welcome to {sm.system_setting("application.name")}!\nTo set up your account, please vising the link below:\n{welcome_url}',
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
    def get_all_users(include_deleted: bool = False, page: int = 1, paginate: bool = True) -> Pagination:
        base_statement = sa.select(User).order_by(User.name)

        if not paginate:
            if not include_deleted:
                base_statement = base_statement.where(User.deleted == False)
            return db.session.scalars(base_statement).all()

        if not include_deleted:
            base_statement = base_statement.where(User.deleted == False)
        users = db.paginate(base_statement, page=page, per_page=10, error_out=False)
        return users

    @staticmethod
    def delete_user(user: User) -> None:
        user.refresh_uuid36()
        user.status = 'deleted'
        user.deleted = True
        user.deleted_at = datetime.now(tz=timezone.utc)
        db.session.commit()

    @staticmethod
    def get_logins(user_id: int, page: int = 1) -> Pagination:
        base_statement = sa.select(LoginRecord).where(LoginRecord.user_id == user_id).options(so.selectinload(LoginRecord.user_device), so.selectinload(LoginRecord.login_token)).order_by(LoginRecord.occurred_at.desc())
        logins = db.paginate(base_statement, page=page, per_page=15, error_out=False)
        return logins

    @staticmethod
    def update_permissions(user: User) -> None:
        """
        Generates missing user permissions from the default.
        :param user:
        """
        for permission in pm.all(include_hidden=True):
            user_permission_record = db.session.scalar(sa.select(UserPermission).where(UserPermission.user_id == user.id, UserPermission.key == permission.permission))
            if user_permission_record is None:
                user_permission_record = UserPermission(key=permission.permission, value=permission.default, user_id=user.id)
                db.session.add(user_permission_record)
            db.session.commit()

    @staticmethod
    def update_settings(user: User) -> None:
        """
        Generates missing user settings from the default.
        :param user:
        """
        for setting in sm.all(include_hidden=True):
            user_setting_record = db.session.scalar(sa.select(UserSetting).where(UserSetting.user_id == user.id, UserSetting.key == setting.setting))
            if user_setting_record is None:
                user_setting_record = UserSetting(key=setting.setting, value=str(setting.default), user_id=user.id)
                db.session.add(user_setting_record)
            db.session.commit()

    @staticmethod
    def lockdown_user(user: User) -> None:
        """
        Secures a user's account
        :param user:
        :return:
        """
        user.refresh_uuid36()
        user.status = 'disabled'
        LoginTokenManager.invalidate_user_tokens(user.id)
        user.phone_number_verified = False
        for perm in pm.all(include_hidden=True):
            if not perm.is_authentication_policy:
                user.set_permission(perm.permission, False)
        db.session.commit()
        NotificationManager.send_notification(user, "Account Locked", "Your account has been locked down for security purposes. Please contact an admin to regain access.", NotificationCategory.ACCOUNT_LOCKDOWN)

    @staticmethod
    def get_user_group_by_uuid36(uuid36: str) -> UserGroup | None:
        group = db.session.scalar(sa.select(UserGroup).where(UserGroup.uuid36 == uuid36))
        return group

    @staticmethod
    def get_all_user_groups(page: int = 1, paginate: bool = True) -> Pagination:
        base_statement = sa.select(UserGroup).order_by(UserGroup.title)

        if not paginate:
            return db.session.scalars(base_statement).all()

        groups = db.paginate(base_statement, page=page, per_page=10, error_out=False)
        return groups

    @staticmethod
    def delete_user_group(group: UserGroup) -> None:
        db.session.delete(group)
        db.session.commit()

    @staticmethod
    def create_user_group(title: str, description: str = None) -> UserGroup:
        group = UserGroup(title=title, description=description)
        db.session.add(group)
        db.session.commit()
        return group


class LoginTokenManager:
    @staticmethod
    def create_login_token(expiration_minutes: int = 5,
                           immediate_login: bool = False,
                           next_url: str = "/",
                           remember_login: bool = False,
                           reset_password: bool = False,
                           create_account: bool = False,
                           auth_source: str = None,
                           for_impersonation: bool = False,
                           user_id: int = None) -> (LoginToken, str):
        """
        Generate and store a new login token.

        :param expiration_minutes: How long until the token expires
        :param immediate_login: Whether the token allows immediate login or requires some other step before
        :param next_url: Where the user is directed once logged in
        :param remember_login: Whether the login session should be persistent
        :param reset_password: Whether this token is for password reset
        :param create_account: Whether this token is for account creation
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
            auth_source=auth_source,
            for_impersonation=for_impersonation,
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
            user_id=existing_token.user_id,
            auth_source=existing_token.auth_source
        )
        token.magic_link_channel = existing_token.magic_link_channel
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
    def claim_login_token(login_token: LoginToken) -> bool:
        """Claim a valid token once - the caller needs to commit the transactions"""
        now = datetime.now(timezone.utc)
        result = db.session.execute(sa.update(LoginToken).where(
            LoginToken.id == login_token.id,
            LoginToken.used.is_(False),
            LoginToken.expiration > now,
        ).values(used=True, used_at=now).execution_options(synchronize_session=False))
        return result.rowcount == 1

    @staticmethod
    def invalidate_user_tokens(user_id: int) -> None:
        """Revoke outstanding tokens in the caller's credential-change transaction."""
        db.session.execute(sa.update(LoginToken).where(
            LoginToken.user_id == user_id, LoginToken.used.is_(False),
        ).values(used=True, used_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False))

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
    def create_login_record(user_id: int, ip_address: str, user_agent: str, login_token: LoginToken, device_record: UserDevice = None) -> LoginRecord:
        login_record = LoginRecord(
            user_id=user_id,
            ip_address=ip_address,
            login_token_id=login_token.id
        )
        db.session.add(login_record)
        if device_record and device_record.user_id == user_id:
            device_record.logins.append(login_record)
            device_record.last_authenticated = datetime.now(tz=timezone.utc)
        db.session.commit()
        return login_record


class UserDeviceManager:
    @staticmethod
    def secure_cookie() -> bool:
        return request.is_secure or current_app.config.get('FLASK_ENV', 'development') != 'development'

    @staticmethod
    def cookie_name(user_id: int) -> str:
        prefix = '__Host-' if UserDeviceManager.secure_cookie() else ''
        return f'{prefix}device_{user_id}'

    @staticmethod
    def create_user_device(user_id: int, user_agent: str) -> UserDevice:
        """
        Creates a device for the user for login tracking.

        Returns the device record. Browser credential issuance is handled by authentication.
        """
        device = UserDevice(
            user_agent=user_agent[:256],
            user_id=user_id
        )
        db.session.add(device)
        db.session.commit()
        return device

    @staticmethod
    def find_device(user_id: int) -> UserDevice | None:
        cookie = request.cookies.get(UserDeviceManager.cookie_name(user_id), '')
        if len(cookie) != 80 or cookie.count('.') != 1:
            return None
        identifier, secret = cookie.split('.', 1)
        try:
            parsed = uuid.UUID(identifier)
        except ValueError:
            return None
        if parsed.version != 4 or str(parsed) != identifier:
            return None
        device = db.session.scalar(sa.select(UserDevice).where(
            UserDevice.user_id == user_id, UserDevice.uuid36 == identifier,
            UserDevice.credential_expires_at > datetime.now(timezone.utc),
        ))
        if not device or not device.secret_hash:
            return None
        digest = hashlib.sha256(secret.encode()).hexdigest()
        return device if secrets.compare_digest(device.secret_hash, digest) else None

    @staticmethod
    def get_device_by_uuid36(uuid36: str) -> UserDevice | None:
        device = db.session.scalar(sa.select(UserDevice).where(UserDevice.uuid36 == uuid36))
        return device


class NotificationManager:
    @staticmethod
    def send_mass_notification(group_ids: list[int], title: str, body: str, channel: str, link: str|None = None, sender: str|User = "System") -> int:
        if channel not in ('web', 'email'):
            raise ValueError('Invalid mass notification channel.')
        users = db.session.scalars(sa.select(User).where(
            User.deleted == False,
            User.groups.any(UserGroup.id.in_(group_ids)),
        )).all()
        channels = ['web', 'email'] if channel == 'email' else ['web']
        for user in users:
            NotificationManager.send_notification(user, title, body, NotificationCategory.USER_SENT,
                                                  link=link, sender=sender, channels=channels)
        return len(users)

    @staticmethod
    def send_notification(user: User, title: str, body: str, category: NotificationCategory, link: str|None = None, sender: str|User = "System", channels: list[str]|None = None) -> None:
        # Determine sender information
        sender_title = sender
        author_name = None if sender == "System" else sender
        author_email = None
        if isinstance(sender, User):
            sender_title = sender.email
            author_name = sender.name
            author_email = sender.email
        # Use explicit channels when supplied; otherwise use the user's settings.
        channels_to_send = channels
        if channels_to_send is None:
            channels_to_send = ['web']
            if user.get_setting(f"{category.value}_via_email"):
                channels_to_send.append('email')
            if user.get_setting(f"{category.value}_via_text"):
                channels_to_send.append('text')
        # Add notification records to database
        notifications_to_send = []
        for channel in channels_to_send:
            notification_record = UserNotification(title=title, body=body, link=link, sender=sender_title, category=category.value, channel=channel, status="pending", user_id=user.id)
            notifications_to_send.append(notification_record)
            db.session.add(notification_record)
        db.session.commit()
        # Send each notification over their channel
        for notification in notifications_to_send:
            if notification.channel == 'email' and user.email:
                notification.status = "sending"
                db.session.commit()
                notification.external_id = send_email(notification.title, notification.body, user.email,
                                                       link=notification.link, author_name=author_name,
                                                       author_email=author_email, reply_to=author_email)
                if notification.external_id:
                    notification.sent_timestamp = datetime.now(tz=timezone.utc)
                    notification.status = "sent"
            elif notification.channel == 'text' and user.phone_number:
                notification.status = "sending"
                db.session.commit()
                message_body = format_notification_sms(notification.title, notification.body, notification.link)
                notification.external_id = send_sms(message_body, user.phone_number)
                if notification.external_id:
                    notification.sent_timestamp = datetime.now(tz=timezone.utc)
                    notification.status = "sent"
            db.session.commit()

    @staticmethod
    def get_web_notifications(user: User, page: int = 1, limit: int = 15, recent_only: bool = False, include_read: bool = False, query=None) -> Pagination:
        base_statement = sa.select(UserNotification).where(UserNotification.user_id == user.id, UserNotification.channel == "web")
        if recent_only:
            base_statement = base_statement.where(UserNotification.created_at > (datetime.now(tz=timezone.utc) - timedelta(days=5)))
        if not include_read:
            base_statement = base_statement.where(UserNotification.read != True)
        base_statement = base_statement.order_by(UserNotification.created_at.desc(), UserNotification.id.desc())
        if query:
            statement = UserNotification.search(query, base_query=base_statement)
            notifications = db.paginate(
                statement,
                page=page,
                per_page=limit,
                error_out=False
            )
        else:
            notifications = db.paginate(base_statement, page=page, per_page=limit, error_out=False)
        return notifications

    @staticmethod
    def mark_notification_as_read(uuid36: str) -> UserNotification | None:
        notification = db.session.scalar(sa.select(UserNotification).where(UserNotification.uuid36 == uuid36))
        if notification:
            notification.read = True
            db.session.commit()
        return notification


class FileManager:
    @staticmethod
    def get_file_by_uuid36(uuid36: str, uploader_id: int = None, attached: bool = None,
                           context: str = None, public: bool = None) -> File | None:
        statement = sa.select(File).where(File.uuid36 == uuid36)
        if uploader_id is not None:
            statement = statement.where(File.uploader_id == uploader_id)
        if attached is not None:
            statement = statement.where(File.attached == attached)
        if context is not None:
            statement = statement.where(File.context == context)
        if public is not None:
            statement = statement.where(File.public == public)
        file = db.session.scalar(statement)
        return file


class APIKeyManager:
    @staticmethod
    def get_api_key_by_id(id: int) -> APIKey | None:
        return db.session.get(APIKey, id)

    @staticmethod
    def get_api_key_by_uuid36(uuid36: str) -> APIKey | None:
        return db.session.scalar(sa.select(APIKey).where(APIKey.uuid36 == uuid36))

    @staticmethod
    def get_all_api_keys(page: int = 1, paginate: bool = True) -> Pagination | list[APIKey]:
        base_statement = sa.select(APIKey).order_by(APIKey.created_at.desc(), APIKey.id.desc())
        if not paginate:
            return db.session.scalars(base_statement).all()
        return db.paginate(base_statement, page=page, per_page=25, error_out=False)

    @staticmethod
    def _generate_credential() -> tuple[str, str]:
        abbreviation = re.sub(r'[^a-z0-9]', '', str(sm.system_setting('application.abbreviation')).lower()) or 'app'
        raw_key = f'{abbreviation}_{secrets.token_urlsafe(32)}'
        return raw_key, hashlib.sha256(raw_key.encode()).hexdigest()

    @staticmethod
    def expiration(value: date | None) -> datetime | None:
        """Convert an inclusive UTC date to an exclusive cutoff."""
        if value is None:
            return None
        try:
            return datetime.combine(value + timedelta(days=1), time.min, tzinfo=timezone.utc)
        except OverflowError as error:
            raise ValueError('Expiration date is too far in the future.') from error

    @staticmethod
    def permission_keys(preset: str = 'custom', permissions: list[str] | tuple[str, ...] = ()) -> list[str]:
        if preset not in ('custom', 'full-control'):
            raise ValueError('Invalid permission preset.')
        if preset == 'full-control':
            if permissions:
                raise ValueError('Custom permissions require the Custom preset.')
            return [spec.permission for spec in pm.all(scope='api', include_hidden=True)]
        keys = sorted({key.lower() for key in permissions})
        if any(pm.get(key, scope='api') is None for key in keys):
            raise ValueError('Unknown API permission.')
        return keys

    @staticmethod
    def create(name: str, expires: date | None = None, preset: str = 'custom',
               permissions: list[str] | tuple[str, ...] = (), creator: User | None = None,
               actor: object = 'CLI') -> tuple[APIKey, str]:
        """Create a shared credential and return its full value once."""
        name = APIKeyManager._validate_metadata(name, expires)
        keys = APIKeyManager.permission_keys(preset, permissions)
        raw_key, digest = APIKeyManager._generate_credential()
        key = APIKey(name=name, expires_at=APIKeyManager.expiration(expires),
                     hashed_key=digest, last_four=raw_key[-4:], creator=creator)
        key.permissions = [APIKeyPermission(key=value, value=True) for value in keys]
        db.session.add(key)
        db.session.commit()
        audit.log('API key created', target=key, actor=actor, category='api_keys')
        return key, raw_key

    @staticmethod
    def _validate_metadata(name: str, expires: date | None) -> str:
        name = name.strip()
        if not name or len(name) > 256:
            raise ValueError('Name must contain between 1 and 256 characters.')
        if expires and APIKeyManager.expiration(expires) <= datetime.now(timezone.utc):
            raise ValueError('Expiration must be today or later (UTC).')
        return name

    @staticmethod
    def update(key: APIKey, name: str, expires: date | None = None, preset: str = 'custom',
               permissions: list[str] | tuple[str, ...] = (), actor: object = 'CLI') -> None:
        name = APIKeyManager._validate_metadata(name, None)
        cutoff = APIKeyManager.expiration(expires)
        if cutoff and cutoff <= datetime.now(timezone.utc) and cutoff != key.utc(key.expires_at):
            raise ValueError('Expiration must be today or later (UTC).')
        keys = APIKeyManager.permission_keys(preset, permissions)
        with audit.track(key, actor=actor, message='API key updated', category='api_keys'):
            key.name = name
            key.expires_at = cutoff
            # Reuse retained definitions to avoid inserting duplicate permission keys.
            existing = {record.key: record for record in key.permissions}
            key.permissions[:] = [existing[value] if value in existing else APIKeyPermission(key=value, value=True)
                                  for value in keys]
            for record in key.permissions:
                record.value = True
            db.session.commit()

    @staticmethod
    def rotate(key: APIKey, actor: object = 'CLI') -> str:
        """Replace the current credential while retaining one previous hash for seven days."""
        now = datetime.now(timezone.utc)
        if key.status != 'valid':
            raise ValueError('Only valid API keys can be rotated.')
        raw_key, digest = APIKeyManager._generate_credential()
        statement = sa.update(APIKey).where(
            APIKey.id == key.id, APIKey.hashed_key == key.hashed_key, APIKey.revoked_at.is_(None),
            sa.or_(APIKey.expires_at.is_(None), APIKey.expires_at > now),
        ).values(
            previous_hashed_key=key.hashed_key, hashed_key=digest, last_four=raw_key[-4:], rotated_at=now,
        ).execution_options(synchronize_session=False)
        result = db.session.execute(statement)
        if result.rowcount != 1:
            db.session.rollback()
            raise ValueError('The API key changed; reload it before rotating.')
        db.session.commit()
        db.session.refresh(key)
        audit.log('API key rotated', target=key, actor=actor, category='api_keys')
        return raw_key

    @staticmethod
    def revoke(key: APIKey, actor: object = 'CLI') -> None:
        statement = sa.update(APIKey).where(
            APIKey.id == key.id, APIKey.revoked_at.is_(None),
        ).values(revoked_at=datetime.now(timezone.utc)).execution_options(synchronize_session=False)
        result = db.session.execute(statement)
        db.session.commit()
        db.session.refresh(key)
        if result.rowcount:
            audit.log('API key revoked', target=key, actor=actor, category='api_keys')

    @staticmethod
    def authenticate(raw_key: str) -> tuple[APIKey | None, str]:
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        statement = sa.select(APIKey).where(
            sa.or_(APIKey.hashed_key == digest, APIKey.previous_hashed_key == digest),
        ).options(so.selectinload(APIKey.permissions)).execution_options(populate_existing=True)
        with db.session.no_autoflush:
            key = db.session.scalar(statement)
        if key is None:
            return None, 'unknown key'
        if key.status != 'valid':
            return key, key.status
        if digest == key.previous_hashed_key and (key.previous_valid_until is None or key.previous_valid_until <= datetime.now(timezone.utc)):
            return key, 'rotation window expired'
        return key, 'authenticated'

    @staticmethod
    def record_use(key: APIKey, raw_key: str) -> datetime | None:
        """Recheck the credential atomically before dispatch, without committing endpoint work."""
        now = datetime.now(timezone.utc)
        digest = hashlib.sha256(raw_key.encode()).hexdigest()
        statement = sa.update(APIKey).where(
            APIKey.id == key.id, APIKey.revoked_at.is_(None),
            sa.or_(APIKey.expires_at.is_(None), APIKey.expires_at > now),
            sa.or_(APIKey.hashed_key == digest, sa.and_(
                APIKey.previous_hashed_key == digest, APIKey.rotated_at > now - timedelta(days=7),
            )),
        ).values(last_used_at=sa.case(
            (sa.or_(APIKey.last_used_at.is_(None), APIKey.last_used_at < now), now),
            else_=APIKey.last_used_at,
        )).returning(APIKey.last_used_at)
        with db.engine.begin() as connection:
            used_at = connection.execute(statement).scalar_one_or_none()
        return key.utc(used_at)
