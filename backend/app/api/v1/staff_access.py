import re
from datetime import datetime
from flask import Blueprint, request, jsonify, abort, g
from sqlalchemy import or_
from app import db
from app.models import User, Store
from app.middlewares.auth import login_required
from app.security.models import StaffAccount, StaffGrant, RolePage, AccessAudit
from app.security.policy import PAGES, PAGE_MAP, ROLES, page_allowed, audit
from app.utils.crypto import encrypt_phone, decrypt_phone
staff_access_bp = Blueprint('staff_access', __name__)

def ok(data):
    return jsonify(Code=0, Message='success', Data=data)

def serialize(account):
    user = db.session.get(User, account.user_id)
    phone = decrypt_phone(account.phone_cipher)
    return {'UserId': account.user_id, 'Name': user.nick_name if user else '', 'Phone': phone[:3] + '****' + phone[-4:], 'Enabled': account.enabled, 'Headquarters': account.headquarters, 'Verified': account.phone_verified_at is not None, 'Grants': [{'StoreId': x.store_id, 'Role': x.role} for x in StaffGrant.query.filter_by(user_id=account.user_id).all()]}

@staff_access_bp.route('/accounts', methods=['GET'])
@login_required('staff-access')
def accounts():
    return ok({'Items': [serialize(a) for a in StaffAccount.query.order_by(StaffAccount.user_id).all()]})

@staff_access_bp.route('/candidates', methods=['GET'])
@login_required('staff-access')
def candidates():
    key = (request.args.get('Keyword') or '').strip()
    if not key:
        return ok({'Items': []})
    query = User.query.filter(User.deleted_at.is_(None))
    conditions = [User.nick_name.like('%' + key + '%')]
    if key.isdigit():
        conditions.append(User.id == int(key))
    if re.fullmatch('1[3-9]\\d{9}', key):
        conditions.append(User.phone_number == encrypt_phone(key))
    return ok({'Items': [{'UserId': u.id, 'Name': u.nick_name, 'Role': u.role} for u in query.filter(or_(*conditions)).limit(30).all()]})

@staff_access_bp.route('/accounts/<int:user_id>', methods=['PUT'])
@login_required('staff-access')
def save_account(user_id):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400, description='请求格式无效')
    StaffAccount.query.filter_by(headquarters=True).order_by(StaffAccount.user_id).with_for_update().all()
    account = db.session.get(StaffAccount, user_id)
    user = db.session.get(User, user_id)
    if not user or user.deleted_at:
        abort(404)
    before = serialize(account) if account else None
    phone = data.get('PhoneNumber')
    if phone and (not isinstance(phone, str) or not re.fullmatch('1[3-9]\\d{9}', phone)):
        abort(400, description='手机号格式错误')
    if not account and (not phone):
        abort(400, description='新增员工需要指定登录手机号')
    if phone:
        cipher = encrypt_phone(phone)
        if StaffAccount.query.filter(StaffAccount.phone_cipher == cipher, StaffAccount.user_id != user_id).first():
            abort(400, description='该号码已绑定其他员工')
        if User.query.filter(User.phone_number == cipher, User.id != user_id, User.deleted_at.is_(None)).first():
            abort(400, description='该号码关联其他用户，请先核实归属')
    (enabled, hq) = (data.get('Enabled', True), data.get('Headquarters', False))
    if not isinstance(enabled, bool) or not isinstance(hq, bool):
        abort(400)
    if user_id == g.staff.user_id and (not enabled or not hq):
        abort(400, description='不能撤销自己的总部管理权限')
    grants = data.get('Grants', [])
    if not isinstance(grants, list):
        abort(400)
    valid = []
    seen = set()
    for item in grants:
        if not isinstance(item, dict) or type(item.get('StoreId')) is not int or item.get('Role') not in ROLES:
            abort(400, description='门店角色无效')
        sid = item['StoreId']
        store = db.session.get(Store, sid)
        if sid in seen or not store or store.deleted_at or (store.status != 1):
            abort(400, description='门店无效或重复')
        seen.add(sid)
        valid.append((sid, item['Role']))
    if enabled and (not hq) and (not valid):
        abort(400, description='启用员工至少需要一个门店授权')
    if account and account.headquarters and (not enabled or not hq):
        if StaffAccount.query.filter(StaffAccount.headquarters.is_(True), StaffAccount.enabled.is_(True), StaffAccount.user_id != user_id).count() == 0:
            abort(400, description='至少保留一位总部管理员')
    if not account:
        account = StaffAccount(user_id=user_id, phone_cipher=cipher, version=0)
        db.session.add(account)
    if phone and (account.phone_cipher != cipher):
        account.phone_cipher = cipher
        account.phone_verified_at = None
    (account.enabled, account.headquarters) = (enabled, hq)
    account.version += 1
    account.updated_at = datetime.utcnow()
    StaffGrant.query.filter_by(user_id=user_id).delete()
    for (sid, role) in valid:
        db.session.add(StaffGrant(user_id=user_id, store_id=sid, role=role))
    user.role = 126 if enabled and hq else 125 if enabled and any((r == 'manager' for (_, r) in valid)) else 1 if enabled else 0
    db.session.flush()
    audit('staff.update', user_id, {'before': before, 'after': serialize(account)})
    db.session.commit()
    return ok(None)

@staff_access_bp.route('/pages', methods=['GET'])
@login_required('staff-access')
def pages():
    return ok({'Pages': PAGES, 'Roles': {role: {p['id']: page_allowed(role, p['id']) for p in PAGES} for role in ROLES}})

@staff_access_bp.route('/pages/<role>', methods=['PUT'])
@login_required('staff-access')
def save_pages(role):
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        abort(400, description='请求格式无效')
    if role not in ROLES or not isinstance(data.get('Pages'), dict):
        abort(400)
    changes = data['Pages']
    if any((k not in PAGE_MAP or PAGE_MAP[k]['scope'] == 'admin' or (not isinstance(v, bool)) for (k, v) in changes.items())):
        abort(400, description='授权管理页不可授予门店角色')
    before = {k: page_allowed(role, k) for k in changes}
    for (key, value) in changes.items():
        row = db.session.get(RolePage, (role, key))
        if not row:
            row = RolePage(role=role, page_id=key)
            db.session.add(row)
        row.allowed = value
    audit('role.pages', role, {'before': before, 'after': changes})
    db.session.commit()
    return ok(None)

@staff_access_bp.route('/audit', methods=['GET'])
@login_required('staff-access')
def audits():
    page = max(1, request.args.get('Page', 1, type=int))
    rows = AccessAudit.query.order_by(AccessAudit.id.desc()).paginate(page=page, per_page=50, error_out=False)
    return ok({'Total': rows.total, 'Items': [{'Id': r.id, 'ActorId': r.actor_id, 'StoreId': r.store_id, 'Action': r.action, 'Target': r.target, 'Detail': r.detail, 'Time': r.created_at.isoformat() + 'Z'} for r in rows.items]})
