"""Tencent SMS adapter. Disabled until approved sign/template and credentials are configured."""
import json
from flask import current_app
KEYS = ('TENCENT_SMS_SECRET_ID', 'TENCENT_SMS_SECRET_KEY', 'TENCENT_SMS_APP_ID', 'TENCENT_SMS_SIGN_NAME', 'TENCENT_SMS_TEMPLATE_ID')
CODE_TTL_MINUTES = 5

def configured():
    return all((current_app.config.get(k) for k in KEYS))

def send_code(phone, code):
    if not configured():
        raise RuntimeError('短信服务尚未配置，资质审核通过后启用')
    from tencentcloud.common import credential
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
    result = client.SendSms(req)
    if not result.SendStatusSet or result.SendStatusSet[0].Code != 'Ok':
        raise RuntimeError('短信发送失败，请稍后重试')
