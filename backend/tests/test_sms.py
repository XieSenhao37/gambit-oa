"""Exercise the approved two-parameter template without calling Tencent Cloud."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from flask import Flask
from app.security import sms


class SmsAdapterTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update({key: 'isolated-test-value' for key in sms.KEYS})
        self.app.config.update(TENCENT_SMS_APP_ID='1400000000',
                               TENCENT_SMS_SIGN_NAME='测试签名',
                               TENCENT_SMS_TEMPLATE_ID='123',
                               TENCENT_SMS_REGION='ap-guangzhou')
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    @patch('tencentcloud.sms.v20210111.sms_client.SmsClient.SendSms')
    def test_approved_template_and_bounded_request(self, send):
        send.return_value = SimpleNamespace(SendStatusSet=[SimpleNamespace(Code='Ok')])
        with patch('tencentcloud.sms.v20210111.sms_client.SmsClient.__init__', return_value=None) as init:
            sms.send_code('13800138001', '012345')
        request = send.call_args.args[0]
        self.assertEqual(request.PhoneNumberSet, ['+8613800138001'])
        self.assertEqual(request.SmsSdkAppId, '1400000000')
        self.assertEqual(request.SignName, '测试签名')
        self.assertEqual(request.TemplateId, '123')
        self.assertEqual(request.TemplateParamSet, ['012345', '5'])
        self.assertEqual(init.call_args.args[2].httpProfile.reqTimeout, 10)

    @patch('tencentcloud.sms.v20210111.sms_client.SmsClient.SendSms')
    def test_rejected_and_empty_provider_response_are_failures(self, send):
        for states in ([], [SimpleNamespace(Code='FailedOperation.InsufficientBalance')]):
            send.return_value = SimpleNamespace(SendStatusSet=states)
            with self.assertRaises(RuntimeError):
                sms.send_code('13800138001', '012345')

    @patch('tencentcloud.sms.v20210111.sms_client.SmsClient.SendSms')
    def test_missing_secret_never_calls_provider(self, send):
        self.app.config['TENCENT_SMS_SECRET_KEY'] = ''
        self.assertFalse(sms.configured())
        with self.assertRaises(RuntimeError):
            sms.send_code('13800138001', '012345')
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
