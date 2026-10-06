import json
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app import db
from app.middlewares.auth import login_required
from app.models import Catering, CateringItem, PayOrder, User
from app.utils.crypto import decrypt_phone
from app.utils.store import get_request_store_id

catering_bp = Blueprint('catering', __name__)


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _safe_decrypt_phone(value):
    if not value:
        return None
    try:
        return decrypt_phone(value)
    except Exception:
        return None


def _now_shanghai_naive():
    return datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)


def _format_selections(selections):
    if not selections:
        return ''
    if isinstance(selections, str):
        try:
            selections = json.loads(selections)
        except Exception:
            return selections
    if isinstance(selections, list):
        parts = []
        for item in selections:
            if isinstance(item, dict):
                name = item.get('name') or item.get('Name') or ''
                option_name = item.get('optionName') or item.get('option_name') or item.get('OptionName')
                if option_name and name:
                    parts.append(f'{option_name}：{name}')
                elif name:
                    parts.append(str(name))
            else:
                parts.append(str(item))
        return '，'.join([part for part in parts if part])
    if isinstance(selections, dict):
        parts = []
        for key, value in selections.items():
            if isinstance(value, list):
                parts.append(f'{key}：{"、".join(map(str, value))}')
            else:
                parts.append(f'{key}：{value}')
        return '，'.join(parts)
    return str(selections)


def _serialize_catering(order, selected_pay_order=None):
    now = _now_shanghai_naive()
    waiting_minutes = int((now - order.created_at).total_seconds() // 60) if order.created_at else 0
    ready_minutes = int((now - order.updated_at).total_seconds() // 60) if order.updated_at and order.status == 1 else 0
    pay_order = selected_pay_order if selected_pay_order is not None else order.pay_order

    return {
        'Id': order.id,
        'StoreId': order.store_id,
        'Code': order.code,
        'OpenId': order.open_id,
        'Status': order.status,
        'SettleStatus': order.settle_status,
        'Takeaway': bool(order.takeaway),
        'TotalPrice': order.total_price,
        'Comment': order.comment,
        'CreatedAt': _format_time(order.created_at),
        'UpdatedAt': _format_time(order.updated_at),
        'WaitingMinutes': waiting_minutes,
        'ReadyMinutes': ready_minutes,
        'TableInfo': {
            'Id': order.table.id,
            'Name': order.table.name,
            'Area': order.table.area,
        } if order.table else None,
        'User': {
            'Id': order.user.id,
            'NickName': order.user.nick_name,
            'Phone': _safe_decrypt_phone(order.user.phone_number),
        } if order.user else None,
        'PayOrder': {
            'Id': pay_order.id,
            'OrderId': pay_order.order_id,
            'PayStatus': pay_order.pay_status,
            'PayType': pay_order.pay_type,
            'Amount': pay_order.amount,
            'WalletAmount': pay_order.wallet_amount,
            'WechatAmount': pay_order.wechat_amount,
            'DiscountAmount': pay_order.discount_amount,
            'TotalAmount': pay_order.total_amount,
            'RefundAmount': pay_order.refund_amount,
            'Description': pay_order.description,
            'ExpireTime': _format_time(pay_order.expire_time),
            'PayEndTime': _format_time(pay_order.pay_end_time),
            'CreatedAt': _format_time(pay_order.created_at),
            'UpdatedAt': _format_time(pay_order.updated_at),
        } if pay_order else None,
        'Items': [{
            'Id': item.id,
            'DishName': item.dish.name if item.dish else '',
            'Count': item.count,
            'TotalPrice': item.total_price,
            'Selections': item.selections,
            'SelectionsText': _format_selections(item.selections),
        } for item in order.items],
    }


def _call_gambit_server_catering_action(catering_id, action):
    base_url = current_app.config.get('GAMBIT_SERVER_BASE_URL')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN')
    if not base_url or not token:
        raise RuntimeError('GambitServer 地址或内部 token 未配置')

    response = requests.post(
        f'{base_url}/microapp_api/admin/catering/v1/{action}',
        json={'CateringID': catering_id},
        headers={'X-GAMBIT-INTERNAL-TOKEN': token},
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get('Code') != 0:
        raise RuntimeError(payload.get('Msg') or payload.get('Message') or 'GambitServer 更新失败')
    return payload.get('Data')


def _call_gambit_server_finish(catering_id):
    return _call_gambit_server_catering_action(catering_id, 'finish')


def _call_gambit_server_complete(catering_id):
    return _call_gambit_server_catering_action(catering_id, 'complete')


@catering_bp.route('/list', methods=['GET'])
@login_required('workbench')
def get_catering_list():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('Status', type=int)
    keyword = request.args.get('Keyword')
    only_today = request.args.get('OnlyToday', '1') != '0'
    store_id = get_request_store_id()

    query = Catering.query.join(PayOrder, PayOrder.catering_id == Catering.id)\
        .outerjoin(User, User.open_id == Catering.open_id)\
        .filter(
            Catering.deleted_at.is_(None),
            Catering.store_id == store_id,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )\
        .options(
            selectinload(Catering.items).selectinload(CateringItem.dish),
            selectinload(Catering.pay_order),
            selectinload(Catering.user),
        )

    if status is not None:
        query = query.filter(Catering.status == status)

    if only_today:
        today_start = _now_shanghai_naive().replace(hour=0, minute=0, second=0, microsecond=0)
        query = query.filter(Catering.created_at >= today_start)

    if keyword:
        like_keyword = f'%{keyword}%'
        query = query.filter(
            (Catering.code.like(like_keyword)) |
            (Catering.open_id.like(like_keyword)) |
            (User.nick_name.like(like_keyword))
        )

    pagination = query.order_by(Catering.status.asc(), Catering.created_at.asc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False
    )

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_catering(order) for order in pagination.items],
        }
    })


@catering_bp.route('/history', methods=['GET'])
@login_required('catering-orders')
def get_catering_history():
    page = request.args.get('current', 1, type=int) or 1
    page_size = min(request.args.get('pageSize', 20, type=int) or 20, 100)
    status = request.args.get('Status', type=int)
    pay_status = request.args.get('PayStatus')
    keyword = (request.args.get('Keyword') or '').strip()
    start_time = request.args.get('StartTime')
    end_time = request.args.get('EndTime')
    store_id = get_request_store_id()

    latest_pay_order = db.session.query(
        PayOrder.catering_id.label('catering_id'),
        func.max(PayOrder.id).label('pay_order_id'),
    ).filter(
        PayOrder.deleted_at.is_(None),
        PayOrder.catering_id.isnot(None),
    ).group_by(PayOrder.catering_id).subquery()

    query = db.session.query(Catering, PayOrder)\
        .outerjoin(
            latest_pay_order,
            latest_pay_order.c.catering_id == Catering.id,
        )\
        .outerjoin(PayOrder, PayOrder.id == latest_pay_order.c.pay_order_id)\
        .outerjoin(User, User.open_id == Catering.open_id)\
        .filter(
            Catering.deleted_at.is_(None),
            Catering.store_id == store_id,
        )\
        .options(
            selectinload(Catering.items).selectinload(CateringItem.dish),
            selectinload(Catering.table),
            selectinload(Catering.user),
        )

    if status is not None:
        query = query.filter(Catering.status == status)

    if pay_status == 'none':
        query = query.filter(PayOrder.id.is_(None))
    elif pay_status not in (None, ''):
        try:
            pay_status_value = int(pay_status)
        except (TypeError, ValueError):
            return jsonify({
                'Code': 1,
                'Message': '支付状态参数错误',
                'Data': None,
            }), 400
        if pay_status_value not in (0, 1, 2, 3):
            return jsonify({
                'Code': 1,
                'Message': '支付状态参数错误',
                'Data': None,
            }), 400
        query = query.filter(PayOrder.pay_status == pay_status_value)

    if keyword:
        conditions = [
            Catering.code.like(f'%{keyword}%'),
            Catering.open_id.like(f'%{keyword}%'),
            User.nick_name.like(f'%{keyword}%'),
        ]
        if keyword.isdigit():
            conditions.append(Catering.id == int(keyword))
        query = query.filter(or_(*conditions))

    try:
        if start_time:
            query = query.filter(
                Catering.created_at >= datetime.strptime(
                    start_time,
                    '%Y-%m-%d %H:%M:%S',
                ),
            )
        if end_time:
            query = query.filter(
                Catering.created_at <= datetime.strptime(
                    end_time,
                    '%Y-%m-%d %H:%M:%S',
                ),
            )
    except ValueError:
        return jsonify({
            'Code': 1,
            'Message': '创建时间参数格式错误',
            'Data': None,
        }), 400

    pagination = query.order_by(Catering.created_at.desc()).paginate(
        page=max(page, 1),
        per_page=max(page_size, 1),
        error_out=False,
    )
    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [
                _serialize_catering(order, pay_order)
                for order, pay_order in pagination.items
            ],
        },
    })


@catering_bp.route('/finish/<int:catering_id>', methods=['POST'])
@login_required('workbench')
def finish_catering(catering_id):
    Catering.query.filter_by(id=catering_id).first_or_404()
    try:
        data = _call_gambit_server_finish(catering_id)
    except Exception as exc:
        return jsonify({
            'Code': 500,
            'Message': str(exc),
            'Data': None,
        }), 500

    return jsonify({
        'Code': 0,
        'Message': '制作完成，顾客端已更新为可取餐',
        'Data': data,
    })


@catering_bp.route('/complete/<int:catering_id>', methods=['POST'])
@login_required('workbench')
def complete_catering(catering_id):
    Catering.query.filter_by(id=catering_id).first_or_404()
    try:
        _call_gambit_server_complete(catering_id)
    except Exception as exc:
        return jsonify({
            'Code': 500,
            'Message': str(exc),
            'Data': None,
        }), 500

    return jsonify({
        'Code': 0,
        'Message': '订单已完成',
        'Data': None,
    })
