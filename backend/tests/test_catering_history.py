import unittest
from datetime import datetime, timedelta

from flask import Flask

from app import db
from app.api.v1.catering import get_catering_history
from app.models import Catering, PayOrder


class CateringHistoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Flask(__name__)
        cls.app.config.update(
            SQLALCHEMY_DATABASE_URI='sqlite:///:memory:',
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(cls.app)
        with cls.app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            db.session.remove()
            db.drop_all()

    def setUp(self):
        now = datetime(2026, 9, 5, 2, 0, 0)
        with self.app.app_context():
            db.session.query(PayOrder).delete()
            db.session.query(Catering).delete()

            refunded_order = Catering(
                id=101,
                created_at=now,
                updated_at=now,
                store_id=1,
                open_id='user-refunded',
                total_price=6800,
                status=2,
                settle_status=1,
                takeaway=False,
                code='A101',
            )
            no_payment_order = Catering(
                id=102,
                created_at=now + timedelta(minutes=1),
                updated_at=now + timedelta(minutes=1),
                store_id=1,
                open_id='user-no-payment',
                total_price=2800,
                status=0,
                settle_status=0,
                takeaway=True,
                code='A102',
            )
            pending_order = Catering(
                id=103,
                created_at=now + timedelta(minutes=2),
                updated_at=now + timedelta(minutes=2),
                store_id=1,
                open_id='user-pending',
                total_price=1800,
                status=0,
                settle_status=0,
                takeaway=False,
                code='A103',
            )
            paid_order = Catering(
                id=104,
                created_at=now + timedelta(minutes=3),
                updated_at=now + timedelta(minutes=3),
                store_id=1,
                open_id='user-paid',
                total_price=4800,
                status=2,
                settle_status=1,
                takeaway=False,
                code='A104',
            )
            closed_order = Catering(
                id=105,
                created_at=now + timedelta(minutes=4),
                updated_at=now + timedelta(minutes=4),
                store_id=1,
                open_id='user-closed',
                total_price=5800,
                status=0,
                settle_status=0,
                takeaway=False,
                code='A105',
            )
            other_store_order = Catering(
                id=201,
                created_at=now,
                updated_at=now,
                store_id=2,
                open_id='user-other-store',
                total_price=3800,
                status=1,
                settle_status=1,
                takeaway=False,
                code='B201',
            )
            db.session.add_all([
                refunded_order,
                no_payment_order,
                pending_order,
                paid_order,
                closed_order,
                other_store_order,
            ])
            db.session.flush()
            db.session.add_all([
                PayOrder(
                    id=1001,
                    created_at=now,
                    updated_at=now,
                    store_id=1,
                    open_id='user-refunded',
                    catering_id=101,
                    amount=6800,
                    wallet_amount=0,
                    wechat_amount=6800,
                    pay_status=1,
                    pay_type=0,
                ),
                PayOrder(
                    id=1002,
                    created_at=now + timedelta(minutes=2),
                    updated_at=now + timedelta(minutes=2),
                    store_id=1,
                    open_id='user-refunded',
                    catering_id=101,
                    amount=6800,
                    wallet_amount=0,
                    wechat_amount=6800,
                    refund_amount=6800,
                    pay_status=3,
                    pay_type=0,
                ),
                PayOrder(
                    id=1003,
                    created_at=now,
                    updated_at=now,
                    store_id=1,
                    open_id='user-pending',
                    catering_id=103,
                    amount=1800,
                    wallet_amount=0,
                    wechat_amount=1800,
                    pay_status=0,
                    pay_type=0,
                ),
                PayOrder(
                    id=1004,
                    created_at=now,
                    updated_at=now,
                    store_id=1,
                    open_id='user-paid',
                    catering_id=104,
                    amount=4800,
                    wallet_amount=0,
                    wechat_amount=4800,
                    pay_status=1,
                    pay_type=0,
                ),
                PayOrder(
                    id=1005,
                    created_at=now,
                    updated_at=now,
                    store_id=1,
                    open_id='user-closed',
                    catering_id=105,
                    amount=5800,
                    wallet_amount=0,
                    wechat_amount=5800,
                    pay_status=2,
                    pay_type=0,
                ),
                PayOrder(
                    id=2001,
                    created_at=now,
                    updated_at=now,
                    store_id=2,
                    open_id='user-other-store',
                    catering_id=201,
                    amount=3800,
                    wallet_amount=0,
                    wechat_amount=3800,
                    pay_status=1,
                    pay_type=0,
                ),
            ])
            db.session.commit()

    def request_history(self, query_string=''):
        path = f'/history{query_string}'
        with self.app.test_request_context(
            path,
            headers={'X-Store-ID': '1'},
        ):
            response = get_catering_history.__wrapped__()
            if isinstance(response, tuple):
                response = response[0]
            return response.get_json()

    def test_returns_all_orders_and_latest_payment_for_current_store(self):
        payload = self.request_history()
        self.assertEqual(payload['Code'], 0)
        self.assertEqual(payload['Data']['Total'], 5)
        items = {item['Id']: item for item in payload['Data']['Items']}
        self.assertIsNone(items[102]['PayOrder'])
        self.assertEqual(items[101]['PayOrder']['Id'], 1002)
        self.assertEqual(items[101]['PayOrder']['PayStatus'], 3)
        self.assertEqual(
            {item['PayOrder']['PayStatus'] if item['PayOrder'] else None for item in items.values()},
            {None, 0, 1, 2, 3},
        )
        self.assertNotIn(201, items)

    def test_filters_missing_payment_and_keyword(self):
        missing_payment = self.request_history('?PayStatus=none')
        self.assertEqual(missing_payment['Data']['Total'], 1)
        self.assertEqual(missing_payment['Data']['Items'][0]['Id'], 102)

        keyword = self.request_history('?Keyword=101')
        self.assertEqual(keyword['Data']['Total'], 1)
        self.assertEqual(keyword['Data']['Items'][0]['Code'], 'A101')


if __name__ == '__main__':
    unittest.main()
