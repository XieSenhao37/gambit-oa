import os
from dotenv import load_dotenv
from pathlib import Path

# 获取项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=False)

class Config:
    # 数据库配置
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # 跨域配置
    CORS_ORIGINS = ['*']

    # 密钥配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev')

    # GambitServer 内部接口配置
    GAMBIT_SERVER_BASE_URL = os.getenv('GAMBIT_SERVER_BASE_URL', '').rstrip('/')
    GAMBIT_INTERNAL_TOKEN = os.getenv('GAMBIT_INTERNAL_TOKEN', "")

    # 腾讯云 COS（与 ims 共用同一个 bucket）
    COS_SECRET_ID = os.getenv('COS_SECRET_ID', "")
    COS_SECRET_KEY = os.getenv('COS_SECRET_KEY', "")
    COS_BUCKET = os.getenv('COS_BUCKET', 'gambit-1301993689')
    COS_REGION = os.getenv('COS_REGION', 'ap-guangzhou')
    OA_AUTH_SECRET = os.getenv("OA_AUTH_SECRET", "")
    TENCENT_SMS_SECRET_ID = os.getenv("TENCENT_SMS_SECRET_ID", "")
    TENCENT_SMS_SECRET_KEY = os.getenv("TENCENT_SMS_SECRET_KEY", "")
    TENCENT_SMS_APP_ID = os.getenv("TENCENT_SMS_APP_ID", "")
    TENCENT_SMS_SIGN_NAME = os.getenv("TENCENT_SMS_SIGN_NAME", "")
    TENCENT_SMS_TEMPLATE_ID = os.getenv("TENCENT_SMS_TEMPLATE_ID", "")
    TENCENT_SMS_REGION = os.getenv("TENCENT_SMS_REGION", "ap-guangzhou")

    # Temporary password entry while Tencent SMS qualification is pending.
    # Set to "sms" to restore the existing staff-phone verification flow.
    OA_ADMIN_PASSWORD = os.getenv("OA_ADMIN_PASSWORD", "")
    OA_LOGIN_MODE = os.getenv("OA_LOGIN_MODE", "password")
