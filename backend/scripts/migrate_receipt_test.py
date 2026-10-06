#!/usr/bin/env python3
"""Add optional receipt image key to the explicitly authorized Guangzhou test DB."""
import getpass,json
from sqlalchemy import create_engine,inspect,text
from sqlalchemy.engine import URL
HOST='gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com'
print(f'仅测试库：{HOST}:21085/gambit；仅为验券到账、积分成本增加可空图片字段，不修改业务数据。',flush=True)
url=URL.create('mysql+pymysql',username='root',password=getpass.getpass('测试库密码（隐藏输入、不保存）：'),host=HOST,port=21085,database='gambit')
engine=create_engine(url,connect_args={'connect_timeout':15})
try:
    with engine.begin() as conn:
        for table in ('settlement_card_remittances','settlement_expenses'):
            columns={c['name'] for c in inspect(conn).get_columns(table)}
            if 'proof_image' not in columns:
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN proof_image VARCHAR(512) NULL'))
            assert 'proof_image' in {c['name'] for c in inspect(conn).get_columns(table)}
    print('RECEIPT_TEST_SCHEMA_COMPLETED：字段已就绪，无需重新初始化或导入模拟数据。')
except Exception as exc:
    original=getattr(exc,'orig',exc);args=getattr(original,'args',())
    print(json.dumps(dict(status='failed',error_type=type(exc).__name__,database_code=args[0] if args and isinstance(args[0],int) else None)))
    raise SystemExit(1)
finally:engine.dispose()
