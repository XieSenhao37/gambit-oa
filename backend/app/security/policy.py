import json
from pathlib import Path
from flask import g, abort
from app import db
from app.models import User, Store
from .models import StaffAccount, StaffGrant, RolePage, AccessAudit
PAGES = json.loads(Path(__file__).with_name('pages.json').read_text())
PAGE_MAP = {p['id']: p for p in PAGES}
ROLES = ('worker', 'manager')
WORKER_PAGES = {'workbench', 'orders', 'catering-orders'}

def principal(user_id):
    account = db.session.get(StaffAccount, user_id)
    user = db.session.get(User, user_id)
    if not account or not account.enabled or (not user) or user.deleted_at:
        abort(401, description='账号已停用或未开通')
    grants = db.session.query(StaffGrant).join(Store, Store.id == StaffGrant.store_id).filter(StaffGrant.user_id == user_id, Store.deleted_at.is_(None), Store.status == 1).all()
    if not account.headquarters and (not grants):
        abort(401, description='没有有效的门店授权')
    return (account, user, {row.store_id: row.role for row in grants})

def page_allowed(role, page_id):
    page = PAGE_MAP.get(page_id)
    if not page or page['scope'] == 'admin':
        return False
    override = db.session.get(RolePage, (role, page_id))
    if override is not None:
        return override.allowed
    return role == 'manager' or (role == 'worker' and page_id in WORKER_PAGES)

def can_page(page_id, store_id):
    if page_id not in PAGE_MAP:
        return False
    return g.staff.headquarters or page_allowed(g.grants.get(store_id), page_id)

def available_stores(account, grants):
    query = Store.query.filter(Store.deleted_at.is_(None), Store.status == 1)
    if not account.headquarters:
        query = query.filter(Store.id.in_(list(grants)))
    return query.order_by(Store.sort, Store.id).all()

def audit(action, target='', detail=None):
    db.session.add(AccessAudit(actor_id=g.staff.user_id, store_id=getattr(g, 'store_id', None), action=action, target=str(target)[:255], detail=detail))
