"""Apply the additive staff migration and bind the named admin on the known test DB only.
Usage: python scripts/migrate_staff_test.py [--env-file /secure/test.env]
Without an env file, prompts for the known test DB password. Never prints credentials.
"""
import argparse
import getpass
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url, URL

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
TEST_HOST = 'gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com'
ADMIN_PHONE = '13380938170'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', help='可选：包含 DATABASE_URL 的本地测试凭据文件；不传则隐藏输入密码')
    args = parser.parse_args()
    if args.env_file:
        connection = dotenv_values(args.env_file).get('DATABASE_URL', '')
        url = make_url(connection)
    else:
        print('目标：广州测试库 ' + TEST_HOST + ':21085 / gambit（root）', flush=True)
        password = getpass.getpass('请输入测试库密码（输入隐藏，不保存）：')
        url = URL.create('mysql+pymysql', username='root', password=password,
                         host=TEST_HOST, port=21085, database='gambit',
                         query={'charset': 'utf8mb4'})
        connection = url.render_as_string(hide_password=False)
        del password
    if (url.host, url.port, url.database) != (TEST_HOST, 21085, 'gambit'):
        raise RuntimeError('只允许连接已确认的广州测试库')
    os.environ['DATABASE_URL'] = connection
    from app import create_app, db
    from app.models import User
    from app.security.models import StaffAccount, AccessAudit
    from app.utils.crypto import encrypt_phone
    app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': connection})
    sql = (ROOT / 'migrations/20260926_staff_access.sql').read_text()
    tables = ['staff_accounts', 'staff_store_grants', 'staff_role_pages',
              'oa_login_challenges', 'oa_login_throttles', 'oa_sessions', 'oa_access_audits']
    logs = Path(tempfile.mkdtemp(prefix='gambit-staff-test-migration-'))
    os.chmod(logs, 0o700)
    print('测试迁移核验目录：' + str(logs), flush=True)
    with app.app_context():
        inspector = inspect(db.engine)
        existing = set(inspector.get_table_names())
        backup = {}
        for table in tables:
            if table in existing:
                backup[table] = db.session.execute(text('SHOW CREATE TABLE `' + table + '`')).one()[1]
                expected = set(db.metadata.tables[table].columns.keys())
                actual = {c['name'] for c in inspector.get_columns(table)}
                if expected != actual:
                    raise RuntimeError('已有表结构不匹配：' + table)
        (logs / 'schema-before.json').write_text(json.dumps(backup, ensure_ascii=False, indent=2))
        cipher = encrypt_phone(ADMIN_PHONE)
        users = User.query.filter(User.phone_number == cipher, User.deleted_at.is_(None)).all()
        if len(users) != 1:
            raise RuntimeError('指定手机号未唯一匹配现有小程序用户，停止迁移；请先核实用户归属')
        user_id = users[0].id
        db.session.rollback()
        with db.engine.begin() as conn:
            executable = '\n'.join(line for line in sql.splitlines() if not line.lstrip().startswith('--'))
            for statement in executable.split(';'):
                if statement.strip():
                    conn.execute(text(statement))
        inspector = inspect(db.engine)
        after = {}
        for table in tables:
            expected = set(db.metadata.tables[table].columns.keys())
            if {c['name'] for c in inspector.get_columns(table)} != expected:
                raise RuntimeError('迁移后字段不匹配：' + table)
            after[table] = db.session.execute(text('SHOW CREATE TABLE `' + table + '`')).one()[1]
        account = db.session.get(StaffAccount, user_id)
        conflict = StaffAccount.query.filter(StaffAccount.phone_cipher == cipher, StaffAccount.user_id != user_id).first()
        if conflict:
            raise RuntimeError('手机号已绑定其他员工，停止管理员初始化')
        changed = not account or not account.enabled or not account.headquarters or account.phone_cipher != cipher
        if not account:
            account = StaffAccount(user_id=user_id, phone_cipher=cipher, version=0)
            db.session.add(account)
        if changed:
            if account.phone_cipher != cipher:
                account.phone_verified_at = None
            account.phone_cipher = cipher
            account.enabled = True
            account.headquarters = True
            account.version += 1
            account.updated_at = datetime.utcnow()
            db.session.get(User, user_id).role = 126
            db.session.add(AccessAudit(actor_id=user_id, action='bootstrap.test', target=str(user_id),
                                      detail={'method': 'explicit_user_authorized_test_admin'}))
        db.session.commit()
        (logs / 'schema-after.json').write_text(json.dumps(after, ensure_ascii=False, indent=2))
        (logs / 'status.json').write_text(json.dumps({'status':'completed', 'environment':'test',
            'tables': tables, 'admin_user_id':user_id, 'admin_changed':changed,
            'migration_sha256':hashlib.sha256(sql.encode()).hexdigest()}, indent=2))
        print('STAFF_TEST_MIGRATION_COMPLETED: 7 张表已核验，指定管理员已绑定。')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Avoid printing driver errors, which can contain connection details or bound data.
        print('迁移未完成（' + type(error).__name__ + '）。未自动重试，请核查测试连接和迁移记录。', file=sys.stderr)
        sys.exit(1)
