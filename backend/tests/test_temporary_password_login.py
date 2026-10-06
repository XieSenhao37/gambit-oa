import hashlib
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from app import create_app, db
from app.models import Store
from app.security.models import OASession, StaffAccount, AccessAudit, RolePage
from app.security.login_mode import ADMIN_USERNAME, ADMIN_ID


ADMIN_PASSWORD = "local-only-test-password"


class TemporaryPasswordLoginTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite://',
                               'OA_LOGIN_MODE': 'password', 'OA_ADMIN_PASSWORD': ADMIN_PASSWORD, 'OA_AUTH_SECRET': ''})
        self.ctx = self.app.app_context(); self.ctx.push(); db.create_all()
        db.session.add_all([Store(id=1, code='a', name='A'), Store(id=2, code='b', name='B')])
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove(); db.drop_all(); self.ctx.pop()

    def login(self, **overrides):
        return self.client.post('/admin_api/auth/v1/login', json={
            'username': ADMIN_USERNAME, 'password': ADMIN_PASSWORD, **overrides})

    def headers(self, token):
        return {'Authorization': 'Bearer ' + token, 'X-Store-ID': '1'}

    def test_fixed_account_has_all_store_and_admin_pages_without_phone_setup(self):
        with patch('app.security.sms.send_code') as sms:
            status = self.client.get('/admin_api/auth/v1/status').json['Data']
            self.assertEqual(status['LoginMode'], 'password')
            self.assertFalse(status['TestLoginEnabled'])
            self.assertNotIn(ADMIN_PASSWORD, str(status))
            result = self.login(); self.assertEqual(result.status_code, 200, result.json)
            headers = self.headers(result.json['Data']['token'])
            me = self.client.get('/admin_api/auth/v1/me', headers=headers).json['Data']
            self.assertTrue(me['Headquarters']); self.assertEqual(me['UserId'], ADMIN_ID)
            self.assertEqual({s['Id'] for s in me['Stores']}, {1, 2})
            all_pages = {p['id'] for p in me['Pages']}
            for store in me['Stores']:
                self.assertEqual(set(store['Pages']), all_pages)
            self.assertEqual(self.client.get('/admin_api/staff-access/v1/accounts', headers=headers).status_code, 200)
            updated = self.client.put('/admin_api/staff-access/v1/pages/manager', json={'Pages': {'users': False}}, headers=headers)
            self.assertEqual(updated.status_code, 200)
            self.assertFalse(db.session.get(RolePage, ('manager', 'users')).allowed)
            # A temporary OA administrator does not modify miniapp staff identities.
            self.assertEqual(StaffAccount.query.count(), 0)
            self.assertEqual(AccessAudit.query.filter_by(action='login').one().actor_id, ADMIN_ID)
            self.assertNotIn(ADMIN_PASSWORD, str([a.detail for a in AccessAudit.query.all()]))
            sms.assert_not_called()

    def test_temporary_admin_keeps_operator_identity_in_proxied_orders(self):
        from flask import request
        from app.api.v1.order import _operator_label
        with self.app.test_request_context():
            request.user = {'user_id': ADMIN_ID}
            self.assertEqual(_operator_label(), 'OA#0')

    def test_unconfigured_password_does_not_allow_login(self):
        self.app.config["OA_ADMIN_PASSWORD"] = ""
        self.assertEqual(self.login(password="").status_code, 401)

    def test_only_exact_credentials_are_accepted(self):
        for data in [dict(username='Admin'), dict(username='other'), dict(password='wrong'),
                     dict(password=ADMIN_PASSWORD + ' '), dict(password=None), dict(password=['bad']),
                     dict(username='管理员'), dict(password='密码'), dict(TestLogin=True)]:
            result = self.login(**data)
            self.assertEqual(result.status_code, 401, result.json)
            self.assertEqual(result.json['Message'], '账号或密码错误')
        self.assertEqual(OASession.query.count(), 0)
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json=['bad']).status_code, 400)

    def test_session_is_fifteen_days_opaque_revocable_and_expires(self):
        before = datetime.utcnow()
        result = self.login()
        token = result.json['Data']['token']
        session = db.session.get(OASession, hashlib.sha256(token.encode()).hexdigest())
        self.assertGreaterEqual(session.expires_at, before + timedelta(days=15))
        self.assertLess(session.expires_at, before + timedelta(days=15, seconds=5))
        self.assertNotEqual(session.token_digest, token)
        session.expires_at = datetime.utcnow() - timedelta(seconds=1); db.session.commit()
        expired = self.client.get('/admin_api/auth/v1/me', headers=self.headers(token))
        self.assertEqual(expired.status_code, 401); self.assertIn('登录已过期', expired.json['Message'])
        token = self.login().json['Data']['token']
        self.assertEqual(self.client.post('/admin_api/auth/v1/logout', headers=self.headers(token)).status_code, 200)
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers=self.headers(token)).status_code, 401)

    def test_previous_phone_bypass_and_sms_entry_are_disabled(self):
        with patch('app.security.sms.send_code') as sms:
            self.assertEqual(self.client.post('/admin_api/auth/v1/send-code', json={'PhoneNumber': '13380938170'}).status_code, 403)
            for data in [{'TestLogin': True, 'PhoneNumber': '13380938170'}, {'ChallengeId': 'x'*48, 'Code': '123456'}]:
                self.assertEqual(self.client.post('/admin_api/auth/v1/login', json=data).status_code, 401)
            sms.assert_not_called()
        old_token = 'old-phone-session'
        db.session.add(OASession(token_digest=hashlib.sha256(old_token.encode()).hexdigest(), user_id=1,
                                 account_version=1, expires_at=datetime.utcnow()+timedelta(days=1)))
        db.session.commit()
        self.assertEqual(self.client.get('/admin_api/auth/v1/me', headers=self.headers(old_token)).status_code, 401)

    def test_switch_to_sms_closes_password_entry_and_existing_temporary_session(self):
        token = self.login().json['Data']['token']
        self.app.config.update(OA_LOGIN_MODE='sms', OA_AUTH_SECRET='test-only-secret-of-at-least-32-characters')
        self.assertEqual(self.client.get('/admin_api/auth/v1/status').json['Data']['LoginMode'], 'sms')
        self.assertEqual(self.login().status_code, 400)
        result = self.client.get('/admin_api/auth/v1/me', headers=self.headers(token))
        self.assertEqual(result.status_code, 401); self.assertIn('临时账号登录已停用', result.json['Message'])
        self.assertEqual(self.client.post('/admin_api/auth/v1/login', json={'TestLogin': True}).status_code, 400)

    def test_login_rate_limit_and_invalid_mode(self):
        for _ in range(30): self.assertEqual(self.login(password='wrong').status_code, 401)
        self.assertEqual(self.login().status_code, 429)
        self.app.config['OA_LOGIN_MODE'] = 'unknown'
        self.assertEqual(self.client.get('/admin_api/auth/v1/status').status_code, 503)


if __name__ == '__main__':
    unittest.main()
