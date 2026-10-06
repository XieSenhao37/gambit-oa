"""Defense in depth for ORM business queries. Raw SQL must explicitly apply the same scope."""
from flask import g, has_request_context, abort
from sqlalchemy import event, select
from sqlalchemy.orm import Session, with_loader_criteria
from app import models as m
SCOPED = (m.PlayOrder, m.PayOrder, m.Catering, m.Table, m.Dish, m.DishStoreItem, m.BoardGameStoreInventory, m.MonthCardOrder, m.GroupActivity, m.PointWithdrawRecord)

@event.listens_for(Session, 'do_orm_execute')
def scope_queries(state):
    if not has_request_context() or not getattr(g, 'scope_store', None) or (not state.is_orm_statement) or state.execution_options.get('global_reference_check'):
        return
    sid = g.scope_store
    for model in SCOPED:
        state.statement = state.statement.options(with_loader_criteria(model, model.store_id == sid, include_aliases=True))
    state.statement = state.statement.options(with_loader_criteria(m.PointRedeemOrder, m.PointRedeemOrder.pickup_store_id == sid, include_aliases=True))
    state.statement = state.statement.options(with_loader_criteria(m.RefundRequest, m.RefundRequest.pay_order_id.in_(select(m.PayOrder.id).where(m.PayOrder.store_id == sid)), include_aliases=True))

@event.listens_for(Session, 'before_flush')
def scope_writes(session, ctx, instances):
    if not has_request_context() or not getattr(g, 'scope_store', None):
        return
    for obj in session.new.union(session.dirty).union(session.deleted):
        if isinstance(obj, SCOPED) and obj.store_id != g.scope_store:
            abort(403, description='目标记录不属于当前门店')
        if isinstance(obj, m.PointRedeemOrder) and obj.pickup_store_id != g.scope_store:
            abort(403)
