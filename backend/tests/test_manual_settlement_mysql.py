"""Run complete report regressions and races on a dedicated disposable MySQL database."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from sqlalchemy.engine import make_url
from sqlalchemy import text
from app import db
from app.settlement import reports
from app.settlement.models import SettlementReport, SettlementEntry, SettlementCardPeriod, SettlementStatement
from tests import test_manual_settlement_reports as manual
from tests import test_settlement as fixtures
from tests import test_settlement_cash as cash_tests


@unittest.skipUnless(os.getenv('MANUAL_SETTLEMENT_TEST_URL'), 'isolated manual settlement MySQL not configured')
class ManualMySQLTest(manual.ManualReportsTest):
    def setUp(self):
        uri=make_url(os.environ['MANUAL_SETTLEMENT_TEST_URL'])
        if uri.host != '127.0.0.1' or uri.port != 33317 or uri.database != 'gambit_manual_settlement_test':
            raise RuntimeError('Only the dedicated local report database may be reset')
        create=fixtures.create_app
        with patch.object(fixtures,'create_app',side_effect=lambda config: create({**config,'SQLALCHEMY_DATABASE_URI':uri})):
            super().setUp()

    def race(self, job):
        barrier=Barrier(2)
        def run(i):
            with self.app.app_context():
                try:
                    # Force a stale REPEATABLE READ snapshot before competing for the control lock.
                    SettlementReport.query.count()
                    barrier.wait(timeout=10)
                    result=job(i);db.session.commit();return result
                except Exception:
                    db.session.rollback();raise
                finally:db.session.remove()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run,range(2)))

    def test_concurrent_generation_same_request_and_confirmation_are_idempotent(self):
        p=self.pool();self.usage(p,1);db.session.commit()
        key=str(uuid.uuid4())
        results=self.race(lambda _: reports.generate('2026-01',1,key).id)
        self.assertEqual(results[0],results[1]);db.session.expire_all()
        r=db.session.get(SettlementReport,results[0]);identity=r.id;checksum=r.digest;db.session.commit()
        self.race(lambda _: reports.confirm(identity,checksum,1,{'1':'proof'},True).id)
        db.session.expire_all()
        self.assertEqual(SettlementReport.query.count(),1)
        self.assertEqual(SettlementEntry.query.count(),1)
        self.assertEqual(SettlementCardPeriod.query.count(),1)
        self.assertEqual(SettlementStatement.query.count(),1)

    def test_two_distinct_generation_requests_cannot_both_be_active(self):
        def job(_):
            try:return reports.generate('2026-01',1,str(uuid.uuid4())).id
            except ValueError:return 'already-generated'
        result=self.race(job)
        self.assertEqual(result.count('already-generated'),1)
        db.session.expire_all();self.assertEqual(SettlementReport.query.filter_by(status='draft').count(),1)

    def test_additive_report_migration_is_reentrant(self):
        from pathlib import Path
        from sqlalchemy import inspect
        SettlementReport.__table__.drop(db.engine)
        sql=(Path(__file__).resolve().parents[1]/'migrations/20260927_manual_settlement_reports.sql').read_text()
        with db.engine.begin() as connection:
            connection.execute(text(sql));connection.execute(text(sql))
        self.assertEqual({c['name'] for c in inspect(db.engine).get_columns('settlement_reports')},
                         {c.name for c in SettlementReport.__table__.columns})
        r=self.generate().json['Data'];self.assertEqual(self.confirm(r).status_code,200)

    def test_cost_edit_checks_current_report_after_stale_snapshot(self):
        e=self.cost();self.save_cost(e)
        self.assertEqual(SettlementReport.query.count(),0)
        with ThreadPoolExecutor(max_workers=1) as pool:
            def generate_other():
                with self.app.app_context():
                    reports.generate('2026-01',1,str(uuid.uuid4()));db.session.commit();db.session.remove()
            pool.submit(generate_other).result(timeout=10)
        with self.assertRaisesRegex(ValueError,'报表'):reports.assert_editable('expense',e.id)
        db.session.rollback()


@unittest.skipUnless(os.getenv('MANUAL_SETTLEMENT_TEST_URL'), 'isolated cash settlement MySQL not configured')
class CashMySQLTest(cash_tests.CashSettlementTest):
    def setUp(self):
        uri=make_url(os.environ['MANUAL_SETTLEMENT_TEST_URL'])
        if uri.host != '127.0.0.1' or uri.port != 33317 or uri.database != 'gambit_manual_settlement_test':
            raise RuntimeError('Only the dedicated local report database may be reset')
        create=fixtures.create_app
        with patch.object(fixtures,'create_app',side_effect=lambda config: create({**config,'SQLALCHEMY_DATABASE_URI':uri})):
            super().setUp()

    race = ManualMySQLTest.race

    def test_concurrent_cash_report_and_confirm(self):
        self.payment();key=str(uuid.uuid4())
        ids=self.race(lambda _: reports.generate('2026-01',1,key).id)
        self.assertEqual(ids[0],ids[1]);db.session.expire_all()
        r=db.session.get(SettlementReport,ids[0]);identity=r.id;checksum=r.digest;db.session.commit()
        self.race(lambda _:reports.confirm(identity,checksum,1,{'1':'proof'},True).id)
        db.session.expire_all()
        self.assertEqual(SettlementEntry.query.filter_by(biz_key='wechat:pay:1').count(),1)
        self.assertEqual(SettlementStatement.query.one().amount,9940)

    def test_stale_transaction_cannot_pay_confirmed_cash_again(self):
        from app.settlement import cash
        self.payment()
        SettlementEntry.query.count()
        def other():
            with self.app.app_context():
                try:
                    r=reports.generate('2026-01',1,str(uuid.uuid4()))
                    reports.confirm(r.id,r.digest,1,{'1':'proof'},True)
                    db.session.commit()
                finally:db.session.remove()
        with ThreadPoolExecutor(max_workers=1) as pool:pool.submit(other).result(timeout=10)
        self.assertEqual(cash.candidates('2026-02',strict=True),[])
        db.session.rollback()


from tests import test_settlement_fees as fee_tests

@unittest.skipUnless(os.getenv('MANUAL_SETTLEMENT_TEST_URL'), 'isolated manual settlement MySQL not configured')
class FeeMySQLTest(fee_tests.FeeSettlementTest):
    def setUp(self):
        uri=make_url(os.environ['MANUAL_SETTLEMENT_TEST_URL'])
        if uri.host != '127.0.0.1' or uri.port != 33317 or uri.database != 'gambit_manual_settlement_test':
            raise RuntimeError('Only the dedicated local report database may be reset')
        create=fixtures.create_app
        with patch.object(fixtures,'create_app',side_effect=lambda config: create({**config,'SQLALCHEMY_DATABASE_URI':uri})):
            super().setUp()
