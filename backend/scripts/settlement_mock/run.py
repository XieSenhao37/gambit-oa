#!/usr/bin/env python3
"""Guarded test-only SQL runner. Password is read with getpass, never persisted."""
import getpass,hashlib,json,os,sys,tempfile
from pathlib import Path
from datetime import datetime
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
HOST='gz-cynosdbmysql-grp-n55s87kv.sql.tencentcdb.com'
PORT=21085
DATABASE='gambit'
os.environ['DATABASE_URL']='sqlite://'
os.environ['STORE_SETTLEMENT_ENABLED']='true'
sys.path.insert(0,str(ROOT))
from sqlalchemy import text,inspect
from sqlalchemy.engine import URL
from app import create_app,db
from app.settlement import reports
from app.settlement.models import SettlementControl,SettlementReport,SettlementEntry,SettlementStatement,SettlementCardPeriod
from fixture import PREFIX,START,A,B,C,D,sql_value

APPROVED_CASH_PROFILE=[dict(month='2026-07',count=4,wechat_paid_fen=4),dict(month='2026-09',count=3,wechat_paid_fen=0)]
CASH_WHERE="""deleted_at IS NULL AND pay_status IN (1,3)
        AND pay_type IN (0,4) AND month_card_order_id IS NULL AND wallet_recharge_order_id IS NULL
        AND group_activity_participant_id IS NULL AND (play_order_id IS NOT NULL OR catering_id IS NOT NULL)
        AND ((pay_end_time >= :start AND pay_end_time < :cutoff) OR
             (pay_end_time IS NULL AND created_at >= :start))"""

EXPECTED={'2026-07':{A:92384,B:54615,C:-9100,D:0},'2026-08':{A:6921,B:52600,C:-5000}}

def metadata_file():
    manifest=json.loads((HERE/'manifest.json').read_text())
    sql=(HERE/'seed.sql').read_text()
    if hashlib.sha256(sql.encode()).hexdigest()!=manifest['sql_sha256']:
        raise ValueError('seed.sql 与核验清单不一致，请重新导出并验证')
    return manifest,sql

def primary(row):return ('id',row['id']) if 'id' in row else ('month',row['month'])
def execute(sql):return db.session.connection().exec_driver_sql(sql)
def scalar(sql,params=None):return db.session.execute(text(sql),params or {}).scalar()
def balance_fingerprint():
    out={}
    for table,cols in [('wallet_accounts','id,open_id,balance,frozen_balance'),('point_accounts','id,open_id,balance'),('users','id,open_id,month_card_expire')]:
        values=[list(r) for r in db.session.execute(text(f'SELECT {cols} FROM `{table}` WHERE open_id NOT LIKE :prefix OR open_id IS NULL ORDER BY id'),{'prefix':PREFIX+'%'})]
        out[table]=dict(count=len(values),sha256=hashlib.sha256(json.dumps(values,default=str).encode()).hexdigest())
    return out

def historical_cash_conflicts(cutoff):
    """Read-only aggregate diagnostics; excludes customer identifiers and credentials."""
    rows=db.session.execute(text(f"""SELECT
        CASE WHEN pay_end_time IS NULL THEN 'missing_payment_time'
             ELSE SUBSTRING(CAST(pay_end_time AS CHAR),1,7) END AS payment_month,
        COUNT(*) AS payment_count, COALESCE(SUM(wechat_amount),0) AS wechat_paid_fen
        FROM pay_orders WHERE {CASH_WHERE}
        GROUP BY payment_month ORDER BY payment_month"""),dict(start=START,cutoff=cutoff))
    return [dict(month=r.payment_month,count=int(r.payment_count),wechat_paid_fen=int(r.wechat_paid_fen)) for r in rows]


def private_backup(path,content):
    """Persist recovery evidence before any soft delete. Do not print row contents."""
    with open(path,'x',encoding='utf-8') as out:
        os.chmod(path,0o600)
        out.write(content);out.flush();os.fsync(out.fileno())


def cleanup_approved_cash(logs):
    """User authorized removal of the seven diagnosed old TEST payments only.

    Soft-delete preserves references, original balances and external payment state.
    The caller commits this together with the mock seed, or rolls both back.
    """
    control=SettlementControl.query.filter_by(id=1).populate_existing().with_for_update().one_or_none()
    if not control or not control.initialized_at or control.cutoff<=START:
        raise ValueError('原期初状态不符，不能清理旧支付记录')
    if SettlementReport.query.filter(SettlementReport.status!='void').count():
        raise ValueError('已有有效报表，不能清理旧支付记录')
    engine=scalar("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='pay_orders'")
    if engine!='InnoDB':raise ValueError('pay_orders 不是事务表，停止清理')
    params=dict(start=START,cutoff=control.cutoff)
    rows=[dict(r) for r in db.session.execute(text(f'SELECT * FROM pay_orders WHERE {CASH_WHERE} ORDER BY id FOR UPDATE'),params).mappings()]
    if not rows:return 0
    profile=historical_cash_conflicts(control.cutoff)
    if len(rows)!=7 or profile!=APPROVED_CASH_PROFILE:
        raise ValueError('旧记录已不匹配获授权的7笔（7月4笔共4分、9月3笔微信部分0分），停止清理：'+json.dumps(profile,ensure_ascii=False))
    ids=','.join(str(int(r['id'])) for r in rows)
    refunds=[dict(r) for r in db.session.execute(text(f'SELECT * FROM refund_requests WHERE pay_order_id IN ({ids}) ORDER BY id FOR UPDATE')).mappings()]
    if any(r['deleted_at'] is None and r['status'] not in ('refunded','rejected','cancelled') for r in refunds):
        raise ValueError('旧支付仍有关联退款待处理，停止清理，不改退款状态')
    refs=[f"pay:{r['id']}" for r in rows]+[f"refund:{r['id']}" for r in refunds]
    for ref in refs:
        if scalar('SELECT COUNT(*) FROM settlement_entries WHERE reference=:ref',dict(ref=ref)) or scalar('SELECT COUNT(*) FROM settlement_allocations WHERE reference=:ref',dict(ref=ref)):
            raise ValueError('旧支付已关联结算流水或资产分配，停止清理，不修改账本')
    removed_at=datetime.now().replace(microsecond=0)
    stamp=sql_value(removed_at)
    forward=[f"UPDATE `pay_orders` SET `deleted_at`={stamp} WHERE `id`={int(r['id'])} AND `deleted_at` IS NULL;" for r in rows]
    restore=[f"UPDATE `pay_orders` SET `deleted_at`=NULL WHERE `id`={int(r['id'])} AND `deleted_at`={stamp};" for r in rows]
    backup=dict(environment='test',host=HOST,port=PORT,database=DATABASE,original_cutoff=control.cutoff,
        mode='soft_delete_pay_orders_only',deleted_at=removed_at,profile=profile,pay_orders=rows,refund_requests_readonly=refunds)
    private_backup(logs/'old-payments-backup.json',json.dumps(backup,ensure_ascii=False,indent=2,default=str))
    private_backup(logs/'cleanup-old-payments.sql','-- TEST ONLY. Executed in the same transaction as seed.sql; no standalone COMMIT.\n'+'\n'.join(forward)+'\n')
    private_backup(logs/'restore-old-payments.sql','-- TEST ONLY. For reviewed recovery after mock cleanup; do not run during the exercise.\n-- Exact IDs and deletion timestamp only; transaction managed by the recovery operator.\n'+'\n'.join(restore)+'\n')
    for command in forward:
        if execute(command).rowcount!=1:raise ValueError('旧支付清理数量不符，回滚本次修改')
    db.session.expire_all()
    if historical_cash_conflicts(control.cutoff):raise ValueError('出现新的历史支付冲突，回滚本次修改')
    print('已备份并在事务内标记删除7笔旧测试支付；模拟数据核验通过后才一并提交。',flush=True)
    return len(rows)


def validate_fixture_schema(manifest):
    """Report all schema mismatches before touching existing rows."""
    inspector=inspect(db.session.connection());schemas={};errors={}
    for item in manifest['rows']:
        table,row=item['table'],item['values']
        if table not in schemas:
            if not inspector.has_table(table):
                schemas[table]={};errors[table]={'table_missing':True}
            else:
                schemas[table]={c['name']:c for c in inspector.get_columns(table)}
                if scalar('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table',{'table':table})!='InnoDB':
                    errors.setdefault(table,{})['non_transactional']=True
        if not schemas[table]:continue
        missing=set(row)-set(schemas[table])
        required={name for name,col in schemas[table].items() if not col['nullable'] and col['default'] is None and not col.get('autoincrement') and name not in row}
        nulls={name for name,col in schemas[table].items() if not col['nullable'] and name in row and row[name] is None}
        for label,values in [('columns_missing_in_db',missing),('required_values_missing',required),('null_not_allowed',nulls)]:
            if values:
                detail=errors.setdefault(table,{})
                detail[label]=sorted(set(detail.get(label,[]))|values)
    if errors:raise ValueError('模拟数据与测试库结构不匹配（已汇总全部涉及表；尚未清理或写入）：'+json.dumps(errors,ensure_ascii=False))


def preflight(manifest):
    control=SettlementControl.query.filter_by(id=1).populate_existing().with_for_update().one_or_none()
    if not control or not control.initialized_at:raise ValueError('测试库尚未完成原期初初始化；此脚本不代替初始化')
    if control.cutoff <= START:raise ValueError('测试库起点已经前移或与预期不一致，停止重复写入')
    if SettlementReport.query.filter(SettlementReport.status!='void').count():raise ValueError('已有有效结算报表，停止改变结算起点')
    conflicts={}
    for table in ('settlement_entries','settlement_periods','settlement_statements','settlement_reports'):
        count=scalar(f"SELECT COUNT(*) FROM `{table}` WHERE month < '2026-09'")
        if count:conflicts[table]=count
    for table,col in [('settlement_card_pools','starts_at'),('settlement_expenses','completed_at'),('settlement_card_remittances','created_at')]:
        count=scalar(f"SELECT COUNT(*) FROM `{table}` WHERE `{col}` < '2026-09-01'")
        if count:conflicts[table]=count
    # Moving cutoff must not accidentally bring previously ignored genuine test cash into the reports.
    cash_conflicts=historical_cash_conflicts(control.cutoff)
    if cash_conflicts:
        conflicts['historical_cash_payments']=sum(r['count'] for r in cash_conflicts)
        conflicts['cash_by_payment_month']=cash_conflicts
    if conflicts:raise ValueError('存在会混入模拟结算的历史记录，未修改任何数据：'+json.dumps(conflicts,ensure_ascii=False))
    validate_fixture_schema(manifest)
    counts=Counter()
    for item in manifest['rows']:
        table,row=item['table'],item['values'];key,value=primary(row)
        if scalar(f'SELECT COUNT(*) FROM `{table}` WHERE `{key}`=:value',{'value':value}):raise ValueError(f'{table} 模拟主键已存在，停止重复写入')
        counts[table]+=1
    if scalar("SELECT COUNT(*) FROM stores WHERE code LIKE 'mock-settle-%'") or scalar('SELECT COUNT(*) FROM users WHERE open_id LIKE :p',{'p':PREFIX+'%'}):
        raise ValueError('已存在同批模拟门店或用户，停止重复执行')
    return dict(control={c.name:getattr(control,c.name) for c in control.__table__.columns},balances=balance_fingerprint(),counts=dict(counts))

def preview(manifest):
    """Exercise both months in a savepoint; none of these confirmations are persisted."""
    baseline=(SettlementReport.query.count(),SettlementCardPeriod.query.count(),SettlementStatement.query.count())
    pool_ids=[r['values']['id'] for r in manifest['rows'] if r['table']=='settlement_card_pools']
    savepoint=db.session.begin_nested();result={}
    try:
        for table,identity,changes in manifest['fixes']:
            sets=', '.join('`'+k+'`='+sql_value(v) for k,v in changes.items())
            execute(f'UPDATE `{table}` SET {sets} WHERE id={identity}')
        db.session.expire_all()
        for month in ('2026-07','2026-08'):
            report=reports.generate(month,0,PREFIX+'-preview-'+month)
            totals={t['StoreId']:t['amount'] for t in report.payload['totals'] if t['StoreId']}
            if totals!=EXPECTED[month]:raise ValueError(f'{month} 模拟报表金额与预期不一致，停止提交：'+str(totals))
            result[month]=dict(totals=report.payload['totals'],fees=report.payload['fees'])
            refs={str(sid):'仅事务内预演，未真实转账' for sid,amount in totals.items() if amount}
            reports.confirm(report.id,report.digest,0,refs,True)
            reports.confirm(report.id,report.digest,0,refs,True)
        slices=SettlementCardPeriod.query.filter(SettlementCardPeriod.pool_id.in_(pool_ids)).all()
        if sum(p.amount for p in slices)!=5*39900:raise ValueError('月卡跨月释放金额不守恒')
        if SettlementStatement.query.count()!=baseline[2]+7:raise ValueError('确认后门店月结单数量不符')
    finally:
        savepoint.rollback();db.session.expire_all()
    if SettlementReport.query.filter(SettlementReport.month.in_(['2026-07','2026-08'])).count():raise ValueError('预演报表未完全回滚')
    after=(SettlementReport.query.count(),SettlementCardPeriod.query.count(),SettlementStatement.query.count())
    if after!=baseline:raise ValueError('预演报表、月卡切片或月结单未完全回滚')
    return result

def seed(manifest,sql):
    db.session.execute(text('SET @gambit_mock_authorized=:token, @gambit_mock_target_db=DATABASE(), @mock_original_cutoff=(SELECT cutoff FROM settlement_controls WHERE id=1)'),{'token':PREFIX})
    for line in sql.splitlines():
        if line.strip() and not line.startswith('--'):execute(line)
    db.session.expire_all()
    counts={}
    for item in manifest['rows']:
        table,row=item['table'],item['values'];key,value=primary(row)
        if scalar(f'SELECT COUNT(*) FROM `{table}` WHERE `{key}`=:value',{'value':value})!=1:raise ValueError('插入行核验失败：'+table)
        counts[table]=counts.get(table,0)+1
    return counts

def main():
    manifest,sql=metadata_file()
    print(f'仅广州测试库：{HOST}:{PORT}/{DATABASE}',flush=True)
    print('写入 7/8 月 MOCK 数据，临时将结算起点前移至 2026-07-01；不重跑期初，不修改原账户余额。',flush=True)
    print('本次包含已授权的7笔旧测试支付清理：先备份，仅标记删除支付记录；关联业务订单、账户余额和退款状态保留。',flush=True)
    print('请暂停测试环境充值、消费、开卡、积分和结算操作，执行完再恢复。',flush=True)
    if input('已暂停且确认仅测试库，请输入 TEST MOCK：').strip()!='TEST MOCK':
        print('输入不匹配，已退出，未连接数据库。',flush=True);return 1
    password=getpass.getpass('测试库密码（隐藏输入、不保存）：')
    url=URL.create('mysql+pymysql',username='root',password=password,host=HOST,port=PORT,database=DATABASE,query={'charset':'utf8mb4'})
    del password
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':url,'SQLALCHEMY_ENGINE_OPTIONS':{'connect_args':{'connect_timeout':15,'read_timeout':60,'write_timeout':60}}})
    logs=Path(tempfile.mkdtemp(prefix='gambit-settlement-mock-'));os.chmod(logs,0o700)
    Path('/tmp/gambit-settlement-mock-result-path').write_text(str(logs))
    print('核验报告目录：'+str(logs),flush=True)
    stage='连接测试库';locked=False;committed=False;commit_started=False
    with app.app_context():
        try:
            if scalar('SELECT DATABASE()')!=DATABASE:raise ValueError('数据库名称不符')
            if scalar("SELECT GET_LOCK('gambit_test_settlement_mock',0)")!=1:raise ValueError('另一个模拟数据操作正在执行')
            locked=True;stage='核验全部模拟表结构'
            validate_fixture_schema(manifest)
            stage='备份并清理已授权的7笔旧测试支付'
            cleaned=cleanup_approved_cash(logs)
            stage='前置冲突和结构检查'
            before=preflight(manifest)
            (logs/'before.json').write_text(json.dumps(before,ensure_ascii=False,indent=2,default=str))
            (logs/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
            stage='执行模拟数据 SQL';counts=seed(manifest,sql)
            stage='事务内预演两个月并回滚预演';expected=preview(manifest)
            if balance_fingerprint()!=before['balances']:raise ValueError('原有用户余额或月卡到期时间发生变化，停止提交')
            (logs/'expected.json').write_text(json.dumps(expected,ensure_ascii=False,indent=2))
            stage='提交模拟数据';commit_started=True;db.session.commit();committed=True
            done=dict(status='completed',environment='test',cutoff='2026-07-01',counts=counts,months=['2026-07','2026-08'],original_accounts_unchanged=True,reports_confirmed=0,old_payments_soft_deleted=cleaned)
            (logs/'status.json').write_text(json.dumps(done,ensure_ascii=False,indent=2))
            print(json.dumps(done,ensure_ascii=False,indent=2),flush=True)
            print('MOCK_SETTLEMENT_TEST_READY：先在 OA 处理验券到账、待核验时长及待补成本，再生成 2026-07 月报。',flush=True)
        except Exception as error:
            db.session.rollback()
            original=getattr(error,'orig',error);args=getattr(original,'args',())
            result=dict(status='completed_report_error' if committed else ('commit_outcome_unknown' if commit_started else 'failed'),stage=stage,error_type=type(error).__name__,database_code=args[0] if args and isinstance(args[0],int) else None,
                reason=('提交结果需核对，禁止直接重跑。' if commit_started else '')+(str(error) if isinstance(error,ValueError) else '未输出数据库 SQL、密码或客户资料。请提供此报告以继续排查。'))
            (logs/'status.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
            return 1
        finally:
            if locked:
                try:scalar("SELECT RELEASE_LOCK('gambit_test_settlement_mock')")
                except Exception:pass
    return 0
if __name__=='__main__':sys.exit(main())
