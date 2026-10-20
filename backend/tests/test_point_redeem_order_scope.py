"""Redeem listing regression checks with isolated SQLite fixtures."""
import unittest
from datetime import datetime

from flask import g

from app import db
from app.models import PointRedeemOrder
from app.security.models import StaffGrant
from tests import test_staff_access as fixtures


class PointRedeemOrderScopeTest(unittest.TestCase):
    headers = fixtures.StaffSecurityTest.headers
    tearDown = fixtures.StaffSecurityTest.tearDown

    def setUp(self):
        fixtures.StaffSecurityTest.setUp(self)
        db.session.get(StaffGrant, (1, 1)).role = 'manager'
        for order_id, status, store, deleted in (
            (101, 0, None, False),
            (102, 0, None, False),
            (103, 0, 1, False),
            (104, 0, 2, False),
            (105, 1, 1, False),
            (106, 1, 2, False),
            (107, 2, 1, False),
            (108, 2, 2, False),
            (109, 1, None, False),
            (110, 2, None, False),
            (111, 0, None, True),
        ):
            db.session.add(PointRedeemOrder(
                id=order_id, order_no=f'REDEEM-{order_id}', open_id='customer',
                product_id=1, product_name='测试礼品', points_price=100,
                quantity=1, total_points=100, status=status, pickup_store_id=store,
                deleted_at=datetime(2026, 10, 1) if deleted else None,
            ))
        db.session.commit()

    def listing(self, query='', store=1, user=1):
        response = self.client.get('/admin_api/point/v1/redeem-orders' + query,
                                   headers=self.headers(store, user))
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['Code'], 0)
        return response.json['Data']

    def test_pending_unassigned_orders_visible_in_each_authorized_store(self):
        for user in (1, 2):
            for store, assigned in ((1, 103), (2, 104)):
                data = self.listing('?Status=0', store, user)
                self.assertEqual(data['Total'], 3)
                self.assertEqual([row['Id'] for row in data['Items']], [assigned, 102, 101])
                self.assertTrue(all(row['StatusText'] == '待领取' for row in data['Items']))

    def test_all_statuses_keep_completed_and_cancelled_orders_store_scoped(self):
        for store, expected in ((1, [107, 105, 103, 102, 101]),
                                (2, [108, 106, 104, 102, 101])):
            data = self.listing(store=store)
            self.assertEqual(data['Total'], 5)
            self.assertEqual([row['Id'] for row in data['Items']], expected)
            for status, order_id in ((1, expected[1]), (2, expected[0])):
                filtered = self.listing(f'?Status={status}', store)
                self.assertEqual([row['Id'] for row in filtered['Items']], [order_id])

    def test_pagination_total_and_keyword_include_unassigned_pending(self):
        data = self.listing('?Status=0&pageSize=1&current=2')
        self.assertEqual(data['Total'], 3)
        self.assertEqual(data['CurrentPage'], 2)
        self.assertEqual([row['Id'] for row in data['Items']], [102])
        for keyword in ('REDEEM-101', 'customer', '测试礼品'):
            data = self.listing('?Status=0&Keyword=' + keyword)
            expected = [101] if keyword == 'REDEEM-101' else [103, 102, 101]
            self.assertEqual([row['Id'] for row in data['Items']], expected)

    def test_listing_requires_authentication_page_and_store_access(self):
        url = '/admin_api/point/v1/redeem-orders?Status=0'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.get(url, headers=self.headers(3)).status_code, 403)
        db.session.get(StaffGrant, (1, 1)).role = 'worker'
        db.session.commit()
        self.assertEqual(self.client.get(url, headers=self.headers()).status_code, 403)

    def test_default_orm_queries_still_exclude_unassigned_orders(self):
        with self.app.test_request_context('/other-endpoint'):
            g.scope_store = 1
            self.assertEqual([row.id for row in PointRedeemOrder.query.order_by(PointRedeemOrder.id)],
                             [103, 105, 107])

    def test_unassigned_order_write_remains_forbidden(self):
        row = db.session.get(PointRedeemOrder, 101)
        with self.app.test_request_context('/other-endpoint'):
            g.scope_store = 1
            row.status = 1
            from werkzeug.exceptions import Forbidden
            with self.assertRaises(Forbidden):
                db.session.flush()
        db.session.rollback()
