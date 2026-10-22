"""Exercise first auth requests after a pooled connection dies; no external services."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import text
from sqlalchemy.pool import QueuePool

from app import create_app, db
from app.config import Config
from app.models import User
from app.security.models import StaffAccount
from app.utils.crypto import encrypt_phone


class AuthStaleConnectionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = create_app({
            'TESTING': True,
            'OA_LOGIN_MODE': 'sms',
            'OA_AUTH_SECRET': 'isolated-test-secret-at-least-32-characters',
            'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(Path(self.directory.name) / 'auth.db'),
            'SQLALCHEMY_ENGINE_OPTIONS': {
                **Config.SQLALCHEMY_ENGINE_OPTIONS,
                'poolclass': QueuePool, 'pool_size': 1, 'max_overflow': 0,
            },
            **{key: 'isolated-test' for key in (
                'TENCENT_SMS_SECRET_ID', 'TENCENT_SMS_SECRET_KEY',
                'TENCENT_SMS_APP_ID', 'TENCENT_SMS_SIGN_NAME', 'TENCENT_SMS_TEMPLATE_ID',
            )},
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        db.session.add(User(id=1, open_id='isolated-staff', role=125))
        db.session.add(StaffAccount(
            user_id=1, phone_cipher=encrypt_phone('13800138001'),
            enabled=True, headquarters=True, version=1,
        ))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.engine.dispose()
        self.ctx.pop()
        self.directory.cleanup()

    def disconnect_idle_connection(self):
        db.session.remove()
        with db.engine.connect() as connection:
            driver = connection.connection.driver_connection
            connection.execute(text('SELECT 1'))
        # Close behind the pool's back, like a server/network idle disconnect.
        driver.close()

    @patch('app.security.sms.send_code')
    def test_first_send_and_login_succeed_after_idle_disconnect(self, send):
        self.disconnect_idle_connection()
        response = self.client.post('/admin_api/auth/v1/send-code', json={
            'PhoneNumber': '13800138001',
        })
        self.assertEqual(response.status_code, 200, response.json)
        send.assert_called_once()
        challenge = response.json['Data']['ChallengeId']
        code = send.call_args.args[1]

        self.disconnect_idle_connection()
        response = self.client.post('/admin_api/auth/v1/login', json={
            'ChallengeId': challenge, 'Code': code,
        })
        self.assertEqual(response.status_code, 200, response.json)
        send.assert_called_once()

        # Reconnection must not bypass one-use verification or resend the SMS.
        response = self.client.post('/admin_api/auth/v1/login', json={
            'ChallengeId': challenge, 'Code': code,
        })
        self.assertEqual(response.status_code, 400)
        send.assert_called_once()
