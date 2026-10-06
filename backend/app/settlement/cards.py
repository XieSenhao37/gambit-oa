"""Natural-month card allocation. Card terms and order prices are immutable snapshots."""
from collections import defaultdict
from datetime import datetime, timedelta
from app import db
from app.models import PlayOrder
from .clock import now
from .models import SettlementCardPool, SettlementCardUsage, SettlementCardPeriod


def term_boundary(order, start, index):
    from .service import add_months
    if order.duration_days:
        if order.duration_days != order.open_period * 30:
            raise ValueError('月卡固定卡期快照不一致')
        return start + timedelta(days=30 * index)
    return add_months(start, index)


def window(pool, month):
    from .service import month_bounds
    month_start, month_end = month_bounds(month)
    start, end = max(pool.starts_at, month_start), min(pool.ends_at, month_end)
    if end <= start:
        return None
    duration = int((pool.ends_at - pool.starts_at).total_seconds())
    if duration <= 0:
        raise ValueError('月卡有效期快照异常')
    # Cumulative floors conserve the original cents across all monthly slices.
    before = int((start - pool.starts_at).total_seconds())
    after = int((end - pool.starts_at).total_seconds())
    amount = pool.amount * after // duration - pool.amount * before // duration
    return start, end, amount


def valid_seconds(usage, start, end):
    if usage.status != 'valid':
        return 0
    begin, finish = max(start, usage.started_at), min(end, usage.ended_at)
    if finish <= begin:
        return 0
    span = int((usage.ended_at - usage.started_at).total_seconds())
    if span <= 0 or usage.seconds < 0 or usage.seconds > span:
        raise ValueError(f'月卡核销 #{usage.id} 的时长异常')
    left = int((begin - usage.started_at).total_seconds())
    right = int((finish - usage.started_at).total_seconds())
    return usage.seconds * right // span - usage.seconds * left // span


def weights_for(uses, start, end):
    weights = defaultdict(int)
    for usage in uses:
        seconds = valid_seconds(usage, start, end)
        if seconds:
            weights[usage.store_id] += seconds
    return dict(weights)


def shares_for(amount, weights):
    from .service import apportion
    return [{'store_id': party, 'seconds': weights.get(party, 0), 'amount': value}
            for party, value in apportion(amount, weights).items()]


def settle_period(pool, month):
    """Caller holds the pool lock before any usage or financial-period lock."""
    from .service import add_entry, month_bounds
    bounds = window(pool, month)
    if not bounds:
        return
    start, end, amount = bounds
    _, month_end = month_bounds(month)
    if month_end > now():
        raise ValueError('自然月尚未结束，每月 1 日开始结算上月')
    existing = SettlementCardPeriod.query.filter_by(pool_id=pool.id, month=month).populate_existing().with_for_update().first()
    if existing:
        return
    uses = SettlementCardUsage.query.filter_by(pool_id=pool.id).populate_existing().with_for_update().all()
    overlapping = [u for u in uses if u.started_at < end and u.ended_at > start]
    if any(u.status == 'review' for u in overlapping):
        raise ValueError(f'月卡 #{pool.id} 在 {month} 有待核验时长')
    unfinished = PlayOrder.query.execution_options(global_reference_check=True).filter(
        PlayOrder.open_id == pool.open_id, PlayOrder.in_time < end,
        PlayOrder.out_time.is_(None), PlayOrder.deleted_at.is_(None)).first()
    if unfinished:
        raise ValueError(f'月卡 #{pool.id} 尚有未离场记录，完成离场后重试')
    weights = weights_for(overlapping, start, end)
    shares = shares_for(amount, weights) if weights else []
    row = SettlementCardPeriod(pool_id=pool.id, month=month, starts_at=start, ends_at=end,
        amount=amount, allocated_amount=amount if weights else 0,
        status='allocated' if weights else 'carried', shares=shares, carry_shares=[], carry_amount=0)
    db.session.add(row)
    # Attribute to the service month even when the card expires exactly on the 1st.
    event_at = end - timedelta(seconds=1)
    for share in shares:
        add_entry(biz_key=f'card:{pool.id}:month:{month}:store:{share["store_id"]}', kind='month_card',
            reference=f'card:{pool.id}', payer_id=pool.payer_id, receiver_id=share['store_id'],
            amount=share['amount'], face_amount=0, event_at=event_at,
            detail=f'月卡 #{pool.id}；{month} 释放 {amount} 分；本店有效时长 {share["seconds"]}/{sum(weights.values())} 秒')
    db.session.flush()
    if end == pool.ends_at:
        periods = SettlementCardPeriod.query.filter_by(pool_id=pool.id).populate_existing().with_for_update().all()
        if sum(p.amount for p in periods) != pool.amount:
            raise ValueError('月卡尚有前期月份未处理，请按月份顺序结算')
        carry = pool.amount - sum(p.allocated_amount for p in periods)
        if carry < 0:
            raise ValueError('月卡累计分配超出原始金额')
        if carry:
            lifetime_weights = weights_for(uses, pool.starts_at, pool.ends_at)
            row.carry_shares = shares_for(carry, lifetime_weights)
            row.carry_amount = carry
            row.allocated_amount += carry
            for share in row.carry_shares:
                add_entry(biz_key=f'card:{pool.id}:carry:store:{share["store_id"]}', kind='month_card_carry',
                    reference=f'card:{pool.id}', payer_id=pool.payer_id, receiver_id=share['store_id'],
                    amount=share['amount'], face_amount=0, event_at=event_at,
                    detail=f'月卡 #{pool.id}；未核销月份暂留款 {carry} 分，到期月统一补分' if lifetime_weights else f'月卡 #{pool.id} 全卡期零使用，暂留款归总部')
        pool.status = 'closed'
        pool.closed_at = now()
    db.session.flush()


def prepare_cards(month):
    """Process every finished slice through this month, in chronological order."""
    from .service import month_bounds, add_months
    _, month_end = month_bounds(month)
    if month_end > now():
        raise ValueError('自然月尚未结束，每月 1 日开始结算上月')
    ids = [p.id for p in SettlementCardPool.query.filter(
        SettlementCardPool.status == 'open', SettlementCardPool.starts_at < month_end).order_by(SettlementCardPool.id)]
    for pool_id in ids:
        pool = SettlementCardPool.query.filter_by(id=pool_id).populate_existing().with_for_update().one()
        if pool.status == 'closed':
            continue
        prepare_pool(pool,month)


def prepare_pool(pool,month):
    from .service import month_bounds, add_months
    if pool.status=='closed':return
    _,month_end=month_bounds(month)
    cursor = pool.starts_at.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    while cursor < min(pool.ends_at, month_end):
        settle_period(pool, cursor.strftime('%Y-%m'))
        cursor = add_months(cursor, 1)


def card_view(pool, month, uses, periods=None):
    """No writes: current-month estimates and committed period snapshots are distinct."""
    from .service import month_bounds
    if periods is None:
        periods = SettlementCardPeriod.query.filter_by(pool_id=pool.id).order_by(SettlementCardPeriod.month).all()
    bounds = window(pool, month)
    weights = weights_for(uses, bounds[0], bounds[1]) if bounds else {}
    recorded = next((p for p in periods if p.month == month), None)
    estimated = recorded.shares if recorded else shares_for(bounds[2], weights) if bounds and weights else []
    _, month_end = month_bounds(month)
    elapsed = max(0, int((min(month_end, pool.ends_at) - pool.starts_at).total_seconds()))
    duration = int((pool.ends_at - pool.starts_at).total_seconds())
    released = pool.amount * elapsed // duration if duration > 0 else 0
    distributed = sum(p.allocated_amount for p in periods if p.month <= month)
    return dict(month=month, released_amount=bounds[2] if bounds else 0,
        released_total=released, distributed_total=distributed, pending_amount=released-distributed,
        future_amount=pool.amount-released, total_seconds=sum(weights.values()), estimated=estimated,
        carry_shares=recorded.carry_shares if recorded else [],
        period_status=recorded.status if recorded else 'estimate', periods=periods)
