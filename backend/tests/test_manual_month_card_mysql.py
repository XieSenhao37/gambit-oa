"""Concurrent issuance tests, restricted to a disposable local MySQL database."""
import os
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from unittest.mock import patch
from sqlalchemy.engine import make_url
from app import create_app, db
from app.models import MonthCardOrder, User
from app.settlement.models import SettlementCardPool
from tests import test_month_card_settlement as fixtures


@unittest.skipUnless(os.getenv('MANUAL_CARD_TEST_URL'), 'isolated manual-card MySQL not configured')
class ManualCardMySQLTest(unittest.TestCase):
    def setUp(self):
        uri = make_url(os.environ['MANUAL_CARD_TEST_URL'])
        if uri.host != '127.0.0.1' or uri.port != 33318 or uri.database != 'gambit_manual_card_test':
            raise RuntimeError('Only the dedicated local card database may be reset')
        with patch('tests.test_month_card_settlement.create_app',
                   side_effect=lambda config: create_app({**config, 'SQLALCHEMY_DATABASE_URI': uri})):
            fixtures.MonthlyCardsTest.setUp(self)

    tearDown = fixtures.MonthlyCardsTest.tearDown
    headers = fixtures.MonthlyCardsTest.headers

    def concurrent(self, keys):
        barrier = Barrier(len(keys))
        def request(key):
            with self.app.test_client() as client:
                barrier.wait(timeout=10)
                return client.post('/admin_api/month-card/v1/manual-open', headers=self.headers(),
                    json=dict(UserId=3, OpenMonths=1, ExpectedPrice=39900, RequestKey=key))
        with ThreadPoolExecutor(max_workers=len(keys)) as executor:
            responses = list(executor.map(request, keys))
        db.session.remove()
        for response in responses:
            self.assertEqual(response.status_code, 200, response.json)
        return responses

    def test_same_request_only_opens_once_under_concurrency(self):
        key = str(uuid.uuid4())
        responses = self.concurrent([key, key])
        self.assertEqual(responses[0].json['Data']['Id'], responses[1].json['Data']['Id'])
        self.assertEqual(MonthCardOrder.query.count(), 1)
        self.assertEqual(SettlementCardPool.query.count(), 1)
        pool = SettlementCardPool.query.one()
        self.assertEqual(db.session.get(User, 3).month_card_expire, pool.ends_at)

    def test_separate_requests_renew_without_lost_days(self):
        self.concurrent([str(uuid.uuid4()), str(uuid.uuid4())])
        pools = SettlementCardPool.query.order_by(SettlementCardPool.starts_at).all()
        self.assertEqual(len(pools), 2)
        self.assertEqual(pools[0].ends_at, pools[1].starts_at)
        self.assertEqual(pools[1].ends_at - pools[0].starts_at, timedelta(days=60))
        self.assertEqual(db.session.get(User, 3).month_card_expire, pools[1].ends_at)

    def test_concurrent_renewals_read_current_expiry(self):
        expires = datetime(2027, 1, 1)
        db.session.get(User, 3).month_card_expire = expires
        db.session.commit()
        self.concurrent([str(uuid.uuid4()), str(uuid.uuid4())])
        self.assertEqual(db.session.get(User, 3).month_card_expire, expires + timedelta(days=60))

    def test_concurrent_batch_retry_only_opens_once(self):
        key = str(uuid.uuid4())
        barrier = Barrier(2)
        def send(ids):
            with self.app.test_client() as client:
                barrier.wait(timeout=10)
                return client.post('/admin_api/month-card/v1/manual-open-batch',headers=self.headers(),
                    json=dict(UserIds=ids,OpenMonths=1,ExpectedPrice=39900,RequestKey=key))
        with patch('app.api.v1.month_card._now',return_value=datetime(2026,1,31,12,0,0,750000)):
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses=list(executor.map(send,[[2,3],[3,2]]))
        db.session.remove()
        for response in responses:
            self.assertEqual(response.status_code,200,response.json)
        self.assertEqual(responses[0].json['Data'],responses[1].json['Data'])
        self.assertEqual(MonthCardOrder.query.count(),2)
        self.assertEqual(SettlementCardPool.query.count(),2)

    def test_same_batch_key_cannot_be_reused_for_disjoint_users_without_settlement(self):
        with patch.dict(os.environ,{'STORE_SETTLEMENT_ENABLED':'false'}):
            key = str(uuid.uuid4())
            barrier = Barrier(2)
            def send(uid):
                with self.app.test_client() as client:
                    barrier.wait(timeout=10)
                    return client.post('/admin_api/month-card/v1/manual-open-batch',headers=self.headers(),
                        json=dict(UserIds=[uid],OpenMonths=1,ExpectedPrice=39900,RequestKey=key))
            with ThreadPoolExecutor(max_workers=2) as executor:
                responses=list(executor.map(send,[2,3]))
            db.session.remove()
            self.assertEqual(sorted(r.status_code for r in responses),[200,400])
            self.assertEqual(MonthCardOrder.query.count(),1)
