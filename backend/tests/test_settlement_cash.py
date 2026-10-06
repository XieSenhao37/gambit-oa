"""Unified monthly cash settlement using isolated fixture accounts only."""
import uuid
import unittest
from datetime import datetime
from app import db
from app.models import PayOrder, PlayOrder, RefundRequest
from app.settlement import cash, reports
from app.settlement.models import SettlementEntry, SettlementStatement
from tests import test_settlement as fixtures


class CashSettlementTest(unittest.TestCase):
    setUp = fixtures.SettlementTest.setUp
    tearDown = fixtures.SettlementTest.tearDown
    headers = fixtures.SettlementTest.headers

    def payment(self, identity=1, store=1, amount=10000, wallet=0, at=None, **values):
        at = at or datetime(2026, 1, 15, 12)
        db.session.add(PlayOrder(id=identity, store_id=store or 1, open_id='p', in_time=at))
        db.session.flush()
        args=dict(id=identity, open_id='p', store_id=store, amount=amount,
            wallet_amount=wallet, wechat_amount=amount-wallet, pay_type=4 if wallet else 0,
            pay_status=1, pay_end_time=at, created_at=at, play_order_id=identity)
        args.update(values)
        p=PayOrder(**args);db.session.add(p);db.session.commit();return p

    def refund(self, p, at=None, status='refunded'):
        r=RefundRequest(id=p.id,open_id=p.open_id,order_type='play',order_id=p.play_order_id or p.catering_id,
            pay_order_id=p.id,amount=p.amount,status=status,refunded_at=at or datetime(2026,1,20))
        if status=='refunded':
            p.pay_status=3;p.wechat_refund_amount=p.wechat_amount;p.wallet_refund_amount=p.wallet_amount
        db.session.add(r);db.session.commit();return r

    def generate(self, month='2026-01'):
        r=reports.generate(month,1,str(uuid.uuid4()));db.session.commit();return r

    def confirm(self,r):
        refs={str(t['StoreId']):'隔离测试凭证' for t in r.payload['totals'] if t['StoreId'] and t['amount']}
        reports.confirm(r.id,r.digest,1,refs,True);db.session.commit()

    def test_mixed_payment_only_cash_leg_no_recharge_or_card_or_deposit(self):
        self.payment(wallet=4000)
        self.payment(2,month_card_order_id=2)
        self.payment(3,wallet_recharge_order_id=3)
        self.payment(4,group_activity_participant_id=4)
        self.payment(5,pay_type=3,wallet=10000)
        rows=cash.candidates('2026-01')
        self.assertEqual([(r['biz_key'],r['amount']) for r in rows],[('wechat:pay:1',6000)])
        self.assertEqual(SettlementEntry.query.count(),0)

    def test_preview_snapshot_confirmation_and_retry_do_not_double_settle(self):
        self.payment();r=self.generate()
        self.assertEqual(SettlementEntry.query.count(),0);self.assertEqual(SettlementStatement.query.count(),0)
        self.assertEqual(next(t['amount'] for t in r.payload['totals'] if t['StoreId']==1),9940)
        self.confirm(r);self.confirm(r)
        self.assertEqual(SettlementEntry.query.count(),2);self.assertEqual(SettlementStatement.query.one().amount,9940)
        self.assertEqual(cash.candidates('2026-02',strict=True),[])

    def test_cross_month_refund_preserves_original_report(self):
        p=self.payment(wallet=4000);jan=self.generate();self.confirm(jan)
        frozen=jan.digest
        self.refund(p,datetime(2026,2,2));feb=self.generate('2026-02')
        entries=feb.payload['entries'];self.assertEqual([(e['kind'],e['amount']) for e in entries],[('wechat_refund',-6000),('settlement_fee',-36)])
        self.confirm(feb)
        self.assertEqual(jan.digest,frozen)
        self.assertEqual(SettlementStatement.query.filter_by(month='2026-01',store_id=1).one().amount,5964)
        self.assertEqual(SettlementStatement.query.filter_by(month='2026-02',store_id=1).one().amount,-5964)

    def test_refund_after_generation_is_carried_without_rewriting_snapshot(self):
        p=self.payment();r=self.generate();original=reports.public(r)
        self.refund(p)
        self.assertEqual(reports.public(r),original)
        self.confirm(r)
        later=self.generate('2026-02')
        self.assertEqual(later.payload['entries'][0]['amount'],-10000)
        self.assertIn('2026-01',later.payload['entries'][0]['detail'])

    def test_same_month_refund_and_pending_refund(self):
        p=self.payment();self.refund(p)
        pending=self.payment(2);self.refund(pending,status='refunding')
        r=self.generate();self.confirm(r)
        self.assertEqual(SettlementStatement.query.one().amount,9940)
        self.assertEqual(SettlementEntry.query.count(),4)

    def test_late_payment_and_month_order(self):
        self.payment()
        with self.assertRaisesRegex(ValueError,'先结算'):self.generate('2026-02')
        db.session.rollback()
        jan=self.generate();self.confirm(jan)
        self.payment(2)
        feb=self.generate('2026-02');self.confirm(feb)
        self.assertEqual(SettlementStatement.query.filter_by(month='2026-02').one().amount,9940)

    def test_cutoff_and_exact_month_boundary(self):
        self.payment(at=datetime(2025,12,31,23,59,59))
        self.payment(2,at=datetime(2026,1,1))
        self.payment(3,at=datetime(2026,2,1))
        self.assertEqual([r['biz_key'] for r in cash.candidates('2026-01')],['wechat:pay:2'])
        with self.assertRaisesRegex(ValueError,'启用月份'):self.generate('2025-12')

    def test_missing_store_and_contradictory_refund_block_report(self):
        p=self.payment(store=None)
        with self.assertRaisesRegex(ValueError,'有效门店'):self.generate()
        db.session.rollback();p.store_id=1;db.session.commit()
        self.refund(p);p.wechat_refund_amount=1;db.session.commit()
        with self.assertRaisesRegex(ValueError,'拆分不一致'):self.generate()

    def test_store_scope_preview_and_frozen_report_export(self):
        self.payment();self.payment(2,store=2,play_order_id=None,catering_id=2)
        path='/admin_api/settlement/v1/'
        def get(url):return self.client.get(path+url,headers=self.headers(2,2))
        own=get('overview?Month=2026-01&Scope=all').json['Data']
        self.assertEqual([t['StoreId'] for t in own['Totals']],[2])
        self.assertEqual(set(own['Breakdown']),{'2'})
        self.assertEqual(get('cash?Month=2026-01&Scope=all').json['Data']['Total'],1)
        r=self.generate();view=reports.public(r,2)
        self.assertEqual(set(view['Breakdown']),{2})
        exported=get(f'export?Month=2026-01&ReportId={r.id}').data.decode('utf-8-sig')
        self.assertIn('pay:2',exported);self.assertNotIn('pay:1',exported)

    def test_breakdown_components_conserve_net(self):
        p=self.payment();self.refund(p);self.payment(2,store=2)
        rows=cash.candidates('2026-01')
        parts=cash.breakdown(rows)
        for t in reports.summarize(rows):self.assertEqual(sum(parts[t['StoreId']].values()),t['amount'])

    def test_cash_sources_added_after_void_are_recalculated(self):
        self.payment();old=self.generate()
        reports.void(old.id,old.digest);db.session.commit()
        self.payment(2);new=self.generate()
        self.assertEqual(new.version,2);self.assertEqual(len(new.payload['entries']),3)
        self.assertEqual(len(old.payload['entries']),2)
