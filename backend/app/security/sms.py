"""Tencent SMS adapter. Disabled until approved sign/template and credentials are configured."""
import json
from flask import current_app
KEYS = ('TENCENT_SMS_SECRET_ID', 'TENCENT_SMS_SECRET_KEY', 'TENCENT_SMS_APP_ID', 'TENCENT_SMS_SIGN_NAME', 'TENCENT_SMS_TEMPLATE_ID')

def configured():
    return all((current_app.config.get(k) for k in KEYS))

def send_code(phone, code):
    if not configured():
        raise RuntimeError('短信服务尚未配置，资质审核通过后启用')
    from tencentcloud.common import credential
    from tencentcloud.sms.v20210111 import sms_client, models
    cfg = current_app.config
    client = sms_client.SmsClient(credential.Credential(cfg[KEYS[0]], cfg[KEYS[1]]), cfg.get('TENCENT_SMS_REGION', 'ap-guangzhou'))
    req = models.SendSmsRequest()
    req.from_json_string(json.dumps({'PhoneNumberSet': ['+86' + phone], 'SmsSdkAppId': cfg[KEYS[2]], 'SignName': cfg[KEYS[3]], 'TemplateId': cfg[KEYS[4]], 'TemplateParamSet': [code]}))
    result = client.SendSms(req)
    if not result.SendStatusSet or result.SendStatusSet[0].Code != 'Ok':
        raise RuntimeError('短信发送失败，请稍后重试')
