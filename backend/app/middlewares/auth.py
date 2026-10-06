from functools import wraps
from datetime import datetime
import hashlib
from flask import request, g, abort
from app import db
from app.security.models import OASession
from app.security.policy import principal, can_page, audit
from app.security.login_mode import login_mode, temporary_admin, ADMIN_ID, ADMIN_SESSION_VERSION
from app.utils.store import get_request_store_id

def authenticate():
    g.pop('scope_store', None)
    g.pop('store_id', None)
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer ') or len(header) > 512:
        abort(401)
    digest = hashlib.sha256(header[7:].encode()).hexdigest()
    session = db.session.get(OASession, digest)
    if session and session.expires_at <= datetime.utcnow():
        abort(401, description='登录已过期，请重新登录')
    if not session or session.revoked:
        abort(401, description='登录状态已失效，请重新登录')
    if login_mode() == 'password':
        if session.user_id != ADMIN_ID or session.account_version != ADMIN_SESSION_VERSION:
            abort(401, description='登录方式已切换，请重新登录')
        account, user, grants = temporary_admin()
    else:
        if session.user_id == ADMIN_ID:
            abort(401, description='临时账号登录已停用，请使用手机号验证码重新登录')
        account, user, grants = principal(session.user_id)
    if session.account_version != account.version:
        abort(401)
    (g.staff, g.staff_user, g.grants, g.oa_session) = (account, user, grants, session)
    request.user = {'user_id': user.id}

def login_required(*pages):

    def decorate(f):

        @wraps(f)
        def wrapped(*args, **kwargs):
            authenticate()
            if pages != ('session',):
                store = get_request_store_id()
                g.store_id = store
                if not g.staff.headquarters and store not in g.grants:
                    abort(403, description='无该门店权限')
                if not any((can_page(page, store) for page in pages)):
                    abort(403, description='无该页面权限')
                g.scope_store = store
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                body = request.get_json(silent=True) or {}
                fields = ('Amount', 'Comment', 'Remark', 'Status', 'Version')
                detail = {k: body[k] for k in fields if isinstance(body, dict) and k in body}
                detail['status'] = 'started'
                audit('request:' + f.__name__, request.path, detail)
                db.session.commit()
            response = f(*args, **kwargs)
            if request.method not in ('GET', 'HEAD', 'OPTIONS'):
                from flask import make_response
                result = make_response(response)
                payload = result.get_json(silent=True) or {}
                audit('result:' + f.__name__, request.path, {'http_status': result.status_code, 'code': payload.get('Code')})
                db.session.commit()
                return result
            return response
        wrapped.oa_pages = pages
        return wrapped
    return decorate
