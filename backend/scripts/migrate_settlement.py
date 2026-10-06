#!/usr/bin/env python3
"""Explicit-target migration. Does not read backend/.env for database credentials."""
import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import URL, make_url

parser=argparse.ArgumentParser()
parser.add_argument('mode',choices=['schema','preview','apply'])
parser.add_argument('--host');parser.add_argument('--port',type=int,default=3306)
parser.add_argument('--database');parser.add_argument('--user',default='root')
parser.add_argument('--cutoff',help='维护窗口真实切换时间（北京时间）；preview/apply 必填，不追溯到10月1日')
parser.add_argument('--legacy-wallet-payer',choices=['headquarters','nanshan'],default='nanshan',help='正式上线历史来源与承担方统一南山；保留原本金折算比例')
parser.add_argument('--legacy-card-policy',choices=['full-period','prospective'],default='prospective',help='正式上线仅保留剩余卡期金额，不导入旧核销或补结算')
parser.add_argument('--card-manifest',type=Path)
parser.add_argument('--maintenance-confirmed',action='store_true')
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--legacy-card-end-tolerance-seconds',type=int,choices=[0,1,2],default=0,help='仅旧无卡期快照月卡，允许回调比支付晚至多2秒，沿用玩家实际到期日')
parser.add_argument('--production-launch',action='store_true',help='正式首次上线目标及口径校验')
args=parser.parse_args()
if args.mode!='schema' and not args.cutoff:parser.error('preview/apply 必须明确维护窗口真实 --cutoff')
cutoff=None
if args.cutoff:
    try:cutoff=datetime.strptime(args.cutoff,'%Y-%m-%d %H:%M:%S')
    except ValueError:parser.error('--cutoff 格式为 YYYY-MM-DD HH:MM:SS（北京时间）')
if args.production_launch:
    if args.legacy_wallet_payer!='nanshan' or args.legacy_card_policy!='prospective' or args.card_manifest:
        parser.error('正式首次上线固定南山承担、剩余卡期，不使用历史月卡清单')
    if args.mode!='schema' and cutoff.strftime('%Y-%m')!='2026-10':
        parser.error('本次计划首次结算2026-10；实际切换月份变化须重新确认')
uri=os.getenv('SETTLEMENT_DATABASE_URL')
if not uri:
    if not args.host or not args.database:parser.error('请明确 --host 和 --database，或设置 SETTLEMENT_DATABASE_URL')
    uri=URL.create('mysql+pymysql',username=args.user,password=getpass.getpass('数据库密码：'),host=args.host,port=args.port,database=args.database)
else:uri=make_url(uri)
if args.production_launch and (uri.host,uri.port,uri.database)!=('sh-cynosdbmysql-grp-a7usn35k.sql.tencentcdb.com',22120,'gambit'):
    parser.error('正式首次上线只允许已核对的上海正式库主机/端口/gambit')
os.environ['DATABASE_URL']=uri.render_as_string(hide_password=False)
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app,db
from app.settlement.models import SettlementBatch
from app.settlement.opening import initialize
from app.models import Store
app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':uri})
with app.app_context():
    tables=[t for t in db.metadata.sorted_tables if t.name.startswith('settlement_')]
    if args.mode=='schema':
        for table in tables:table.create(db.engine,checkfirst=True)
        columns={c['name'] for c in inspect(db.engine).get_columns('month_card_orders')}
        if 'duration_days' not in columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE month_card_orders ADD COLUMN duration_days INT NOT NULL DEFAULT 0'))
        if 'request_key' not in columns:
            with db.engine.begin() as connection:
                connection.execute(text('ALTER TABLE month_card_orders ADD COLUMN request_key VARCHAR(64) NULL, ADD UNIQUE KEY uq_month_card_request_key (request_key)'))
        for table_name in ('settlement_card_remittances','settlement_expenses'):
            proof_columns={c['name'] for c in inspect(db.engine).get_columns(table_name)}
            if 'proof_image' not in proof_columns:
                with db.engine.begin() as connection:
                    connection.execute(text(f'ALTER TABLE {table_name} ADD COLUMN proof_image VARCHAR(512) NULL'))
        output={'Mode':'schema','Tables':[t.name for t in tables],'OrderSnapshotColumns':['month_card_orders.duration_days','month_card_orders.request_key']}
    else:
        if args.mode=='apply' and not args.maintenance_confirmed:parser.error('正式执行须确认暂停相关写入并备份，传入 --maintenance-confirmed')
        ns=Store.query.filter_by(code='nanshan').one()
        payer=0 if args.legacy_wallet_payer=='headquarters' else ns.id
        manifest=json.loads(args.card_manifest.read_text()) if args.card_manifest else {}
        lock_connection=None
        try:
            # Serialize operator retries across processes; the maintenance window also
            # prevents old application instances from changing source balances.
            if db.engine.dialect.name=='mysql':
                lock_connection=db.engine.connect()
                locked=lock_connection.execute(text("SELECT GET_LOCK('gambit_settlement_opening', 0)")).scalar()
                if locked!=1:raise RuntimeError('另一个期初初始化正在执行')
            output=initialize(cutoff,payer,args.legacy_card_policy,manifest,args.legacy_card_end_tolerance_seconds)
            # Report carries balances/counts, never credentials or customer identifiers.
            output.update(Mode=args.mode,Host=uri.host,Database=uri.database,LegacyWalletPayer=args.legacy_wallet_payer,LegacyCardPolicy=args.legacy_card_policy)
            args.report.write_text(json.dumps(output,ensure_ascii=False,indent=2))
            if args.mode=='apply':
                db.session.commit();output['Committed']=True
            else:db.session.rollback()
        except Exception:
            db.session.rollback();raise
        finally:
            if lock_connection is not None:
                lock_connection.execute(text("SELECT RELEASE_LOCK('gambit_settlement_opening')"));lock_connection.close()
    args.report.write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps(output,ensure_ascii=False,indent=2))
