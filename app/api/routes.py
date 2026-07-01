from flask import request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from ..core.helper import get_s3_client
from app import db
from app.api import apiv1
from app.models import File
from ..model_managers import NotificationManager


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

    object_key = f"uploads/{context}/{uploaded_file.uuid36}.{ext}"
    uploaded_file.object_key = object_key
    db.session.commit()

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

    return jsonify({
        "file_id": uploaded_file.uuid36,
        "upload_url": presigned_url,
        "object_key": object_key,
        "expires_in": 300,
    })


@apiv1.route('/notifications', methods=['GET'])
@apiv1.route('/notifications/<string:uuid36>', methods=['PATCH'])
@login_required
def notifications(uuid36: str = None):
    if request.method == 'GET':
        include_read_str = request.args.get("include_read", default="false", type=str)
        include_read = include_read_str.lower() in ['true', '1', 't', 'y', 'yes']
        recent_only_str = request.args.get("recent_only", default="true", type=str)
        recent_only = recent_only_str.lower() in ['true', '1', 't', 'y', 'yes']
        page = request.args.get('page', 1, type=int)

        # Fetch from manager
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
                "link": n.link,
                "timestamp": n.created_at
            })

        return jsonify(notifications_data), 200

    elif request.method == 'PATCH':
        if not uuid36:
            return jsonify({"error": "Notification ID is required"}), 400
        NotificationManager.mark_notification_as_read(uuid36)
        return jsonify({"status": "success", "message": "Notification marked as read"}), 200

    return jsonify({"error": "Method not allowed"}), 405
