"""Read ordinary WeChat payments into report snapshots; never mutate payment records."""
from collections import defaultdict
from sqlalchemy import or_
from app import db
from app.models import PayOrder, RefundRequest, Store
from .models import SettlementControl, SettlementEntry, SettlementPeriod, SettlementReport
from . import service

CASH_KINDS = ('wechat_play', 'wechat_catering', 'wechat_refund')


def candidates(month, sid=None, strict=False):
    """Unsettled successful cash events, including late events from confirmed months.

    Recharge/card purchases and refundable organization deposits are separate liabilities.
    Only the WeChat leg of play/catering payments belongs in this ordinary-cash section.
    """
    control = db.session.get(SettlementControl, 1)
    if not control or not control.initialized_at:
        raise ValueError('结算期初初始化未完成')
    _, end = service.month_bounds(month)
    if end <= control.cutoff:
        return []
    q = PayOrder.query.execution_options(global_reference_check=True).filter(
        PayOrder.deleted_at.is_(None), PayOrder.pay_status.in_([1, 3]),
        PayOrder.pay_type.in_([0, 4]), PayOrder.month_card_order_id.is_(None),
        PayOrder.wallet_recharge_order_id.is_(None), PayOrder.group_activity_participant_id.is_(None),
        or_(PayOrder.play_order_id.isnot(None), PayOrder.catering_id.isnot(None)),
        or_(PayOrder.pay_end_time >= control.cutoff,
            (PayOrder.pay_end_time.is_(None) & (PayOrder.created_at >= control.cutoff))),
        or_(PayOrder.pay_end_time < end, PayOrder.pay_end_time.is_(None)))
    if sid is not None:
        q = q.filter(PayOrder.store_id == sid)
    payments = q.order_by(PayOrder.id).populate_existing().all()
    if not payments:
        return []
    ids = [p.id for p in payments]
    refunds = defaultdict(list)
    for r in RefundRequest.query.execution_options(global_reference_check=True).filter(RefundRequest.pay_order_id.in_(ids),
            RefundRequest.deleted_at.is_(None), RefundRequest.status == 'refunded').populate_existing():
        refunds[r.pay_order_id].append(r)
    posted = {key for (key,) in db.session.query(SettlementEntry.biz_key).filter(
        SettlementEntry.kind.in_(CASH_KINDS))}
    periods = {p.month: p.status for p in SettlementPeriod.query}
    if strict:
        # The control lock serializes confirmations. Read their reports with a current
        # read as well: an older MySQL transaction snapshot must not pay a source twice.
        for report in SettlementReport.query.filter_by(status='confirmed').populate_existing().with_for_update():
            periods[report.month] = 'locked'
            posted.update(e['biz_key'] for e in report.payload['entries'] if e['kind'] in CASH_KINDS)
    stores = {s.id for s in Store.query}
    rows = []

    def add(p, amount, at, key, kind, reference, detail):
        if key in posted or at >= end or at < control.cutoff:
            return
        source_month = at.strftime('%Y-%m')
        if source_month < month:
            if strict and periods.get(source_month) != 'locked':
                raise ValueError(f'请先结算 {source_month} 的微信消费或退款，不能跳过未结算月份')
            detail = f'补入此前未结算微信记录，原发生月 {source_month}；' + detail
        rows.append(dict(id=None, month=month, event_at=at.isoformat(),
            biz_key=key, kind=kind, reference=reference, payer_id=0,
            receiver_id=p.store_id, amount=amount, face_amount=0, detail=detail))

    for p in payments:
        if p.store_id not in stores or not p.store_id:
            raise ValueError(f'微信支付单 #{p.id} 缺少有效门店，不能生成结算金额')
        if p.pay_end_time is None:
            raise ValueError(f'微信支付单 #{p.id} 缺少支付成功时间，请核对原单')
        if bool(p.play_order_id) == bool(p.catering_id):
            raise ValueError(f'微信支付单 #{p.id} 的游玩/餐饮归属不唯一')
        cash, wallet = p.wechat_amount or 0, p.wallet_amount or 0
        if cash < 0 or wallet < 0 or cash + wallet != p.amount or (p.pay_type == 0 and wallet):
            raise ValueError(f'微信支付单 #{p.id} 的支付金额拆分不一致，请核对原单')
        if not cash:
            continue
        kind = 'wechat_play' if p.play_order_id else 'wechat_catering'
        business = f'游玩单 #{p.play_order_id}' if p.play_order_id else f'餐饮单 #{p.catering_id}'
        detail = f'{business}；支付单 #{p.id}；商户单号 {p.order_id or "未记录"}；仅微信实收部分，储值部分另行折算'
        add(p, cash, p.pay_end_time, f'wechat:pay:{p.id}', kind, f'pay:{p.id}', detail)
        succeeded = refunds[p.id]
        # Current refund service permits one full-order refund, and snapshots the two legs.
        # Never infer a split for future partial refunds or contradictory historical rows.
        if len(succeeded) > 1:
            raise ValueError(f'支付单 #{p.id} 存在多笔成功退款，需核对逐笔微信退款金额')
        if not succeeded and ((p.wechat_refund_amount or 0) or p.pay_status == 3):
            raise ValueError(f'支付单 #{p.id} 缺少成功退款记录，不能核对退款归月')
        for r in succeeded:
            if not r.refunded_at or r.refunded_at < p.pay_end_time:
                raise ValueError(f'退款单 #{r.id} 的退款成功时间异常')
            if r.amount != p.amount or (p.wechat_refund_amount or 0) != cash or (p.wallet_refund_amount or 0) != wallet:
                raise ValueError(f'退款单 #{r.id} 的微信/储值退款拆分不一致，请核对原单')
            add(p, -cash, r.refunded_at, f'wechat:refund:{r.id}', 'wechat_refund',
                f'refund:{r.id}', f'{business}；原支付单 #{p.id}；退款单 #{r.id}；仅冲减已成功退回的微信金额')
    return sorted(rows, key=lambda r: (r['event_at'], r['biz_key']))


def breakdown(entries):
    """Signed store-level contributions. Components add up to the settlement net."""
    result = defaultdict(lambda: dict(wechat_play=0, wechat_catering=0, wechat_refund=0,
        wallet=0, month_card=0, point_compensation=0, point_cost=0, adjustment=0, settlement_fee=0))
    for e in entries:
        kind = e['kind']
        for party, sign in ((e['receiver_id'], 1), (e['payer_id'], -1)):
            if kind == 'point_cost':
                category = 'point_compensation' if sign == 1 else 'point_cost'
            elif kind in ('wallet', 'wallet_refund'):
                category = 'wallet'
            elif kind in ('month_card', 'month_card_carry'):
                category = 'month_card'
            else:
                category = kind if kind in (*CASH_KINDS, 'settlement_fee') else 'adjustment'
            result[party][category] += sign * e['amount']
    return dict(result)
