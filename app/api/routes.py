from flask import request, jsonify, current_app, abort, redirect, g
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
import phonenumbers
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..core.helper import get_s3_client, route_url, datetime_iso, normalize_phone_number
from app import db, audit, pm, sm
from app.api import apiv1
from app.models import File, User, UserGroup, NotificationCategory, user_group_members
from ..model_managers import NotificationManager, FileManager, UserManager, LoginTokenManager, SystemManager
from ..core.forms import THEME_CHOICES
from ..extensions.flask_permissions import require_permission
from .helper import token_required, current_api_key


@apiv1.route("/files/<string:uuid36>", methods=["GET"])
def get_file_url(uuid36: str):
    file = FileManager.get_file_by_uuid36(uuid36)

    if file is None:
        abort(404)

    if not file.public and not current_user.is_authenticated:
        abort(401)

    # Add ownership/authorization checks here when necessary.
    # Example:
    # if not file.public and file.uploader_id != current_user.id:
    #     abort(403)

    s3 = get_s3_client()

    presigned_url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={
            "Bucket": current_app.config["S3_BUCKET_NAME"],
            "Key": file.object_key,
            "ResponseContentType": file.content_type,
            "ResponseContentDisposition": (
                f'inline; filename="{file.original_filename}"'
            ),
        },
        ExpiresIn=3600
    )

    response = redirect(presigned_url, code=302)
    response.headers["Cache-Control"] = "private, max-age=240"
    return response


@apiv1.route('/uploads/presign', methods=['POST'])
@login_required
def presign_upload():
    data = request.get_json() or {}

    original_filename = data.get("filename")
    content_type = data.get("content_type")
    size_bytes = int(data.get("size_bytes", 0))
    context = data.get("context", "general")

    # Make sure file has a name
    if not original_filename:
        return jsonify({"error": "Missing filename"}), 400
    # Make sure file has an allowable content type
    if content_type not in current_app.config['ALLOWED_CONTENT_TYPES']:
        return jsonify({"error": "File type not allowed"}), 400
    # Make sure the file is not too big
    if size_bytes <= 0 or size_bytes > current_app.config['MAX_UPLOAD_SIZE']:
        return jsonify({"error": "File size not allowed"}), 400
    # Save the file's original filename as a safe name
    safe_name = secure_filename(original_filename)
    ext = safe_name.rsplit(".", 1)[-1].lower() if "." in safe_name else "bin"

    # Save the file record to the database
    uploaded_file = File(
        original_filename=original_filename,
        content_type=content_type,
        object_key="",
        size=size_bytes,
        context=context,
        uploader_id=current_user.id,
    )
    db.session.add(uploaded_file)
    db.session.commit()

    # Create the file's key
    object_key = f"uploads/{context}/{uploaded_file.uuid36}.{ext}"
    uploaded_file.object_key = object_key
    db.session.commit()

    # Generate a presigned URL to upload the file
    s3 = get_s3_client()
    presigned_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": current_app.config["S3_BUCKET_NAME"],
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=300,
    )
    audit.log("User requested file upload", target=uploaded_file, actor=current_user)

    return jsonify({
        'file_id': uploaded_file.uuid36,
        'object_key': object_key,
        'upload_url': presigned_url,
        'content_type': content_type,
    })


@apiv1.route('/notifications', methods=['GET'])
@apiv1.route('/notifications/<string:uuid36>', methods=['PATCH'])
@login_required
def notifications(uuid36: str = None):
    if request.method == 'GET':
        include_read_str = request.args.get("include_read", default="false", type=str)
        include_read = include_read_str.lower() in ['true', '1', 't', 'y', 'yes']
        recent_only_str = request.args.get("recent_only", default="false", type=str)
        recent_only = recent_only_str.lower() in ['true', '1', 't', 'y', 'yes']
        page = request.args.get('page', 1, type=int)

        # Fetch notifications from manager
        notification_page = NotificationManager.get_web_notifications(
            current_user,
            page=page,
            recent_only=recent_only,
            include_read=include_read
        )

        # Serialize the notification objects into a list of dictionaries
        notifications_data = []
        for n in notification_page.items:
            notifications_data.append({
                "id": n.uuid36,
                "title": n.title,
                "body": n.body,
                "sender": n.sender,
                "link": route_url(n.link) if n.link else None,
                "timestamp": datetime_iso(n.created_at),
            })

        return jsonify(notifications=notifications_data, has_more=notification_page.has_next,
                       total=notification_page.total), 200

    # If marking the notification as read
    elif request.method == 'PATCH':
        if not uuid36:
            return jsonify({"error": "Notification ID is required"}), 400
        notification = NotificationManager.mark_notification_as_read(uuid36)
        if notification is not None:
            audit.log("User marked notification as read", target=notification, actor=current_user)
        return jsonify({"status": "success", "message": "Notification marked as read"}), 200

    return jsonify({"error": "Method not allowed"}), 405


# Service-key routes use explicit user/group IDs; a service key is not a browser user.
APPLICATION_SETTING_KEYS = ('application.name', 'application.abbreviation', 'application.default_theme')
USER_PREFERENCE_GROUPS = ('Preferences', 'Notifications')


def _api_error(status, message):
    response = jsonify(error=message)
    response.status_code = status
    abort(response)


def _api_json(allowed, required=()):
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        _api_error(400, 'A non-empty JSON object is required.')
    if data.keys() - set(allowed):
        _api_error(400, 'Unknown or unsupported fields.')
    if not set(required).issubset(data):
        _api_error(400, 'Missing required fields.')
    return data


def _api_text(value, field, maximum, allow_empty=False, multiline=False):
    if not isinstance(value, str):
        _api_error(400, f'{field} must be a string.')
    value = value.strip()
    if (not value and not allow_empty) or len(value) > maximum:
        _api_error(400, f'{field} must contain {0 if allow_empty else 1} to {maximum} characters.')
    allowed_controls = '\n\r\t' if multiline else ''
    if any((ord(character) < 32 or ord(character) == 127) and character not in allowed_controls for character in value):
        _api_error(400, f'{field} contains invalid control characters.')
    return value


def _api_page():
    page = request.args.get('page', '1')
    if not page.isascii() or not page.isdigit() or len(page) > 9 or int(page) < 1:
        _api_error(400, 'page must be a positive integer.')
    return int(page)


def _api_user(user_id, include_deleted=False):
    if user_id > 2**63 - 1:
        _api_error(404, 'User not found.')
    user = UserManager.get_user_by_id(user_id)
    if user is None or (user.deleted and not include_deleted):
        _api_error(404, 'User not found.')
    return user


def _api_group(group_id):
    if group_id > 2**63 - 1:
        _api_error(404, 'Group not found.')
    group = db.session.get(UserGroup, group_id)
    if group is None:
        _api_error(404, 'Group not found.')
    return group


def _api_user_data(user):
    return dict(id=user.id, name=user.name, email=user.email, phone_number=user.phone_number,
                status=user.status, deleted=user.deleted, email_verified=user.email_verified,
                phone_number_verified=user.phone_number_verified,
                created_at=datetime_iso(user.created_at), updated_at=datetime_iso(user.updated_at))


def _api_group_data(group):
    return dict(id=group.id, title=group.title, description=group.description,
                created_at=datetime_iso(group.created_at), updated_at=datetime_iso(group.updated_at))


def _api_audit(message, target, related=None):
    # Stable identifiers keep untrusted names/contact details out of audit headers.
    identity = f'{type(target).__name__} {target.id}'
    if related is not None:
        identity += f', {type(related).__name__} {related.id}'
    audit.log(message, target=identity, actor=current_api_key, category='api_keys')


def _api_commit():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        _api_error(409, 'The change conflicts with an existing record.')


def _api_invalidate_user_access(user):
    with db.session.no_autoflush:
        user.refresh_uuid36()
        LoginTokenManager.invalidate_user_tokens(user.id)


def _api_user_fields(data):
    values = {}
    if 'name' in data:
        values['name'] = _api_text(data['name'], 'name', 256)
    if 'email' in data:
        email = _api_text(data['email'], 'email', 120)
        try:
            email = validate_email(email, check_deliverability=False).normalized.lower()
        except EmailNotValidError:
            _api_error(400, 'Enter a valid email address.')
        if len(email) > 120:
            _api_error(400, 'Email addresses cannot exceed 120 characters.')
        values['email'] = email
    if 'phone_number' in data:
        phone = data['phone_number']
        if phone is not None:
            phone = _api_text(phone, 'phone_number', 32, allow_empty=True)
        try:
            values['phone_number'] = normalize_phone_number(phone, None) if phone else None
        except (phonenumbers.NumberParseException, ValueError):
            _api_error(400, 'Enter a valid phone number with a country calling code.')
        if values['phone_number'] and len(values['phone_number']) > 15:
            _api_error(400, 'Phone numbers cannot exceed 15 characters including the calling code.')
    return values


@apiv1.after_request
def service_response_headers(response):
    if getattr(g, 'api_key_attempt', None) is not None:
        response.headers['Cache-Control'] = 'no-store'
    return response


@apiv1.errorhandler(500)
def service_internal_error(error):
    if getattr(g, 'api_key_attempt', None) is not None:
        db.session.rollback()
        return jsonify(error='Internal server error.'), 500
    from ..errors.routes import internal_error
    return internal_error(error)


@apiv1.route('/key', methods=['GET'])
@token_required
@require_permission('api_keys.read', scope='api')
def inspect_api_key():
    key = current_api_key
    permissions = sorted(record.key for record in key.permissions if record.value and pm.get(record.key, scope='api'))
    return jsonify(key=dict(id=key.uuid36, name=key.name, last_four=key.last_four, status=key.status,
                            created_at=datetime_iso(key.created_at), expires_at=datetime_iso(key.expires_at) if key.expires_at else None,
                            last_used_at=datetime_iso(key.last_used_at), permissions=permissions))


@apiv1.route('/settings/application', methods=['GET'])
@token_required
@require_permission('application_settings.read', scope='api')
def read_application_settings():
    return jsonify(settings={key: SystemManager.get_setting(key) for key in APPLICATION_SETTING_KEYS})


@apiv1.route('/users', methods=['GET'])
@token_required
@require_permission('users.read', scope='api')
def list_users():
    statement = db.select(User).where(User.deleted.is_(False)).order_by(User.name, User.id)
    if 'email' in request.args:
        values = _api_user_fields({'email': request.args['email']})
        statement = statement.where(User.email == values['email'])
    users = db.paginate(statement, page=_api_page(), per_page=10, error_out=False)
    return jsonify(users=[_api_user_data(user) for user in users.items], total=users.total, has_more=users.has_next)


@apiv1.route('/users/<int:user_id>', methods=['GET'])
@token_required
@require_permission('users.read', scope='api')
def read_user(user_id):
    return jsonify(user=_api_user_data(_api_user(user_id)))


@apiv1.route('/users', methods=['POST'])
@token_required
@require_permission('users.create', scope='api')
def create_user():
    data = _api_json(('name', 'email', 'phone_number', 'send_welcome_email'), required=('name', 'email'))
    send_welcome_email = data.get('send_welcome_email', True)
    if type(send_welcome_email) is not bool:
        _api_error(400, 'send_welcome_email must be a JSON boolean.')
    values = _api_user_fields(data)
    try:
        user = UserManager.create_user(**values, status='pending', send_welcome_email=send_welcome_email)
    except IntegrityError:
        db.session.rollback()
        _api_error(409, 'The email address or phone number is already in use.')
    _api_audit('API created user', user)
    return jsonify(user=_api_user_data(user)), 201


@apiv1.route('/users/<int:user_id>', methods=['PATCH'])
@token_required
@require_permission('users.update', scope='api')
def update_user(user_id):
    user = _api_user(user_id)
    data = _api_json(('name', 'phone_number'))
    values = _api_user_fields(data)
    phone_changed = 'phone_number' in values and values['phone_number'] != user.phone_number
    if phone_changed:
        user.phone_number_verified = False
    for field, value in values.items():
        setattr(user, field, value)
    if phone_changed:
        _api_invalidate_user_access(user)
    _api_commit()
    _api_audit('API updated user', user)
    return jsonify(status='success', user_id=user.id)


@apiv1.route('/users/<int:user_id>/enable', methods=['POST'])
@token_required
@require_permission('users.enable', scope='api')
def enable_user(user_id):
    user = _api_user(user_id)
    user.status = 'active'
    _api_commit()
    _api_audit('API enabled user', user)
    return jsonify(status='success', user_id=user.id)


@apiv1.route('/users/<int:user_id>/disable', methods=['POST'])
@token_required
@require_permission('users.disable', scope='api')
def disable_user(user_id):
    user = _api_user(user_id)
    user.status = 'disabled'
    _api_invalidate_user_access(user)
    _api_commit()
    _api_audit('API disabled user', user)
    return jsonify(status='success', user_id=user.id)


@apiv1.route('/users/<int:user_id>', methods=['DELETE'])
@token_required
@require_permission('users.delete', scope='api')
def delete_user(user_id):
    user = _api_user(user_id, include_deleted=True)
    if not user.deleted:
        _api_invalidate_user_access(user)
        UserManager.delete_user(user)
        _api_audit('API deleted user', user)
    return '', 204


@apiv1.route('/users/<int:user_id>/recover', methods=['POST'])
@token_required
@require_permission('users.recover', scope='api')
def recover_user(user_id):
    user = _api_user(user_id, include_deleted=True)
    if not user.deleted:
        _api_error(409, 'Only deleted accounts can be recovered.')
    user.deleted = False
    user.deleted_at = None
    user.status = 'disabled'
    _api_invalidate_user_access(user)
    _api_commit()
    _api_audit('API recovered user', user)
    return jsonify(status='success', user_id=user.id)


def _api_preference_specs():
    return {spec.setting: spec for spec in sm.all() if spec.group in USER_PREFERENCE_GROUPS}


@apiv1.route('/users/<int:user_id>/preferences', methods=['GET'])
@token_required
@require_permission('user_preferences.read', scope='api')
def read_user_preferences(user_id):
    user = _api_user(user_id)
    records = {record.key: record.value for record in user.settings}
    preferences = {}
    for key, spec in _api_preference_specs().items():
        value = records.get(key)
        if value is None:
            value = spec.default
        elif isinstance(spec.default, bool):
            value = value.lower() == 'true'
        preferences[key] = value
    return jsonify(user_id=user.id, preferences=preferences)


@apiv1.route('/users/<int:user_id>/preferences', methods=['PATCH'])
@token_required
@require_permission('user_preferences.update', scope='api')
def update_user_preferences(user_id):
    user = _api_user(user_id)
    specs = _api_preference_specs()
    data = _api_json(specs)
    themes = {value for choices in THEME_CHOICES.values() for value, label in choices}
    for key, value in data.items():
        spec = specs[key]
        if isinstance(spec.default, bool):
            if type(value) is not bool:
                _api_error(400, 'Boolean preferences must be JSON booleans.')
        else:
            _api_text(value, key, 2048, allow_empty=True)
        if key == 'preferences.theme' and value not in themes:
            _api_error(400, 'Unknown visual theme.')
    for key, value in data.items():
        user.set_setting(key, value)
    _api_commit()
    _api_audit('API updated user preferences', user)
    return jsonify(status='success')


@apiv1.route('/users/<int:user_id>/permissions', methods=['GET'])
@token_required
@require_permission('user_permissions.read', scope='api')
def read_user_permissions(user_id):
    user = _api_user(user_id)
    return jsonify(user_id=user.id, permissions={spec.permission: user.can(spec.permission) for spec in pm.all()})


@apiv1.route('/groups', methods=['GET'])
@token_required
@require_permission('groups.read', scope='api')
def list_groups():
    groups = UserManager.get_all_user_groups(page=_api_page())
    return jsonify(groups=[_api_group_data(group) for group in groups.items], total=groups.total, has_more=groups.has_next)


@apiv1.route('/groups/<int:group_id>', methods=['GET'])
@token_required
@require_permission('groups.read', scope='api')
def read_group(group_id):
    return jsonify(group=_api_group_data(_api_group(group_id)))


@apiv1.route('/groups', methods=['POST'])
@token_required
@require_permission('groups.create', scope='api')
def create_group():
    data = _api_json(('title', 'description'), required=('title',))
    title = _api_text(data['title'], 'title', 256)
    description = _api_text(data.get('description', ''), 'description', 256, allow_empty=True, multiline=True)
    group = UserManager.create_user_group(title, description)
    _api_audit('API created group', group)
    return jsonify(group=_api_group_data(group)), 201


@apiv1.route('/groups/<int:group_id>', methods=['PATCH'])
@token_required
@require_permission('groups.update', scope='api')
def update_group(group_id):
    group = _api_group(group_id)
    data = _api_json(('title', 'description'))
    values = {field: _api_text(value, field, 256, allow_empty=field == 'description', multiline=field == 'description')
              for field, value in data.items()}
    for field, value in values.items():
        setattr(group, field, value)
    _api_commit()
    _api_audit('API updated group', group)
    return jsonify(status='success', group_id=group.id)


@apiv1.route('/groups/<int:group_id>', methods=['DELETE'])
@token_required
@require_permission('groups.delete', scope='api')
def delete_group(group_id):
    group = _api_group(group_id)
    UserManager.delete_user_group(group)
    _api_audit('API deleted group', group)
    return '', 204


@apiv1.route('/groups/<int:group_id>/members', methods=['GET'])
@token_required
@require_permission('groups.read_members', scope='api')
def read_group_members(group_id):
    group = _api_group(group_id)
    statement = db.select(User).join(user_group_members).where(user_group_members.c.group_id == group.id).order_by(User.id)
    members = db.paginate(statement, page=_api_page(), per_page=10, error_out=False)
    return jsonify(members=[user.id for user in members.items], total=members.total, has_more=members.has_next)


@apiv1.route('/groups/<int:group_id>/members/<int:user_id>', methods=['PUT'])
@token_required
@require_permission('groups.add_members', scope='api')
def add_group_member(group_id, user_id):
    group = _api_group(group_id)
    user = _api_user(user_id)
    if user not in group.users:
        group.users.append(user)
        _api_commit()
        _api_audit('API added group member', group, user)
    return '', 204


@apiv1.route('/groups/<int:group_id>/members/<int:user_id>', methods=['DELETE'])
@token_required
@require_permission('groups.remove_members', scope='api')
def remove_group_member(group_id, user_id):
    group = _api_group(group_id)
    user = _api_user(user_id, include_deleted=True)
    if user in group.users:
        group.users.remove(user)
        _api_commit()
        _api_audit('API removed group member', group, user)
    return '', 204


@apiv1.route('/users/<int:user_id>/notifications', methods=['POST'])
@token_required
@require_permission('notifications.send', scope='api')
def send_user_notification(user_id):
    user = _api_user(user_id)
    data = _api_json(('title', 'body', 'category', 'link'), required=('title', 'body', 'category'))
    title = _api_text(data['title'], 'title', 512)
    body = _api_text(data['body'], 'body', 10000, multiline=True)
    if not isinstance(data['category'], str):
        _api_error(400, 'category must be a registered notification category.')
    try:
        category = NotificationCategory(data['category'])
    except ValueError:
        _api_error(400, 'Unknown notification category.')
    link = data.get('link')
    if link is not None:
        link = _api_text(link, 'link', 2048)
        try:
            valid_link = route_url(link)
        except ValueError:
            _api_error(400, 'Invalid notification link.')
        if valid_link == '/' and link != '/':
            _api_error(400, 'Invalid notification link.')
    NotificationManager.send_notification(user, title, body, category, link=link,
                                          sender=f'API key {current_api_key.uuid36}')
    _api_audit('API sent notification', user)
    return jsonify(status='success'), 201
