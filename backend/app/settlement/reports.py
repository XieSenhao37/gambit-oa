"""Manual monthly reports: disposable calculation, immutable snapshot, atomic confirmation."""
import hashlib
import json
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy import func
from app import db
from app.models import Store
from . import service, cash, fees
from .clock import now
from .models import (SettlementReport, SettlementPeriod, SettlementEntry, SettlementStatement,
    SettlementCardPool, SettlementCardPeriod, SettlementCardUsage, SettlementExpense)


def dump(row):
    return {c.name: (v.isoformat() if isinstance(v, datetime) else v)
            for c in row.__table__.columns for v in [getattr(row, c.name)]}


def restore(model, values, omit=()):
    values = {k: v for k, v in values.items() if k not in omit}
    for c in model.__table__.columns:
        if c.name in values and isinstance(c.type, db.DateTime) and values[c.name]:
            values[c.name] = datetime.fromisoformat(values[c.name])
    return values


def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def current(month, lock=False):
    q = SettlementReport.query.filter_by(month=month).filter(SettlementReport.status != 'void').order_by(SettlementReport.version.desc())
    if lock: q = q.populate_existing().with_for_update()
    return q.first()


def assert_editable(kind, identity):
    # A distributed report must not silently change when its source is edited.
    for report in SettlementReport.query.filter_by(status='draft').populate_existing().with_for_update().all():
        rows = report.payload['expenses' if kind == 'expense' else 'pools']
        if any(r['id'] == identity for r in rows):
            raise ValueError(f'资料已纳入 {report.month} V{report.version} 报表；未开始收付款时请先作废报表，再修改并重新生成')


def summarize(entries):
    totals = defaultdict(lambda: dict(income=0, deduction=0, amount=0))
    for e in entries:
        totals[e['receiver_id']]['income'] += e['amount']
        totals[e['payer_id']]['deduction'] += e['amount']
    names = {s.id: s.name for s in Store.query.all()}; names[0] = '总部'
    return [dict(StoreId=sid, StoreName=names.get(sid, f'门店 #{sid}'), **{**v, 'amount': v['income'] - v['deduction']}) for sid, v in sorted(totals.items())]


def generate(month, actor, key):
    control = service.lock_operations()
    start, end = service.month_bounds(month)
    if month < control.cutoff.strftime('%Y-%m'):
        raise ValueError('所选月份早于结算启用月份，不生成历史结算')
    if end > now(): raise ValueError('自然月尚未结束，请在次月 1 日起生成报表')
    if not isinstance(key, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', key):
        raise ValueError('请提供有效的报表请求标识')
    old = SettlementReport.query.filter_by(request_key=key).populate_existing().with_for_update().first()
    if old:
        if old.month != month or old.status == 'void': raise ValueError('该请求对应其他月份或已作废报表，请重新生成')
        return old
    if current(month, True): raise ValueError('本月已有有效报表；如需修改，请先作废待确认报表')
    period = SettlementPeriod.query.filter_by(month=month).populate_existing().with_for_update().first()
    if period and period.status != 'draft': raise ValueError('本月已结算，不能重新生成')
    later = SettlementReport.query.filter(SettlementReport.month > month, SettlementReport.status != 'void').populate_existing().with_for_update().first()
    if later: raise ValueError(f'已有 {later.month} 的有效报表，不能倒序生成；历史差错请补记调整')
    earlier = SettlementReport.query.filter(SettlementReport.month < month, SettlementReport.status == 'draft').populate_existing().with_for_update().first()
    if earlier: raise ValueError(f'请先完成 {earlier.month} 的待确认报表')
    earlier = SettlementEntry.query.join(SettlementPeriod, SettlementPeriod.month == SettlementEntry.month).filter(
        SettlementEntry.month < month, SettlementPeriod.status == 'draft').order_by(SettlementEntry.month).populate_existing().with_for_update().first()
    if earlier: raise ValueError(f'请先处理 {earlier.month} 的未结算记录')
    # Existing versions wrote permanent card slices / expenses before month confirmation.
    # Never guess whether those records were paid, and never silently delete them.
    legacy = SettlementEntry.query.filter(SettlementEntry.month == month, SettlementEntry.kind.in_(['month_card', 'month_card_carry', 'point_cost'])).first()
    legacy_slice = SettlementCardPeriod.query.filter_by(month=month).first()
    if legacy or legacy_slice: raise ValueError('发现旧版提前入账的月卡或积分记录，请先核对迁移，不能直接生成新版报表')
    expenses = SettlementExpense.query.filter(SettlementExpense.completed_at < end,
        SettlementExpense.status.in_(['needs_cost', 'ready'])).populate_existing().with_for_update().all()
    for e in expenses:
        if e.status != 'ready' or e.amount is None:
            raise ValueError(f'积分成本 #{e.id} 尚未补全并保存结算资料')
    expense_before = [dump(e) for e in expenses]
    pools = SettlementCardPool.query.filter(SettlementCardPool.status == 'open', SettlementCardPool.starts_at < end).order_by(SettlementCardPool.id).populate_existing().with_for_update().all()
    pool_before = [dump(p) for p in pools]
    pool_ids = [p.id for p in pools]
    uses = [dump(u) for u in SettlementCardUsage.query.filter(SettlementCardUsage.pool_id.in_(pool_ids)).populate_existing().with_for_update().all()]
    original_slices = {p.id for p in SettlementCardPeriod.query.filter(SettlementCardPeriod.pool_id.in_(pool_ids)).populate_existing().with_for_update().all()}
    existing = SettlementEntry.query.filter_by(month=month).populate_existing().with_for_update().all()
    existing_ids = {e.id for e in existing}
    cash_entries = cash.candidates(month, strict=True)
    previous_id = db.session.query(func.max(SettlementEntry.id)).scalar() or 0
    snapshot = None
    # Reuse the cent-conserving allocator inside a SAVEPOINT, ALWAYS roll it back.
    # Only the report below is persisted; pools, usages, expenses and entries stay unchanged.
    savepoint = db.session.begin_nested()
    try:
        from .cards import prepare_cards
        prepare_cards(month)
        for e in expenses: service.post_expense(e.id)
        db.session.flush()
        generated = SettlementEntry.query.filter(SettlementEntry.id > previous_id, SettlementEntry.kind.in_(['month_card', 'month_card_carry', 'point_cost'])).all()
        for e in generated:
            if e.month != month:
                # Full-period legacy cards are included in the first cutover report.
                if e.month < control.cutoff.strftime('%Y-%m') and month == control.cutoff.strftime('%Y-%m'):
                    e.month = month
                    e.detail = '期初有效旧卡完整卡期补入；' + e.detail
                else: raise ValueError(f'尚有 {e.month} 的未结算区间，请先按月份顺序生成报表')
        slices = [dump(p) for p in SettlementCardPeriod.query.filter(SettlementCardPeriod.pool_id.in_(pool_ids)).populate_existing().with_for_update().all() if p.id not in original_slices]
        for part in slices:
            if part['month'] < month:
                previous = db.session.get(SettlementPeriod, part['month'])
                opening = part['month'] < control.cutoff.strftime('%Y-%m') and month == control.cutoff.strftime('%Y-%m')
                if not opening and (not previous or previous.status != 'locked'):
                    raise ValueError(f"尚有 {part['month']} 的月卡区间未处理，请按月份顺序生成报表")
        entries = [dump(e) for e in existing] + [dict(dump(e), id=None) for e in generated] + cash_entries
        fee_details, fee_entries = fees.calculate(month, entries)
        entries += fee_entries
        snapshot = dict(fee_policy=fees.POLICY, fees=fee_details, entries=entries, existing_ids=sorted(existing_ids), periods=slices,
            pools=pool_before, pool_after=[dump(p) for p in pools], usages=uses,
            expenses=expense_before, totals=summarize(entries),
            names={str(s.id):s.name for s in Store.query.all()} | {'0':'总部'},
            cash_included=True,coverage_start=max(start,control.cutoff).isoformat(timespec='seconds'),
            coverage_end=end.isoformat(timespec='seconds'))
    finally:
        savepoint.rollback()
    version = max([r.version for r in SettlementReport.query.filter_by(month=month).populate_existing().with_for_update().all()], default=0) + 1
    report = SettlementReport(month=month, version=version, request_key=key, created_by=actor,
        payload=snapshot, digest=digest(snapshot), status='draft')
    db.session.add(report); db.session.flush()
    return report


def void(report_id, expected_digest):
    service.lock_operations()
    report = SettlementReport.query.filter_by(id=report_id).populate_existing().with_for_update().first()
    if not report or report.digest != expected_digest: raise ValueError('报表版本无效，请刷新')
    if report.status == 'confirmed': raise ValueError('已结算报表不能作废，请补记调整')
    report.status = 'void'
    return report


def confirm(report_id, expected_digest, actor, references, completed):
    if isinstance(report_id,bool) or not isinstance(report_id,int) or report_id < 1: raise ValueError('请指定有效报表版本')
    service.lock_operations()
    report = SettlementReport.query.filter_by(id=report_id).populate_existing().with_for_update().first()
    if not report or report.digest != expected_digest or report.digest != digest(report.payload):
        raise ValueError('报表版本或内容校验失败，请刷新核对')
    if report.status == 'void': raise ValueError('报表已作废，请使用最新有效版本')
    if completed is not True: raise ValueError('请确认各方核对无误，且应付与应收款均已完成')
    needed = {str(t['StoreId']) for t in report.payload['totals'] if t['StoreId'] and t['amount']}
    if not isinstance(references, dict) or set(references) != needed or any(
        not isinstance(v, str) or not v.strip() or len(v.strip()) > 200 for v in references.values()):
        raise ValueError('请逐店填写实际付款或收回总部的凭证；负数不能结转下月')
    references = {k: v.strip() for k, v in references.items()}
    if report.status == 'confirmed':
        if report.confirmation['references'] != references: raise ValueError('已确认报表的收付款凭证不能覆盖')
        return report
    if not report.payload.get('cash_included'):
        raise ValueError('此旧版报表未包含微信消费；未开始收付款时请先作废并重新生成，已开始收付款请联系总部核对')
    if report.payload.get('fee_policy') != fees.POLICY:
        raise ValueError('此旧版报表未包含统一手续费；未开始收付款时请先作废并重新生成，已开始收付款请联系总部核对')
    payload = report.payload
    # Lock assets before the financial period, matching Go business writer order.
    for before in payload['pools']:
        pool = SettlementCardPool.query.filter_by(id=before['id']).populate_existing().with_for_update().one()
        if dump(pool) != before: raise ValueError('月卡状态与报表不一致，请联系总部核对，不能重复结算')
    for before in payload['expenses']:
        e = SettlementExpense.query.filter_by(id=before['id']).populate_existing().with_for_update().one()
        if dump(e) != dict(before, proof_image=before.get('proof_image')): raise ValueError('积分成本与报表不一致，请联系总部核对')
    period = service.locked_period(report.month)
    if period.status != 'draft': raise ValueError('本月已由其他报表结算')
    entries = SettlementEntry.query.filter_by(month=report.month).populate_existing().with_for_update().all()
    selected = {e['id']: e for e in payload['entries'] if e['id'] is not None}
    for identity, before in selected.items():
        match = next((e for e in entries if e.id == identity), None)
        if not match or dump(match) != before: raise ValueError('原始流水与报表不一致，请联系总部核对')
    late = [e for e in entries if e.id not in selected]
    # Late wallet/refund entries must remain payable, without changing the paid report.
    next_month = service.add_months(datetime.strptime(report.month, '%Y-%m'), 1).strftime('%Y-%m')
    if late:
        target = service.locked_period(next_month)
        if target.status != 'draft': raise ValueError('后续月份已结算，不能归入迟到流水；请联系总部核对')
        for e in late:
            e.month = next_month
            e.detail = f'报表生成后新增，原归账月 {report.month}，转入后续月；' + e.detail
    for row in payload['entries']:
        if row['id'] is None:
            db.session.add(SettlementEntry(**restore(SettlementEntry, row, ('id', 'created_at'))))
    for row in payload['periods']:
        db.session.add(SettlementCardPeriod(**restore(SettlementCardPeriod, row, ('id', 'settled_at'))))
    for after in payload['pool_after']:
        p = db.session.get(SettlementCardPool, after['id'])
        p.status = after['status']
        if p.status == 'closed': p.closed_at = now()
    for before in payload['expenses']: db.session.get(SettlementExpense, before['id']).status = 'posted'
    late_uses = []
    _, end = service.month_bounds(report.month)
    known = {u['id'] for u in payload['usages']}
    for u in SettlementCardUsage.query.filter(SettlementCardUsage.pool_id.in_([p['id'] for p in payload['pools']]), SettlementCardUsage.started_at < end).populate_existing().with_for_update():
        if u.id not in known: late_uses.append(u.id)
    for t in payload['totals']:
        if t['StoreId']:
            db.session.add(SettlementStatement(month=report.month, store_id=t['StoreId'], amount=t['amount'],
                paid_at=now(), paid_by=actor, payment_ref=references.get(str(t['StoreId']), '零净额，无需转账')))
    period.status = 'locked'; period.locked_at = now(); period.locked_by = actor
    report.status = 'confirmed'; report.confirmed_at = now(); report.confirmed_by = actor
    report.confirmation = dict(references=references, late_entry_ids=[e.id for e in late], late_usage_ids=late_uses)
    db.session.flush()
    return report


def public(report, sid=None):
    """Only expose the selected store's financial lines, never internal source snapshots."""
    if not report: return None
    entries = [e for e in report.payload['entries'] if sid is None or sid in (e['payer_id'], e['receiver_id'])]
    totals = [t for t in report.payload['totals'] if sid is None or t['StoreId'] == sid]
    names = {int(k):v for k,v in report.payload['names'].items()}
    if report.status == 'confirmed':
        ids = dict(db.session.query(SettlementEntry.biz_key, SettlementEntry.id).filter(SettlementEntry.biz_key.in_([e['biz_key'] for e in entries])).all())
        entries = [dict(e, id=ids.get(e['biz_key'], e['id'])) for e in entries]
    return dict(Id=report.id, Month=report.month, Version=report.version, Number=f'{report.month}-V{report.version}',
        CashIncluded=bool(report.payload.get('cash_included')),
        FeesIncluded=bool(report.payload.get('fee_policy')),
        Fees=[f for f in report.payload.get('fees', []) if sid is None or f['StoreId']==sid],
        Breakdown={k:v for k,v in cash.breakdown(entries).items() if sid is None or k==sid},
        Status=report.status, Digest=report.digest, CreatedAt=report.created_at.isoformat(timespec='seconds'),
        ConfirmedAt=report.confirmed_at.isoformat(timespec='seconds') if report.confirmed_at else None,
        Totals=totals, Entries=[dict(e, id=e['id'] or e['biz_key'], payer_name=names.get(e['payer_id'], str(e['payer_id'])),
                                   receiver_name=names.get(e['receiver_id'], str(e['receiver_id']))) for e in entries],
        Confirmation=report.confirmation if sid is None else None)
