import enum
import hashlib
from typing import Optional
from flask_login import UserMixin
import sqlalchemy as sa
import sqlalchemy.orm as so
from datetime import datetime, timezone, timedelta
import uuid
from .extensions.searchable import SearchableMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import login, db, pm, sm
import secrets


user_group_members = sa.Table(
    'user_group_members',
    db.metadata,
    sa.Column('user_id', sa.Integer, sa.ForeignKey('user.id'), primary_key=True),
    sa.Column('group_id', sa.Integer, sa.ForeignKey('user_group.id'), primary_key=True),
)


class SystemSetting(db.Model):
    """
    Model representing a site setting as a key-value pair.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        key: Setting key
        value: Setting value
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    key: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    value: so.Mapped[str] = so.mapped_column(sa.String(2048), nullable=False)

    def __repr__(self):
        return '<SystemSetting {}: {}>'.format(self.key, self.value)


class User(db.Model, UserMixin):
    """
    User model representing a user in the system.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        name: Full name
        email
        profile_picture_url: URL to profile picture
        password_hash
        status: active, disabled, pending
        phone_number: Phone number in E.164 format
        email_verified
        phone_number_verified
        deleted: Soft delete flag
        deleted_at

        groups: Many-to-many relationship with UserGroup model
        settings: One-to-many relationship with UserSetting model
        permissions: One-to-many relationship with UserPermission model
        notifications: One-to-many relationship with Notification model
        login_tokens: One-to-many relationship with LoginToken model
        login_records: One-to-many relationship with LoginRecord model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    name: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True, unique=True)
    profile_picture_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(2048))
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    status: so.Mapped[str] = so.mapped_column(sa.String(32), nullable=False, default='active')

    phone_number: so.Mapped[Optional[str]] = so.mapped_column(sa.String(15), unique=True)

    email_verified: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    phone_number_verified: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    totp_verified: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False)
    totp_entity: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    totp_factor: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    deleted: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    deleted_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime)

    groups: so.Mapped[list["UserGroup"]] = db.relationship("UserGroup", secondary=user_group_members, back_populates="users")
    settings: so.Mapped[list["UserSetting"]] = so.relationship('UserSetting', backref='user', lazy='dynamic')
    permissions: so.Mapped[list["UserPermission"]] = so.relationship('UserPermission', backref='user', lazy='dynamic')
    notifications: so.Mapped[list["UserNotification"]] = so.relationship('UserNotification', backref='user', lazy='dynamic')
    login_tokens: so.Mapped[list["LoginToken"]] = so.relationship('LoginToken', backref='user', lazy='dynamic')
    devices: so.Mapped[list["UserDevice"]] = so.relationship('UserDevice', backref='user', lazy='dynamic')
    login_records: so.Mapped[list["LoginRecord"]] = so.relationship('LoginRecord', backref='user', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.email)

    def get_id(self) -> str:
        return self.uuid36

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash or password is None:
            return False
        return check_password_hash(self.password_hash, password)

    def refresh_uuid36(self) -> None:
        self.uuid36 = str(uuid.uuid4())
        if self.id is not None:
            db.session.execute(sa.update(UserDevice).where(UserDevice.user_id == self.id).values(
                device_trusted=False, secret_hash=None, credential_expires_at=None,
            ).execution_options(synchronize_session=False))

    def refresh_totp_entity(self) -> None:
        self.totp_entity = str(uuid.uuid4())

    def can_login(self) -> bool:
        if self.deleted or not self.email_verified:
            return False
        return self.status in ('active', 'pending')

    def get_setting(self, key: str) -> str | bool:
        setting_record = self.settings.filter_by(key=key).first()
        if setting_record is None:
            return False
        else:
            if setting_record.value in ["true", "True"]:
                return True
            elif setting_record.value in ["false", "False"]:
                return False
            else:
                return setting_record.value

    def set_setting(self, setting: str, value: str | bool) -> None:
        setting_record = self.settings.filter_by(key=setting).first()
        if setting_record is None:
            if setting not in [setting_spec.setting for setting_spec in sm.all()]:
                raise ValueError(f"Invalid permission: {setting}")
            setting_record = UserSetting(key=setting, value=str(value), user_id=self.id)
            db.session.add(setting_record)
        else:
            setting_record.value = str(value)

    def set_permission(self, permission: str, value: bool) -> None:
        permission_record = self.permissions.filter_by(key=permission).first()
        if permission_record is None:
            if permission not in [perm_spec.permission for perm_spec in pm.all()]:
                raise ValueError(f"Invalid permission: {permission}")
            permission_record = UserPermission(key=permission, value=value, user_id=self.id)
            db.session.add(permission_record)
        else:
            permission_record.value = value

    def inherited_permissions(self) -> dict:
        inherited = {}
        for group in self.groups:
            for definition in group.permissions:
                sources = inherited.setdefault(definition.key, {'allow_groups': [], 'deny_groups': []})
                sources['allow_groups' if definition.value else 'deny_groups'].append(group)
        for sources in inherited.values():
            sources['value'] = bool(sources['allow_groups'])
            sources['conflict'] = bool(sources['allow_groups'] and sources['deny_groups'])
        return inherited

    def can(self, permission: str) -> bool:
        permission = permission.lower()
        inherited = self.inherited_permissions()
        if "." in permission:
            if pm.get(permission) is None:
                return False
            if permission in inherited:
                return inherited[permission]['value']
            perm_record = self.permissions.filter_by(key=permission).first()
            return bool(perm_record and perm_record.value)
        # Broad checks use the effective value of each matching permission.
        values = {record.key: record.value for record in self.permissions.all()}
        values.update({key: sources['value'] for key, sources in inherited.items()})
        return any(value for key, value in values.items() if key.startswith(permission + ".") and pm.get(key) is not None)


class UserGroup(db.Model):
    """
    Model representing a group of users.
    Attributes:
        id
        uuid36
        created_at
        updated_at

        title
        description: Optional description of the group

        users: Many-to-many relationship with User model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    title: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    description: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))

    users: so.Mapped[list["User"]] = db.relationship("User", secondary=user_group_members, back_populates="groups")
    permissions: so.Mapped[list["UserGroupPermission"]] = so.relationship('UserGroupPermission', back_populates='group', cascade='all, delete-orphan')

    def set_permission(self, permission: str, value: bool | None) -> None:
        permission = permission.lower()
        if pm.get(permission) is None:
            raise ValueError(f"Invalid permission: {permission}")
        permission_record = next((record for record in self.permissions if record.key == permission), None)
        if value is None:
            if permission_record is not None:
                self.permissions.remove(permission_record)
        elif permission_record is None:
            self.permissions.append(UserGroupPermission(key=permission, value=value))
        else:
            permission_record.value = value

    def __repr__(self):
        return '<UserGroup {}>'.format(self.title)


class LoginToken(db.Model):
    """
    Model representing a login token for user authentication.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        hashed_token: SHA-1 hashed token string
        expiration: Expiration datetime of the token
        immediate_login: Whether the token allows immediate login
        next_url: URL to redirect to after login
        remember_login
        reset_password: Whether the token is for password reset
        for_impersonation: Whether the token is for account impersonation
        verify_phone_number: Whether the token is for phone number verification
        create_account: Whether the token is used for account creation
        two_factor_verified: Whether 2FA was completed for this token
        magic_link_channel: Delivery channel for an issued magic link
        used: Whether the token has been used
        auth_source: Source of authentication (traditional username/password, magic link, social, etc.)

        user_id: Foreign key to the User model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    hashed_token: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False, unique=True, index=True)
    expiration: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc) + timedelta(minutes=5))
    immediate_login: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    next_url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(2048))
    remember_login: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    reset_password: so.Mapped[Optional[bool]] = so.mapped_column(sa.Boolean, default=False)
    for_impersonation: so.Mapped[Optional[bool]] = so.mapped_column(sa.Boolean, default=False)
    verify_phone_number: so.Mapped[Optional[bool]] = so.mapped_column(sa.Boolean, default=False)
    create_account: so.Mapped[Optional[bool]] = so.mapped_column(sa.Boolean, default=False)
    two_factor_verified: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    magic_link_channel: so.Mapped[Optional[str]] = so.mapped_column(sa.String(16))
    used: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    used_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime)
    auth_source: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))

    user_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<LoginToken {}>'.format(self.hashed_token)

    def set_secure_token(self) -> str:
        """
        Generate a secure random token.
        Returns:
            str: A secure random token.
        """
        token = secrets.token_urlsafe(32)
        self.hashed_token = hashlib.sha1(token.encode('utf-8')).hexdigest()
        return token

    def is_valid(self, raw_token: str) -> bool:
        """
        Check if the token is still valid based on expiration time, and token content.

        :returns bool: True if valid, False otherwise.
        """
        if self.used:
            return False
        if datetime.now(tz=timezone.utc) > self.expiration:
            return False
        hashed_token = hashlib.sha1(raw_token.encode('utf-8')).hexdigest()
        if hashed_token != self.hashed_token:
            return False
        return True


class UserDevice(db.Model):
    """
    Model representing a user's device for login tracking.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        user_agent: User agent string of the client
        last_authenticated: Last time the device was authenticated
        device_trusted: Whether the user trusts this browser
        secret_hash: SHA-256 hash of the browser credential's random secret
        credential_expires_at: Server-side expiration of the browser credential

        logins: One-to-many relationship with LoginRecord model
        user_id: Foreign key to the User model
    """

    CREDENTIAL_LIFETIME = timedelta(days=30)

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    user_agent: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    last_authenticated: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    device_trusted: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    secret_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64))
    credential_expires_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))

    logins: so.Mapped[list["LoginRecord"]] = so.relationship('LoginRecord', backref='user_device', lazy='dynamic')
    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<UserDevice {}>'.format(self.id)

    def set_secret(self) -> str:
        secret = secrets.token_urlsafe(32)
        self.secret_hash = hashlib.sha256(secret.encode()).hexdigest()
        self.credential_expires_at = datetime.now(timezone.utc) + self.CREDENTIAL_LIFETIME
        return secret

    @property
    def has_active_credential(self) -> bool:
        if not self.secret_hash or self.credential_expires_at is None:
            return False
        expiration = self.credential_expires_at
        if expiration.tzinfo is None:
            expiration = expiration.replace(tzinfo=timezone.utc)
        return expiration > datetime.now(timezone.utc)


class UserSetting(db.Model):
    """
    Model representing a user setting as a key-value pair.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        key: Setting key
        value: Setting value

        user_id: Foreign key to the User model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    key: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    value: so.Mapped[str] = so.mapped_column(sa.String(2048), nullable=False)

    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<UserSetting {}: {}>'.format(self.key, self.value)


class UserPermission(db.Model):
    """
    Model representing a user permission as a key-value pair.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        key: Setting key
        value: Setting value

        user_id: Foreign key to the User model
    """
    __table_args__ = (sa.UniqueConstraint('user_id', 'key', name='uq_user_permission_user_key'),)

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    key: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    value: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)

    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<UserPermission {}: {}>'.format(self.key, self.value)


class UserGroupPermission(db.Model):
    """A group permission definition; an absent record means not defined."""
    __table_args__ = (sa.UniqueConstraint('group_id', 'key', name='uq_user_group_permission_group_key'),)

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    key: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    value: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False)
    group_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user_group.id'), nullable=False)
    group: so.Mapped["UserGroup"] = so.relationship('UserGroup', back_populates='permissions')

    def __repr__(self):
        return '<UserGroupPermission {}: {}>'.format(self.key, self.value)


class NotificationCategory(enum.Enum):
    USER_SENT = "notifications.user_sent"

    # Account
    PERIODIC_PASSWORD_RESET = "notifications.security_alerts"
    PASSWORD_RESET = "notifications.security_alerts"
    PASSWORD_CHANGE = "notifications.security_alerts"
    PHONE_NUMBER_CHANGE = "notifications.security_alerts"
    NEW_DEVICE_LOGIN = "notifications.security_alerts"
    ACCOUNT_LOCKDOWN = "notifications.security_alerts"
    ACCOUNT_IMPERSONATION = "notifications.security_alerts"


class UserNotification(SearchableMixin, db.Model):
    """
    Model representing a notification sent to the user
    A notification record can only be sent through the channel as specified. To send a notification through
    multiple channels, create multiple records.
    Attributes:
        id
        uuid36
        created_at
        updated_at
        title: Notification title
        body: Notification body/content
        link: Optional link associated with the notification
        sender: User or system that sent the notification
        category: Notification category/type
        read: Whether the notification has been read
        channel: Channel through which the notification was intended (email, text, etc.)
        external_id: Identifier used to track the notification (like Twilio SIDs)
        status: For tracking the status of the notification (sent, failed, etc.)
        sent_timestamp: Timestamp of the notification

        user_id: Foreign key to the User model
    """
    __searchable__ = {
        "title": "A",
        "body": "B",
        "sender": "C",
    }

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    title: so.Mapped[str] = so.mapped_column(sa.String(512), nullable=False)
    body: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)
    link: so.Mapped[Optional[str]] = so.mapped_column(sa.String(2048))
    sender: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    category: so.Mapped[Optional[str]] = so.mapped_column(sa.String(128))
    read: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    channel: so.Mapped[str] = so.mapped_column(sa.String(32), nullable=False)
    external_id: so.Mapped[Optional[str]] = so.mapped_column(sa.String(512))
    status: so.Mapped[Optional[str]] = so.mapped_column(sa.String(32))
    sent_timestamp: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))

    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<Notification {}: {}>'.format(self.uuid36, self.title)


class LoginRecord(db.Model):
    """
    Model representing a login record for auditing purposes.
    Attributes:
        id
        uuid36
        occurred_at
        user_id: Foreign key to the User model
        ip_address: IP address of the login attempt
        login_token_id: Foreign key to the LoginToken model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    occurred_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    user_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))
    ip_address: so.Mapped[Optional[str]] = so.mapped_column(sa.String(45))
    login_token_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('login_token.id'))
    login_token: so.Mapped["LoginToken"] = so.relationship("LoginToken")
    user_device_id: so.Mapped[Optional[int]] = so.mapped_column(sa.Integer, sa.ForeignKey('user_device.id'))

    def __repr__(self):
        return '<LoginRecord {}>'.format(self.uuid36)


class AuditEvent(db.Model):
    """
    Model representing an event for auditing purposes.
    Attributes:
        id
        uuid36
        occurred_at
        message: Event message with the details
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    occurred_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))

    message: so.Mapped[str] = so.mapped_column(sa.Text, nullable=False)

    def __repr__(self):
        return '<AuditEvent {}>'.format(self.uuid36)


class File(db.Model):
    """
    Model representing a file uploaded to the application
    Attributes:
        id
        uuid36
        created_at
        updated_at

        original_filename: Original filename of the uploaded file
        object_key: Unique key for the file in storage (e.g., S3)
        content_type: MIME type of the file
        size: Size of the file in bytes
        context: Use of the file (form attachment, profile picture, etc.)
        public: whether a user must be logged in to view the file
        attached: whether the upload has been accepted for use by an application record

        uploader_id: Foreign key to the User model
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(tz=timezone.utc), onupdate=lambda: datetime.now(tz=timezone.utc))

    original_filename: so.Mapped[str] = so.mapped_column(sa.String(512), nullable=False)
    object_key: so.Mapped[str] = so.mapped_column(sa.String(2048), unique=True, nullable=False)
    content_type: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    size: so.Mapped[int] = so.mapped_column(sa.Integer, nullable=False)
    context: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    public: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)
    attached: so.Mapped[bool] = so.mapped_column(sa.Boolean, default=False, nullable=False)

    uploader_id: so.Mapped[int] = so.mapped_column(sa.Integer, sa.ForeignKey('user.id'))

    def __repr__(self):
        return '<File {}>'.format(self.uuid36)


class APIKey(db.Model):
    """
    Shared credential for external applications, independent of its creator's account.
    Stores only current/previous hashes and the current key's last four characters.
    Permissions are explicit API-scope grants; expiration and revocation apply to both hashes.
    """
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    name: so.Mapped[str] = so.mapped_column(sa.String(256), nullable=False)
    expires_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))
    last_used_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))
    revoked_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))
    hashed_key: so.Mapped[str] = so.mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    last_four: so.Mapped[str] = so.mapped_column(sa.String(4), nullable=False)
    previous_hashed_key: so.Mapped[Optional[str]] = so.mapped_column(sa.String(64), unique=True, index=True)
    rotated_at: so.Mapped[Optional[datetime]] = so.mapped_column(sa.DateTime(timezone=True))

    creator_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey('user.id'))

    creator: so.Mapped[Optional["User"]] = so.relationship('User')
    permissions: so.Mapped[list["APIKeyPermission"]] = so.relationship('APIKeyPermission', back_populates='api_key', cascade='all, delete-orphan')

    @staticmethod
    def utc(value: datetime | None) -> datetime | None:
        # SQLite returns naive datetimes even for timezone-aware columns.
        return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

    @property
    def status(self) -> str:
        if self.revoked_at is not None:
            return 'revoked'
        if self.expires_at is not None and self.utc(self.expires_at) <= datetime.now(timezone.utc):
            return 'expired'
        return 'valid'

    @property
    def masked_key(self) -> str:
        return '••••' + self.last_four

    @property
    def previous_valid_until(self) -> datetime | None:
        if self.rotated_at is None:
            return None
        deadline = self.utc(self.rotated_at) + timedelta(days=7)
        return min(deadline, self.utc(self.expires_at)) if self.expires_at else deadline

    def can(self, permission: str) -> bool:
        permission = permission.lower()
        if self.status != 'valid':
            return False
        return any(record.value and pm.get(record.key, scope='api') is not None
                   and (record.key == permission if '.' in permission else record.key.startswith(permission + '.'))
                   for record in self.permissions)

    def __repr__(self):
        return '<APIKey {}>'.format(self.uuid36)


class APIKeyPermission(db.Model):
    """An explicit API permission definition; absent definitions deny access."""
    __table_args__ = (sa.UniqueConstraint('api_key_id', 'key', name='uq_api_key_permission_key'),)

    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    uuid36: so.Mapped[str] = so.mapped_column(sa.String(36), unique=True, index=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    key: so.Mapped[str] = so.mapped_column(sa.String(128), nullable=False)
    value: so.Mapped[bool] = so.mapped_column(sa.Boolean, nullable=False, default=True)

    api_key_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey('api_key.id'), nullable=False)
    api_key: so.Mapped["APIKey"] = so.relationship('APIKey', back_populates='permissions')

    def __repr__(self):
        return '<APIKeyPermission {}: {}>'.format(self.key, self.value)


@login.user_loader
def load_user(uuid36):
    try:
        return db.session.scalar(sa.select(User).where(User.uuid36 == uuid36))
    except Exception:
        return None
