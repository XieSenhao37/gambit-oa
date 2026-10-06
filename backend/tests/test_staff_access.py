import unittest
import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch
from flask import g
from app import create_app, db
from app.models import User, Store, PlayOrder, Catering, PayOrder, RefundRequest
from app.security.models import StaffAccount, StaffGrant, OASession, RolePage, LoginChallenge
from app.utils.crypto import encrypt_phone

class StaffSecurityTest(unittest.TestCase):

    def setUp(self):
        self.app = create_app({'TESTING': True, 'OA_LOGIN_MODE':'sms', 'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'OA_AUTH_SECRET': 'test-only-secret-of-at-least-32-characters', 'TENCENT_SMS_SECRET_ID': 'test', 'TENCENT_SMS_SECRET_KEY': 'test', 'TENCENT_SMS_APP_ID': 'test', 'TENCENT_SMS_SIGN_NAME': 'test', 'TENCENT_SMS_TEMPLATE_ID': 'test'})
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add_all([Store(id=1, code='a', name='A'), Store(id=2, code='b', name='B'), Store(id=3, code='c', name='C'), User(id=1, open_id='staff', role=125), User(id=2, open_id='admin', role=126), User(id=3, open_id='customer', role=0)])
        db.session.add_all([StaffAccount(user_id=1, phone_cipher=encrypt_phone('13800138001'), enabled=True, headquarters=False, version=1), StaffAccount(user_id=2, phone_cipher=encrypt_phone('13800138002'), enabled=True, headquarters=True, version=1), StaffGrant(user_id=1, store_id=1, role='worker'), StaffGrant(user_id=1, store_id=2, role='manager')])
        for uid in (1, 2):
            db.session.add(OASession(token_digest=hashlib.sha256(f'token{uid}'.encode()).hexdigest(), user_id=uid, account_version=1, expires_at=datetime.utcnow() + timedelta(hours=1)))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def headers(self, store=1, user=1):
        return {'Authorization': f'Bearer token{user}', 'X-Store-ID': str(store)}

    def test_page_and_scope(self):
        self.assertEqual(self.client.get('/admin_api/stats/v1/play/overview', headers=self.headers()).status_code, 403)
        self.assertEqual(self.client.get('/admin_api/user/v1/list', headers=self.headers(2)).status_code, 200)
        self.assertEqual(self.client.get('/admin_api/user/v1/list', headers=self.headers(3)).status_code, 403)
        self.assertEqual(self.client.get('/admin_api/staff-access/v1/accounts', headers=self.headers(2)).status_code, 403)
        self.assertEqual(self.client.get('/admin_api/user/v1/list?StoreID=3', headers=self.headers(2)).status_code, 400)
        self.assertEqual(self.client.put('/admin_api/user/v1/3', json={'Role': 127}, headers=self.headers(2)).status_code, 403)

    def test_me_role_pairing(self):
        r = self.client.get('/admin_api/auth/v1/me', headers=self.headers()).json['Data']
        self.assertNotIn('dashboard', r['Stores'][0]['Pages'])
        self.assertIn('dashboard', r['Stores'][1]['Pages'])
        self.assertEqual(len(self.client.get('/admin_api/store/v1/list', headers=self.headers()).json['Data']['Items']), 2)

    def test_revocation_and_logout(self):
        db.session.get(StaffAccount, 1).enabled = False
        db.session.commit()
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers=self.headers()).status_code, 401)
        self.assertEqual(self.client.post('/admin_api/auth/v1/logout', headers=self.headers(user=2)).status_code, 200)
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers=self.headers(user=2)).status_code, 401)

    @patch('app.security.sms.send_code')
    def test_otp_one_use_and_nonstaff_not_sent(self, send):
        self.assertEqual(self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138003'}).status_code, 403)
        send.assert_not_called()
        r = self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138001'})
        self.assertEqual(r.status_code, 200, r.json)
        code = send.call_args.args[1]
        cid = r.json['Data']['ChallengeId']
        body = {'ChallengeId': cid, 'Code': code}
        self.assertEqual(self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138001'}).status_code, 429)
        login = self.client.post('/admin_api/auth/v1/login', json=body)
        self.assertEqual(login.status_code, 200, login.json)
        self.assertNotIn(code, str(login.json))
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json=body).status_code, 400)
        self.assertIsNotNone(db.session.get(StaffAccount, 1).phone_verified_at)

    @patch('app.security.sms.send_code')
    def test_otp_failures_expiry_version_and_unconfigured(self, send):
        r = self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138001'})
        cid = r.json['Data']['ChallengeId']
        code = send.call_args.args[1]
        wrong = '999999' if code != '999999' else '888888'
        for _ in range(5):
            self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'ChallengeId': cid, 'Code': wrong}).status_code, 400)
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'ChallengeId': cid, 'Code': code}).status_code, 400)
        self.app.config['TENCENT_SMS_TEMPLATE_ID'] = ''
        self.assertFalse(self.client.get('/admin_api/auth/v1/status').json['Data']['SmsReady'])
        self.assertEqual(self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138002'}).status_code, 503)

    def test_unknown_token_and_old_password_denied(self):
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers={'Authorization': 'Bearer old-jwt'}).status_code, 401)
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'username': 'admin', 'password': 'anything'}).status_code, 400)

    def test_pages_dynamic_protected_and_immediate(self):
        r = self.client.get('/admin_api/staff-access/v1/pages', headers=self.headers(user=2))
        self.assertEqual(r.status_code, 200)
        ids = {p['id'] for p in r.json['Data']['Pages']}
        self.assertIn('staff-access', ids)
        self.assertEqual(self.client.put('/admin_api/staff-access/v1/pages/manager', json={'Pages': {'staff-access': True}}, headers=self.headers(user=2)).status_code, 400)
        self.assertEqual(self.client.put('/admin_api/staff-access/v1/pages/manager', json={'Pages': {'users': False}}, headers=self.headers(user=2)).status_code, 200)
        self.assertEqual(self.client.get('/admin_api/user/v1/list', headers=self.headers(2)).status_code, 403)

    @patch('app.api.v1.refund._call_gambit_server_refund_action')
    def test_refund_target_cannot_cross_store(self, proxy):
        db.session.add(PayOrder(id=22, open_id='customer', store_id=1, amount=100, pay_status=1))
        db.session.add(RefundRequest(id=11, open_id='customer', order_type='play', order_id=1, pay_order_id=22, amount=100, status='pending'))
        db.session.commit()
        result = self.client.post('/admin_api/refund/v1/approve/11', headers=self.headers(2))
        self.assertEqual(result.status_code, 404, result.json)
        proxy.assert_not_called()

    def test_all_api_routes_have_page_mapping(self):
        public = {'auth.login', 'auth.send_code', 'auth.status'}
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith('/admin_api'):
                continue
            fn = self.app.view_functions[rule.endpoint]
            if rule.endpoint.removeprefix('api_v1.') in public:
                continue
            self.assertTrue(getattr(fn, 'oa_pages', None), rule.endpoint)

    def test_store_filtered_orders_and_aggregate(self):
        db.session.add_all([PlayOrder(id=101, open_id='customer', store_id=1, amount=100, in_time=datetime.utcnow(), settle_status=1), PlayOrder(id=102, open_id='customer', store_id=2, amount=200, in_time=datetime.utcnow(), settle_status=1)])
        db.session.commit()
        for (store, expected) in ((1, 101), (2, 102), (1, 101)):
            r = self.client.get('/admin_api/order/v1/list', headers=self.headers(store))
            self.assertEqual(r.status_code, 200, r.json)
            self.assertEqual([x['Id'] for x in r.json['Data']['Items']], [expected])

    @patch('app.security.sms.send_code')
    def test_pending_code_invalid_after_revoke(self, send):
        r = self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138001'})
        cid = r.json['Data']['ChallengeId']
        code = send.call_args.args[1]
        db.session.get(StaffAccount, 1).enabled = False
        db.session.commit()
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'ChallengeId': cid, 'Code': code}).status_code, 401)

    @patch('app.security.sms.send_code')
    def test_expired_code(self, send):
        r = self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13800138001'})
        cid = r.json['Data']['ChallengeId']
        code = send.call_args.args[1]
        db.session.get(LoginChallenge, cid).expires_at = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'ChallengeId': cid, 'Code': code}).status_code, 400)

    def test_admin_updates_grants_and_revokes_session(self):
        r = self.client.put('/admin_api/staff-access/v1/accounts/1', json={'Enabled': True, 'Headquarters': False, 'Grants': [{'StoreId': 1, 'Role': 'manager'}, {'StoreId': 2, 'Role': 'worker'}]}, headers=self.headers(user=2))
        self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(db.session.get(StaffGrant, (1, 1)).role, 'manager')
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers=self.headers()).status_code, 401)

    def test_sensitive_global_metrics_are_unavailable_not_zero(self):
        from app.security.reporting import redact_global_metrics
        from flask import jsonify
        with self.app.test_request_context('/admin_api/stats/v1/wallet/overview'):
            g.staff = db.session.get(StaffAccount, 1)
            r = redact_global_metrics(jsonify(Code=0, Data={'Summary': {'BalanceTotal': 9999, 'ConsumeAmount': 123, 'RechargeAmount': 999}, 'Trend': [{'Amount': 999}]})).json['Data']
            self.assertIsNone(r['Summary']['BalanceTotal'])
            self.assertEqual(r['Summary']['ConsumeAmount'], 123)
            self.assertEqual(r['Trend'], [])

    def test_no_self_lockout(self):
        r = self.client.put('/admin_api/staff-access/v1/accounts/2', json={'Enabled': False, 'Headquarters': False, 'Grants': []}, headers=self.headers(user=2))
        self.assertEqual(r.status_code, 400)
if __name__ == '__main__':
    unittest.main()
