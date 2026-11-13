import hashlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import requests
from app import create_app, db
from app.models import Store, User, RefundRequest, PayOrder
from app.security.models import StaffAccount, StaffGrant, OASession

class RetailGatewayTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'OA_LOGIN_MODE': 'sms', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'GAMBIT_SERVER_BASE_URL': 'https://isolated.invalid', 'GAMBIT_INTERNAL_TOKEN': 'isolated-test-token'})
        self.context = self.app.app_context(); self.context.push(); db.create_all()
        db.session.add_all([Store(id=1, code='a', name='A'), Store(id=2, code='b', name='B'), User(id=1, open_id='staff')])
        db.session.add(StaffAccount(user_id=1, phone_cipher='isolated-fixture', enabled=True, headquarters=False, version=1))
        db.session.add_all([StaffGrant(user_id=1, store_id=1, role='manager'), StaffGrant(user_id=1, store_id=2, role='worker')])
        db.session.add(OASession(token_digest=hashlib.sha256(b'test').hexdigest(), user_id=1, account_version=1, expires_at=datetime.utcnow()+timedelta(hours=1)))
        db.session.commit(); self.client=self.app.test_client(); self.headers={'Authorization':'Bearer test', 'X-Store-ID':'1'}
        self.response=Mock(); self.response.json.return_value={'Code':0, 'Data':{'OK':True}}
    def tearDown(self):
        db.session.remove(); db.drop_all(); self.context.pop()
    def test_store_and_actor_cannot_be_spoofed(self):
        with patch('app.api.v1.retail.requests.request', return_value=self.response) as send:
            r=self.client.put('/admin_api/retail/v1/stock', headers=self.headers, json={'StoreID':2, 'Actor':'other', 'RequestKey':'unchanged-key'})
            self.assertEqual(r.status_code, 400)
            send.assert_not_called()
            r=self.client.put('/admin_api/retail/v1/stock', headers=self.headers, json={'StoreID':1, 'Actor':'other', 'RequestKey':'unchanged-key'})
            self.assertEqual(r.status_code, 200)
            self.assertEqual(send.call_args.kwargs['json']['StoreID'],1)
            self.assertEqual(send.call_args.kwargs['json']['Actor'],'1')
            self.assertEqual(send.call_args.kwargs['json']['RequestKey'],'unchanged-key')
            self.assertEqual(self.client.get('/admin_api/retail/v1/orders?StoreID=2',headers=self.headers).status_code,400)
            self.client.get('/admin_api/retail/v1/orders',headers=self.headers)
            self.assertEqual(send.call_args.kwargs['params']['StoreID'],1)
    def test_worker_fulfillment_but_not_catalog_stock_or_refunds(self):
        worker={**self.headers, 'X-Store-ID':'2'}
        with patch('app.api.v1.retail.requests.request', return_value=self.response) as send:
            self.assertEqual(self.client.get('/admin_api/retail/v1/orders',headers=worker).status_code,200)
            self.assertEqual(self.client.post('/admin_api/retail/v1/action',headers=worker,json={'Action':'ship'}).status_code,200)
            for path,method,data in [('products','put',{}),('stock','put',{}),('coupon-templates','put',{}),('coupons/issue','post',{}),('after-sales/review','post',{'Action':'approve'}),('after-sales/1/retry-refund','post',{})]:
                self.assertEqual(getattr(self.client,method)('/admin_api/retail/v1/'+path,headers=worker,json=data).status_code,403,path)
            self.assertEqual(send.call_count,2)
    def test_catalog_requires_headquarters_and_cross_store_forbidden(self):
        with patch('app.api.v1.retail.requests.request') as send:
            self.assertEqual(self.client.put('/admin_api/retail/v1/products',headers=self.headers,json={}).status_code,403)
            self.assertEqual(self.client.get('/admin_api/retail/v1/orders',headers={**self.headers,'X-Store-ID':'999'}).status_code,403)
            self.assertEqual(self.client.get('/admin_api/retail/v1/orders').status_code,401)
            send.assert_not_called()
    def test_unknown_outcome_and_action_allowlist(self):
        with patch('app.api.v1.retail.requests.request',side_effect=requests.Timeout):
            r=self.client.put('/admin_api/retail/v1/stock',headers=self.headers,json={})
            self.assertEqual(r.status_code,502)
            self.assertIn('同一请求编号',r.json['Message'])
        self.assertEqual(self.client.post('/admin_api/retail/v1/action',headers=self.headers,json={'Action':'receive'}).status_code,400)

    def test_recipient_lookup_is_minimal_and_manager_only(self):
        db.session.add_all([User(id=20,open_id='private-recipient',nick_name='测试顾客'), User(id=21,open_id='deleted-recipient',nick_name='测试顾客',deleted_at=datetime.utcnow())])
        db.session.commit()
        r=self.client.get('/admin_api/retail/v1/recipients?Keyword=测试',headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['Data']['Items'],[{'Id':20,'NickName':'测试顾客','PhoneNumber':''}])
        self.assertNotIn('OpenId',str(r.json))
        self.assertEqual(self.client.get('/admin_api/retail/v1/recipients?Keyword=测试',headers={**self.headers,'X-Store-ID':'2'}).status_code,403)
        self.assertEqual(self.client.get('/admin_api/retail/v1/recipients',headers=self.headers).json['Data']['Items'],[])

    def test_legacy_refund_actions_cannot_bypass_retail_review(self):
        db.session.add(PayOrder(id=1,store_id=1,open_id='staff',amount=100))
        db.session.add(RefundRequest(id=50, pay_order_id=1, order_type='retail', order_id=1, open_id='staff', amount=100, status='pending_review', out_refund_no='isolated-retail'))
        db.session.commit()
        with patch('app.api.v1.refund.requests.post') as send:
            for action in ('approve', 'reject'):
                r=self.client.post('/admin_api/refund/v1/'+action+'/50', headers=self.headers,json={})
                self.assertEqual(r.status_code,403)
                self.assertIn('商城订单',r.json['Message'])
            send.assert_not_called()
