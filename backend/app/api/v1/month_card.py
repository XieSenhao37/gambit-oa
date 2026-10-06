from datetime import datetime

from flask import Blueprint, jsonify, request, g

from app import db
from app.middlewares.auth import login_required
from app.models import MonthCardOrder, User
from app.utils.crypto import decrypt_phone
from app.security.policy import audit
from app.settlement.card_config import card_config

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
@login_required('users')
def get_month_card_config():
    try:
        _,value,price=card_config()
        return jsonify(Code=0,Data={'Price':price,'DurationDays':30,'MonthLimit':value.get('MonthLimit',0)})
    except ValueError as exc:
        return jsonify(Code=400,Message=str(exc)),400


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
