from .clock import now
"""Internal store settlement. Integer cents throughout; no bank-transfer side effects."""
import calendar
import os
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy import select
from app import db
from .models import *


def enabled():
    if os.getenv('STORE_SETTLEMENT_ENABLED') != 'true':
        return False
    control = db.session.get(SettlementControl, 1)
    if not control or not control.initialized_at:
        raise ValueError('结算期初初始化未完成')
    return now() >= control.cutoff


def add_months(value, months):
    year, month = divmod(value.year * 12 + value.month - 1 + months, 12)
    return value.replace(year=year, month=month+1, day=min(value.day, calendar.monthrange(year,month+1)[1]))


def apportion(amount, weights):
    """Largest remainders, stable party-ID ties, conserving every cent."""
    if amount < 0 or any(v < 0 for v in weights.values()):
        raise ValueError('分配金额或权重无效')
    total = sum(weights.values())
    if not total:
        return {0: amount}
    result = {k: amount*v//total for k,v in weights.items()}
    ranks = sorted(weights, key=lambda k: (-(amount*weights[k] % total), k))
    for k in ranks[:amount-sum(result.values())]: result[k] += 1
    return result


def lock_operations():
    # Serialize OA financial mutations and manual report confirmations; Go business hooks
    # only read this control row and retain their existing account/asset locks.
    return SettlementControl.query.filter_by(id=1).populate_existing().with_for_update().one()


def locked_period(month):
    # A separate SAVEPOINT prevents a duplicate row race from rolling back business writes.
    row = db.session.get(SettlementPeriod, month)
    if not row:
        from sqlalchemy.exc import IntegrityError
        try:
            with db.session.begin_nested():
                db.session.add(SettlementPeriod(month=month,status='draft'))
                db.session.flush()
        except IntegrityError: pass
    return db.session.execute(select(SettlementPeriod).where(SettlementPeriod.month==month).with_for_update().execution_options(populate_existing=True)).scalar_one()


def add_entry(**values):
    if SettlementEntry.query.filter_by(biz_key=values['biz_key']).first(): return
    at = values.setdefault('event_at', now())
    month = at.strftime('%Y-%m')
    for _ in range(120):
        period = locked_period(month)
        if period.status == 'draft':
            db.session.add(SettlementEntry(month=month,**values));db.session.flush();return
        month = add_months(datetime.strptime(month,'%Y-%m'),1).strftime('%Y-%m')
    raise ValueError('未找到开放结算月份')


def create_card_pools(order, start, payer):
    if not enabled(): return
    if SettlementCardPool.query.filter_by(order_id=order.id).first(): return
    from .cards import term_boundary
    amounts = apportion(order.amount, {i:1 for i in range(order.open_period)})
    for i in range(order.open_period):
        db.session.add(SettlementCardPool(source_key=f'card:{order.id}:{i}',order_id=order.id,open_id=order.open_id,starts_at=term_boundary(order,start,i),ends_at=term_boundary(order,start,i+1),amount=amounts[i],payer_id=payer,status='open'))


def close_card(pool_id):
    from .cards import prepare_pool
    pool = SettlementCardPool.query.filter_by(id=pool_id).populate_existing().with_for_update().first()
    if not pool:raise ValueError('月卡不存在')
    _,end = month_bounds((pool.ends_at-timedelta(seconds=1)).strftime('%Y-%m'))
    if end>now():raise ValueError('请在到期月份结束后，按自然月统一结算')
    prepare_pool(pool,(end-timedelta(seconds=1)).strftime('%Y-%m'))


def post_expense(expense_id):
    expense = SettlementExpense.query.filter_by(id=expense_id).populate_existing().with_for_update().one()
    if expense.status=='posted': return
    if expense.status!='ready' or expense.amount is None or expense.completed_at is None: raise ValueError('成本未确认或尚未履约')
    rows = db.session.query(SettlementAllocation,SettlementBatch).join(SettlementBatch,SettlementBatch.id==SettlementAllocation.batch_id).filter(SettlementAllocation.expense_key==expense.expense_key,SettlementAllocation.state=='consumed').populate_existing().with_for_update().all()
    weights=defaultdict(int)
    for a,b in rows: weights[b.responsible_store_id]+=a.amount
    if not weights: raise ValueError('缺少消耗积分的来源明细')
    for store,amount in apportion(expense.amount,weights).items():
        add_entry(biz_key=f'expense:{expense.id}:party:{store}',kind='point_cost',reference=expense.expense_key,payer_id=store,receiver_id=expense.provider_id,amount=amount,event_at=expense.completed_at,detail=f'积分成本 #{expense.id}；责任积分 {weights[store]} / {sum(weights.values())}；{expense.note}')
    expense.status='posted'


def month_bounds(month):
    start=datetime.strptime(month,'%Y-%m')
    if start.strftime('%Y-%m')!=month: raise ValueError('月份格式应为 YYYY-MM')
    return start,add_months(start,1)


def totals(month, current_read=False):
    result=defaultdict(lambda:{'income':0,'deduction':0,'amount':0})
    query=SettlementEntry.query.filter_by(month=month)
    # MySQL REPEATABLE READ may have an older snapshot from the card/expense scans.
    # The period lock prevents new writers; a locking read includes all committed entries.
    if current_read:query=query.populate_existing().with_for_update()
    for e in query.all():
        result[e.receiver_id]['income']+=e.amount
        result[e.payer_id]['deduction']+=e.amount
    for data in result.values(): data['amount']=data['income']-data['deduction']
    return dict(result)


def prepare_month(month):
    raise ValueError('旧版直接生成结算明细已停用，请手动生成固定版本报表')


def lock_month(month, actor):
    raise ValueError('旧版直接锁月已停用，请按报表版本在收付款完成后确认结算')
