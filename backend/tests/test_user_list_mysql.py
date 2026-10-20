"""User list regression for real MySQL mixed collations; disposable local DB only."""
import os
import unittest
from datetime import datetime
from unittest.mock import patch
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from app import create_app, db
from app.models import User, WalletAccount, PointAccount, PayOrder, PlayOrder
from tests import test_settlement as fixtures


@unittest.skipUnless(os.getenv('USER_LIST_TEST_URL'), 'isolated user-list MySQL not configured')
class UserListMySQLTest(unittest.TestCase):
    def setUp(self):
        uri = make_url(os.environ['USER_LIST_TEST_URL'])
        if uri.host != '127.0.0.1' or uri.port != 33319 or uri.database != 'gambit_user_list_test':
            raise RuntimeError('Only the dedicated local user-list database may be reset')
        with patch('tests.test_settlement.create_app',
                   side_effect=lambda config: create_app({**config, 'SQLALCHEMY_DATABASE_URI': uri})):
            fixtures.SettlementTest.setUp(self)
        self.addCleanup(fixtures.SettlementTest.tearDown, self)
        db.session.execute(text('ALTER TABLE users MODIFY open_id VARCHAR(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci NOT NULL'))
        db.session.execute(text('ALTER TABLE wallet_accounts MODIFY open_id VARCHAR(60) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci NOT NULL'))
        db.session.add(WalletAccount(open_id='p', balance=12500))
        db.session.add(PointAccount(open_id='p', balance=80))
        db.session.add(PlayOrder(id=1,open_id='p',store_id=2,in_time=datetime(2026,1,1)))
        db.session.flush()
        db.session.add(PayOrder(open_id='p',amount=2400,pay_status=1,pay_type=0,play_order_id=1,store_id=2))
        db.session.get(User, 3).registered_store_id = 2
        db.session.commit()

    headers = fixtures.SettlementTest.headers

    def request_list(self, params='', user=1, store=2):
        response = self.client.get('/admin_api/user/v1/list' + params, headers=self.headers(user, store))
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['Data']

    def test_original_join_reproduces_1267_and_fixed_list_keeps_metrics(self):
        with self.assertRaises(OperationalError) as failure:
            db.session.query(User.id).outerjoin(WalletAccount, WalletAccount.open_id == User.open_id).all()
        self.assertEqual(failure.exception.orig.args[0], 1267)
        db.session.rollback()
        data = self.request_list()
        self.assertEqual(data['Total'], 3)
        player = next(row for row in data['Items'] if row['Id'] == 3)
        self.assertEqual((player['WalletBalance'], player['PointBalance'], player['TotalConsumptionAmount']), (12500, 80, 2400))

    def test_balance_sort_and_pagination_under_mixed_collations(self):
        data = self.request_list('?SortField=WalletBalance&SortOrder=desc&PageSize=1')
        self.assertEqual((data['Total'], data['Items'][0]['Id']), (3, 3))
        data = self.request_list('?SortField=WalletBalance&SortOrder=asc&Current=2&PageSize=2')
        self.assertEqual((data['Total'], data['Items'][0]['Id']), (3, 3))
        data = self.request_list('?SortField=TotalConsumptionAmount&SortOrder=desc&PageSize=1')
        self.assertEqual(data['Items'][0]['TotalConsumptionAmount'], 2400)

    def test_store_scope_and_filter_still_apply(self):
        data = self.request_list(user=2, store=2)
        self.assertEqual([row['Id'] for row in data['Items']], [3])
        self.assertEqual(self.request_list('?Id=1', user=2, store=2)['Items'], [])
        self.assertEqual(self.request_list('?Id=3')['Items'][0]['WalletBalance'], 12500)

    def test_deleted_wallet_does_not_contribute(self):
        WalletAccount.query.one().deleted_at = datetime(2026, 1, 1)
        db.session.commit()
        self.assertEqual(self.request_list('?Id=3')['Items'][0]['WalletBalance'], 0)
