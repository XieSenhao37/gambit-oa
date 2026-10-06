"""Run once on an explicitly selected DB: DATABASE_URL=... OA_AUTH_SECRET=... python scripts/bootstrap_staff.py --user-id N
Prompts for verified-by-operator phone. Does not auto-migrate, grant existing users or print secrets.
"""
import os, sys, argparse, getpass, re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
if not os.environ.get('DATABASE_URL'):
    raise SystemExit('必须显式设置 DATABASE_URL；不允许使用 .env 默认数据库')
from app import create_app, db
from app.models import User
from app.security.models import StaffAccount, AccessAudit
from app.utils.crypto import encrypt_phone
parser = argparse.ArgumentParser()
parser.add_argument('--user-id', type=int, required=True)
args = parser.parse_args()
phone = getpass.getpass('已人工核实归属的管理员手机号（输入隐藏）：')
if not re.fullmatch(r'1[3-9]\d{9}', phone):
    raise SystemExit('手机号无效')
app = create_app({'TESTING': True})
with app.app_context():
    if StaffAccount.query.count():
        raise SystemExit('已有员工账号，初始化入口已关闭；请通过现有管理员授权')
    user = db.session.get(User, args.user_id)
    if not user or user.deleted_at:
        raise SystemExit('用户不存在')
    cipher = encrypt_phone(phone)
    if User.query.filter(User.phone_number == cipher, User.id != user.id, User.deleted_at.is_(None)).first():
        raise SystemExit('手机号关联其他用户，请核实')
    db.session.add(StaffAccount(user_id=user.id, phone_cipher=cipher, enabled=True, headquarters=True, version=1))
    db.session.add(AccessAudit(actor_id=user.id, action='bootstrap', target=str(user.id), detail={'method': 'explicit_operator_bootstrap'}))
    user.role = 126
    db.session.commit()
    print('已建立首位总部管理员，首次登录仍需短信验证。')
