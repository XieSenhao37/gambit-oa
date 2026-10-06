"""开屏与首页弹窗；一个开屏配置位，弹窗组独立频控。"""
import copy
import hashlib
import json
import re
from app.services.home_banners import image_url

PROMOTIONS_KEY = 'HomePromotions'
DEFAULT_PROMOTIONS = {
    'Splash': {'Title': '开屏展示', 'Img': '', 'Enabled': False, 'Frequency': 'daily', 'Seconds': 3},
    'Popup': {'Enabled': False, 'Frequency': 'daily', 'Items': []},
}


def read_promotions(config):
    return copy.deepcopy(config.get(PROMOTIONS_KEY) or DEFAULT_PROMOTIONS)


def promotion_revision(config):
    return hashlib.sha256(json.dumps(read_promotions(config), ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def settings(value):
    if not isinstance(value, dict) or type(value.get('Enabled')) is not bool:
        raise ValueError('上下线状态无效')
    if value.get('Frequency') not in ('daily', 'entry'):
        raise ValueError('展示频率须为每天一次或每次进入')
    return {'Enabled': value['Enabled'], 'Frequency': value['Frequency']}


def title(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 60:
        raise ValueError('请填写 1–60 字的名称')
    return value.strip()


def validate_promotions(value):
    if not isinstance(value, dict):
        raise ValueError('展示配置格式错误')
    splash, popup = value.get('Splash'), value.get('Popup')
    # Splash must be an object: there is no list or second online splash slot.
    s, p = settings(splash), settings(popup)
    img = image_url(splash.get('Img', ''))
    seconds = splash.get('Seconds')
    if type(seconds) is not int or not 2 <= seconds <= 5:
        raise ValueError('开屏时长须为 2–5 秒')
    if s['Enabled'] and not img:
        raise ValueError('请先上传开屏图片再上线')
    s.update(Title=title(splash.get('Title')), Img=img, Seconds=seconds)
    items = popup.get('Items')
    if not isinstance(items, list) or len(items) > 20:
        raise ValueError('首页弹窗最多配置 20 张图片')
    result, ids = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('弹窗图片格式错误')
        ident = item.get('Id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('弹窗图片 ID 无效或重复')
        ids.add(ident)
        if type(item.get('Enabled')) is not bool or type(item.get('Sort')) is not int or not 0 <= item['Sort'] <= 9999:
            raise ValueError('弹窗状态或排序无效')
        img = image_url(item.get('Img', ''))
        if not img:
            raise ValueError('请上传弹窗图片')
        result.append({'Id': ident, 'Title': title(item.get('Title')), 'Img': img, 'Enabled': item['Enabled'], 'Sort': item['Sort']})
    p['Items'] = sorted(result, key=lambda i: i['Sort'])
    return {'Splash': s, 'Popup': p}
