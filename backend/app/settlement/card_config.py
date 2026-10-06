"""Shared price configuration used by both WeChat and OA card issuance."""
import json
from app import db
from app.models import Config


def card_config(lock=False):
    query = Config.query.filter_by(config_key='MonthCardConfig').filter(Config.deleted_at.is_(None))
    if lock:
        query = query.populate_existing().with_for_update()
    row = query.first()
    if not row:
        raise ValueError('尚未配置月卡价格，请由总部设置后再开卡')
    value = row.config_value
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError('月卡价格配置无效')
    price = value.get('CommonPrice')
    if isinstance(price, bool) or not isinstance(price, int) or price <= 0 or price > 1000000:
        raise ValueError('月卡每期价格必须为有效的正整数分')
    return row, value, price
