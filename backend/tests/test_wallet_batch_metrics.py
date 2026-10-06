import unittest
from datetime import datetime
from tests import test_settlement as fixtures
from app import db
from app.settlement import reports, service
from app.settlement.models import SettlementBatch, SettlementAllocation


class WalletBatchMetricsTest(unittest.TestCase):
    setUp=fixtures.SettlementTest.setUp
    tearDown=fixtures.SettlementTest.tearDown
    headers=fixtures.SettlementTest.headers

    def batch(self, id, face, principal):
        row=SettlementBatch(id=id,kind='wallet',open_id='p',source_key=f'test:{id}',face_total=face,
            principal_total=principal,remaining=face,principal_remaining=principal,responsible_store_id=0)
        db.session.add(row);db.session.flush();return row

    def entry(self, key, batch, month, face, principal, refund=False):
        service.add_entry(biz_key=key,kind='wallet_refund' if refund else 'wallet',reference='pay:1',
            payer_id=0,receiver_id=1,amount=principal,face_amount=face,
            event_at=datetime.fromisoformat(month+'-05'),detail='test')
        db.session.flush()

    def get(self, month='2026-01', **params):
        return self.client.get('/admin_api/settlement/v1/assets',query_string=dict(Month=month,Scope='all',Kind='wallet',**params),headers=self.headers())

    def test_selected_month_excludes_other_month_and_keeps_returned_consumption(self):
        a=self.batch(1,12000,10000)
        self.entry('settle:consume:batch:1',a,'2026-01',6000,5000)
        self.entry('refund:batch:1',a,'2026-02',-6000,-5000,True)
        db.session.commit()
        january=self.get().json['Data']['Items'][0]
        self.assertEqual((january['month_consumption'],january['month_settlement']),(6000,5000))
        february=self.get('2026-02').json['Data']['Items'][0]
        self.assertEqual((february['month_consumption'],february['month_refund'],february['month_settlement']),(0,6000,-5000))
        self.assertEqual(january['remaining'],12000)  # Current balance restored by refund, not historical snapshot.

    def test_aggregated_cross_batch_entry_matches_allocations_before_paging(self):
        a=self.batch(1,12000,10000);b=self.batch(2,10000,5000)
        for batch,face,principal,state in ((a,6000,5000,'returned'),(b,3000,1500,'consumed')):
            db.session.add(SettlementAllocation(biz_key=f'fixture:{batch.id}',batch_id=batch.id,kind='wallet',
                open_id='p',reference='pay:1',store_id=1,amount=face,principal=principal,state=state))
        self.entry('mock:aggregate',a,'2026-01',9000,6500)
        db.session.commit()
        r=self.get(PageSize=1).json['Data']
        self.assertEqual(r['Total'],2)
        self.assertEqual(r['Items'][0]['id'],2)
        self.assertEqual((r['Items'][0]['month_consumption'],r['Items'][0]['month_settlement']),(3000,1500))
        second=self.get(PageSize=1,Current=2).json['Data']['Items'][0]
        self.assertEqual((second['month_consumption'],second['month_settlement']),(6000,5000))

    def test_report_snapshot_used_instead_of_changed_live_ledger(self):
        a=self.batch(1,12000,10000)
        self.entry('first:batch:1',a,'2026-01',6000,5000)
        db.session.commit();reports.generate('2026-01',1,'wallet-metric-report')
        self.entry('later:batch:1',a,'2026-01',1200,1000)
        db.session.commit()
        data=self.get().json['Data']
        self.assertEqual(data['ReportStatus'],'draft')
        self.assertEqual(data['Items'][0]['month_settlement'],5000)

    def test_inconsistent_aggregated_amount_is_not_reported_as_zero(self):
        a=self.batch(1,12000,10000)
        db.session.add(SettlementAllocation(biz_key='bad',batch_id=a.id,kind='wallet',open_id='p',
            reference='pay:1',store_id=1,amount=6000,principal=5000,state='consumed'))
        self.entry('mock:bad',a,'2026-01',6000,4000)
        db.session.commit()
        self.assertEqual(self.get().status_code,400)

    def test_point_batch_keeps_responsibility_and_has_no_wallet_metrics(self):
        db.session.add(SettlementBatch(kind='point',open_id='p',source_key='points',face_total=100,
            remaining=100,responsible_store_id=2));db.session.commit()
        r=self.client.get('/admin_api/settlement/v1/assets?Month=2026-01&Scope=all&Kind=point',headers=self.headers()).json['Data']['Items'][0]
        self.assertEqual(r['responsible_store_id'],2)
        self.assertNotIn('month_settlement',r)
