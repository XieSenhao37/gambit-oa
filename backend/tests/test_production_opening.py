"""Production launch policy, exercised only against isolated SQLite data."""
import unittest
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch
from app import db
from app.models import User, MonthCardOrder, WalletAccount, WalletRechargeOrder, WalletTransaction, PayOrder, PointAccount
from app.settlement.models import SettlementControl, SettlementBatch, SettlementEntry, SettlementCardPool, SettlementCardUsage, SettlementCardPeriod
from app.settlement.opening import initialize
from app.settlement import cards, reports
from tests import test_settlement as fixtures


class ProductionOpeningTest(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.SettlementTest()
        self.fixture.setUp()
        db.session.delete(db.session.get(SettlementControl,1))
        db.session.commit()
        self.cutoff=datetime(2026,10,6,12)
        self.clock=patch('app.settlement.opening.now',return_value=self.cutoff)
        self.clock.start()

    def tearDown(self):
        self.clock.stop()
        self.fixture.tearDown()

    def card(self,start,amount=39900,periods=1):
        user=User.query.filter_by(open_id='p').one()
        user.month_card_expire=start+timedelta(days=30*periods)
        db.session.add(MonthCardOrder(id=1,open_id='p',open_period=periods,amount=amount,
            duration_days=30*periods,open_type=1,source='wechat',settle_status=1,effective_at=start,created_at=start))
        db.session.commit()

    def test_remaining_card_term_no_old_usage_and_draft_does_not_post(self):
        self.card(datetime(2026,10,1,12))
        initialize(self.cutoff,1,'prospective')
        db.session.commit()
        pool=SettlementCardPool.query.one()
        self.assertEqual((pool.starts_at,pool.ends_at,pool.amount,pool.payer_id),
            (self.cutoff,datetime(2026,10,31,12),33250,1))
        self.assertEqual(SettlementCardUsage.query.count(),0)
        db.session.add(SettlementCardUsage(pool_id=pool.id,play_order_id=100,store_id=2,
            started_at=self.cutoff+timedelta(days=1),ended_at=self.cutoff+timedelta(days=1,hours=1),seconds=3600,status='valid'))
        db.session.commit()
        with patch('app.settlement.reports.now',return_value=datetime(2026,11,1)), patch('app.settlement.cards.now',return_value=datetime(2026,11,1)):
            report=reports.generate('2026-10',1,'production-opening-report-001')
        self.assertEqual(report.payload['coverage_start'],self.cutoff.isoformat())
        card_entries=[e for e in report.payload['entries'] if e['kind']=='month_card']
        self.assertEqual([(e['payer_id'],e['receiver_id'],e['amount']) for e in card_entries],[(1,2,33250)])
        self.assertEqual(SettlementEntry.query.count(),0)
        self.assertEqual(SettlementCardPeriod.query.count(),0)
        self.assertEqual(pool.status,'open')
        db.session.commit()
        references={str(t['StoreId']):'本地测试' for t in report.payload['totals'] if t['StoreId'] and t['amount']}
        reports.confirm(report.id,report.digest,1,references,True)
        self.assertEqual(SettlementCardPeriod.query.one().month,'2026-10')
        self.assertEqual(db.session.get(SettlementCardPool,pool.id).status,'closed')

    def test_future_terms_and_remaining_cents_are_conserved(self):
        self.card(datetime(2026,9,20,12),79801,2)
        initialize(self.cutoff,1,'prospective')
        pools=SettlementCardPool.query.order_by(SettlementCardPool.id).all()
        # Equal split retains the odd cent; only the already elapsed first term is removed.
        first=39901-39901*16//30
        self.assertEqual([p.amount for p in pools],[first,39900])
        self.assertEqual(pools[0].starts_at,self.cutoff)
        self.assertEqual(pools[1].starts_at,datetime(2026,10,20,12))
        self.assertEqual(sum(cards.window(p,m)[2] for p in pools for m in ['2026-10','2026-11'] if cards.window(p,m)),first+39900)

    def test_legacy_callback_seconds_use_existing_expiry_and_reject_other_drift(self):
        start=datetime(2026,10,1,12)
        self.card(start)
        order=MonthCardOrder.query.one();order.duration_days=0;order.effective_at=None
        user=User.query.filter_by(open_id='p').one()
        user.month_card_expire=datetime(2026,11,1,12,0,2)
        db.session.commit()
        with self.assertRaisesRegex(ValueError,'无法对应原始卡期'):
            initialize(self.cutoff,1,'prospective')
        db.session.rollback()
        output=initialize(self.cutoff,1,'prospective',legacy_card_end_tolerance_seconds=2)
        self.assertEqual(output['AdjustedCardEndUserIds'],[user.id])
        self.assertEqual(SettlementCardPool.query.one().ends_at,user.month_card_expire)
        db.session.rollback()
        user.month_card_expire=datetime(2026,11,1,12,0,3);db.session.commit()
        with self.assertRaisesRegex(ValueError,'无法对应原始卡期'):
            initialize(self.cutoff,1,'prospective',legacy_card_end_tolerance_seconds=2)
        db.session.rollback()

    def test_wallet_discount_ratio_points_nanshan_and_preview_rollback(self):
        at=datetime(2026,9,1)
        db.session.add_all([WalletAccount(id=1,open_id='p',balance=60000,frozen_balance=0),
            WalletRechargeOrder(id=1,open_id='p',amount=100000,bonus_amount=20000,status=1),
            PayOrder(id=1,open_id='p',store_id=2,amount=60000,pay_status=1,pay_type=3),
            PointAccount(id=1,open_id='p',balance=70)])
        for i,typ,amount,before,after in [(1,'recharge',100000,0,100000),(2,'bonus',20000,100000,120000),(3,'consume',60000,120000,60000)]:
            db.session.add(WalletTransaction(id=i,created_at=at,open_id='p',account_id=1,type=typ,
                direction='out' if typ=='consume' else 'in',amount=amount,balance_before=before,balance_after=after,
                frozen_before=0,frozen_after=0,biz_key=f'old-wallet:{i}',
                related_recharge_order_id=1 if i<3 else None,related_pay_order_id=1 if i==3 else None))
        db.session.commit()
        output=initialize(self.cutoff,1,'prospective')
        self.assertEqual((output['WalletFace'],output['WalletPrincipal'],output['Points'],output['HistoricalEntries']),(60000,50000,70,0))
        self.assertTrue(all((b.source_store_id,b.responsible_store_id)==(1,1) for b in SettlementBatch.query.all()))
        self.assertEqual(SettlementEntry.query.count(),0)
        db.session.rollback()
        self.assertEqual(SettlementBatch.query.count(),0)
        self.assertEqual(WalletAccount.query.one().balance,60000)
        self.assertEqual(PointAccount.query.one().balance,70)
        initialize(self.cutoff,1,'prospective');db.session.commit()
        self.assertTrue(initialize(self.cutoff,1,'prospective')['AlreadyInitialized'])

    def test_reject_wrong_payer_and_partial_existing_book(self):
        with self.assertRaisesRegex(ValueError,'统一为南山'):
            initialize(self.cutoff,0,'prospective')
        db.session.add(SettlementBatch(kind='point',open_id='p',source_key='partial',face_total=1,remaining=1))
        db.session.commit()
        with self.assertRaisesRegex(ValueError,'结算账已有记录'):
            initialize(self.cutoff,1,'prospective')

    def test_backdating_cannot_skip_existing_asset_changes(self):
        self.card(datetime(2026,10,2))
        with self.assertRaisesRegex(ValueError,'切换点之后'):
            initialize(datetime(2026,10,1),1,'prospective')

    def test_production_cli_rejects_wrong_rules_before_connection(self):
        script=Path(__file__).resolve().parents[1]/'scripts/migrate_settlement.py'
        cases=[([], '必须明确'),
            (['--cutoff','2026-11-01 00:00:00'],'实际切换月份'),
            (['--cutoff','2026-10-06 12:00:00','--legacy-wallet-payer','headquarters'],'固定南山'),
            (['--cutoff','2026-10-06 12:00:00'],'只允许已核对')]
        # A SQLite URL fails the production target guard without opening any connection.
        for extra,message in cases:
            proc=subprocess.run([sys.executable,str(script),'preview','--production-launch',
                '--report','/tmp/gambit-opening-cli-not-written.json',*extra],
                env={**os.environ,'SETTLEMENT_DATABASE_URL':'sqlite://'},capture_output=True,text=True)
            self.assertEqual(proc.returncode,2)
            self.assertIn(message,proc.stderr)


if __name__=='__main__':unittest.main()
