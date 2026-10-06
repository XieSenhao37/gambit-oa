from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, request
from sqlalchemy import case, desc, func, or_

from app import db
from app.middlewares.auth import login_required
from app.models import (
    Catering,
    CateringItem,
    CouponPromotion,
    CouponRecord,
    Dish,
    DishCategory,
    MonthCardOrder,
    PayOrder,
    PlayOrder,
    PointAccount,
    PointRedeemOrder,
    PointTransaction,
    PointWithdrawRecord,
    ReferralRecord,
    Store,
    User,
    WalletAccount,
    WalletRechargeOrder,
    WalletRechargeTier,
    WalletTransaction,
)
from app.utils.store import get_request_store_id

stats_bp = Blueprint('stats', __name__)

# 支付方式映射，与 GambitServer pay_constant 对齐
PAY_TYPE_TEXT = {
    0: '微信',
    1: '月卡',
    2: '线下',
    3: '储值钱包',
    4: '钱包+微信',
}

UNCATEGORIZED_NAME = '未分类'
REFERRAL_COUPON_PROMOTION_ID = 11
BILLING_MODE_TEXT = {
    0: '线上计费',
    1: '线下计费',
    2: '月卡',
}
COUPON_TYPE_TEXT = {
    0: '时长券',
    1: '金额券',
    2: '折扣券',
    3: '免单券',
}
MONTH_CARD_SOURCE_TEXT = {
    'third_party': '第三方验券',
    'gift': '免费赠送（总部补贴）',
    'wechat': '小程序微信',
    'meituan': '美团核销',
    'storage_gift': '寄存赠送',
    'manual_adjustment': '手动调整',
    'other': '其他',
}


def _now_shanghai_naive():
    return datetime.now(ZoneInfo('Asia/Shanghai')).replace(tzinfo=None)


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        return None


def _resolve_date_range():
    """解析查询区间，返回 (start_dt, end_dt_exclusive)，按上海时区 0 点切日，默认近 7 天。"""
    start = _parse_date(request.args.get('StartDate'))
    end = _parse_date(request.args.get('EndDate'))

    today = _now_shanghai_naive().replace(hour=0, minute=0, second=0, microsecond=0)
    if end is None:
        end = today
    if start is None:
        start = end - timedelta(days=6)

    if start > end:
        start, end = end, start

    start_dt = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end_dt_exclusive = end.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return start_dt, end_dt_exclusive


def _yuan(cents):
    return round((cents or 0) / 100, 2)


def _current_store_id():
    return get_request_store_id()


def _range_params():
    granularity = request.args.get('Granularity', 'day')
    if granularity not in ('day', 'week', 'month'):
        granularity = 'day'
    start_dt, end_dt = _resolve_date_range()
    return start_dt, end_dt, granularity


def _date_meta(start_dt, end_dt, granularity):
    return {
        'StartDate': start_dt.strftime('%Y-%m-%d'),
        'EndDate': (end_dt - timedelta(days=1)).strftime('%Y-%m-%d'),
        'Granularity': granularity,
    }


def _percent(numerator, denominator):
    return round(numerator * 100 / denominator, 2) if denominator else 0


def _dt_text(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def _paid_order_filters(start_dt, end_dt, store_id=None):
    filters = [
        PayOrder.deleted_at.is_(None),
        PayOrder.created_at >= start_dt,
        PayOrder.created_at < end_dt,
        PayOrder.pay_status == 1,
    ]
    if store_id:
        filters.append(PayOrder.store_id == store_id)
    return filters


def _paid_catering_filters(start_dt, end_dt, store_id=None):
    """已支付餐饮订单的通用过滤条件。"""
    filters = [
        Catering.deleted_at.is_(None),
        Catering.created_at >= start_dt,
        Catering.created_at < end_dt,
        PayOrder.pay_status == 1,
        PayOrder.deleted_at.is_(None),
    ]
    if store_id:
        filters.append(Catering.store_id == store_id)
    return filters


def _build_summary(start_dt, end_dt, store_id=None):
    row = db.session.query(
        func.coalesce(func.sum(Catering.total_price), 0),
        func.count(func.distinct(Catering.id)),
    ).join(PayOrder, PayOrder.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id)).one()

    revenue_cents = int(row[0] or 0)
    order_count = int(row[1] or 0)

    cup_count = db.session.query(
        func.coalesce(func.sum(CateringItem.count), 0)
    ).select_from(Catering)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .join(CateringItem, CateringItem.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id), CateringItem.deleted_at.is_(None))\
        .scalar()
    cup_count = int(cup_count or 0)

    revenue = _yuan(revenue_cents)
    avg_order_value = round(revenue / order_count, 2) if order_count else 0

    return {
        'Revenue': revenue,
        'OrderCount': order_count,
        'AvgOrderValue': avg_order_value,
        'CupCount': cup_count,
    }


def _trend_format(granularity):
    if granularity == 'month':
        return '%Y-%m'
    if granularity == 'week':
        return '%x-W%v'
    return '%Y-%m-%d'


def _build_trend(start_dt, end_dt, granularity, store_id=None):
    date_format = _trend_format(granularity)
    bucket = func.date_format(Catering.created_at, date_format)
    rows = db.session.query(
        bucket.label('bucket'),
        func.coalesce(func.sum(Catering.total_price), 0),
        func.count(func.distinct(Catering.id)),
    ).join(PayOrder, PayOrder.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id))\
        .group_by('bucket').order_by('bucket').all()

    cup_bucket = func.date_format(Catering.created_at, date_format)
    cup_rows = db.session.query(
        cup_bucket.label('bucket'),
        func.coalesce(func.sum(CateringItem.count), 0),
    ).select_from(Catering)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .join(CateringItem, CateringItem.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id), CateringItem.deleted_at.is_(None))\
        .group_by('bucket').all()
    cup_map = {r[0]: int(r[1] or 0) for r in cup_rows}

    return [{
        'Date': row[0],
        'Revenue': _yuan(int(row[1] or 0)),
        'OrderCount': int(row[2] or 0),
        'CupCount': cup_map.get(row[0], 0),
    } for row in rows]


def _build_dish_ranking(start_dt, end_dt, store_id=None, limit=10):
    rows = db.session.query(
        Dish.name,
        func.coalesce(func.sum(CateringItem.count), 0),
        func.coalesce(func.sum(CateringItem.total_price), 0),
    ).select_from(CateringItem)\
        .join(Catering, Catering.id == CateringItem.catering_id)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .join(Dish, Dish.id == CateringItem.dish_id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id), CateringItem.deleted_at.is_(None))\
        .group_by(Dish.id, Dish.name)\
        .order_by(func.sum(CateringItem.count).desc())\
        .limit(limit).all()

    return [{
        'DishName': row[0] or '',
        'Count': int(row[1] or 0),
        'Revenue': _yuan(int(row[2] or 0)),
    } for row in rows]


def _build_hourly(start_dt, end_dt, store_id=None):
    order_rows = db.session.query(
        func.hour(Catering.created_at).label('hour'),
        func.count(func.distinct(Catering.id)),
    ).join(PayOrder, PayOrder.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id))\
        .group_by('hour').all()

    cup_rows = db.session.query(
        func.hour(Catering.created_at).label('hour'),
        func.coalesce(func.sum(CateringItem.count), 0),
    ).select_from(Catering)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .join(CateringItem, CateringItem.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id), CateringItem.deleted_at.is_(None))\
        .group_by('hour').all()

    order_map = {int(r[0]): int(r[1] or 0) for r in order_rows}
    cup_map = {int(r[0]): int(r[1] or 0) for r in cup_rows}

    return [{
        'Hour': hour,
        'OrderCount': order_map.get(hour, 0),
        'CupCount': cup_map.get(hour, 0),
    } for hour in range(24)]


def _build_category(start_dt, end_dt, store_id=None):
    # 先按 dish 聚合销量与销售额
    dish_rows = db.session.query(
        CateringItem.dish_id,
        func.coalesce(func.sum(CateringItem.count), 0),
        func.coalesce(func.sum(CateringItem.total_price), 0),
    ).select_from(CateringItem)\
        .join(Catering, Catering.id == CateringItem.catering_id)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id), CateringItem.deleted_at.is_(None))\
        .group_by(CateringItem.dish_id).all()

    if not dish_rows:
        return []

    dish_ids = [r[0] for r in dish_rows]
    dishes = Dish.query.filter(Dish.id.in_(dish_ids)).all()
    dish_primary_category = {}
    for dish in dishes:
        category_ids = dish.category_ids or []
        dish_primary_category[dish.id] = category_ids[0] if category_ids else None

    category_names = {
        c.id: c.name
        for c in DishCategory.query.filter(DishCategory.deleted_at.is_(None)).all()
    }

    aggregated = {}
    for dish_id, count, revenue_cents in dish_rows:
        category_id = dish_primary_category.get(dish_id)
        name = category_names.get(category_id, UNCATEGORIZED_NAME) if category_id else UNCATEGORIZED_NAME
        bucket = aggregated.setdefault(name, {'Count': 0, 'RevenueCents': 0})
        bucket['Count'] += int(count or 0)
        bucket['RevenueCents'] += int(revenue_cents or 0)

    result = [{
        'CategoryName': name,
        'Count': data['Count'],
        'Revenue': _yuan(data['RevenueCents']),
    } for name, data in aggregated.items()]
    result.sort(key=lambda x: x['Revenue'], reverse=True)
    return result


def _build_payment(start_dt, end_dt, store_id=None):
    rows = db.session.query(
        PayOrder.pay_type,
        func.count(func.distinct(Catering.id)),
        func.coalesce(func.sum(Catering.total_price), 0),
    ).select_from(Catering)\
        .join(PayOrder, PayOrder.catering_id == Catering.id)\
        .filter(*_paid_catering_filters(start_dt, end_dt, store_id))\
        .group_by(PayOrder.pay_type).all()

    return [{
        'PayType': row[0],
        'PayTypeText': PAY_TYPE_TEXT.get(row[0], f'其他({row[0]})' if row[0] is not None else '未知'),
        'OrderCount': int(row[1] or 0),
        'Revenue': _yuan(int(row[2] or 0)),
    } for row in rows]


def _play_query(start_dt, end_dt, store_id=None):
    query = db.session.query(PlayOrder, PayOrder)\
        .join(PayOrder, PayOrder.play_order_id == PlayOrder.id)\
        .filter(
            PlayOrder.deleted_at.is_(None),
            PlayOrder.created_at >= start_dt,
            PlayOrder.created_at < end_dt,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )
    if store_id:
        query = query.filter(PlayOrder.store_id == store_id)
    return query


def _play_summary(start_dt, end_dt, store_id=None):
    row = db.session.query(
        func.coalesce(func.sum(PayOrder.amount), 0),
        func.count(func.distinct(PlayOrder.id)),
        func.coalesce(func.sum(PlayOrder.play_time), 0),
        func.count(func.distinct(PlayOrder.open_id)),
    ).select_from(PlayOrder)\
        .join(PayOrder, PayOrder.play_order_id == PlayOrder.id)\
        .filter(
            PlayOrder.deleted_at.is_(None),
            PlayOrder.created_at >= start_dt,
            PlayOrder.created_at < end_dt,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )
    if store_id:
        row = row.filter(PlayOrder.store_id == store_id)
    revenue_cents, order_count, total_hours, unique_users = row.one()
    order_count = int(order_count or 0)
    revenue = _yuan(int(revenue_cents or 0))
    total_hours = int(total_hours or 0)
    return {
        'Revenue': revenue,
        'OrderCount': order_count,
        'AvgOrderValue': round(revenue / order_count, 2) if order_count else 0,
        'TotalPlayHours': total_hours,
        'AvgPlayHours': round(total_hours / order_count, 2) if order_count else 0,
        'UniqueUsers': int(unique_users or 0),
    }


def _play_trend(start_dt, end_dt, granularity, store_id=None):
    bucket = func.date_format(PlayOrder.created_at, _trend_format(granularity))
    query = db.session.query(
        bucket.label('bucket'),
        func.coalesce(func.sum(PayOrder.amount), 0),
        func.count(func.distinct(PlayOrder.id)),
        func.coalesce(func.sum(PlayOrder.play_time), 0),
    ).select_from(PlayOrder)\
        .join(PayOrder, PayOrder.play_order_id == PlayOrder.id)\
        .filter(
            PlayOrder.deleted_at.is_(None),
            PlayOrder.created_at >= start_dt,
            PlayOrder.created_at < end_dt,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )
    if store_id:
        query = query.filter(PlayOrder.store_id == store_id)
    rows = query.group_by('bucket').order_by('bucket').all()
    return [{
        'Date': row[0],
        'Revenue': _yuan(int(row[1] or 0)),
        'OrderCount': int(row[2] or 0),
        'TotalPlayHours': int(row[3] or 0),
    } for row in rows]


def _play_billing_mode(start_dt, end_dt, store_id=None):
    query = db.session.query(
        PlayOrder.billing_mode,
        func.count(func.distinct(PlayOrder.id)),
        func.coalesce(func.sum(PayOrder.amount), 0),
    ).select_from(PlayOrder)\
        .join(PayOrder, PayOrder.play_order_id == PlayOrder.id)\
        .filter(
            PlayOrder.deleted_at.is_(None),
            PlayOrder.created_at >= start_dt,
            PlayOrder.created_at < end_dt,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )
    if store_id:
        query = query.filter(PlayOrder.store_id == store_id)
    rows = query.group_by(PlayOrder.billing_mode).all()
    return [{
        'BillingMode': row[0],
        'BillingModeText': BILLING_MODE_TEXT.get(row[0], f'其他({row[0]})'),
        'OrderCount': int(row[1] or 0),
        'Revenue': _yuan(int(row[2] or 0)),
    } for row in rows]


def _play_payment(start_dt, end_dt, store_id=None):
    query = db.session.query(
        PayOrder.pay_type,
        func.count(func.distinct(PlayOrder.id)),
        func.coalesce(func.sum(PayOrder.amount), 0),
    ).select_from(PlayOrder)\
        .join(PayOrder, PayOrder.play_order_id == PlayOrder.id)\
        .filter(
            PlayOrder.deleted_at.is_(None),
            PlayOrder.created_at >= start_dt,
            PlayOrder.created_at < end_dt,
            PayOrder.deleted_at.is_(None),
            PayOrder.pay_status == 1,
        )
    if store_id:
        query = query.filter(PlayOrder.store_id == store_id)
    rows = query.group_by(PayOrder.pay_type).all()
    return [{
        'PayType': row[0],
        'PayTypeText': PAY_TYPE_TEXT.get(row[0], f'其他({row[0]})' if row[0] is not None else '未知'),
        'OrderCount': int(row[1] or 0),
        'Revenue': _yuan(int(row[2] or 0)),
    } for row in rows]


def _catering_summary_values(start_dt, end_dt, store_id=None):
    summary = _build_summary(start_dt, end_dt, store_id)
    return summary['Revenue'], summary['OrderCount']


def _refund_amount(start_dt, end_dt, store_id=None):
    query = db.session.query(
        func.coalesce(func.sum(PayOrder.refund_amount), 0),
    ).select_from(PayOrder).filter(
        PayOrder.deleted_at.is_(None),
        PayOrder.updated_at >= start_dt,
        PayOrder.updated_at < end_dt,
        PayOrder.pay_status == 3,
    )
    if store_id:
        query = query.filter(PayOrder.store_id == store_id)
    return _yuan(int(query.scalar() or 0))


def _active_users(start_dt, end_dt, store_id=None):
    query = db.session.query(func.count(func.distinct(PayOrder.open_id))).filter(
        *_paid_order_filters(start_dt, end_dt, store_id)
    ).filter(or_(PayOrder.play_order_id.isnot(None), PayOrder.catering_id.isnot(None)))
    return int(query.scalar() or 0)


def _new_users(start_dt, end_dt, store_id=None):
    query = User.query.filter(
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    )
    if store_id:
        query = query.filter(User.registered_store_id == store_id)
    return int(query.count() or 0)


def _wallet_recharge_summary(start_dt, end_dt):
    row = db.session.query(
        func.coalesce(func.sum(WalletRechargeOrder.amount), 0),
        func.coalesce(func.sum(WalletRechargeOrder.bonus_amount), 0),
        func.count(WalletRechargeOrder.id),
        func.count(func.distinct(WalletRechargeOrder.open_id)),
    ).filter(
        WalletRechargeOrder.deleted_at.is_(None),
        WalletRechargeOrder.status == 1,
        WalletRechargeOrder.created_at >= start_dt,
        WalletRechargeOrder.created_at < end_dt,
    ).one()
    return {
        'RechargeAmount': _yuan(int(row[0] or 0)),
        'BonusAmount': _yuan(int(row[1] or 0)),
        'RechargeCount': int(row[2] or 0),
        'RechargeUsers': int(row[3] or 0),
    }


def _point_summary_values(start_dt, end_dt, store_id=None):
    query = PointTransaction.query.filter(
        PointTransaction.deleted_at.is_(None),
        PointTransaction.created_at >= start_dt,
        PointTransaction.created_at < end_dt,
    )
    if store_id:
        query = query.outerjoin(PayOrder, PointTransaction.related_pay_order_id == PayOrder.id)\
            .outerjoin(PointWithdrawRecord, PointTransaction.related_withdraw_id == PointWithdrawRecord.id)\
            .outerjoin(PointRedeemOrder, PointTransaction.related_redeem_order_id == PointRedeemOrder.id)\
            .filter(or_(
                PayOrder.store_id == store_id,
                PointWithdrawRecord.store_id == store_id,
                PointRedeemOrder.pickup_store_id == store_id,
            ))
    earned = query.filter(PointTransaction.direction == 'in').with_entities(
        func.coalesce(func.sum(PointTransaction.amount), 0)
    ).scalar()
    consumed = query.filter(PointTransaction.direction == 'out').with_entities(
        func.coalesce(func.sum(PointTransaction.amount), 0)
    ).scalar()
    return int(earned or 0), int(consumed or 0)


def _ops_trend(start_dt, end_dt, granularity, store_id=None):
    bucket_format = _trend_format(granularity)
    play_rows = db.session.query(
        func.date_format(PlayOrder.created_at, bucket_format).label('bucket'),
        func.coalesce(func.sum(PayOrder.amount), 0),
        func.count(func.distinct(PlayOrder.id)),
    ).select_from(PlayOrder).join(PayOrder, PayOrder.play_order_id == PlayOrder.id).filter(
        PlayOrder.deleted_at.is_(None),
        PlayOrder.created_at >= start_dt,
        PlayOrder.created_at < end_dt,
        PayOrder.deleted_at.is_(None),
        PayOrder.pay_status == 1,
    )
    catering_rows = db.session.query(
        func.date_format(Catering.created_at, bucket_format).label('bucket'),
        func.coalesce(func.sum(Catering.total_price), 0),
        func.count(func.distinct(Catering.id)),
    ).select_from(Catering).join(PayOrder, PayOrder.catering_id == Catering.id).filter(
        *_paid_catering_filters(start_dt, end_dt, store_id)
    )
    user_rows = db.session.query(
        func.date_format(User.created_at, bucket_format).label('bucket'),
        func.count(User.id),
    ).filter(
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    )
    if store_id:
        play_rows = play_rows.filter(PlayOrder.store_id == store_id)
        user_rows = user_rows.filter(User.registered_store_id == store_id)
    play_map = {
        row[0]: {'PlayRevenue': int(row[1] or 0), 'PlayOrderCount': int(row[2] or 0)}
        for row in play_rows.group_by('bucket').all()
    }
    catering_map = {
        row[0]: {'CateringRevenue': int(row[1] or 0), 'CateringOrderCount': int(row[2] or 0)}
        for row in catering_rows.group_by('bucket').all()
    }
    user_map = {row[0]: int(row[1] or 0) for row in user_rows.group_by('bucket').all()}
    buckets = sorted(set(play_map.keys()) | set(catering_map.keys()) | set(user_map.keys()))
    result = []
    for bucket in buckets:
        play = play_map.get(bucket, {})
        catering = catering_map.get(bucket, {})
        play_revenue = play.get('PlayRevenue', 0)
        catering_revenue = catering.get('CateringRevenue', 0)
        result.append({
            'Date': bucket,
            'Revenue': _yuan(play_revenue + catering_revenue),
            'PlayRevenue': _yuan(play_revenue),
            'CateringRevenue': _yuan(catering_revenue),
            'OrderCount': play.get('PlayOrderCount', 0) + catering.get('CateringOrderCount', 0),
            'NewUsers': user_map.get(bucket, 0),
        })
    return result


def _source_store_distribution(start_dt, end_dt):
    rows = db.session.query(
        Store.id,
        Store.name,
        func.count(User.id),
    ).select_from(User).outerjoin(Store, Store.id == User.registered_store_id).filter(
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    ).filter(Store.id == _current_store_id()).group_by(Store.id, Store.name).all()
    return [{
        'StoreId': row[0],
        'StoreName': row[1] or '未知来源',
        'UserCount': int(row[2] or 0),
    } for row in rows]


def _user_trend(start_dt, end_dt, granularity, store_id=None):
    bucket = func.date_format(User.created_at, _trend_format(granularity))
    query = db.session.query(bucket.label('bucket'), func.count(User.id)).filter(
        User.deleted_at.is_(None),
        User.created_at >= start_dt,
        User.created_at < end_dt,
    )
    if store_id:
        query = query.filter(User.registered_store_id == store_id)
    rows = query.group_by('bucket').order_by('bucket').all()
    return [{'Date': row[0], 'NewUsers': int(row[1] or 0)} for row in rows]


def _paid_user_counts(start_dt, end_dt, store_id=None):
    first_paid_subq = db.session.query(
        PayOrder.open_id.label('open_id'),
        func.min(PayOrder.created_at).label('first_paid_at'),
    ).filter(
        PayOrder.deleted_at.is_(None),
        PayOrder.pay_status == 1,
        or_(PayOrder.play_order_id.isnot(None), PayOrder.catering_id.isnot(None)),
    )
    if store_id:
        first_paid_subq = first_paid_subq.filter(PayOrder.store_id == store_id)
    first_paid_subq = first_paid_subq.group_by(PayOrder.open_id).subquery()

    paid_users = db.session.query(func.count(func.distinct(PayOrder.open_id))).filter(
        *_paid_order_filters(start_dt, end_dt, store_id)
    ).filter(or_(PayOrder.play_order_id.isnot(None), PayOrder.catering_id.isnot(None))).scalar()
    new_paid_users = db.session.query(func.count(first_paid_subq.c.open_id)).filter(
        first_paid_subq.c.first_paid_at >= start_dt,
        first_paid_subq.c.first_paid_at < end_dt,
    ).scalar()
    paid_users = int(paid_users or 0)
    new_paid_users = int(new_paid_users or 0)
    return paid_users, new_paid_users, max(paid_users - new_paid_users, 0)


def _coupon_effect_orders(start_dt, end_dt, store_id=None):
    query = db.session.query(
        CouponRecord.promotion_id,
        func.count(func.distinct(PayOrder.id)),
        func.coalesce(func.sum(PayOrder.amount), 0),
        func.coalesce(func.sum(PayOrder.discount_amount), 0),
    ).select_from(PayOrder).join(CouponRecord, CouponRecord.id == PayOrder.coupon_id).filter(
        PayOrder.deleted_at.is_(None),
        PayOrder.pay_status == 1,
        PayOrder.created_at >= start_dt,
        PayOrder.created_at < end_dt,
        CouponRecord.deleted_at.is_(None),
    )
    if store_id:
        query = query.filter(PayOrder.store_id == store_id)
    rows = query.group_by(CouponRecord.promotion_id).all()
    return {
        row[0]: {
            'OrderCount': int(row[1] or 0),
            'Revenue': _yuan(int(row[2] or 0)),
            'DiscountAmount': _yuan(int(row[3] or 0)),
        }
        for row in rows
    }


def _coupon_promotion_stats(start_dt, end_dt, store_id=None):
    received_rows = db.session.query(
        CouponRecord.promotion_id,
        func.count(CouponRecord.id),
    ).filter(
        CouponRecord.deleted_at.is_(None),
        CouponRecord.received_at >= start_dt,
        CouponRecord.received_at < end_dt,
    ).group_by(CouponRecord.promotion_id).all()
    used_query = db.session.query(
        CouponRecord.promotion_id,
        func.count(CouponRecord.id),
    ).filter(
        CouponRecord.deleted_at.is_(None),
        CouponRecord.status == 1,
        CouponRecord.used_at >= start_dt,
        CouponRecord.used_at < end_dt,
    )
    if store_id:
        used_query = used_query.filter(CouponRecord.verified_store_id == store_id)
    used_rows = used_query.group_by(CouponRecord.promotion_id).all()

    from flask import g
    received_map = {row[0]: int(row[1] or 0) for row in received_rows} if g.staff.headquarters else {}
    used_map = {row[0]: int(row[1] or 0) for row in used_rows}
    effect_map = _coupon_effect_orders(start_dt, end_dt, store_id)
    promotion_ids = set(received_map.keys()) | set(used_map.keys()) | set(effect_map.keys())
    if not promotion_ids:
        return []

    promotions = {
        p.id: p
        for p in CouponPromotion.query.filter(CouponPromotion.id.in_(promotion_ids)).all()
    }
    result = []
    for promotion_id in promotion_ids:
        promotion = promotions.get(promotion_id)
        received = received_map.get(promotion_id, 0)
        used = used_map.get(promotion_id, 0)
        effect = effect_map.get(promotion_id, {})
        result.append({
            'PromotionId': promotion_id,
            'ActivityName': promotion.activity_name if promotion else f'活动 {promotion_id}',
            'Title': promotion.title if promotion else '',
            'CouponType': promotion.coupon_type if promotion else None,
            'CouponTypeText': COUPON_TYPE_TEXT.get(promotion.coupon_type, '未知') if promotion else '未知',
            'IsReferralCoupon': promotion_id == REFERRAL_COUPON_PROMOTION_ID,
            'ReceivedCount': received,
            'UsedCount': used,
            'UseRate': _percent(used, received),
            'OrderCount': effect.get('OrderCount', 0),
            'Revenue': effect.get('Revenue', 0),
            'DiscountAmount': effect.get('DiscountAmount', 0),
        })
    result.sort(key=lambda item: (item['Revenue'], item['UsedCount'], item['ReceivedCount']), reverse=True)
    return result


def _coupon_store_distribution(start_dt, end_dt):
    rows = db.session.query(
        Store.id,
        Store.name,
        func.count(CouponRecord.id),
    ).select_from(CouponRecord).outerjoin(Store, Store.id == CouponRecord.verified_store_id).filter(
        CouponRecord.deleted_at.is_(None),
        CouponRecord.status == 1,
        CouponRecord.used_at >= start_dt,
        CouponRecord.used_at < end_dt,
    ).filter(Store.id == _current_store_id()).group_by(Store.id, Store.name).all()
    return [{
        'StoreId': row[0],
        'StoreName': row[1] or '未知门店',
        'UsedCount': int(row[2] or 0),
    } for row in rows]


def _referral_summary(start_dt, end_dt):
    base = ReferralRecord.query.filter(
        ReferralRecord.deleted_at.is_(None),
        ReferralRecord.created_at >= start_dt,
        ReferralRecord.created_at < end_dt,
    )
    bound_count = base.count()
    coupon_issued_count = base.filter(ReferralRecord.status >= 1).count()
    first_order_count = base.filter(ReferralRecord.status >= 2).count()
    rewarded_count = base.filter(ReferralRecord.status >= 3).count()
    inviter_count = base.with_entities(func.count(func.distinct(ReferralRecord.inviter_open_id))).scalar()
    return {
        'BoundCount': int(bound_count or 0),
        'NewUserCouponIssuedCount': int(coupon_issued_count or 0),
        'FirstOrderCount': int(first_order_count or 0),
        'InviterRewardedCount': int(rewarded_count or 0),
        'InviterCount': int(inviter_count or 0),
        'FirstOrderRate': _percent(first_order_count, bound_count),
        'RewardRate': _percent(rewarded_count, bound_count),
    }


def _referral_trend(start_dt, end_dt, granularity):
    bucket = func.date_format(ReferralRecord.created_at, _trend_format(granularity))
    rows = db.session.query(
        bucket.label('bucket'),
        func.count(ReferralRecord.id),
        func.sum(case((ReferralRecord.status >= 1, 1), else_=0)),
        func.sum(case((ReferralRecord.status >= 2, 1), else_=0)),
        func.sum(case((ReferralRecord.status >= 3, 1), else_=0)),
    ).filter(
        ReferralRecord.deleted_at.is_(None),
        ReferralRecord.created_at >= start_dt,
        ReferralRecord.created_at < end_dt,
    ).group_by('bucket').order_by('bucket').all()
    return [{
        'Date': row[0],
        'BoundCount': int(row[1] or 0),
        'NewUserCouponIssuedCount': int(row[2] or 0),
        'FirstOrderCount': int(row[3] or 0),
        'InviterRewardedCount': int(row[4] or 0),
    } for row in rows]


def _referral_share_ranking(start_dt, end_dt, limit=10):
    rows = db.session.query(
        ReferralRecord.share_id,
        func.count(ReferralRecord.id),
        func.sum(case((ReferralRecord.status >= 2, 1), else_=0)),
    ).filter(
        ReferralRecord.deleted_at.is_(None),
        ReferralRecord.created_at >= start_dt,
        ReferralRecord.created_at < end_dt,
    ).group_by(ReferralRecord.share_id).order_by(desc(func.count(ReferralRecord.id))).limit(limit).all()
    return [{
        'ShareId': row[0] or '未知',
        'BoundCount': int(row[1] or 0),
        'FirstOrderCount': int(row[2] or 0),
        'FirstOrderRate': _percent(int(row[2] or 0), int(row[1] or 0)),
    } for row in rows]


def _membership_summary(start_dt, end_dt, store_id=None):
    row = db.session.query(
        func.coalesce(func.sum(case((MonthCardOrder.source.in_(['gift','storage_gift']), 0), else_=MonthCardOrder.amount)), 0),
        func.count(MonthCardOrder.id),
        func.count(func.distinct(MonthCardOrder.open_id)),
        func.coalesce(func.sum(case((MonthCardOrder.source=='gift',MonthCardOrder.amount),else_=0)),0),
    ).filter(
        MonthCardOrder.deleted_at.is_(None),
        MonthCardOrder.settle_status == 1,
        MonthCardOrder.created_at >= start_dt,
        MonthCardOrder.created_at < end_dt,
    ).one()
    now = _now_shanghai_naive()
    active_users = User.query.filter(
        User.deleted_at.is_(None),
        User.month_card_expire.isnot(None),
        User.month_card_expire >= now,
    ).count()
    month_card_open_ids = db.session.query(User.open_id).filter(
        User.deleted_at.is_(None),
        User.month_card_expire.isnot(None),
        User.month_card_expire >= now,
    ).subquery()
    play_query = db.session.query(
        func.count(func.distinct(PlayOrder.id)),
        func.coalesce(func.sum(PlayOrder.play_time), 0),
    ).filter(
        PlayOrder.deleted_at.is_(None),
        PlayOrder.open_id.in_(month_card_open_ids),
        PlayOrder.created_at >= start_dt,
        PlayOrder.created_at < end_dt,
    )
    catering_query = db.session.query(
        func.count(func.distinct(Catering.id)),
        func.coalesce(func.sum(Catering.total_price), 0),
    ).select_from(Catering).join(PayOrder, PayOrder.catering_id == Catering.id).filter(
        *_paid_catering_filters(start_dt, end_dt, store_id),
        Catering.open_id.in_(month_card_open_ids),
    )
    if store_id:
        play_query = play_query.filter(PlayOrder.store_id == store_id)
    play_row = play_query.one()
    catering_row = catering_query.one()
    return {
        'Revenue': _yuan(int(row[0] or 0)),
        'SubsidyAmount': _yuan(int(row[3] or 0)),
        'OpenCount': int(row[1] or 0),
        'OpenUsers': int(row[2] or 0),
        'ActiveMonthCardUsers': int(active_users or 0),
        'PlayOrderCount': int(play_row[0] or 0),
        'TotalPlayHours': int(play_row[1] or 0),
        'CateringOrderCount': int(catering_row[0] or 0),
        'CateringRevenue': _yuan(int(catering_row[1] or 0)),
    }


def _membership_trend(start_dt, end_dt, granularity):
    bucket = func.date_format(MonthCardOrder.created_at, _trend_format(granularity))
    rows = db.session.query(
        bucket.label('bucket'),
        func.coalesce(func.sum(case((MonthCardOrder.source.in_(['gift','storage_gift']), 0), else_=MonthCardOrder.amount)), 0),
        func.count(MonthCardOrder.id),
    ).filter(
        MonthCardOrder.deleted_at.is_(None),
        MonthCardOrder.settle_status == 1,
        MonthCardOrder.created_at >= start_dt,
        MonthCardOrder.created_at < end_dt,
    ).group_by('bucket').order_by('bucket').all()
    return [{
        'Date': row[0],
        'Revenue': _yuan(int(row[1] or 0)),
        'OpenCount': int(row[2] or 0),
    } for row in rows]


def _membership_source_distribution(start_dt, end_dt):
    source_expr = func.coalesce(MonthCardOrder.source, 'wechat')
    rows = db.session.query(
        source_expr.label('source'),
        func.coalesce(func.sum(case((MonthCardOrder.source.in_(['gift','storage_gift']), 0), else_=MonthCardOrder.amount)), 0),
        func.count(MonthCardOrder.id),
        func.count(func.distinct(MonthCardOrder.open_id)),
        func.sum(case((source_expr.in_(['gift','storage_gift']), 1), else_=0)),
    ).filter(
        MonthCardOrder.deleted_at.is_(None),
        MonthCardOrder.settle_status == 1,
        MonthCardOrder.created_at >= start_dt,
        MonthCardOrder.created_at < end_dt,
    ).group_by('source').order_by(desc(func.count(MonthCardOrder.id))).all()
    return [{
        'Source': row[0],
        'SourceText': MONTH_CARD_SOURCE_TEXT.get(row[0], row[0] or '未知'),
        'Revenue': _yuan(int(row[1] or 0)),
        'OpenCount': int(row[2] or 0),
        'OpenUsers': int(row[3] or 0),
        'GiftedCount': int(row[4] or 0),
    } for row in rows]


def _wallet_trend(start_dt, end_dt, granularity):
    bucket = func.date_format(WalletRechargeOrder.created_at, _trend_format(granularity))
    rows = db.session.query(
        bucket.label('bucket'),
        func.coalesce(func.sum(WalletRechargeOrder.amount), 0),
        func.coalesce(func.sum(WalletRechargeOrder.bonus_amount), 0),
        func.count(WalletRechargeOrder.id),
    ).filter(
        WalletRechargeOrder.deleted_at.is_(None),
        WalletRechargeOrder.status == 1,
        WalletRechargeOrder.created_at >= start_dt,
        WalletRechargeOrder.created_at < end_dt,
    ).group_by('bucket').order_by('bucket').all()
    return [{
        'Date': row[0],
        'RechargeAmount': _yuan(int(row[1] or 0)),
        'BonusAmount': _yuan(int(row[2] or 0)),
        'RechargeCount': int(row[3] or 0),
    } for row in rows]


def _wallet_tier_distribution(start_dt, end_dt):
    rows = db.session.query(
        WalletRechargeOrder.amount,
        WalletRechargeOrder.bonus_amount,
        func.count(WalletRechargeOrder.id),
    ).filter(
        WalletRechargeOrder.deleted_at.is_(None),
        WalletRechargeOrder.status == 1,
        WalletRechargeOrder.created_at >= start_dt,
        WalletRechargeOrder.created_at < end_dt,
    ).group_by(WalletRechargeOrder.amount, WalletRechargeOrder.bonus_amount).order_by(WalletRechargeOrder.amount.asc()).all()
    tier_labels = {
        (tier.amount, tier.bonus_amount): tier.label
        for tier in WalletRechargeTier.query.filter(WalletRechargeTier.deleted_at.is_(None)).all()
    }
    return [{
        'Amount': _yuan(int(row[0] or 0)),
        'BonusAmount': _yuan(int(row[1] or 0)),
        'Label': tier_labels.get((row[0], row[1])) or f'充{_yuan(int(row[0] or 0))}',
        'RechargeCount': int(row[2] or 0),
    } for row in rows]


def _wallet_consume_amount(start_dt, end_dt, store_id=None):
    query = db.session.query(func.coalesce(func.sum(WalletTransaction.amount), 0)).filter(
        WalletTransaction.deleted_at.is_(None),
        WalletTransaction.type == 'consume',
        WalletTransaction.direction == 'out',
        WalletTransaction.created_at >= start_dt,
        WalletTransaction.created_at < end_dt,
    )
    if store_id:
        query = query.join(PayOrder, PayOrder.id == WalletTransaction.related_pay_order_id).filter(
            PayOrder.store_id == store_id,
            PayOrder.deleted_at.is_(None),
        )
    return _yuan(int(query.scalar() or 0))


def _point_trend(start_dt, end_dt, granularity, store_id=None):
    bucket = func.date_format(PointTransaction.created_at, _trend_format(granularity))
    query = db.session.query(
        bucket.label('bucket'),
        PointTransaction.direction,
        func.coalesce(func.sum(PointTransaction.amount), 0),
    ).filter(
        PointTransaction.deleted_at.is_(None),
        PointTransaction.created_at >= start_dt,
        PointTransaction.created_at < end_dt,
    )
    if store_id:
        query = query.outerjoin(PayOrder, PointTransaction.related_pay_order_id == PayOrder.id)\
            .outerjoin(PointWithdrawRecord, PointTransaction.related_withdraw_id == PointWithdrawRecord.id)\
            .outerjoin(PointRedeemOrder, PointTransaction.related_redeem_order_id == PointRedeemOrder.id)\
            .filter(or_(
                PayOrder.store_id == store_id,
                PointWithdrawRecord.store_id == store_id,
                PointRedeemOrder.pickup_store_id == store_id,
            ))
    rows = query.group_by('bucket', PointTransaction.direction).order_by('bucket').all()
    data = {}
    for bucket_value, direction, amount in rows:
        item = data.setdefault(bucket_value, {'Date': bucket_value, 'EarnedPoints': 0, 'ConsumedPoints': 0})
        if direction == 'in':
            item['EarnedPoints'] += int(amount or 0)
        else:
            item['ConsumedPoints'] += int(amount or 0)
    return list(data.values())


def _point_redeem_ranking(start_dt, end_dt, store_id=None, limit=10):
    query = db.session.query(
        PointRedeemOrder.product_name,
        func.coalesce(func.sum(PointRedeemOrder.quantity), 0),
        func.coalesce(func.sum(PointRedeemOrder.total_points), 0),
    ).filter(
        PointRedeemOrder.deleted_at.is_(None),
        PointRedeemOrder.created_at >= start_dt,
        PointRedeemOrder.created_at < end_dt,
    )
    if store_id:
        query = query.filter(PointRedeemOrder.pickup_store_id == store_id)
    rows = query.group_by(PointRedeemOrder.product_name).order_by(desc(func.sum(PointRedeemOrder.quantity))).limit(limit).all()
    return [{
        'ProductName': row[0],
        'Quantity': int(row[1] or 0),
        'TotalPoints': int(row[2] or 0),
    } for row in rows]


def _user_insight_items(start_dt, end_dt, store_id=None, limit=50):
    play_query = db.session.query(
        PlayOrder.open_id,
        func.count(func.distinct(PlayOrder.id)).label('play_order_count'),
        func.coalesce(func.sum(PayOrder.amount), 0).label('play_revenue'),
        func.coalesce(func.sum(PlayOrder.play_time), 0).label('play_hours'),
        func.max(PlayOrder.created_at).label('last_play_at'),
    ).select_from(PlayOrder).join(PayOrder, PayOrder.play_order_id == PlayOrder.id).filter(
        PlayOrder.deleted_at.is_(None),
        PlayOrder.created_at >= start_dt,
        PlayOrder.created_at < end_dt,
        PayOrder.deleted_at.is_(None),
        PayOrder.pay_status == 1,
    )
    catering_query = db.session.query(
        Catering.open_id,
        func.count(func.distinct(Catering.id)).label('catering_order_count'),
        func.coalesce(func.sum(Catering.total_price), 0).label('catering_revenue'),
        func.max(Catering.created_at).label('last_catering_at'),
    ).select_from(Catering).join(PayOrder, PayOrder.catering_id == Catering.id).filter(
        *_paid_catering_filters(start_dt, end_dt, store_id)
    )
    if store_id:
        play_query = play_query.filter(PlayOrder.store_id == store_id)
    play_rows = play_query.group_by(PlayOrder.open_id).all()
    catering_rows = catering_query.group_by(Catering.open_id).all()

    users = {}
    for row in play_rows:
        users.setdefault(row.open_id, {}).update({
            'OpenId': row.open_id,
            'PlayOrderCount': int(row.play_order_count or 0),
            'PlayRevenue': _yuan(int(row.play_revenue or 0)),
            '_PlayRevenueCents': int(row.play_revenue or 0),
            'TotalPlayHours': int(row.play_hours or 0),
            'LastPlayAt': row.last_play_at,
        })
    for row in catering_rows:
        users.setdefault(row.open_id, {}).update({
            'OpenId': row.open_id,
            'CateringOrderCount': int(row.catering_order_count or 0),
            'CateringRevenue': _yuan(int(row.catering_revenue or 0)),
            '_CateringRevenueCents': int(row.catering_revenue or 0),
            'LastCateringAt': row.last_catering_at,
        })

    if not users:
        return []

    open_ids = list(users.keys())
    user_map = {
        user.open_id: user
        for user in User.query.filter(User.open_id.in_(open_ids)).all()
    }
    coupon_rows = db.session.query(CouponRecord.open_id, func.count(CouponRecord.id)).filter(
        CouponRecord.deleted_at.is_(None),
        CouponRecord.open_id.in_(open_ids),
        CouponRecord.status == 1,
        CouponRecord.used_at >= start_dt,
        CouponRecord.used_at < end_dt,
    ).group_by(CouponRecord.open_id).all()
    coupon_map = {row[0]: int(row[1] or 0) for row in coupon_rows}
    wallet_rows = db.session.query(WalletRechargeOrder.open_id, func.coalesce(func.sum(WalletRechargeOrder.amount), 0)).filter(
        WalletRechargeOrder.deleted_at.is_(None),
        WalletRechargeOrder.open_id.in_(open_ids),
        WalletRechargeOrder.status == 1,
        WalletRechargeOrder.created_at >= start_dt,
        WalletRechargeOrder.created_at < end_dt,
    ).group_by(WalletRechargeOrder.open_id).all()
    wallet_map = {row[0]: int(row[1] or 0) for row in wallet_rows}
    point_map = {
        account.open_id: account.balance
        for account in PointAccount.query.filter(PointAccount.open_id.in_(open_ids), PointAccount.deleted_at.is_(None)).all()
    }

    now = _now_shanghai_naive()
    result = []
    for open_id, item in users.items():
        user = user_map.get(open_id)
        play_revenue_cents = item.pop('_PlayRevenueCents', 0)
        catering_revenue_cents = item.pop('_CateringRevenueCents', 0)
        last_order_at = max([dt for dt in [item.get('LastPlayAt'), item.get('LastCateringAt')] if dt], default=None)
        total_orders = item.get('PlayOrderCount', 0) + item.get('CateringOrderCount', 0)
        total_revenue = play_revenue_cents + catering_revenue_cents
        result.append({
            'OpenId': open_id,
            'NickName': user.nick_name if user else '',
            'RegisteredStoreId': user.registered_store_id if user else None,
            'CreatedAt': _dt_text(user.created_at) if user else None,
            'IsMonthCardUser': bool(user and user.month_card_expire and user.month_card_expire >= now),
            'MonthCardExpire': _dt_text(user.month_card_expire) if user else None,
            'PlayOrderCount': item.get('PlayOrderCount', 0),
            'CateringOrderCount': item.get('CateringOrderCount', 0),
            'TotalOrderCount': total_orders,
            'PlayRevenue': item.get('PlayRevenue', 0),
            'CateringRevenue': item.get('CateringRevenue', 0),
            'TotalRevenue': _yuan(total_revenue),
            '_TotalRevenueCents': total_revenue,
            'TotalPlayHours': item.get('TotalPlayHours', 0),
            'AvgOrderValue': _yuan(round(total_revenue / total_orders) if total_orders else 0),
            'CouponUsedCount': coupon_map.get(open_id, 0),
            'WalletRechargeAmount': _yuan(wallet_map.get(open_id, 0)),
            'PointBalance': int(point_map.get(open_id, 0) or 0),
            'LastOrderAt': _dt_text(last_order_at),
            'Tags': [
                tag for tag, enabled in [
                    ('月卡用户', bool(user and user.month_card_expire and user.month_card_expire >= now)),
                    ('储值用户', wallet_map.get(open_id, 0) > 0),
                    ('高频游玩', item.get('PlayOrderCount', 0) >= 3),
                    ('饮品活跃', item.get('CateringOrderCount', 0) >= 3),
                    ('优惠券敏感', coupon_map.get(open_id, 0) >= 2),
                ] if enabled
            ],
        })
    result.sort(key=lambda item: item['_TotalRevenueCents'], reverse=True)
    for item in result:
        item.pop('_TotalRevenueCents', None)
    return result[:limit]


@stats_bp.route('/catering/overview', methods=['GET'])
@login_required('dashboard')
def catering_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()

    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': _build_summary(start_dt, end_dt, store_id),
        'Trend': _build_trend(start_dt, end_dt, granularity, store_id),
        'DishRanking': _build_dish_ranking(start_dt, end_dt, store_id),
        'Hourly': _build_hourly(start_dt, end_dt, store_id),
        'Category': _build_category(start_dt, end_dt, store_id),
        'Payment': _build_payment(start_dt, end_dt, store_id),
    }

    return jsonify({
        'Code': 0,
        'Message': 'success',
        'Data': data,
    })


@stats_bp.route('/ops/overview', methods=['GET'])
@login_required('dashboard')
def ops_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    play = _play_summary(start_dt, end_dt, store_id)
    catering_revenue, catering_order_count = _catering_summary_values(start_dt, end_dt, store_id)
    wallet = _wallet_recharge_summary(start_dt, end_dt)
    earned_points, consumed_points = _point_summary_values(start_dt, end_dt, store_id)
    order_count = play['OrderCount'] + catering_order_count
    total_revenue = play['Revenue'] + catering_revenue
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': {
            'TotalRevenue': round(total_revenue, 2),
            'PlayRevenue': play['Revenue'],
            'CateringRevenue': catering_revenue,
            'OrderCount': order_count,
            'AvgOrderValue': round(total_revenue / order_count, 2) if order_count else 0,
            'NewUsers': _new_users(start_dt, end_dt, store_id),
            'ActiveUsers': _active_users(start_dt, end_dt, store_id),
            'RefundAmount': _refund_amount(start_dt, end_dt, store_id),
            'WalletRechargeAmount': wallet['RechargeAmount'],
            'PointEarned': earned_points,
            'PointConsumed': consumed_points,
        },
        'Trend': _ops_trend(start_dt, end_dt, granularity, store_id),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/play/overview', methods=['GET'])
@login_required('dashboard')
def play_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': _play_summary(start_dt, end_dt, store_id),
        'Trend': _play_trend(start_dt, end_dt, granularity, store_id),
        'BillingMode': _play_billing_mode(start_dt, end_dt, store_id),
        'Payment': _play_payment(start_dt, end_dt, store_id),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/user/overview', methods=['GET'])
@login_required('dashboard')
def user_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    paid_users, new_paid_users, returning_paid_users = _paid_user_counts(start_dt, end_dt, store_id)
    new_users = _new_users(start_dt, end_dt, store_id)
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': {
            'NewUsers': new_users,
            'PaidUsers': paid_users,
            'NewPaidUsers': new_paid_users,
            'ReturningPaidUsers': returning_paid_users,
            'NewUserPayRate': _percent(new_paid_users, new_users),
            'ActiveUsers': _active_users(start_dt, end_dt, store_id),
        },
        'Trend': _user_trend(start_dt, end_dt, granularity, store_id),
        'SourceStore': _source_store_distribution(start_dt, end_dt),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/coupon/overview', methods=['GET'])
@login_required('dashboard')
def coupon_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    promotions = _coupon_promotion_stats(start_dt, end_dt, store_id)
    received = sum(item['ReceivedCount'] for item in promotions)
    used = sum(item['UsedCount'] for item in promotions)
    revenue = round(sum(item['Revenue'] for item in promotions), 2)
    discount = round(sum(item['DiscountAmount'] for item in promotions), 2)
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': {
            'ReceivedCount': received,
            'UsedCount': used,
            'UseRate': _percent(used, received),
            'OrderCount': sum(item['OrderCount'] for item in promotions),
            'Revenue': revenue,
            'DiscountAmount': discount,
        },
        'Promotions': promotions,
        'StoreDistribution': _coupon_store_distribution(start_dt, end_dt),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/referral/overview', methods=['GET'])
@login_required('dashboard')
def referral_overview():
    start_dt, end_dt, granularity = _range_params()
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'Summary': _referral_summary(start_dt, end_dt),
        'Trend': _referral_trend(start_dt, end_dt, granularity),
        'ShareRanking': _referral_share_ranking(start_dt, end_dt),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/membership/overview', methods=['GET'])
@login_required('dashboard')
def membership_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': _membership_summary(start_dt, end_dt, store_id),
        'Trend': _membership_trend(start_dt, end_dt, granularity),
        'SourceDistribution': _membership_source_distribution(start_dt, end_dt),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/wallet/overview', methods=['GET'])
@login_required('dashboard')
def wallet_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    summary = _wallet_recharge_summary(start_dt, end_dt)
    summary['ConsumeAmount'] = _wallet_consume_amount(start_dt, end_dt, store_id)
    summary['BalanceTotal'] = _yuan(int(db.session.query(func.coalesce(func.sum(WalletAccount.balance), 0)).filter(
        WalletAccount.deleted_at.is_(None)
    ).scalar() or 0))
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': summary,
        'Trend': _wallet_trend(start_dt, end_dt, granularity),
        'TierDistribution': _wallet_tier_distribution(start_dt, end_dt),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/point/overview', methods=['GET'])
@login_required('dashboard')
def point_overview():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    earned_points, consumed_points = _point_summary_values(start_dt, end_dt, store_id)
    redeem_query = PointRedeemOrder.query.filter(
        PointRedeemOrder.deleted_at.is_(None),
        PointRedeemOrder.created_at >= start_dt,
        PointRedeemOrder.created_at < end_dt,
    )
    withdraw_query = PointWithdrawRecord.query.filter(
        PointWithdrawRecord.deleted_at.is_(None),
        PointWithdrawRecord.status == 1,
        PointWithdrawRecord.created_at >= start_dt,
        PointWithdrawRecord.created_at < end_dt,
    )
    if store_id:
        redeem_query = redeem_query.filter(PointRedeemOrder.pickup_store_id == store_id)
        withdraw_query = withdraw_query.filter(PointWithdrawRecord.store_id == store_id)
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Summary': {
            'EarnedPoints': earned_points,
            'ConsumedPoints': consumed_points,
            'BalanceTotal': int(db.session.query(func.coalesce(func.sum(PointAccount.balance), 0)).filter(
                PointAccount.deleted_at.is_(None)
            ).scalar() or 0),
            'RedeemOrderCount': int(redeem_query.count() or 0),
            'RedeemPoints': int(redeem_query.with_entities(func.coalesce(func.sum(PointRedeemOrder.total_points), 0)).scalar() or 0),
            'WithdrawIssuedPoints': int(withdraw_query.with_entities(func.coalesce(func.sum(PointWithdrawRecord.points), 0)).scalar() or 0),
        },
        'Trend': _point_trend(start_dt, end_dt, granularity, store_id),
        'RedeemRanking': _point_redeem_ranking(start_dt, end_dt, store_id),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})


@stats_bp.route('/user/insights', methods=['GET'])
@login_required('dashboard')
def user_insights():
    start_dt, end_dt, granularity = _range_params()
    store_id = _current_store_id()
    try:
        limit = int(request.args.get('Limit', 50))
    except (TypeError, ValueError):
        limit = 50
    limit = min(max(limit, 1), 200)
    items = _user_insight_items(start_dt, end_dt, store_id, limit)
    data = {
        **_date_meta(start_dt, end_dt, granularity),
        'StoreId': store_id,
        'Items': items,
        'Total': len(items),
    }
    return jsonify({'Code': 0, 'Message': 'success', 'Data': data})
