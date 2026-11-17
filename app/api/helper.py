from functools import wraps

from flask import current_app, g, jsonify, request
from werkzeug.local import LocalProxy
from sqlalchemy.orm.attributes import set_committed_value

from app import audit
from app.model_managers import APIKeyManager


current_api_key = LocalProxy(lambda: getattr(g, 'api_key', None))


def token_required(view_func):
    """Authenticate a service key without creating or accepting a browser session."""
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        g.api_key = None
        g.api_key_attempt = {'key': None, 'outcome': 'missing or malformed credentials'}
        authorization = request.headers.get('Authorization', '').split()
        if len(authorization) == 2 and authorization[0].lower() == 'bearer':
            key, outcome = APIKeyManager.authenticate(authorization[1])
            g.api_key_attempt = {'key': key, 'outcome': outcome}
            if outcome == 'authenticated':
                used_at = APIKeyManager.record_use(key, authorization[1])
                if used_at is not None:
                    g.api_key = key
                    set_committed_value(key, 'last_used_at', used_at)
                else:
                    g.api_key_attempt['outcome'] = 'credentials changed'
        if not current_api_key:
            return jsonify(error='Invalid or missing API key.'), 401, {'WWW-Authenticate': 'Bearer'}
        return current_app.ensure_sync(view_func)(*args, **kwargs)
    return wrapper


def log_api_key_usage(response):
    attempt = getattr(g, 'api_key_attempt', None)
    if attempt is not None:
        key = attempt['key']
        route = str(request.url_rule) if request.url_rule else ''
        audit.log(f"API key request: {request.method} {route}; status={response.status_code}; "
                  f"ip={request.remote_addr}; authentication={attempt['outcome']}",
                  target=key, actor=key if key is not None else 'Anonymous', category='api_keys')
    return response
