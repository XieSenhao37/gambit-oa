from datetime import datetime, timedelta
import re
import hashlib

from flask import Blueprint, jsonify, request, g

from app import db
from app.middlewares.auth import login_required
from app.models import MonthCardOrder, User
from app.utils.crypto import decrypt_phone
from app.security.policy import audit
from app.settlement.card_config import card_config
from app.settlement import service as settlement
from sqlalchemy.exc import IntegrityError

month_card_bp = Blueprint('month_card', __name__)

SOURCE_LABELS = {
    'wechat': '小程序微信',
    'third_party': '第三方验券',
    'gift': '免费赠送（总部补贴）',
    'meituan': '美团核销',
    'storage_gift': '寄存赠送',
    'manual_adjustment': '手动调整',
    'other': '其他',
}


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _now():
    from app.settlement.clock import now
    return now()


def _read_json():
    return request.get_json(silent=True) or {}


def _parse_time(value):
    if not value:
        return None
    value = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError('时间格式错误，请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:mm:ss')


def _serialize_order(order, user=None):
    source = order.source or 'wechat'
    return {
        'Id': order.id,
        'OpenId': order.open_id,
        'UserId': user.id if user else None,
        'NickName': user.nick_name if user else '',
        'PhoneNumber': decrypt_phone(user.phone_number) if user and user.phone_number else None,
        'OpenPeriod': order.open_period,
        'DurationDays': order.duration_days,
        'UnitPrice': order.amount//order.open_period if order.open_period else 0,
        'FundingType': 'headquarters_subsidy' if source=='gift' else 'headquarters',
        'Amount': order.amount,
        'OpenType': order.open_type,
        'SettleStatus': order.settle_status,
        'Source': source,
        'SourceText': SOURCE_LABELS.get(source, source),
        'Operator': order.operator or '',
        'ExternalNo': order.external_no or '',
        'StoreId': order.store_id,
        'EffectiveAt': _format_time(order.effective_at),
        'Remark': order.remark or '',
        'CreatedAt': _format_time(order.created_at),
        'UpdatedAt': _format_time(order.updated_at),
    }


@month_card_bp.route('/orders', methods=['GET'])
@login_required('users')
def list_month_card_orders():
    page = request.args.get('Current', 1, type=int)
    page_size = request.args.get('PageSize', 20, type=int)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = MonthCardOrder.query.filter(MonthCardOrder.deleted_at.is_(None))
    user_id = request.args.get('UserId', type=int)
    open_id = (request.args.get('OpenId') or '').strip()
    source = (request.args.get('Source') or '').strip()
    external_no = (request.args.get('ExternalNo') or '').strip()

    if user_id:
        user = User.query.filter(User.id == user_id, User.deleted_at.is_(None)).first()
        if not user:
            return jsonify({'Code': 404, 'Message': '用户不存在', 'Data': None}), 404
        query = query.filter(MonthCardOrder.open_id == user.open_id)
    elif open_id:
        query = query.filter(MonthCardOrder.open_id == open_id)
    if source:
        query = query.filter(MonthCardOrder.source == source)
    if external_no:
        query = query.filter(MonthCardOrder.external_no == external_no)

    try:
        start_time = _parse_time(request.args.get('StartTime'))
        end_time = _parse_time(request.args.get('EndTime'))
    except ValueError as exc:
        return jsonify({'Code': 400, 'Message': str(exc), 'Data': None}), 400
    if start_time:
        query = query.filter(MonthCardOrder.created_at >= start_time)
    if end_time:
        query = query.filter(MonthCardOrder.created_at < end_time)

    pagination = query.order_by(MonthCardOrder.created_at.desc(), MonthCardOrder.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    open_ids = [item.open_id for item in pagination.items]
    users = {
        user.open_id: user
        for user in User.query.filter(User.open_id.in_(open_ids), User.deleted_at.is_(None)).all()
    } if open_ids else {}

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_order(order, users.get(order.open_id)) for order in pagination.items],
        },
    })


@month_card_bp.route('/config',methods=['GET'])
@login_required('users', 'month-card-open')
def get_month_card_config():
    try:
        _,value,price=card_config()
        return jsonify(Code=0,Data={'Price':price,'DurationDays':30,'MonthLimit':value.get('MonthLimit',0)})
    except ValueError as exc:
        return jsonify(Code=400,Message=str(exc)),400


def _issue_cards(user_ids, months, expected, keys, batch_prefix=None):
    if settlement.enabled():
        settlement.lock_operations()
    # A common configuration lock also serializes retries when settlement is disabled.
    _, _, price = card_config(lock=True)
    users = User.query.filter(User.id.in_(user_ids), User.deleted_at.is_(None)).order_by(
        User.id).populate_existing().with_for_update().all()
    found = {user.id: user for user in users}
    for uid in user_ids:
        if uid not in found or not found[uid].open_id:
            raise ValueError(f'用户 #{uid} 不存在或未关联小程序账号，整批未开通')
    query = MonthCardOrder.query.execution_options(global_reference_check=True)
    query = query.filter(MonthCardOrder.request_key.like(batch_prefix + '%')) if batch_prefix else query.filter(
        MonthCardOrder.request_key.in_(keys.values()))
    existing = query.populate_existing().with_for_update().all()
    if existing:
        by_key = {order.request_key: order for order in existing}
        if set(by_key) != set(keys.values()):
            raise ValueError('请求标识已用于其他用户，请刷新后重试')
        result = []
        for uid in user_ids:
            order, user = by_key[keys[uid]], found[uid]
            if (order.deleted_at or order.open_id != user.open_id or order.source != 'gift'
                    or order.open_period != months or order.amount != expected * months):
                raise ValueError('请求标识已用于其他开卡内容，请刷新后重试')
            result.append(_serialize_order(order, user))
        return result
    if expected != price:
        raise ValueError('月卡价格已变化，请重新读取价格确认后再开通')
    # MySQL DATETIME stores whole seconds; normalize before snapshotting the response.
    at = _now().replace(microsecond=0)
    result = []
    for uid in user_ids:
        user = found[uid]
        start = max(at, user.month_card_expire) if user.month_card_expire else at
        order = MonthCardOrder(
            open_id=user.open_id, open_period=months, duration_days=30 * months,
            amount=price * months, open_type=2, settle_status=1, source='gift',
            request_key=keys[uid], operator=str(g.staff.user_id), store_id=g.store_id,
            effective_at=start, created_at=at, updated_at=at)
        db.session.add(order)
        db.session.flush()
        settlement.create_card_pools(order, start, 0)
        user.month_card_expire = start + timedelta(days=30 * months)
        user.updated_at = at
        audit('month-card:manual-open', order.id, {'user_id': uid, 'months': months,
              'amount': order.amount, 'payer_id': 0, 'source': 'gift'})
        result.append(_serialize_order(order, user))
    return result


def _manual_open(batch=False):
    from flask import abort
    if not g.staff.headquarters:
        abort(403, description='仅总部可手动开通月卡')
    data = _read_json()
    try:
        user_field = 'UserIds' if batch else 'UserId'
        if not isinstance(data, dict) or set(data) - {user_field, 'OpenMonths', 'ExpectedPrice', 'RequestKey'}:
            raise ValueError('仅支持总部承担的月卡开通，不接受渠道或收款参数')
        ids = data.get(user_field) if batch else [data.get(user_field)]
        months, expected, key = data.get('OpenMonths'), data.get('ExpectedPrice'), data.get('RequestKey')
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 100
                or any(type(uid) is not int or not 0 < uid < 2**63 for uid in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError('请选择 1 至 100 位不同的有效用户')
        if type(months) is not int or not 1 <= months <= 12:
            raise ValueError('请选择 1 至 12 期月卡')
        if type(expected) is not int or not 0 < expected <= 1000000:
            raise ValueError('请先读取当前月卡价格')
        if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', key):
            raise ValueError('请求标识无效，请刷新后重试')
        ids = sorted(ids)
        prefix = 'b' + hashlib.sha256(key.encode()).hexdigest()[:40] + '-' if batch else None
        keys = {uid: prefix + str(uid) if batch else key for uid in ids}
        items = _issue_cards(ids, months, expected, keys, prefix)
        db.session.commit()
        return jsonify(Code=0, Data={'Items': items} if batch else items[0])
    except ValueError as exc:
        db.session.rollback()
        return jsonify(Code=400, Message=str(exc)), 400
    except IntegrityError:
        db.session.rollback()
        return jsonify(Code=409, Message='开卡请求冲突，请使用同一请求重试'), 409


@month_card_bp.route('/manual-open', methods=['POST'])
@login_required('month-card-open')
def manual_open_month_card():
    return _manual_open()


@month_card_bp.route('/manual-open-batch', methods=['POST'])
@login_required('month-card-open')
def manual_open_month_cards():
    return _manual_open(batch=True)


@month_card_bp.route('/config',methods=['POST'])
@login_required('settlement')
def update_month_card_config():
    from flask import abort
    if not g.staff.headquarters:abort(403)
    from app.models import Config
    try:
        data=_read_json();price=data.get('Price');note=str(data.get('Note') or '').strip()
        if isinstance(price,bool) or not isinstance(price,int) or not 0<price<=1000000 or not note or len(note)>500:
            raise ValueError('请输入有效月卡价格（整数分）和调整说明')
        row=Config.query.filter_by(config_key='MonthCardConfig').populate_existing().with_for_update().first()
        if row:
            import json
            value=json.loads(row.config_value) if isinstance(row.config_value,str) else dict(row.config_value)
            if data.get('ExpectedPrice')!=value.get('CommonPrice'):raise ValueError('配置已变化，请刷新后重试')
            value['CommonPrice']=price;row.config_value=value;row.updated_at=_now()
        else:
            raise ValueError('缺少基础月卡配置，请先初始化 MonthCardConfig')
        audit('month-card:price','MonthCardConfig',{'price':price,'note':note})
        db.session.commit();return jsonify(Code=0,Data={'Price':price,'DurationDays':30})
    except ValueError as exc:
        db.session.rollback();return jsonify(Code=400,Message=str(exc)),400
