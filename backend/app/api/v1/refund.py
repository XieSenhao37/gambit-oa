from flask import Blueprint, current_app, jsonify, request
import requests
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from app.middlewares.auth import login_required
from app.models import (
    Catering,
    GroupActivity,
    GroupActivityParticipant,
    PlayOrder,
    RefundRequest,
    User,
)
from app.utils.crypto import decrypt_phone, encrypt_phone

refund_bp = Blueprint('refund', __name__)


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _safe_decrypt_phone(value):
    if not value:
        return None
    try:
        return decrypt_phone(value)
    except Exception:
        return None


def _format_price(value):
    return value or 0


def _get_order_snapshot(refund_request, organization_participant=None):
    if refund_request.order_type == 'catering':
        order = Catering.query.filter(
            Catering.id == refund_request.order_id,
            Catering.deleted_at.is_(None),
        ).first()
        if not order:
            return None
        return {
            'TypeText': '吃喝订单',
            'StatusText': {0: '制作中', 1: '可取餐', 2: '已完成'}.get(order.status, '未知'),
            'Title': f'取餐号 {order.code}',
            'Amount': _format_price(order.total_price),
            'CreatedAt': _format_time(order.created_at),
        }

    if refund_request.order_type == 'play':
        order = PlayOrder.query.filter(
            PlayOrder.id == refund_request.order_id,
            PlayOrder.deleted_at.is_(None),
        ).first()
        if not order:
            return None
        return {
            'TypeText': '玩乐订单',
            'StatusText': '已结算' if order.settle_status == 1 else '待结算',
            'Title': f'游玩 {order.play_time or "-"} 小时',
            'Amount': _format_price(order.amount),
            'CreatedAt': _format_time(order.created_at),
        }

    if refund_request.order_type == 'organization':
        participant = organization_participant
        if not participant:
            return None

        activity = participant.activity
        registration_status_text = {
            0: '待支付',
            1: '已报名',
            2: '已取消',
        }.get(participant.status, '未知')
        return {
            'TypeText': '组局意向金',
            'StatusText': registration_status_text,
            'Title': activity.title if activity else f'组局报名 {participant.id}',
            'Amount': _format_price(refund_request.amount),
            'CreatedAt': _format_time(participant.created_at),
            'ActivityId': activity.id if activity else participant.activity_id,
            'ActivityTitle': activity.title if activity else None,
            'StoreId': activity.store_id if activity else None,
            'StoreName': activity.store.name if activity and activity.store else None,
            'ActivityStartTime': _format_time(activity.start_time) if activity else None,
            'RegistrationStatus': participant.status,
        }

    return None


def _serialize_refund(refund_request, organization_participant=None):
    user = (
        organization_participant.user
        if refund_request.order_type == 'organization'
        and organization_participant
        and organization_participant.user
        else refund_request.user
    )
    return {
        'Id': refund_request.id,
        'OrderType': refund_request.order_type,
        'OrderId': refund_request.order_id,
        'PayOrderId': refund_request.pay_order_id,
        'Amount': refund_request.amount,
        'Status': refund_request.status,
        'OutRefundNo': refund_request.out_refund_no,
        'WxRefundId': refund_request.wx_refund_id,
        'ReviewRemark': refund_request.review_remark,
        'RefundError': refund_request.refund_error,
        'CreatedAt': _format_time(refund_request.created_at),
        'UpdatedAt': _format_time(refund_request.updated_at),
        'ReviewedAt': _format_time(refund_request.reviewed_at),
        'RefundedAt': _format_time(refund_request.refunded_at),
        'User': {
            'Id': user.id,
            'NickName': user.nick_name,
            'Phone': _safe_decrypt_phone(user.phone_number),
        } if user else None,
        'PayOrder': {
            'Id': refund_request.pay_order.id,
            'OrderId': refund_request.pay_order.order_id,
            'PayStatus': refund_request.pay_order.pay_status,
            'PayType': refund_request.pay_order.pay_type,
            'PayEndTime': _format_time(refund_request.pay_order.pay_end_time),
            'GroupActivityParticipantId': refund_request.pay_order.group_activity_participant_id,
        } if refund_request.pay_order else None,
        'OrderSnapshot': _get_order_snapshot(refund_request, organization_participant),
    }


def _call_gambit_server_refund_action(refund_request_id, action, payload=None):
    base_url = current_app.config.get('GAMBIT_SERVER_BASE_URL')
    token = current_app.config.get('GAMBIT_INTERNAL_TOKEN')
    if not base_url or not token:
        raise RuntimeError('GambitServer 地址或内部 token 未配置')

    body = {
        'RefundRequestID': refund_request_id,
        **(payload or {}),
    }
    response = requests.post(
        f'{base_url}/microapp_api/admin/refund/v1/{action}',
        json=body,
        headers={'X-GAMBIT-INTERNAL-TOKEN': token},
        timeout=12,
    )
    response.raise_for_status()
    data = response.json()
    if data.get('Code') != 0:
        raise RuntimeError(data.get('Msg') or data.get('Message') or 'GambitServer 退款操作失败')
    return data.get('Data')


@refund_bp.route('/list', methods=['GET'])
@login_required('refunds')
def list_refunds():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    status = request.args.get('Status')
    order_type = request.args.get('OrderType')
    keyword = (request.args.get('Keyword') or '').strip()

    query = RefundRequest.query.outerjoin(User, User.open_id == RefundRequest.open_id).filter(
        RefundRequest.deleted_at.is_(None),
    )

    if status:
        query = query.filter(RefundRequest.status == status)
    if order_type:
        query = query.filter(RefundRequest.order_type == order_type)
    if keyword:
        like_keyword = f'%{keyword}%'
        encrypted_phone = encrypt_phone(keyword)
        query = query.outerjoin(
            GroupActivityParticipant,
            and_(
                RefundRequest.order_type == 'organization',
                RefundRequest.order_id == GroupActivityParticipant.id,
                GroupActivityParticipant.deleted_at.is_(None),
            ),
        ).outerjoin(
            GroupActivity,
            and_(
                GroupActivity.id == GroupActivityParticipant.activity_id,
                GroupActivity.deleted_at.is_(None),
            ),
        )
        query = query.filter(
            or_(
                RefundRequest.open_id.like(like_keyword),
                User.nick_name.like(like_keyword),
                User.phone_number == encrypted_phone,
                GroupActivity.title.like(like_keyword),
            )
        )

    pagination = query.order_by(RefundRequest.created_at.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )

    participant_ids = [
        item.order_id
        for item in pagination.items
        if item.order_type == 'organization'
    ]
    organization_participants = {}
    if participant_ids:
        participants = GroupActivityParticipant.query.options(
            selectinload(GroupActivityParticipant.activity).selectinload(GroupActivity.store),
            selectinload(GroupActivityParticipant.user),
        ).filter(
            GroupActivityParticipant.id.in_(participant_ids),
            GroupActivityParticipant.deleted_at.is_(None),
        ).all()
        organization_participants = {
            participant.id: participant
            for participant in participants
        }

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [
                _serialize_refund(
                    item,
                    organization_participants.get(item.order_id),
                )
                for item in pagination.items
            ],
        },
    })


@refund_bp.route('/approve/<int:refund_request_id>', methods=['POST'])
@login_required('refunds')
def approve_refund(refund_request_id):
    RefundRequest.query.filter_by(id=refund_request_id).first_or_404()
    try:
        data = _call_gambit_server_refund_action(refund_request_id, 'approve')
    except Exception as exc:
        return jsonify({
            'Code': 500,
            'Message': str(exc),
            'Data': None,
        }), 500

    return jsonify({
        'Code': 0,
        'Message': '已发起微信退款',
        'Data': data,
    })


@refund_bp.route('/reject/<int:refund_request_id>', methods=['POST'])
@login_required('refunds')
def reject_refund(refund_request_id):
    RefundRequest.query.filter_by(id=refund_request_id).first_or_404()
    remark = (request.get_json() or {}).get('Remark', '')
    try:
        data = _call_gambit_server_refund_action(
            refund_request_id,
            'reject',
            {'Remark': remark},
        )
    except Exception as exc:
        return jsonify({
            'Code': 500,
            'Message': str(exc),
            'Data': None,
        }), 500

    return jsonify({
        'Code': 0,
        'Message': '已拒绝退款申请',
        'Data': data,
    })
