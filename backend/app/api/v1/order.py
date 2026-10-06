from flask import Blueprint, current_app, jsonify, request
from app.models import PlayOrder, User
from datetime import datetime
from decimal import Decimal, InvalidOperation
from app.middlewares.auth import login_required
from app.utils.crypto import decrypt_phone
from app.utils.store import get_request_store_id
import requests

order_bp = Blueprint('order', __name__)


def _operator_label():
    user = getattr(request, 'user', {}) or {}
    user_id = next((user[key] for key in ('user_id', 'id', 'sub')
                    if user.get(key) is not None), None)
    return f'OA#{user_id}' if user_id is not None else 'OA'


def _call_gambit_server_play(method, action, *, params=None, data=None):
    base_url = current_app.config.get('GAMBIT_SERVER_BASE_URL')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN')
    if not base_url or not token:
        raise RuntimeError('GambitServer 地址或内部 token 未配置')

    response = requests.request(
        method,
        f'{base_url}/microapp_api/admin/play/v1/{action}',
        params=params,
        json=data,
        headers={'X-GAMBIT-INTERNAL-TOKEN': token},
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get('Code') != 0:
        raise RuntimeError(payload.get('Msg') or payload.get('Message') or 'GambitServer 操作失败')
    return payload


def _amount_yuan_to_cents(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('请输入正确的结算金额')
    if not amount.is_finite() or amount < 0 or amount.as_tuple().exponent < -2:
        raise ValueError('结算金额必须大于等于 0，且最多保留两位小数')
    return int(amount * 100)


@order_bp.route('/workbench', methods=['GET'])
@login_required('workbench')
def get_play_workbench():
    try:
        payload = _call_gambit_server_play(
            'GET',
            'workbench',
            params={'StoreID': get_request_store_id()},
        )
        return jsonify(payload)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        return jsonify({'Code': 1, 'Message': str(error), 'Data': None})


@order_bp.route('/workbench/settle/<int:order_id>', methods=['POST'])
@login_required('workbench')
def settle_play_workbench_order(order_id):
    PlayOrder.query.filter_by(id=order_id).first_or_404()
    data = request.get_json(silent=True) or {}
    try:
        amount = _amount_yuan_to_cents(data.get('Amount'))
        comment = data.get('Comment') or ''
        if not isinstance(comment, str) or len(comment) > 500:
            raise ValueError('备注必须为不超过 500 字的文本')
        payload = _call_gambit_server_play(
            'POST',
            'settle',
            data={
                'PlayOrderID': order_id,
                'StoreID': get_request_store_id(),
                'Amount': amount,
                'Comment': comment.strip(),
                'Operator': _operator_label(),
            },
        )
        return jsonify(payload)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        return jsonify({'Code': 1, 'Message': str(error), 'Data': None})


@order_bp.route('/workbench/quick-settle/<int:order_id>', methods=['POST'])
@login_required('workbench')
def quick_settle_play_workbench_order(order_id):
    PlayOrder.query.filter_by(id=order_id).first_or_404()
    try:
        payload = _call_gambit_server_play(
            'POST',
            'quick-settle',
            data={
                'PlayOrderID': order_id,
                'StoreID': get_request_store_id(),
                'Operator': _operator_label(),
            },
        )
        return jsonify(payload)
    except (requests.RequestException, RuntimeError, ValueError) as error:
        return jsonify({'Code': 1, 'Message': str(error), 'Data': None})


@order_bp.route('/list', methods=['GET'])
@login_required('orders')
def get_order_list():
    # 获取查询参数并打印
    print("收到的请求参数:", request.args)
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 10, type=int)
    open_id = request.args.get('OpenId')
    user_id = request.args.get('UserId', type=int)
    settle_status = request.args.get('SettleStatus', type=int)

    # 添加入场时间和出场时间的范围筛选
    in_time_start = request.args.get('InTimeStart')
    in_time_end = request.args.get('InTimeEnd')
    out_time_start = request.args.get('OutTimeStart')
    out_time_end = request.args.get('OutTimeEnd')

    start_time = request.args.get('StartTime')
    end_time = request.args.get('EndTime')

    # 构建查询条件
    query = PlayOrder.query.outerjoin(User, PlayOrder.open_id == User.open_id)\
        .filter(PlayOrder.deleted_at.is_(None))

    if open_id:
        query = query.filter(PlayOrder.open_id == open_id)
    if user_id:
        query = query.filter(User.id == user_id)
    if settle_status is not None:
        query = query.filter(PlayOrder.settle_status == settle_status)

    # 添加入场时间范围筛选
    if in_time_start:
        in_start_datetime = datetime.strptime(in_time_start, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.in_time >= in_start_datetime)
    if in_time_end:
        in_end_datetime = datetime.strptime(in_time_end, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.in_time <= in_end_datetime)

    # 添加出场时间范围筛选
    if out_time_start:
        out_start_datetime = datetime.strptime(out_time_start, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.out_time >= out_start_datetime)
    if out_time_end:
        out_end_datetime = datetime.strptime(out_time_end, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.out_time <= out_end_datetime)

    if start_time:
        start_datetime = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.created_at >= start_datetime)
    if end_time:
        end_datetime = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S')
        query = query.filter(PlayOrder.created_at <= end_datetime)

    # 分页查询
    pagination = query.order_by(PlayOrder.created_at.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False
    )

    # 格式化返回数据
    orders = [{
        'Id': order.id,
        'StoreId': order.store_id,
        'OpenId': order.open_id,
        'InTime': order.in_time.strftime('%Y-%m-%d %H:%M:%S') if order.in_time else None,
        'OutTime': order.out_time.strftime('%Y-%m-%d %H:%M:%S') if order.out_time else None,
        'PlayTime': order.play_time,
        'Amount': order.amount,
        'SettleStatus': order.settle_status,
        'Comment': order.comment,
        'UnitPrice': order.unit_price,
        'CreatedAt': order.created_at.strftime('%Y-%m-%d %H:%M:%S') if order.created_at else None,
        'UpdatedAt': order.updated_at.strftime('%Y-%m-%d %H:%M:%S') if order.updated_at else None,
        'User': {
            'Id': order.user.id if order.user else None,
            'OpenId': order.open_id,
            'NickName': order.user.nick_name if order.user else None,
            'Phone': decrypt_phone(order.user.phone_number) if order.user and order.user.phone_number else None
        }
    } for order in pagination.items]

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': orders
        }
    })
