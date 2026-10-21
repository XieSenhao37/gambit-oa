"""Tencent SMS adapter. Disabled until approved sign/template and credentials are configured."""
import json
import re
from flask import current_app
KEYS = ('TENCENT_SMS_SECRET_ID', 'TENCENT_SMS_SECRET_KEY', 'TENCENT_SMS_APP_ID', 'TENCENT_SMS_SIGN_NAME', 'TENCENT_SMS_TEMPLATE_ID')
CODE_TTL_MINUTES = 5


class SmsSendError(RuntimeError):
    """Safe diagnostics only: never retain provider messages or request contents."""

    def __init__(self, code, request_id=None):
        self.code = code if isinstance(code, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_.]{0,99}', code) else 'UnknownProviderError'
        self.request_id = request_id if isinstance(request_id, str) and re.fullmatch(r'[A-Za-z0-9-]{1,80}', request_id) else '-'
        if self.code == 'LimitExceeded.PhoneNumberDailyLimit':
            self.user_message = '该手机号今日验证码发送次数已达上限，请明日再试或联系管理员'
        elif self.code.startswith('LimitExceeded.'):
            self.user_message = '验证码发送过于频繁，请稍后重试'
        elif self.code.startswith('FailedOperation.InsufficientBalance'):
            self.user_message = '短信额度不足，请联系管理员'
        elif self.code in ('FailedOperation.TemplateIncorrectOrUnapproved', 'FailedOperation.SignatureIncorrectOrUnapproved'):
            self.user_message = '短信签名或模板暂不可用，请联系管理员'
        elif self.code.startswith(('AuthFailure.', 'UnauthorizedOperation.')):
            self.user_message = '短信服务配置异常，请联系管理员'
        else:
            self.user_message = '短信发送失败，请稍后重试或联系管理员'
        super().__init__(self.user_message)

def configured():
    return all((current_app.config.get(k) for k in KEYS))

def send_code(phone, code):
    if not configured():
        raise RuntimeError('短信服务尚未配置，资质审核通过后启用')
    from tencentcloud.common import credential
    from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.sms.v20210111 import sms_client, models
    cfg = current_app.config
    profile = ClientProfile()
    profile.httpProfile = HttpProfile()
    profile.httpProfile.reqTimeout = 10
    client = sms_client.SmsClient(credential.Credential(cfg[KEYS[0]], cfg[KEYS[1]]), cfg.get('TENCENT_SMS_REGION', 'ap-guangzhou'), profile)
    req = models.SendSmsRequest()
    req.from_json_string(json.dumps({'PhoneNumberSet': ['+86' + phone], 'SmsSdkAppId': cfg[KEYS[2]], 'SignName': cfg[KEYS[3]], 'TemplateId': cfg[KEYS[4]], 'TemplateParamSet': [code, str(CODE_TTL_MINUTES)]}))
    try:
        result = client.SendSms(req)
    except TencentCloudSDKException as error:
        raise SmsSendError(error.get_code(), error.get_request_id()) from None
    if not result.SendStatusSet:
        raise SmsSendError('EmptySendStatus', getattr(result, 'RequestId', None))
    if result.SendStatusSet[0].Code != 'Ok':
        raise SmsSendError(result.SendStatusSet[0].Code, getattr(result, 'RequestId', None))
