"""Fixed internal settlement charge, computed once per store and report in cents."""
from collections import defaultdict
from datetime import timedelta
from app import db
from app.models import MonthCardOrder
from .models import SettlementCardPool, SettlementEntry
from .service import month_bounds

POLICY = 'store-month-0.6-v1'
RATE_BPS = 60


def calculate(month, entries):
    bases = defaultdict(int)
    origins = {}

    def eligible(row, seen=None):
        kind = row['kind']
        if kind in ('wechat_play', 'wechat_catering', 'wechat_refund', 'wallet', 'wallet_refund'):
            return True
        if kind in ('point_cost', 'settlement_fee'):
            return False
        if kind == 'adjustment':
            seen = set() if seen is None else seen
            try:
                identity = int(row['reference'])
            except (ValueError, TypeError):
                raise ValueError('结算调整缺少原始流水，无法确定手续费口径')
            if identity in seen:
                raise ValueError('结算调整来源循环，无法确定手续费口径')
            original = db.session.get(SettlementEntry, identity)
            if not original:
                raise ValueError(f'结算调整的原始流水 #{identity} 不存在')
            return eligible(dict(kind=original.kind, reference=original.reference), seen | {identity})
        if kind in ('month_card', 'month_card_carry'):
            reference = row['reference']
            if reference not in origins:
                try:
                    prefix, identity = reference.split(':')
                    if prefix != 'card': raise ValueError()
                    pool = db.session.get(SettlementCardPool, int(identity))
                except (ValueError, TypeError, AttributeError):
                    pool = None
                order = MonthCardOrder.query.execution_options(global_reference_check=True).filter_by(id=pool.order_id).first() if pool else None
                if not order:
                    raise ValueError(f'月卡分配 {reference} 缺少原始开卡订单，无法确定手续费')
                # Legacy null/empty source also means WeChat, as in the order API.
                source = order.source or 'wechat'
                if source not in ('wechat', 'gift', 'third_party', 'meituan', 'storage_gift'):
                    raise ValueError(f'月卡订单 #{order.id} 的渠道「{source}」需核对后才能确定手续费')
                origins[reference] = source == 'wechat'
            return origins[reference]
        raise ValueError(f'结算类型 {kind} 尚无手续费口径，请核对')

    for row in entries:
        # Include exempt stores with a zero base for explicit report disclosure.
        for party in (row['payer_id'], row['receiver_id']):
            if party: bases[party] += 0
        if not eligible(row): continue
        if row['receiver_id']: bases[row['receiver_id']] += row['amount']
        if row['payer_id']: bases[row['payer_id']] -= row['amount']
    _, end = month_bounds(month)
    charges, disclosures = [], []
    for sid, base in sorted(bases.items()):
        # Symmetric half-up rounding: refunds reverse fees; never round per order.
        fee = (abs(base) * RATE_BPS + 5000) // 10000 * (1 if base >= 0 else -1)
        disclosures.append(dict(StoreId=sid, Base=base, RateBps=RATE_BPS, Fee=fee))
        if not fee: continue
        charges.append(dict(id=None, month=month, event_at=(end-timedelta(microseconds=1)).isoformat(),
            biz_key=f'settlement:fee:{month}:{sid}', kind='settlement_fee', reference=f'fee:{month}:{sid}',
            payer_id=sid, receiver_id=0, amount=fee, face_amount=0,
            detail=f'统一结算手续费；整月计费基数 {base / 100:.2f} 元 × 0.6%，四舍五入到分；积分不计费；负值为手续费冲回'))
    return disclosures, charges
