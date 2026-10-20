"""Legacy inventory edits share the same parent-row lock as Go stock allocation."""
from sqlalchemy import inspect, text
from app import db

def require_unallocated_inventory(store_id, game_id, target):
    # Old deployments may not have migrated the new module yet. No commerce pool
    # can exist in that case; once tables exist, errors fail closed.
    if not inspect(db.engine).has_table('game_service_stocks'):
        return
    # Authentication may already have opened an older repeatable-read snapshot.
    # A locking read sees the latest committed pools after acquiring the parent
    # inventory lock shared with Go; a plain SUM could miss a concurrent allocation.
    lock = ' FOR UPDATE' if db.engine.dialect.name == 'mysql' else ''
    if inspect(db.engine).has_table('game_service_inventories'):
        quota = db.session.execute(text('SELECT quantity FROM game_service_inventories WHERE store_id=:store AND board_game_id=:game' + lock), {'store': store_id, 'game': game_id}).scalar()
        if quota is not None:
            if target < quota:
                raise ValueError('总数量不能低于对外租售额度，请在桌游库存一并调整')
            # Old quantity-only clients must invalidate the integrated editor's version.
            current = db.session.execute(text('SELECT count FROM board_game_store_inventories WHERE store_id=:store AND board_game_id=:game' + lock), {'store': store_id, 'game': game_id}).scalar()
            if current is not None and current != target:
                db.session.execute(text('UPDATE game_service_inventories SET version=version+1 WHERE store_id=:store AND board_game_id=:game'), {'store': store_id, 'game': game_id})
            return
    quantities = db.session.execute(text('SELECT quantity FROM game_service_stocks WHERE store_id=:store AND board_game_id=:game' + lock), {'store':store_id, 'game':game_id}).scalars().all()
    allocated = sum(quantities)
    if target < int(allocated or 0):
        raise ValueError('数量不能低于已分配的租售库存，请先在桌游租售管理调整库存池')
