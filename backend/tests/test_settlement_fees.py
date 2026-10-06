"""Fixed monthly fee: exemptions, rounding, immutable reporting and access scope."""
import unittest
from datetime import datetime
from app import db
from app.models import MonthCardOrder, PlayOrder
from app.settlement import fees, reports, service, cash
from app.settlement.models import SettlementEntry, SettlementStatement
from tests import test_settlement as fixtures
from tests import test_settlement_cash as cash_tests


class FeeSettlementTest(unittest.TestCase):
    setUp = fixtures.SettlementTest.setUp
    tearDown = fixtures.SettlementTest.tearDown
    headers = fixtures.SettlementTest.headers
    pool = fixtures.SettlementTest.pool
    usage = fixtures.SettlementTest.usage
    payment = cash_tests.CashSettlementTest.payment
    generate = cash_tests.CashSettlementTest.generate
    confirm = cash_tests.CashSettlementTest.confirm

    def row(self, kind, amount, receiver=1, payer=0, reference='test'):
        return dict(kind=kind, amount=amount, payer_id=payer, receiver_id=receiver, reference=reference)

    def test_aggregate_rounding_not_each_payment_and_signed_refunds(self):
        details, rows = fees.calculate('2026-01', [self.row('wechat_play',50), self.row('wechat_catering',50)])
        self.assertEqual(details,[dict(StoreId=1,Base=100,RateBps=60,Fee=1)])
        self.assertEqual(rows[0]['amount'],1)
        details, _ = fees.calculate('2026-02',[self.row('wechat_refund',-100)])
        self.assertEqual(details[0]['Fee'],-1)
        self.assertEqual(fees.calculate('2026-01',[self.row('wallet',250)])[0][0]['Fee'],2)
        self.assertEqual(fees.calculate('2026-01',[self.row('wallet_refund',-250)])[0][0]['Fee'],-2)

    def test_channel_exemptions_and_missing_source_rejected(self):
        p=self.pool();order=db.session.get(MonthCardOrder,p.order_id)
        row=self.row('month_card',39900,reference=f'card:{p.id}')
        for source in ('gift','third_party','meituan','storage_gift'):
            order.source=source;db.session.flush()
            self.assertEqual(fees.calculate('2026-01',[row])[0][0]['Fee'],0)
        order.source='wechat';db.session.flush()
        self.assertEqual(fees.calculate('2026-01',[row])[0][0]['Fee'],239)
        order.source='other';db.session.flush()
        with self.assertRaisesRegex(ValueError,'渠道'):fees.calculate('2026-01',[row])
        with self.assertRaisesRegex(ValueError,'原始开卡订单'):
            fees.calculate('2026-01',[self.row('month_card',100,reference='card:999')])

    def test_points_do_not_reduce_base_or_increase_provider_fee(self):
        rows=[self.row('wechat_play',10000),self.row('wallet',6000),
            self.row('point_cost',30000,payer=1,receiver=2)]
        details,charges=fees.calculate('2026-01',rows)
        self.assertEqual({d['StoreId']:(d['Base'],d['Fee']) for d in details},{1:(16000,96),2:(0,0)})
        combined=rows+charges
        self.assertEqual({t['StoreId']:t['amount'] for t in reports.summarize(combined)},
            {0:-15904,1:-14096,2:30000})
        parts=cash.breakdown(combined)
        for t in reports.summarize(combined):
            self.assertEqual(sum(parts[t['StoreId']].values()),t['amount'])

    def test_online_card_cash_and_wallet_charge_once_snapshot_and_scoped_export(self):
        p=self.pool();db.session.get(MonthCardOrder,p.order_id).source='wechat'
        self.usage(p,1);db.session.commit()
        self.payment(wallet=4000)
        db.session.get(PlayOrder,1).out_time=datetime(2026,1,15,13)
        service.add_entry(biz_key='wallet:sample',kind='wallet',reference='pay:1',payer_id=0,
            receiver_id=1,amount=3000,event_at=datetime(2026,1,15),detail='本金比例折算')
        db.session.commit();r=self.generate()
        self.assertEqual(r.payload['fees'],[dict(StoreId=1,Base=48900,RateBps=60,Fee=293)])
        self.assertEqual(SettlementEntry.query.count(),1)
        self.assertEqual(SettlementStatement.query.count(),0)
        self.assertEqual(reports.public(r,2)['Fees'],[])
        exported=self.client.get(f'/admin_api/settlement/v1/export?Month=2026-01&ReportId={r.id}',headers=self.headers()).data.decode('utf-8-sig')
        for text in ('0.6%','489.00','2.93','486.07'):self.assertIn(text,exported)
        self.confirm(r);self.confirm(r)
        self.assertEqual(SettlementEntry.query.filter_by(kind='settlement_fee').count(),1)
        self.assertEqual(SettlementStatement.query.one().amount,48607)

    def test_adjustments_follow_original_channel_without_fee_on_fee(self):
        service.add_entry(biz_key='original',kind='wallet',reference='pay:1',payer_id=0,
            receiver_id=1,amount=10000,event_at=datetime(2026,1,1),detail='original')
        db.session.flush();original=SettlementEntry.query.one()
        row=self.row('adjustment',-10000,reference=str(original.id))
        self.assertEqual(fees.calculate('2026-02',[row])[0][0]['Fee'],-60)
        original.kind='settlement_fee';db.session.flush()
        self.assertEqual(fees.calculate('2026-02',[row])[0][0]['Fee'],0)
        with self.assertRaisesRegex(ValueError,'不存在'):
            fees.calculate('2026-02',[self.row('adjustment',100,reference='999')])

    def test_old_draft_requires_regeneration_and_confirmed_snapshot_is_immutable(self):
        self.payment();r=self.generate();original=dict(r.payload)
        r.payload={k:v for k,v in original.items() if k!='fee_policy'};r.digest=reports.digest(r.payload)
        db.session.commit()
        with self.assertRaisesRegex(ValueError,'旧版报表'):self.confirm(r)
        db.session.rollback()
        r.payload=original;r.digest=reports.digest(original);db.session.commit()
        self.confirm(r);frozen=r.digest
        self.assertEqual(reports.public(r)['Fees'][0]['Fee'],60)
        self.confirm(r);self.assertEqual(r.digest,frozen)

    def test_headquarters_generation_includes_all_stores_and_manager_cannot_leak_fees(self):
        import uuid
        self.payment();self.payment(2,store=2)
        response=self.client.post('/admin_api/settlement/v1/prepare', headers=self.headers(),
            json={'Month':'2026-01','RequestKey':str(uuid.uuid4())})
        self.assertEqual(response.status_code,200,response.json)
        data=response.json['Data']
        self.assertEqual({f['StoreId']:f['Fee'] for f in data['Fees']},{1:60,2:60})
        own=self.client.get('/admin_api/settlement/v1/overview?Month=2026-01&Scope=all',headers=self.headers(2,2)).json['Data']
        self.assertEqual(own['Fees'],[dict(StoreId=2,Base=10000,RateBps=60,Fee=60)])
        self.assertEqual([t['StoreId'] for t in own['Totals']],[2])
        self.assertEqual(set(own['Report']['Breakdown']),{'2'})
