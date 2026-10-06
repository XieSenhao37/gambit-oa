import hashlib
import hmac
import secrets
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, current_app, abort, g
from sqlalchemy.exc import IntegrityError
from app import db
from app.models import User
from app.middlewares.auth import login_required
from app.security.models import StaffAccount, LoginChallenge, OASession, LoginThrottle
from app.security.policy import principal, available_stores, can_page, PAGES, audit
from app.security import sms
from app.security.login_mode import login_mode, verify_admin, temporary_admin
from app.utils.crypto import encrypt_phone
auth_bp = Blueprint('auth', __name__)

def ok(data):
    return jsonify(Code=0, Message='success', Data=data)

def secret():
    key = current_app.config.get('OA_AUTH_SECRET', '')
    if len(key) < 32:
        abort(503, description='登录服务尚未配置')
    return key.encode()

def digest(value):
    return hmac.new(secret(), value.encode(), hashlib.sha256).hexdigest()

def throttle(key, limit, seconds):
    # Password login has opaque sessions; only the SMS challenge needs an HMAC secret.
    key = hashlib.sha256(key.encode()).hexdigest() if login_mode() == 'password' else digest(key)
    now = datetime.utcnow()
    row = db.session.get(LoginThrottle, key)
    if row is None:
        try:
            db.session.add(LoginThrottle(key=key, window_start=now, count=0))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    row = db.session.query(LoginThrottle).filter_by(key=key).with_for_update().one()
    if row.window_start <= now - timedelta(seconds=seconds):
        (row.count, row.window_start) = (0, now)
    if row.count >= limit:
        db.session.rollback()
        abort(429, description='操作过于频繁，请稍后重试')
    row.count += 1
    db.session.commit()

def issue_session(account, method):
    token = secrets.token_urlsafe(48)
    expires = datetime.utcnow() + timedelta(days=15)
    db.session.add(OASession(token_digest=hashlib.sha256(token.encode()).hexdigest(),
                            user_id=account.user_id, account_version=account.version,
                            expires_at=expires))
    g.staff = account
    audit('login', account.user_id, {'method': method})
    db.session.commit()
    return ok({'token': token, 'ExpiresAt': expires.isoformat() + 'Z'})


@auth_bp.route('/status', methods=['GET'])
def status():
    mode = login_mode()
    return ok({'LoginMode': mode, 'SmsReady': sms.configured() and len(current_app.config.get('OA_AUTH_SECRET', '')) >= 32, 'TestLoginEnabled': False})

@auth_bp.route('/send-code', methods=['POST'])
def send_code():
    if login_mode() != 'sms':
        abort(403, description='当前使用账号密码登录，短信登录暂未开放')
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400, description='请求格式无效')
    phone = data.get('PhoneNumber', '')
    if not isinstance(phone, str) or not re.fullmatch('1[3-9]\\d{9}', phone):
        abort(400, description='请输入正确的手机号')
    throttle('send-ip:' + str(request.remote_addr), 20, 3600)
    account = StaffAccount.query.filter_by(phone_cipher=encrypt_phone(phone), enabled=True).first()
    if not account:
        abort(403, description='该手机号暂不可用于后台登录，请联系管理员')
    principal(account.user_id)
    if not sms.configured():
        abort(503, description='短信服务尚未就绪，请等待资质及模板审核通过')
    throttle('phone-minute:' + phone, 1, 60)
    throttle('phone-day:' + phone, 10, 86400)
    throttle('send-global', 200, 86400)
    challenge_id = secrets.token_hex(24)
    code = f'{secrets.randbelow(1000000):06d}'
    LoginChallenge.query.filter_by(user_id=account.user_id, consumed=False).update({'consumed': True})
    challenge = LoginChallenge(id=challenge_id, user_id=account.user_id, account_version=account.version, code_digest=digest(challenge_id + ':' + code), expires_at=datetime.utcnow() + timedelta(minutes=5))
    db.session.add(challenge)
    db.session.commit()
    try:
        sms.send_code(phone, code)
    except Exception:
        abort(503, description='短信发送失败或服务未就绪，请稍后重试')
    challenge.sent = True
    db.session.commit()
    return ok({'ChallengeId': challenge_id, 'RetryAfter': 60})

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400, description='请求格式无效')
    throttle('verify-ip:' + str(request.remote_addr), 30, 600)
    if login_mode() == 'password':
        if set(data) - {'username','password'} or not verify_admin(data.get('username'), data.get('password')):
            abort(401, description='账号或密码错误')
        account, _, _ = temporary_admin()
        return issue_session(account, 'temporary_password')
    if any(key in data for key in ('username','password','TestLogin')):
        abort(400, description='当前仅支持手机号验证码登录')
    (cid, code) = (data.get('ChallengeId'), data.get('Code'))
    if not isinstance(cid, str) or len(cid) != 48 or (not isinstance(code, str)) or (not re.fullmatch('\\d{6}', code)):
        abort(400, description='请输入六位验证码')
    row = LoginChallenge.query.filter_by(id=cid).with_for_update().first()
    if not row or not row.sent or row.consumed or (row.attempts >= 5) or (row.expires_at <= datetime.utcnow()):
        abort(400, description='验证码无效或已过期')
    row.attempts += 1
    if not hmac.compare_digest(row.code_digest, digest(cid + ':' + code)):
        db.session.commit()
        abort(400, description='验证码错误')
    (account, user, grants) = principal(row.user_id)
    if row.account_version != account.version:
        abort(400, description='账号已变更，请重新获取验证码')
    account.phone_verified_at = datetime.utcnow()
    row.consumed = True
    return issue_session(account, 'sms')

@auth_bp.route('/me', methods=['GET'])
@login_required('session')
def me():
    stores = available_stores(g.staff, g.grants)
    return ok({'UserId': g.staff.user_id, 'Name': g.staff_user.nick_name or '员工', 'Headquarters': g.staff.headquarters, 'Stores': [{'Id': s.id, 'Name': s.name, 'Role': 'admin' if g.staff.headquarters else g.grants[s.id], 'Pages': [p['id'] for p in PAGES if can_page(p['id'], s.id)]} for s in stores], 'Pages': PAGES})

@auth_bp.route('/logout', methods=['POST'])
@login_required('session')
def logout():
    g.oa_session.revoked = True
    db.session.commit()
    return ok(None)
