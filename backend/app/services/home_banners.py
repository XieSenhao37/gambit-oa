"""首页 Banner 配置：保留旧版 HomeBanners，供已发布的小程序继续使用。"""
import copy
import hashlib
import json
import re
from urllib.parse import urlsplit

CONFIG_KEY = 'CommonConfig'
ITEMS_KEY = 'HomeBannerItems'
CLOUD_ROOT = 'cloud://prod-9getnl5m2b89e2b3.7072-prod-9getnl5m2b89e2b3-1301993689/microApp/home/'


def migrate_banners(config):
    if ITEMS_KEY in config:
        return copy.deepcopy(config[ITEMS_KEY])
    items = [
        dict(Id='legacy-referral', Title='邀请好友', Img=CLOUD_ROOT+'InviteFriend.jpg', Preview='', Action='page', Page='/pages/referral/index', Enabled=True, Sort=10),
        dict(Id='legacy-join-group', Title='加入群聊', Img=CLOUD_ROOT+'JoinGroup.jpg', Preview='', Action='page', Page='/pages/joinGroup/index', Enabled=True, Sort=20),
    ]
    for i, old in enumerate(config.get('HomeBanners') or []):
        img = CLOUD_ROOT+'PriceBanner0519.jpg' if i == 0 else old.get('Img', '')
        preview = CLOUD_ROOT+'PricePreview.jpg' if i == 0 else old.get('Preview') or ''
        items.append(dict(Id=f'legacy-config-{i}', Title='门店价格' if i == 0 else f'原有 Banner {i+1}', Img=img, Preview=preview, Action='preview' if preview else 'none', Page='', Enabled=True, Sort=(i+3)*10))
    return items


def revision(config):
    payload = {'migrated': ITEMS_KEY in config, 'items': migrate_banners(config)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def image_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError('图片地址无效')
    value = value.strip()
    if not value:
        return ''
    parts = urlsplit(value)
    if parts.scheme not in ('https', 'cloud') or not parts.netloc or parts.username or parts.password:
        raise ValueError('图片地址须为 HTTPS 或云存储地址')
    return value



def normalize_page(value):
    if not isinstance(value, str):
        raise ValueError('请输入小程序页面路径')
    page = value.strip()
    if not page.startswith('/'):
        page = '/' + page
    if (len(page) > 2048 or re.search(r'[\s\x00-\x1f\x7f\\#]', page)
            or not re.fullmatch(r'/(?:[a-zA-Z0-9_-]+/)+[a-zA-Z0-9_-]+(?:\?[^#]*)?', page)):
        raise ValueError('请输入有效的小程序页面路径，如 /pages/eventCalendar/index，可携带参数')
    return page


def validate_items(items):
    if not isinstance(items, list) or len(items) > 30:
        raise ValueError('最多可配置 30 条 Banner')
    result, ids = [], set()
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Banner 数据格式错误')
        ident = item.get('Id')
        if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('Banner ID 无效或重复')
        ids.add(ident)
        title = item.get('Title')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 60:
            raise ValueError('请填写 1–60 字的 Banner 名称')
        img, preview = image_url(item.get('Img')), image_url(item.get('Preview', ''))
        if not img:
            raise ValueError('请上传首页展示图')
        action = item.get('Action')
        if action not in ('preview', 'page', 'none'):
            raise ValueError('请选择有效的点击方式')
        if action == 'preview' and not preview:
            raise ValueError('查看大图时必须配置点击大图')
        page = normalize_page(item.get('Page', '')) if action == 'page' else ''
        if type(item.get('Enabled')) is not bool:
            raise ValueError('上下架状态无效')
        sort = item.get('Sort')
        if type(sort) is not int or not 0 <= sort <= 9999:
            raise ValueError('排序须为 0–9999 的整数')
        result.append(dict(Id=ident, Title=title.strip(), Img=img, Preview=preview, Action=action, Page=page if action == 'page' else '', Enabled=item['Enabled'], Sort=sort))
    return sorted(result, key=lambda item: item['Sort'])
