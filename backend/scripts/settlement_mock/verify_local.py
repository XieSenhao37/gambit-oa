"""Destructive ONLY to dedicated localhost:33317/gambit_manual_settlement_test."""
import json,os,tempfile,copy
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.engine import URL
import run
from app import db,create_app
from app.models import User,WalletAccount,PointAccount
from app.settlement import reports
from app.settlement.models import SettlementControl,SettlementReport,SettlementEntry,SettlementCardUsage,SettlementCardRemittance,SettlementExpense
from fixture import START,PREFIX,A,B,C,D,sql_value,insert_sql
from datetime import datetime

def main():
    uri=URL.create('mysql+pymysql',username='root',password='manual-local-only-0927',host='127.0.0.1',port=33317,database='gambit_manual_settlement_test')
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':uri})
    manifest,sql=run.metadata_file()
    with app.app_context():
        for table in ('raffle_notifications','raffle_entries','raffle_prizes','raffles'):
            run.execute('DROP TABLE IF EXISTS '+table)
        db.session.commit();db.drop_all();db.create_all()
        # Shared test uses Go's NOT NULL category_ids, stricter than OA metadata.
        run.execute('ALTER TABLE dishes MODIFY category_ids JSON NOT NULL')
        db.session.commit()
        raffle_sql=Path('/Users/toneyxie/Documents/Code/GambitServer/sql/20260921_create_raffles.sql').read_text()
        for statement in raffle_sql.split(';'):
            if statement.strip():run.execute(statement)
        db.session.add(SettlementControl(id=1,cutoff=datetime(2026,9,27,19,15,13),initialized_at=datetime(2026,9,27,19,15,13),legacy_wallet_payer=0,legacy_card_policy='full-period'))
        db.session.add(User(id=1,open_id='original-test-customer',role=0))
        db.session.add(WalletAccount(id=1,open_id='original-test-customer',balance=12345,frozen_balance=0))
        db.session.add(PointAccount(id=1,open_id='original-test-customer',balance=777))
        db.session.commit()
        incomplete=copy.deepcopy(manifest)
        for item in incomplete['rows']:
            if item['table']=='dishes':item['values'].pop('category_ids',None)
            if item['table']=='stores':item['values'].pop('name',None)
        try:run.validate_fixture_schema(incomplete)
        except ValueError as e:assert 'category_ids' in str(e) and 'stores' in str(e) and 'name' in str(e) and '尚未清理' in str(e)
        else:raise AssertionError('Missing required fields across tables must all be reported')
        run.validate_fixture_schema(manifest)
        # Conflict diagnostics must retain the guard and distinguish July/August/September.
        probe=db.session.begin_nested()
        sample=next(r['values'] for r in manifest['rows'] if r['table']=='pay_orders')
        for item in manifest['rows']:
            if item['table'] in ('stores','users') or (item['table']=='play_orders' and item['values']['id']==sample['play_order_id']):
                run.execute(insert_sql(item['table'],item['values']))
        for n,at in enumerate(['2026-07-10 12:00:00','2026-08-10 12:00:00','2026-09-10 12:00:00',None]):
            row=dict(sample,id=10+n,order_id='conflict-probe-'+str(n),pay_end_time=at)
            run.execute(insert_sql('pay_orders',row))
        diagnostics=run.historical_cash_conflicts(datetime(2026,9,27,19,15,13))
        assert [r['month'] for r in diagnostics]==['2026-07','2026-08','2026-09','missing_payment_time']
        assert sum(r['count'] for r in diagnostics)==4
        try:run.preflight(manifest)
        except ValueError as e:assert 'cash_by_payment_month' in str(e) and '未修改任何数据' in str(e)
        else:raise AssertionError('Historical cash guard must remain active')
        probe.rollback();db.session.expire_all()
        # Reproduce the approved seven legacy cash records without altering original accounts.
        legacy_play=next(r['values'] for r in manifest['rows'] if r['table']=='play_orders')
        run.execute(insert_sql('play_orders',dict(legacy_play,id=50,open_id='original-test-customer',store_id=0)))
        for n in range(7):
            at='2026-07-10 12:00:00' if n<4 else '2026-09-10 12:00:00'
            run.execute(insert_sql('pay_orders',dict(sample,id=50+n,order_id='approved-old-'+str(n),
                open_id='original-test-customer',play_order_id=50,store_id=0,
                wechat_amount=1 if n<4 else 0,amount=1 if n<4 else 0,pay_end_time=at)))
        logs=Path(tempfile.mkdtemp(prefix='gambit-mock-cleanup-local-'))
        balances=run.balance_fingerprint()
        # A changed target profile must not be treated as authorization for other rows.
        guard=db.session.begin_nested()
        run.execute('UPDATE pay_orders SET wechat_amount=2 WHERE id=50')
        try:run.cleanup_approved_cash(logs/'unwritten')
        except ValueError as e:assert '不匹配' in str(e)
        else:raise AssertionError('Changed target set must be rejected')
        guard.rollback();db.session.expire_all()
        # Deletion is reversible and remains part of the surrounding seed transaction.
        mark=db.session.begin_nested()
        assert run.cleanup_approved_cash(logs)==7
        assert run.scalar('SELECT COUNT(*) FROM pay_orders WHERE id BETWEEN 50 AND 56 AND deleted_at IS NOT NULL')==7
        assert json.loads((logs/'old-payments-backup.json').read_text())['pay_orders'][0]['deleted_at'] is None
        mark.rollback();db.session.expire_all()
        assert run.scalar('SELECT COUNT(*) FROM pay_orders WHERE id BETWEEN 50 AND 56 AND deleted_at IS NULL')==7
        live_logs=logs/'final';live_logs.mkdir()
        assert run.cleanup_approved_cash(live_logs)==7
        assert run.balance_fingerprint()==balances
        assert run.scalar('SELECT COUNT(*) FROM play_orders WHERE id=50')==1
        before=run.preflight(manifest);run.seed(manifest,sql)
        # Each of the three intended manual steps must block July until handled.
        for expected,table in [('到账','settlement_card_remittances'),('积分成本','settlement_expenses'),('待核验','settlement_card_usages')]:
            mark=db.session.begin_nested()
            try:
                reports.generate('2026-07',0,PREFIX+'-blocker-'+table)
                raise AssertionError('Missing expected blocker '+expected)
            except ValueError as e:
                assert expected in str(e),str(e)
            finally:mark.rollback();db.session.expire_all()
            for t,identity,changes in manifest['fixes']:
                if t==table:
                    run.execute(f'UPDATE `{t}` SET '+', '.join('`'+k+'`='+sql_value(v) for k,v in changes.items())+f' WHERE id={identity}')
            db.session.expire_all()
        # Reset fixes to the fixture values before its reversible preview.
        for table,identity,_ in manifest['fixes']:
            row=next(r['values'] for r in manifest['rows'] if r['table']==table and r['values']['id']==identity)
            run.execute(f'UPDATE `{table}` SET '+', '.join('`'+k+'`='+sql_value(v) for k,v in row.items())+f' WHERE id={identity}')
        db.session.expire_all()
        expected=run.preview(manifest)
        assert run.balance_fingerprint()==before['balances']
        assert SettlementReport.query.count()==0
        assert SettlementEntry.query.count()==3
        assert SettlementCardUsage.query.filter_by(status='review').count()==1
        assert SettlementExpense.query.filter_by(status='needs_cost').count()==1
        assert SettlementCardRemittance.query.filter_by(status='pending').count()==1
        wallet=run.scalar('SELECT SUM(remaining) FROM settlement_batches WHERE kind=\'wallet\'')
        assert wallet==13000
        assert run.scalar('SELECT SUM(principal_remaining) FROM settlement_batches WHERE kind=\'wallet\'')==8500
        assert run.scalar('SELECT SUM(remaining) FROM settlement_batches WHERE kind=\'point\'')==200
        # Cleanup/resume flow can use a committed mock fixture in this dedicated DB only.
        db.session.commit()
        try:run.preflight(manifest)
        except ValueError as e:assert '重复' in str(e) or '前移' in str(e)
        else:raise AssertionError('Repeat seed should be rejected')
        db.session.rollback()
        print(json.dumps({'status':'passed','rows':len(manifest['rows']),'expected':expected,
            'checks':['strict Go dish schema and aggregated pre-write errors','authorized legacy cleanup, private backup, target guard and atomic rollback','historical cash month diagnostics and guard','three manual blockers','two full natural months','fees and exemptions','negative remittance','zero net','cross-month refunds','card carry/full term conservation','duplicate confirmation','preview rollback','existing balance preservation','duplicate seed rejection']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
