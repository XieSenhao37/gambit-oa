"""Opt-in MySQL locking regression checks; only a disposable local database is allowed."""
import os
import unittest
import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.engine import make_url
from app import create_app, db
from app.settlement.models import SettlementEntry, SettlementPeriod, SettlementStatement, SettlementBatch, SettlementAllocation, SettlementExpense
from app.settlement import service, reports


@unittest.skipUnless(os.getenv('SETTLEMENT_LOCK_TEST_URL'), 'isolated settlement MySQL not configured')
class SettlementMySQLTest(unittest.TestCase):
    def setUp(self):
        uri=make_url(os.environ['SETTLEMENT_LOCK_TEST_URL'])
        if uri.host!='127.0.0.1' or uri.port!=33316 or uri.database!='gambit_settlement_lock_test':
            raise RuntimeError('Only the dedicated local test database may be reset')
        self.app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':uri})
        self.ctx=self.app.app_context();self.ctx.push()
        # Only our own settlement tables are needed; the unfinished-visit check is unused.
        for table in db.metadata.sorted_tables:
            if table.name.startswith('settlement_') or table.name == 'stores':
                table.create(db.engine,checkfirst=True)
                db.session.execute(table.delete())
        from app.settlement.models import SettlementControl
        db.session.add(SettlementControl(id=1,cutoff=datetime(2026,1,1),initialized_at=datetime(2026,1,1),legacy_wallet_payer=0,legacy_card_policy='full-period'))
        db.session.commit()

    def tearDown(self):
        db.session.remove();self.ctx.pop()

    def entry(self,key,amount):
        service.add_entry(biz_key=key,kind='wallet',reference=key,payer_id=0,receiver_id=1,amount=amount,event_at=datetime(2026,1,5),detail='local fixture')

    def test_period_lock_refreshes_cached_draft(self):
        self.entry('first',100);db.session.commit()
        cached=db.session.get(SettlementPeriod,'2026-01')
        self.assertEqual(cached.status,'draft')
        with db.engine.begin() as other:
            other.execute(text("UPDATE settlement_periods SET status='locked' WHERE month='2026-01'"))
        self.entry('late',200);db.session.flush()
        self.assertEqual(SettlementEntry.query.filter_by(biz_key='late').one().month,'2026-02')
        db.session.rollback()

    def test_month_lock_uses_current_read_not_earlier_snapshot(self):
        self.entry('first',100);db.session.commit()
        # Establish a REPEATABLE READ snapshot, as the pre-lock pool scans do.
        self.assertEqual(SettlementEntry.query.count(),1)
        with db.engine.begin() as other:
            other.execute(SettlementEntry.__table__.insert().values(biz_key='concurrent',kind='wallet',reference='pay:2',payer_id=0,receiver_id=1,amount=200,event_at=datetime(2026,1,6),month='2026-01',detail='concurrent local fixture'))
        r=reports.generate('2026-01',1,str(uuid.uuid4()))
        reports.confirm(r.id,r.digest,1,{'1':'local proof'},True);db.session.flush()
        self.assertEqual(SettlementStatement.query.one().amount,300)
        db.session.commit()

    def test_expense_includes_sources_committed_after_earlier_snapshot(self):
        for sid,points in ((1,60),(2,40)):
            db.session.add(SettlementBatch(id=sid,kind='point',open_id=f'local-{sid}',source_key=f'point-{sid}',face_total=points,remaining=0,responsible_store_id=sid))
        db.session.add(SettlementAllocation(biz_key='entry-1',batch_id=1,kind='point',open_id='local-1',reference='entry-1',expense_key='raffle:1',amount=60,state='consumed'))
        e=SettlementExpense(expense_key='raffle:1',kind='raffle',source_id=1,amount=5000,provider_id=2,status='pending')
        db.session.add(e);db.session.commit()
        self.assertEqual(e.status,'pending')
        with db.engine.begin() as other:
            other.execute(SettlementAllocation.__table__.insert().values(biz_key='entry-2',batch_id=2,kind='point',open_id='local-2',reference='entry-2',expense_key='raffle:1',amount=40,state='consumed'))
            other.execute(SettlementExpense.__table__.update().where(SettlementExpense.id==e.id).values(status='ready',completed_at=datetime(2026,1,5)))
        service.post_expense(e.id);db.session.flush()
        self.assertEqual(service.totals('2026-01')[1]['amount'],-3000)
        self.assertEqual(service.totals('2026-01')[2]['amount'],3000)
        db.session.commit()
