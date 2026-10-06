"""Financial boundary regressions; tests use isolated in-memory SQLite only."""
import uuid
from datetime import datetime, timedelta
from unittest.mock import patch
from sqlalchemy import event
import unittest
from tests import test_settlement as fixtures
from app import db
from app.settlement import reports, service
from app.settlement.models import *


class ManualReportsTest(unittest.TestCase):
    setUp = fixtures.SettlementTest.setUp
    tearDown = fixtures.SettlementTest.tearDown
    headers = fixtures.SettlementTest.headers
    pool = fixtures.SettlementTest.pool
    usage = fixtures.SettlementTest.usage
    # Reuse fixture helpers without inheriting the old workflow assertions.
    def generate(self, month='2026-01', key=None):
        return self.client.post('/admin_api/settlement/v1/prepare', headers=self.headers(),
            json={'Month': month, 'RequestKey': key or str(uuid.uuid4())})

    def confirm(self, report, refs=None):
        return self.client.post('/admin_api/settlement/v1/lock', headers=self.headers(), json={
            'ReportId': report['Id'], 'Digest': report['Digest'], 'AllTransfersCompleted': True,
            'References': refs if refs is not None else {str(t['StoreId']): f'银行凭证-{t["StoreId"]}' for t in report['Totals'] if t['StoreId'] and t['amount']}})

    def void(self, report):
        return self.client.post(f'/admin_api/settlement/v1/reports/{report["Id"]}/void', headers=self.headers(),
            json={'Digest': report['Digest'], 'NoTransfersStarted': True})

    def cost(self):
        for sid, weight in [(1,60),(2,40)]:
            b=SettlementBatch(kind='point',open_id='p',source_key=f'point:{sid}',responsible_store_id=sid,face_total=weight,remaining=0)
            db.session.add(b);db.session.flush()
            db.session.add(SettlementAllocation(biz_key=f'alloc:{sid}',batch_id=b.id,kind='point',open_id='p',reference='redeem:1',expense_key='redeem:1',amount=weight,state='consumed'))
        e=SettlementExpense(expense_key='redeem:1',kind='redeem',source_id=1,amount=5000,provider_id=2,status='needs_cost',completed_at=datetime(2026,1,20))
        db.session.add(e);db.session.commit();return e

    def save_cost(self, e, amount=5000):
        return self.client.post(f'/admin_api/settlement/v1/expenses/{e.id}/confirm', headers=self.headers(),json={'Amount':amount,'ProviderId':2,'Note':'核对采购成本'})

    def test_retired_voucher_registration_cannot_block_or_write(self):
        from app.settlement.models import SettlementCardRemittance
        row=SettlementCardRemittance(order_id=999,voucher_key='retired-test',channel='old',external_no='old',store_id=1,amount=39900,status='pending',created_at=datetime(2026,1,1))
        db.session.add(row);db.session.commit()
        for method,path in [('get','remittances'),('post',f'remittances/{row.id}/save'),('post',f'remittances/{row.id}/confirm')]:
            response=getattr(self.client,method)('/admin_api/settlement/v1/'+path,headers=self.headers())
            self.assertEqual(response.status_code,404)
        report=self.generate().json['Data']
        response=self.confirm(report)
        self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(db.session.get(SettlementCardRemittance,row.id).status,'pending')

    def test_preview_has_no_financial_effect_and_confirm_half_card_once(self):
        p=self.pool();p.starts_at=datetime(2026,1,17);p.ends_at=p.starts_at+timedelta(days=30)
        self.usage(p,1);db.session.commit()
        key=str(uuid.uuid4());res=self.generate(key=key);self.assertEqual(res.status_code,200,res.json)
        r=res.json['Data'];self.assertEqual(next(t['amount'] for t in r['Totals'] if t['StoreId']==1),19950)
        self.assertEqual(self.generate(key=key).json['Data']['Id'],r['Id'])
        self.assertEqual(SettlementEntry.query.count(),0);self.assertEqual(SettlementCardPeriod.query.count(),0)
        self.assertEqual(SettlementStatement.query.count(),0);self.assertEqual(p.status,'open')
        self.assertEqual(self.generate().status_code,400)
        for _ in range(2): self.assertEqual(self.confirm(r).status_code,200)
        self.assertEqual(SettlementCardPeriod.query.count(),1);self.assertEqual(SettlementEntry.query.count(),1)
        self.assertEqual(SettlementStatement.query.one().amount,19950)
        self.assertEqual(self.void(r).status_code,400)
        u=SettlementCardUsage(pool_id=p.id,play_order_id=99,store_id=2,started_at=datetime(2026,2,5),ended_at=datetime(2026,2,5,2),seconds=7200,status='valid',note='')
        db.session.add(u);db.session.commit()
        later=self.generate('2026-02');self.assertEqual(later.status_code,200,later.json)
        self.assertEqual(self.confirm(later.json['Data']).status_code,200)
        self.assertEqual(sum(e.amount for e in SettlementEntry.query),39900)
        self.assertEqual(service.totals('2026-02')[2]['amount'],19950)
        self.assertEqual(db.session.get(SettlementCardPool,p.id).status,'closed')

    def test_cost_save_no_post_negative_store_must_remit_and_old_version_cannot_confirm(self):
        e=self.cost();self.assertEqual(self.generate().status_code,400)
        self.assertEqual(self.save_cost(e).status_code,200)
        self.assertEqual(e.status,'ready');self.assertEqual(SettlementEntry.query.count(),0)
        r=self.generate().json['Data'];self.assertEqual({t['StoreId']:t['amount'] for t in r['Totals']},{1:-3000,2:3000})
        self.assertEqual(self.save_cost(e,3000).status_code,400)
        self.assertEqual(self.confirm(r,{'2':'已付款'}).status_code,400)
        self.assertEqual(e.status,'ready');self.assertEqual(SettlementEntry.query.count(),0)
        self.assertEqual(self.void(r).status_code,200)
        self.assertEqual(self.save_cost(e,3000).status_code,200)
        new=self.generate().json['Data'];self.assertEqual(new['Version'],2)
        self.assertEqual(self.confirm(r).status_code,400)
        self.assertEqual(self.confirm(new).status_code,200)
        self.assertEqual(db.session.get(SettlementExpense,e.id).status,'posted')
        self.assertEqual(SettlementStatement.query.filter_by(store_id=1).one().amount,-1800)
        self.assertIsNotNone(SettlementStatement.query.filter_by(store_id=1).one().paid_at)
        self.assertEqual(self.save_cost(e,4000).status_code,400)

    def test_confirm_uses_snapshot_late_wallet_is_next_month_and_export_is_versioned(self):
        service.add_entry(biz_key='before',kind='wallet',reference='pay:1',payer_id=0,receiver_id=1,amount=100,event_at=datetime(2026,1,2),detail='original');db.session.commit()
        r=self.generate().json['Data']
        service.add_entry(biz_key='late',kind='wallet_refund',reference='pay:1',payer_id=0,receiver_id=1,amount=-40,event_at=datetime(2026,1,3),detail='late refund');db.session.commit()
        view=self.client.get('/admin_api/settlement/v1/overview?Month=2026-01&Scope=all',headers=self.headers()).json['Data']
        self.assertEqual(view['EntryCount'],2)
        res=self.client.get(f'/admin_api/settlement/v1/export?Month=2026-01&Scope=all&ReportId={r["Id"]}',headers=self.headers())
        self.assertEqual(res.status_code,200);self.assertIn('2026-01-V1',res.data.decode('utf-8-sig'));self.assertNotIn('late refund',res.data.decode('utf-8-sig'))
        self.assertEqual(self.confirm(r).status_code,200)
        self.assertEqual(SettlementStatement.query.one().amount,99)
        self.assertEqual(SettlementEntry.query.filter_by(biz_key='late').one().month,'2026-02')

    def test_failure_rolls_back_everything_and_disabled_legacy_entry_points(self):
        p=self.pool();self.usage(p,1);db.session.commit()
        r=self.generate().json['Data']
        def fail(mapper, connection, target): raise RuntimeError('injected statement insert failure')
        event.listen(SettlementStatement, 'before_insert', fail)
        try:
            with self.assertRaises(RuntimeError): reports.confirm(r['Id'],r['Digest'],1,{'1':'proof'},True)
        finally:
            event.remove(SettlementStatement, 'before_insert', fail)
            db.session.rollback()
        self.assertEqual(SettlementEntry.query.count(),0);self.assertEqual(SettlementCardPeriod.query.count(),0)
        self.assertEqual(SettlementReport.query.one().status,'draft')
        for path in [f'cards/{p.id}/close','statements/1/paid']:
            self.assertEqual(self.client.post('/admin_api/settlement/v1/'+path,json={},headers=self.headers()).status_code,400)
        from scripts.settle_monthly import run_once
        with self.assertRaisesRegex(RuntimeError,'停用'):run_once(self.app)
        self.assertEqual(SettlementEntry.query.count(),0)

    def test_store_cannot_generate_confirm_or_see_other_store_report(self):
        e=self.cost();self.save_cost(e);r=self.generate().json['Data']
        res=self.client.get('/admin_api/settlement/v1/overview?Month=2026-01&Scope=all',headers=self.headers(2,2)).json['Data']
        self.assertEqual([t['StoreId'] for t in res['Totals']],[2])
        self.assertIsNone(res['Report']['Confirmation'])
        for path,data in [('prepare',{'Month':'2026-01','RequestKey':str(uuid.uuid4())}),('lock',{'ReportId':r['Id']})]:
            self.assertEqual(self.client.post('/admin_api/settlement/v1/'+path,json=data,headers=self.headers(2,2)).status_code,403)


    def test_zero_use_month_is_processed_but_money_carried_until_expiry(self):
        p=self.pool();p.starts_at=datetime(2026,1,17);p.ends_at=p.starts_at+timedelta(days=30);db.session.commit()
        blocked=self.generate('2026-02');self.assertEqual(blocked.status_code,400)
        self.assertEqual(SettlementCardPeriod.query.count(),0)
        r=self.generate().json['Data'];self.assertEqual(r['Totals'],[])
        self.assertEqual(self.confirm(r).status_code,200)
        part=SettlementCardPeriod.query.one();self.assertEqual((part.amount,part.allocated_amount,part.status),(19950,0,'carried'))
        r2=self.generate('2026-02').json['Data'];self.assertEqual(self.confirm(r2).status_code,200)
        self.assertEqual(SettlementEntry.query.one().amount,39900)
        self.assertEqual(SettlementEntry.query.one().receiver_id,0)
        self.assertEqual(SettlementStatement.query.count(),0)

    def test_invalid_digests_future_month_and_confirmation_acknowledgement(self):
        with patch('app.settlement.reports.now',return_value=datetime(2026,1,31,23,59,59)):
            self.assertEqual(self.generate().status_code,400)
        r=self.generate().json['Data']
        self.assertEqual(self.confirm({**r,'Digest':'wrong'}).status_code,400)
        res=self.client.post('/admin_api/settlement/v1/lock',headers=self.headers(),json={'ReportId':r['Id'],'Digest':r['Digest'],'References':{}})
        self.assertEqual(res.status_code,400)
        self.assertEqual(SettlementReport.query.one().status,'draft')

    def test_late_usage_is_flagged_without_changing_the_paid_snapshot(self):
        p=self.pool();self.usage(p,1);db.session.commit()
        r=self.generate().json['Data']
        self.usage(p,2);db.session.commit()
        result=self.confirm(r);self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(len(result.json['Data']['Confirmation']['late_usage_ids']),1)
        self.assertEqual(SettlementStatement.query.one().amount,39900)
        self.assertEqual(SettlementStatement.query.one().store_id,1)

    def test_void_and_recreate_keeps_original_assets_and_rejects_old_export(self):
        p=self.pool();self.usage(p,1);db.session.commit()
        r=self.generate().json['Data'];self.void(r)
        self.assertEqual(SettlementCardPeriod.query.count(),0);self.assertEqual(p.status,'open')
        new=self.generate().json['Data'];self.assertEqual(new['Version'],2)
        res=self.client.get(f'/admin_api/settlement/v1/export?Month=2026-01&ReportId={r["Id"]}',headers=self.headers())
        self.assertEqual(res.status_code,400)

    def test_rejects_unfinished_usage_without_retaining_earlier_pool_calculations(self):
        p=self.pool();self.usage(p,1,status='review');db.session.commit()
        r=self.generate();self.assertEqual(r.status_code,400,r.json)
        self.assertEqual(SettlementReport.query.count(),0);self.assertEqual(SettlementCardPeriod.query.count(),0)

    def test_historical_preposted_records_require_explicit_migration(self):
        p=self.pool();self.usage(p,1);service.close_card(p.id);db.session.commit()
        r=self.generate();self.assertEqual(r.status_code,400);self.assertIn('旧版',r.json['Message'])
        self.assertEqual(SettlementEntry.query.count(),1)

    def test_overview_explains_unavailable_months_before_generation(self):
        def view(month):
            return self.client.get('/admin_api/settlement/v1/overview?Month='+month,headers=self.headers()).json['Data']
        early=view('2025-12')
        self.assertEqual(early['FirstSettlementMonth'],'2026-01')
        self.assertIn('早于启用月份',early['GenerationBlockedReason'])
        with patch('app.api.v1.settlement.now',return_value=datetime(2026,1,20)):
            response=self.client.get('/admin_api/settlement/v1/overview?Month=2026-01',headers=self.headers())
            self.assertEqual(response.status_code,400)
            self.assertIn('已结束自然月',response.json['Message'])
        self.assertEqual(view('2026-01')['GenerationBlockedReason'],'')
        self.assertEqual(SettlementReport.query.count(),0)

    def test_draft_card_details_show_exact_snapshot_without_posting(self):
        p=self.pool();p.starts_at=datetime(2026,1,17);p.ends_at=p.starts_at+timedelta(days=30)
        u=self.usage(p,1);db.session.commit()
        report=self.generate().json['Data']
        def cards(headers=None):
            return self.client.get('/admin_api/settlement/v1/cards?Month=2026-01&Scope=all',headers=headers or self.headers()).json['Data']['Items']
        before=cards()[0]
        self.assertEqual(before['period_status'],'draft')
        self.assertEqual(before['distributed_total'],19950)
        self.assertEqual(before['estimated'],[{'store_id':1,'seconds':3600,'amount':19950}])
        self.assertEqual(SettlementCardPeriod.query.count(),0)
        self.assertEqual(SettlementEntry.query.count(),0)
        # A late edit must not silently change the distributed report's evidence.
        u.seconds=1800;db.session.commit()
        self.assertEqual(cards()[0]['estimated'],before['estimated'])
        self.assertEqual(cards()[0]['uses'][0]['seconds'],3600)
        self.assertEqual(cards(self.headers(2,2)),[])
        self.assertEqual(self.confirm(report).status_code,200)
        after=cards()[0]
        self.assertEqual(after['estimated'],before['estimated'])
        self.assertEqual(after['distributed_total'],19950)
        self.assertEqual(after['report_status'],'confirmed')

    def test_point_draft_details_match_report_and_do_not_post(self):
        e=self.cost();self.save_cost(e)
        r=self.generate().json['Data']
        path='/admin_api/settlement/v1/'
        def detail(headers=None):
            return self.client.get(path+'allocations?Month=2026-01&Scope=all&Reference=redeem:1',headers=headers or self.headers()).json['Data']['Expense']
        before=detail()
        self.assertEqual(before['report_status'],'draft')
        self.assertEqual({x['store_id']:x['amount'] for x in before['shares']},{1:3000,2:2000})
        self.assertEqual(detail(self.headers(2,2))['shares'],[{'store_id':2,'points':40,'amount':2000}])
        rows=self.client.get(path+'expenses?Month=2026-01&Scope=all',headers=self.headers()).json['Data']['Items']
        self.assertEqual(rows[0]['report_status'],'draft')
        self.assertEqual(e.status,'ready');self.assertEqual(SettlementEntry.query.count(),0)
        self.assertEqual(self.confirm(r).status_code,200)
        self.assertEqual(detail()['shares'],before['shares'])
        self.assertEqual(detail()['report_status'],'confirmed')

    def test_expiry_carry_is_visible_in_draft_before_any_finalization(self):
        p=self.pool();p.starts_at=datetime(2026,1,17);p.ends_at=p.starts_at+timedelta(days=30);db.session.commit()
        first=self.generate().json['Data'];self.confirm(first)
        self.generate('2026-02')
        card=self.client.get('/admin_api/settlement/v1/cards?Month=2026-02&Scope=all',headers=self.headers()).json['Data']['Items'][0]
        self.assertEqual(card['carry_shares'],[{'store_id':0,'seconds':0,'amount':39900}])
        self.assertEqual((card['distributed_total'],card['pending_amount'],card['future_amount']),(39900,0,0))
        self.assertEqual(card['period_status'],'draft')
        self.assertEqual(SettlementCardPeriod.query.count(),1)
        self.assertEqual(SettlementEntry.query.count(),0)

    def test_future_reads_reject_before_loading_financial_data(self):
        with patch('app.api.v1.settlement.now',return_value=datetime(2026,10,1)):
            for endpoint in ['overview','cash','cards','expenses']:
                for month in ['2026-10','2026-11']:
                    response=self.client.get(f'/admin_api/settlement/v1/{endpoint}?Month={month}&Scope=all',headers=self.headers())
                    self.assertEqual(response.status_code,400)
            self.assertEqual(self.client.get('/admin_api/settlement/v1/overview?Month=2026-09',headers=self.headers()).status_code,200)
        self.assertEqual(SettlementReport.query.count(),0)
        self.assertEqual(SettlementCardPeriod.query.count(),0)

    def test_export_shows_refund_direction_without_changing_snapshot(self):
        import csv,io
        service.add_entry(biz_key='display-income',kind='wallet',reference='pay:display',
            payer_id=0,receiver_id=1,amount=3000,event_at=datetime(2026,1,2),detail='original evidence')
        service.add_entry(biz_key='display-refund',kind='wallet_refund',reference='refund:display',
            payer_id=0,receiver_id=1,amount=-1000,event_at=datetime(2026,1,3),detail='refund evidence')
        db.session.commit()
        report=self.generate().json['Data']
        snapshot=SettlementReport.query.one()
        original_digest=snapshot.digest
        response=self.client.get(f'/admin_api/settlement/v1/export?Month=2026-01&Scope=all&ReportId={report["Id"]}',headers=self.headers())
        self.assertEqual(response.status_code,200)
        rows=list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))))
        header=next(r for r in rows if r and r[0]=='结算月')
        self.assertEqual(header[4:7],['结算出款方','结算收款方','金额（元）'])
        paid=next(r for r in rows if len(r)>3 and r[3]=='pay:display')
        refund=next(r for r in rows if len(r)>3 and r[3]=='refund:display')
        self.assertEqual(paid[4:7],['总部','南山','30.00'])
        self.assertEqual(refund[4:7],['南山','总部','10.00'])
        self.assertEqual(refund[-1],'refund evidence')
        self.assertEqual(snapshot.digest,original_digest)
        self.assertEqual(next(e['amount'] for e in snapshot.payload['entries'] if e['reference']=='refund:display'),-1000)
