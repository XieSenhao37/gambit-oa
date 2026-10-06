"""积分系统管理接口（OA 直连数据库，供小程序读取使用）

包含：积分商品分类 CRUD、积分商品 CRUD（含图片/上下架/删除）、积分提取审计（只读）、积分规则配置读写。
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import re

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from app import db
from app.middlewares.auth import login_required
from app.models import (
    Config,
    PointProduct,
    PointProductCategory,
    PointRedeemOrder,
    PointWithdrawRecord,
    User,
)
from app.services.cos_service import upload_file_to_cos
from app.settlement.models import SettlementCostRule
from app.security.policy import audit

point_bp = Blueprint('point', __name__)

ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB
SHANGHAI_TZ = ZoneInfo('Asia/Shanghai')
_MISSING = object()

POINT_CONFIG_KEY = 'PointConfig'
DEFAULT_POINT_CONFIG = {
    'EarnThresholdAmount': 1000,
    'EarnPoints': 1,
    'MaxWithdrawPerTime': 0,
}

WITHDRAW_STATUS_TEXT = {
    0: '待发放',
    1: '已发放',
    2: '已过期',
    3: '已取消',
}

REDEEM_ORDER_STATUS_TEXT = {
    0: '待领取',
    1: '已完成',
    2: '已取消',
}


def _format_time(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _read_form_value(key, *, default=None):
    """form-data 或 JSON body 都能读到字段。"""
    if request.form and key in request.form:
        return request.form.get(key)
    if request.is_json:
        data = request.get_json(silent=True) or {}
        return data.get(key, default)
    return default


def _parse_redeem_start_at(raw_value, *, now=None):
    """将 13 位 epoch 毫秒转换为 Asia/Shanghai 的无时区 datetime。"""
    if raw_value in (None, ''):
        return None

    value = str(raw_value).strip()
    if len(value) != 13 or not value.isdigit():
        raise ValueError('开兑时间必须为 13 位毫秒时间戳')

    try:
        redeem_start_at = datetime.fromtimestamp(
            int(value) / 1000,
            tz=SHANGHAI_TZ,
        ).replace(tzinfo=None)
    except (OverflowError, OSError, ValueError):
        raise ValueError('开兑时间无效')

    now_shanghai = now or datetime.now(SHANGHAI_TZ).replace(tzinfo=None)
    if redeem_start_at <= now_shanghai:
        raise ValueError('定时开兑时间必须晚于当前时间')
    return redeem_start_at


def _parse_max_redeem_per_user(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError('每人限兑必须是整数')
    if value != -1 and value < 1:
        raise ValueError('每人限兑必须为 -1（不限）或大于等于 1')
    return value


def _parse_product_status(raw_value):
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        raise ValueError('状态必须为 0 或 1')
    if value not in (0, 1):
        raise ValueError('状态必须为 0 或 1')
    return value


def _validate_and_upload_image(file_storage):
    filename = (file_storage.filename or '').lower()
    if '.' not in filename:
        raise ValueError('图片缺少扩展名')
    ext = '.' + filename.rsplit('.', 1)[-1]
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError(f'图片格式不支持，仅支持 {", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}')
    file_bytes = file_storage.read()
    if not file_bytes:
        raise ValueError('图片内容为空')
    if len(file_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f'图片大小超过 {MAX_IMAGE_BYTES // 1024 // 1024}MB')
    return upload_file_to_cos(file_bytes, file_storage.filename, folder='point-products')


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------

def _serialize_category(category):
    return {
        'Id': category.id,
        'Name': category.name,
        'Sort': category.sort,
        'Status': int(category.status) if category.status is not None else 1,
        'CreatedAt': _format_time(category.created_at),
        'UpdatedAt': _format_time(category.updated_at),
    }


def _serialize_product(product, category_map=None):
    category_name = ''
    if category_map is not None and product.category_id is not None:
        category_name = category_map.get(product.category_id, '')
    cost_rule = db.session.get(SettlementCostRule, f'product:{product.id}')
    return {
        'SettlementPrice': cost_rule.amount if cost_rule else None,
        'Id': product.id,
        'Name': product.name,
        'CategoryId': product.category_id,
        'CategoryName': category_name,
        'Description': product.description or '',
        'PointsPrice': product.points_price,
        'OriginalPrice': product.original_price,
        'ImageUrl': product.image_url or '',
        'Stock': product.stock if product.stock is not None else -1,
        'Sort': product.sort,
        'Status': int(product.status) if product.status is not None else 1,
        'RedeemStartAt': _format_time(product.redeem_start_at),
        'MaxRedeemPerUser': (
            product.max_redeem_per_user
            if product.max_redeem_per_user is not None
            else -1
        ),
        'CreatedAt': _format_time(product.created_at),
        'UpdatedAt': _format_time(product.updated_at),
    }


def _serialize_withdraw(record):
    user = record.user
    issuer = record.issuer
    return {
        'Id': record.id,
        'OpenID': record.open_id,
        'UserNickName': user.nick_name if user else '',
        'Points': record.points,
        'Status': int(record.status) if record.status is not None else 0,
        'StatusText': WITHDRAW_STATUS_TEXT.get(int(record.status) if record.status is not None else 0, ''),
        'IssuerOpenID': record.issuer_open_id or '',
        'IssuerNickName': issuer.nick_name if issuer else '',
        'IssuedAt': _format_time(record.issued_at),
        'ExpireAt': _format_time(record.expire_at),
        'CreatedAt': _format_time(record.created_at),
    }


def _serialize_redeem_order(order, user_map=None, verifier_map=None):
    user = user_map.get(order.open_id) if user_map is not None else order.user
    if verifier_map is not None:
        verifier = verifier_map.get(order.verifier_open_id) if order.verifier_open_id else None
    else:
        verifier = order.verifier
    status = int(order.status) if order.status is not None else 0
    return {
        'Id': order.id,
        'OrderNo': order.order_no,
        'OpenID': order.open_id,
        'UserNickName': user.nick_name if user else '',
        'ProductId': order.product_id,
        'ProductName': order.product_name,
        'ProductImageUrl': order.product_image_url or '',
        'PointsPrice': order.points_price,
        'Quantity': order.quantity,
        'TotalPoints': order.total_points,
        'Status': status,
        'StatusText': REDEEM_ORDER_STATUS_TEXT.get(status, ''),
        'VerifierOpenID': order.verifier_open_id or '',
        'VerifierNickName': verifier.nick_name if verifier else '',
        'VerifiedAt': _format_time(order.verified_at),
        'CreatedAt': _format_time(order.created_at),
        'UpdatedAt': _format_time(order.updated_at),
    }


# ---------------------------------------------------------------------------
# 积分商品分类
# ---------------------------------------------------------------------------

def _build_category_from_body():
    name = (_read_form_value('Name') or '').strip()
    if not name:
        raise ValueError('分类名称不能为空')
    if len(name) > 60:
        raise ValueError('分类名称过长，最多 60 字')

    sort_raw = _read_form_value('Sort', default=0)
    try:
        sort = int(sort_raw) if sort_raw not in (None, '') else 0
    except (TypeError, ValueError):
        raise ValueError('排序必须是整数')

    status_raw = _read_form_value('Status', default=1)
    try:
        status = int(status_raw) if status_raw not in (None, '') else 1
    except (TypeError, ValueError):
        raise ValueError('状态必须为 0 或 1')
    if status not in (0, 1):
        raise ValueError('状态必须为 0 或 1')

    return {'name': name, 'sort': sort, 'status': status}


@point_bp.route('/categories', methods=['GET'])
@login_required('point-categories', 'point-products')
def list_categories():
    categories = PointProductCategory.query.filter(
        PointProductCategory.deleted_at.is_(None)
    ).order_by(PointProductCategory.sort.asc(), PointProductCategory.id.asc()).all()
    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Items': [_serialize_category(c) for c in categories],
            'Total': len(categories),
        },
    })


@point_bp.route('/categories', methods=['POST'])
@login_required('point-categories')
def create_category():
    try:
        payload = _build_category_from_body()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400

    now = datetime.utcnow()
    category = PointProductCategory(
        name=payload['name'],
        sort=payload['sort'],
        status=payload['status'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(category)
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '创建成功', 'Data': _serialize_category(category)})


@point_bp.route('/categories/<int:category_id>', methods=['PUT'])
@login_required('point-categories')
def update_category(category_id):
    category = PointProductCategory.query.filter(
        PointProductCategory.id == category_id, PointProductCategory.deleted_at.is_(None)
    ).first()
    if not category:
        return jsonify({'Code': 404, 'Message': '分类不存在', 'Data': None}), 404

    try:
        payload = _build_category_from_body()
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400

    category.name = payload['name']
    category.sort = payload['sort']
    category.status = payload['status']
    category.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '更新成功', 'Data': _serialize_category(category)})


@point_bp.route('/categories/<int:category_id>/status', methods=['PATCH'])
@login_required('point-categories')
def update_category_status(category_id):
    category = PointProductCategory.query.filter(
        PointProductCategory.id == category_id, PointProductCategory.deleted_at.is_(None)
    ).first()
    if not category:
        return jsonify({'Code': 404, 'Message': '分类不存在', 'Data': None}), 404

    body = request.get_json(silent=True) or {}
    raw_status = body.get('Status')
    try:
        status = int(raw_status)
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400
    if status not in (0, 1):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400

    category.status = status
    category.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        'Code': 0,
        'Message': '启用成功' if status == 1 else '停用成功',
        'Data': _serialize_category(category),
    })


@point_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@login_required('point-categories')
def delete_category(category_id):
    category = PointProductCategory.query.filter(
        PointProductCategory.id == category_id, PointProductCategory.deleted_at.is_(None)
    ).first()
    if not category:
        return jsonify({'Code': 404, 'Message': '分类不存在', 'Data': None}), 404

    # 分类下仍有未删除商品时禁止删除
    product_count = PointProduct.query.filter(
        PointProduct.category_id == category_id, PointProduct.deleted_at.is_(None)
    ).count()
    if product_count > 0:
        return jsonify({'Code': 1, 'Message': f'该分类下还有 {product_count} 个商品，无法删除', 'Data': None}), 400

    category.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '删除成功', 'Data': None})


# ---------------------------------------------------------------------------
# 积分商品
# ---------------------------------------------------------------------------

def _build_product_from_form(*, require_image, existing_product=None):
    name = (_read_form_value('Name') or '').strip()
    if not name:
        raise ValueError('商品名称不能为空')
    if len(name) > 120:
        raise ValueError('商品名称过长，最多 120 字')

    points_raw = _read_form_value('PointsPrice')
    if points_raw is None or points_raw == '':
        raise ValueError('兑换所需积分不能为空')
    try:
        points_price = int(points_raw)
    except (TypeError, ValueError):
        raise ValueError('兑换所需积分必须是整数')
    if points_price < 0:
        raise ValueError('兑换所需积分不能为负数')

    category_raw = _read_form_value('CategoryId')
    category_id = None
    if category_raw not in (None, '', 'null'):
        try:
            category_id = int(category_raw)
        except (TypeError, ValueError):
            raise ValueError('分类参数错误')

    description = (_read_form_value('Description') or '').strip()
    if len(description) > 255:
        raise ValueError('描述过长，最多 255 字')

    original_raw = _read_form_value('OriginalPrice')
    original_price = None
    if original_raw not in (None, ''):
        try:
            original_price = int(original_raw)
        except (TypeError, ValueError):
            raise ValueError('市场参考价必须是整数（单位：分）')
        if original_price < 0:
            raise ValueError('市场参考价不能为负数')

    settlement_raw = _read_form_value('SettlementPrice', default=_MISSING)
    settlement_price = settlement_raw
    if settlement_raw is not _MISSING:
        if settlement_raw in (None, ''):
            settlement_price = None
        elif isinstance(settlement_raw, bool) or not re.fullmatch(r'\d{1,9}', str(settlement_raw)) or int(settlement_raw) > 100000000:
            raise ValueError('单件结算价须为 0 至 100000000 的整数分，或留空')
        else:
            settlement_price = int(settlement_raw)

    stock_raw = _read_form_value('Stock', default=-1)
    try:
        stock = int(stock_raw) if stock_raw not in (None, '') else -1
    except (TypeError, ValueError):
        raise ValueError('库存必须是整数')
    if stock < -1:
        stock = -1

    sort_raw = _read_form_value('Sort', default=0)
    try:
        sort = int(sort_raw) if sort_raw not in (None, '') else 0
    except (TypeError, ValueError):
        raise ValueError('排序必须是整数')

    status_raw = _read_form_value('Status', default=_MISSING)
    if status_raw is _MISSING:
        status = existing_product.status if existing_product is not None else 0
    else:
        status = _parse_product_status(status_raw)

    redeem_start_raw = _read_form_value('RedeemStartAt', default=_MISSING)
    if redeem_start_raw is _MISSING:
        redeem_start_at = (
            existing_product.redeem_start_at if existing_product is not None else None
        )
    else:
        redeem_start_at = _parse_redeem_start_at(redeem_start_raw)

    max_redeem_raw = _read_form_value('MaxRedeemPerUser', default=_MISSING)
    if max_redeem_raw is _MISSING:
        max_redeem_per_user = (
            existing_product.max_redeem_per_user
            if existing_product is not None
            else -1
        )
    else:
        max_redeem_per_user = _parse_max_redeem_per_user(max_redeem_raw)

    image_url = None
    image_file = request.files.get('Image') if request.files else None
    if image_file:
        image_url = _validate_and_upload_image(image_file)
    elif require_image:
        raise ValueError('请上传商品图片')

    return {
        'name': name,
        'category_id': category_id,
        'description': description,
        'points_price': points_price,
        'original_price': original_price,
        'settlement_price': settlement_price,
        'stock': stock,
        'sort': sort,
        'status': status,
        'redeem_start_at': redeem_start_at,
        'max_redeem_per_user': max_redeem_per_user,
        'image_url': image_url,
    }


def _save_product_settlement_price(product, amount):
    if amount is _MISSING:
        return
    key = f'product:{product.id}'
    rule = db.session.get(SettlementCostRule, key)
    before = rule.amount if rule else None
    if amount is None:
        if rule:
            db.session.delete(rule)
    else:
        rule = rule or SettlementCostRule(key=key)
        rule.amount = amount
        rule.note = '商品编辑页预估单件结算价，待总部按成本单确认'
        rule.updated_at = datetime.utcnow()
        db.session.add(rule)
    if before != amount:
        audit('settlement:product-estimate', key, {'before': before, 'after': amount})


@point_bp.route('/products', methods=['GET'])
@login_required('point-products')
def list_products():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    keyword = (request.args.get('Keyword') or '').strip()
    category_id = request.args.get('CategoryId', type=int)

    query = PointProduct.query.filter(PointProduct.deleted_at.is_(None))
    if keyword:
        query = query.filter(PointProduct.name.like(f'%{keyword}%'))
    if category_id:
        query = query.filter(PointProduct.category_id == category_id)

    pagination = query.order_by(PointProduct.sort.asc(), PointProduct.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    categories = PointProductCategory.query.filter(
        PointProductCategory.deleted_at.is_(None)
    ).order_by(PointProductCategory.sort.asc(), PointProductCategory.id.asc()).all()
    category_map = {c.id: c.name for c in categories}

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_product(p, category_map) for p in pagination.items],
            'Categories': [_serialize_category(c) for c in categories],
        },
    })


@point_bp.route('/products', methods=['POST'])
@login_required('point-products')
def create_product():
    try:
        payload = _build_product_from_form(require_image=True)
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    now = datetime.utcnow()
    product = PointProduct(
        name=payload['name'],
        category_id=payload['category_id'],
        description=payload['description'],
        points_price=payload['points_price'],
        original_price=payload['original_price'],
        image_url=payload['image_url'],
        stock=payload['stock'],
        sort=payload['sort'],
        status=payload['status'],
        redeem_start_at=payload['redeem_start_at'],
        max_redeem_per_user=payload['max_redeem_per_user'],
        created_at=now,
        updated_at=now,
    )
    db.session.add(product)
    db.session.flush()
    _save_product_settlement_price(product, payload['settlement_price'])
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '创建成功', 'Data': _serialize_product(product)})


@point_bp.route('/products/<int:product_id>', methods=['PUT'])
@login_required('point-products')
def update_product(product_id):
    product = PointProduct.query.filter(
        PointProduct.id == product_id, PointProduct.deleted_at.is_(None)
    ).first()
    if not product:
        return jsonify({'Code': 404, 'Message': '商品不存在', 'Data': None}), 404

    try:
        payload = _build_product_from_form(
            require_image=False,
            existing_product=product,
        )
    except ValueError as exc:
        return jsonify({'Code': 1, 'Message': str(exc), 'Data': None}), 400
    except Exception as exc:
        return jsonify({'Code': 500, 'Message': f'图片上传失败：{exc}', 'Data': None}), 500

    product.name = payload['name']
    product.category_id = payload['category_id']
    product.description = payload['description']
    product.points_price = payload['points_price']
    product.original_price = payload['original_price']
    product.stock = payload['stock']
    product.sort = payload['sort']
    product.status = payload['status']
    product.redeem_start_at = payload['redeem_start_at']
    product.max_redeem_per_user = payload['max_redeem_per_user']
    if payload['image_url']:
        product.image_url = payload['image_url']
    product.updated_at = datetime.utcnow()
    _save_product_settlement_price(product, payload['settlement_price'])
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '更新成功', 'Data': _serialize_product(product)})


@point_bp.route('/products/<int:product_id>/status', methods=['PATCH'])
@login_required('point-products')
def update_product_status(product_id):
    product = PointProduct.query.filter(
        PointProduct.id == product_id, PointProduct.deleted_at.is_(None)
    ).first()
    if not product:
        return jsonify({'Code': 404, 'Message': '商品不存在', 'Data': None}), 404

    body = request.get_json(silent=True) or {}
    raw_status = body.get('Status')
    try:
        status = int(raw_status)
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400
    if status not in (0, 1):
        return jsonify({'Code': 1, 'Message': 'Status 必须为 0 或 1', 'Data': None}), 400

    product.status = status
    product.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        'Code': 0,
        'Message': '上架成功' if status == 1 else '下架成功',
        'Data': _serialize_product(product),
    })


@point_bp.route('/products/<int:product_id>', methods=['DELETE'])
@login_required('point-products')
def delete_product(product_id):
    product = PointProduct.query.filter(
        PointProduct.id == product_id, PointProduct.deleted_at.is_(None)
    ).first()
    if not product:
        return jsonify({'Code': 404, 'Message': '商品不存在', 'Data': None}), 404

    product.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'Code': 0, 'Message': '删除成功', 'Data': None})


# ---------------------------------------------------------------------------
# 积分提取审计（只读）
# ---------------------------------------------------------------------------

@point_bp.route('/withdraws', methods=['GET'])
@login_required('point-withdraws')
def list_withdraws():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    keyword = (request.args.get('Keyword') or '').strip()
    status = request.args.get('Status', type=int)

    query = PointWithdrawRecord.query.filter(PointWithdrawRecord.deleted_at.is_(None))
    if keyword:
        query = query.filter(PointWithdrawRecord.open_id.like(f'%{keyword}%'))
    if status is not None:
        query = query.filter(PointWithdrawRecord.status == status)

    pagination = query.order_by(PointWithdrawRecord.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [_serialize_withdraw(r) for r in pagination.items],
        },
    })


# ---------------------------------------------------------------------------
# 积分兑换明细（只读）
# ---------------------------------------------------------------------------

@point_bp.route('/redeem-orders', methods=['GET'])
@login_required('point-redeem-orders')
def list_redeem_orders():
    page = request.args.get('current', 1, type=int)
    page_size = request.args.get('pageSize', 20, type=int)
    keyword = (request.args.get('Keyword') or '').strip()
    status = request.args.get('Status', type=int)

    query = PointRedeemOrder.query.filter(PointRedeemOrder.deleted_at.is_(None))
    if keyword:
        like = f'%{keyword}%'
        matched_user_open_ids = [
            row.open_id
            for row in User.query.with_entities(User.open_id)
            .filter(or_(User.open_id.like(like), User.nick_name.like(like)))
            .limit(200)
            .all()
        ]
        keyword_filters = [
            PointRedeemOrder.open_id.like(like),
            PointRedeemOrder.order_no.like(like),
            PointRedeemOrder.product_name.like(like),
        ]
        if matched_user_open_ids:
            keyword_filters.append(PointRedeemOrder.open_id.in_(matched_user_open_ids))
        query = query.filter(or_(
            *keyword_filters,
        ))
    if status is not None:
        query = query.filter(PointRedeemOrder.status == status)

    pagination = query.order_by(PointRedeemOrder.id.desc()).paginate(
        page=page, per_page=page_size, error_out=False
    )
    open_ids = {
        open_id
        for order in pagination.items
        for open_id in (order.open_id, order.verifier_open_id)
        if open_id
    }
    users = User.query.filter(User.open_id.in_(open_ids)).all() if open_ids else []
    user_map = {u.open_id: u for u in users}

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': {
            'Total': pagination.total,
            'CurrentPage': pagination.page,
            'PageSize': page_size,
            'Items': [
                _serialize_redeem_order(r, user_map=user_map, verifier_map=user_map)
                for r in pagination.items
            ],
        },
    })


# ---------------------------------------------------------------------------
# 积分规则配置
# ---------------------------------------------------------------------------

def _serialize_point_config(config_row):
    value = DEFAULT_POINT_CONFIG.copy()
    if config_row and isinstance(config_row.config_value, dict):
        for key in DEFAULT_POINT_CONFIG:
            if key in config_row.config_value and config_row.config_value[key] is not None:
                value[key] = config_row.config_value[key]
    return value


@point_bp.route('/config', methods=['GET'])
@login_required('point-config')
def get_point_config():
    config_row = Config.query.filter(Config.config_key == POINT_CONFIG_KEY).first()
    return jsonify({'Code': 0, 'Message': 'success', 'Data': _serialize_point_config(config_row)})


@point_bp.route('/config', methods=['PUT'])
@login_required('point-config')
def update_point_config():
    body = request.get_json(silent=True) or {}

    try:
        earn_threshold = int(body.get('EarnThresholdAmount'))
        earn_points = int(body.get('EarnPoints'))
        max_withdraw = int(body.get('MaxWithdrawPerTime', 0))
    except (TypeError, ValueError):
        return jsonify({'Code': 1, 'Message': '参数必须为整数', 'Data': None}), 400

    if earn_threshold < 1:
        return jsonify({'Code': 1, 'Message': '消费门槛必须大于 0（单位：分）', 'Data': None}), 400
    if earn_points < 1:
        return jsonify({'Code': 1, 'Message': '每档积分必须大于 0', 'Data': None}), 400
    if max_withdraw < 0:
        return jsonify({'Code': 1, 'Message': '单次提取上限不能为负数', 'Data': None}), 400

    value = {
        'EarnThresholdAmount': earn_threshold,
        'EarnPoints': earn_points,
        'MaxWithdrawPerTime': max_withdraw,
    }

    now = datetime.utcnow()
    config_row = Config.query.filter(Config.config_key == POINT_CONFIG_KEY).first()
    if config_row:
        config_row.config_value = value
        config_row.updated_at = now
    else:
        config_row = Config(
            config_key=POINT_CONFIG_KEY,
            config_value=value,
            created_at=now,
            updated_at=now,
        )
        db.session.add(config_row)
    db.session.commit()

    return jsonify({'Code': 0, 'Message': '保存成功', 'Data': value})
