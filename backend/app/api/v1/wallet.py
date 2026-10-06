"""充值档位管理接口（OA 直连数据库，供小程序读取使用）"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from app import db
from app.middlewares.auth import login_required
from app.models import WalletRechargeTier

wallet_bp = Blueprint('wallet', __name__)


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _serialize_tier(tier):
    return {
        'Id': tier.id,
        'Amount': tier.amount,
        'BonusAmount': tier.bonus_amount,
        'Label': tier.label or '',
        'Sort': tier.sort,
        'Enabled': int(tier.enabled) if tier.enabled is not None else 1,
        'CreatedAt': _format_time(tier.created_at),
        'UpdatedAt': _format_time(tier.updated_at),
    }


def _read_value(key, default=None):
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return data.get(key, default)
    if request.form and key in request.form:
        return request.form.get(key)
    return default


def _build_tier_from_body():
    amount_raw = _read_value('Amount')
    if amount_raw is None or amount_raw == '':
        raise ValueError('充值金额不能为空')
    try:
        amount = int(amount_raw)
    except (TypeError, ValueError):
        raise ValueError('充值金额必须是整数（单位：分）')
    if amount < 100:
        raise ValueError('充值金额不能小于 1 元')
    if amount > 500000:
        raise ValueError('充值金额不能大于 5000 元')

    bonus_raw = _read_value('BonusAmount', 0)
    try:
        bonus_amount = int(bonus_raw) if bonus_raw not in (None, '') else 0
    except (TypeError, ValueError):
        raise ValueError('赠送金额必须是整数（单位：分）')
    if bonus_amount < 0:
        raise ValueError('赠送金额不能为负数')

    label = (_read_value('Label') or '').strip()
    if len(label) > 64:
        raise ValueError('档位文案过长，最多 64 字')

    sort_raw = _read_value('Sort', 0)
    try:
        sort = int(sort_raw) if sort_raw not in (None, '') else 0
    except (TypeError, ValueError):
        raise ValueError('排序必须是整数')

    enabled_raw = _read_value('Enabled', 1)
    try:
        enabled = int(enabled_raw) if enabled_raw not in (None, '') else 1
    except (TypeError, ValueError):
        raise ValueError('启用状态必须为 0 或 1')
    if enabled not in (0, 1):
        raise ValueError('启用状态必须为 0 或 1')

    return {
        'amount': amount,
        'bonus_amount': bonus_amount,
        'label': label or None,
        'sort': sort,
        'enabled': enabled,
    }


@wallet_bp.route('/tiers', methods=['GET'])
@login_required('wallet-tiers')
def list_tiers():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 50, type=int)

    query = WalletRechargeTier.query.filter(WalletRechargeTier.deleted_at.is_(None))
    pagination = query.order_by(
        WalletRechargeTier.sort.asc(), WalletRechargeTier.amount.asc()
    ).paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_tier(tier) for tier in pagination.items],
        },
    })


@wallet_bp.route('/tiers', methods=['POST'])
@login_required('wallet-tiers')
def create_tier():
    try:
        payload = _build_tier_from_body()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400

    now = datetime.utcnow()
    tier = WalletRechargeTier(
        amount=payload['amount'],
        bonus_amount=payload['bonus_amount'],
        label=payload['label'],
        sort=payload['sort'],
        enabled=payload['enabled'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(tier)
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '创建成功',
        'Data': _serialize_tier(tier),
    })


@wallet_bp.route('/tiers/<int:tier_id>', methods=['PUT'])
@login_required('wallet-tiers')
def update_tier(tier_id):
    tier = WalletRechargeTier.query.filter(
        WalletRechargeTier.id == tier_id, WalletRechargeTier.deleted_at.is_(None)
    ).first()
    if not tier:
        return jsonify({'Code': 404, 'Message': '充值档位不存在', 'Data': None}), 404

    try:
        payload = _build_tier_from_body()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400

    tier.amount = payload['amount']
    tier.bonus_amount = payload['bonus_amount']
    tier.label = payload['label']
    tier.sort = payload['sort']
    tier.enabled = payload['enabled']
    tier.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '更新成功',
        'Data': _serialize_tier(tier),
    })


@wallet_bp.route('/tiers/<int:tier_id>/status', methods=['PATCH'])
@login_required('wallet-tiers')
def update_tier_status(tier_id):
    tier = WalletRechargeTier.query.filter(
        WalletRechargeTier.id == tier_id, WalletRechargeTier.deleted_at.is_(None)
    ).first()
    if not tier:
        return jsonify({'Code': 404, 'Message': '充值档位不存在', 'Data': None}), 404

    body = request.get_json(silent=True) or {}
    raw_status = body.get('Enabled')
    if raw_status is None:
        return jsonify({'Code': 1, 'Message': '缺少 Enabled 字段', 'Data': None}), 400
    try:
        enabled = int(raw_status)
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': 'Enabled 必须为 0 或 1', 'Data': None}), 400
    if enabled not in (0, 1):
        return jsonify({'Code': 1, 'Message': 'Enabled 必须为 0 或 1', 'Data': None}), 400

    tier.enabled = enabled
    tier.updated_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '启用成功' if enabled == 1 else '停用成功',
        'Data': _serialize_tier(tier),
    })


@wallet_bp.route('/tiers/<int:tier_id>', methods=['DELETE'])
@login_required('wallet-tiers')
def delete_tier(tier_id):
    tier = WalletRechargeTier.query.filter(
        WalletRechargeTier.id == tier_id, WalletRechargeTier.deleted_at.is_(None)
    ).first()
    if not tier:
        return jsonify({'Code': 404, 'Message': '充值档位不存在', 'Data': None}), 404

    tier.deleted_at = datetime.utcnow()
    db.session.commit()

    return jsonify({
        'Code': 0,
        'Message': '删除成功',
        'Data': None,
    })
