from .clock import now
from app import db
from datetime import datetime

class SettlementControl(db.Model):
    __tablename__ = 'settlement_controls'
    id = db.Column(db.Integer, primary_key=True)
    cutoff = db.Column(db.DateTime, nullable=False)
    initialized_at = db.Column(db.DateTime)
    legacy_wallet_payer = db.Column(db.Integer, nullable=False)
    legacy_card_policy = db.Column(db.String(32), nullable=False)

class SettlementBatch(db.Model):
    __tablename__ = 'settlement_batches'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    kind = db.Column(db.String(16), nullable=False, index=True)
    open_id = db.Column(db.String(60), nullable=False, index=True)
    source_key = db.Column(db.String(180), unique=True, nullable=False)
    source_store_id = db.Column(db.Integer, default=0, nullable=False)
    responsible_store_id = db.Column(db.Integer, default=0, nullable=False)
    face_total = db.Column(db.Integer, nullable=False)
    principal_total = db.Column(db.Integer, default=0, nullable=False)
    remaining = db.Column(db.Integer, nullable=False)
    principal_remaining = db.Column(db.Integer, default=0, nullable=False)
    frozen = db.Column(db.Integer, default=0, nullable=False)
    legacy = db.Column(db.Boolean, default=False, nullable=False)
    __table_args__ = (db.CheckConstraint('remaining >= 0 AND frozen >= 0 AND frozen <= remaining AND principal_remaining >= 0 AND principal_remaining <= remaining'),)

class SettlementAllocation(db.Model):
    __tablename__ = 'settlement_allocations'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    biz_key = db.Column(db.String(220), unique=True, nullable=False)
    batch_id = db.Column(db.Integer, nullable=False, index=True)
    kind = db.Column(db.String(16), nullable=False)
    open_id = db.Column(db.String(60), nullable=False)
    reference = db.Column(db.String(180), nullable=False, index=True)
    expense_key = db.Column(db.String(100), default='', nullable=False, index=True)
    store_id = db.Column(db.Integer, default=0, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    principal = db.Column(db.Integer, default=0, nullable=False)
    state = db.Column(db.String(16), nullable=False)

class SettlementEntry(db.Model):
    __tablename__ = 'settlement_entries'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    event_at = db.Column(db.DateTime, nullable=False)
    month = db.Column(db.String(7), nullable=False, index=True)
    biz_key = db.Column(db.String(240), unique=True, nullable=False)
    kind = db.Column(db.String(32), nullable=False)
    reference = db.Column(db.String(180), nullable=False)
    payer_id = db.Column(db.Integer, nullable=False, index=True)
    receiver_id = db.Column(db.Integer, nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    face_amount = db.Column(db.Integer, default=0, nullable=False)
    detail = db.Column(db.Text, nullable=False)

class SettlementPeriod(db.Model):
    __tablename__ = 'settlement_periods'
    month = db.Column(db.String(7), primary_key=True)
    status = db.Column(db.String(16), default='draft', nullable=False)
    locked_at = db.Column(db.DateTime)
    locked_by = db.Column(db.Integer)

class SettlementStatement(db.Model):
    __tablename__ = 'settlement_statements'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    paid_at = db.Column(db.DateTime)
    payment_ref = db.Column(db.String(200), default='', nullable=False)
    paid_by = db.Column(db.Integer)
    __table_args__ = (db.UniqueConstraint('month','store_id', name='statement_store'),)

class SettlementCardPool(db.Model):
    __tablename__ = 'settlement_card_pools'
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(100), nullable=False, unique=True)
    order_id = db.Column(db.Integer, nullable=False, index=True)
    open_id = db.Column(db.String(60), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    payer_id = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(16), default='open', nullable=False)
    legacy = db.Column(db.Boolean, default=False, nullable=False)
    closed_at = db.Column(db.DateTime)

class SettlementCardUsage(db.Model):
    __tablename__ = 'settlement_card_usages'
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.Integer, nullable=False, index=True)
    play_order_id = db.Column(db.Integer, nullable=False)
    store_id = db.Column(db.Integer, nullable=False)
    started_at = db.Column(db.DateTime, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=False)
    seconds = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), default='valid', nullable=False)
    note = db.Column(db.String(500), default='', nullable=False)
    __table_args__ = (db.UniqueConstraint('pool_id','play_order_id', name='usage_pool'),)

class SettlementExpense(db.Model):
    __tablename__ = 'settlement_expenses'
    id = db.Column(db.Integer, primary_key=True)
    expense_key = db.Column(db.String(100), unique=True, nullable=False)
    kind = db.Column(db.String(16), nullable=False)
    source_id = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    completed_at = db.Column(db.DateTime)
    amount = db.Column(db.Integer)
    provider_id = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    note = db.Column(db.String(500), default='', nullable=False)
    proof_image = db.Column(db.String(512), nullable=True)

class SettlementCostRule(db.Model):
    __tablename__ = 'settlement_cost_rules'
    key = db.Column(db.String(100), primary_key=True)
    amount = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(500), default='', nullable=False)
    updated_at = db.Column(db.DateTime, default=now, nullable=False)

class SettlementCardPeriod(db.Model):
    __tablename__ = 'settlement_card_periods'
    id = db.Column(db.Integer, primary_key=True)
    pool_id = db.Column(db.Integer, nullable=False, index=True)
    month = db.Column(db.String(7), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False)
    ends_at = db.Column(db.DateTime, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    allocated_amount = db.Column(db.Integer, nullable=False, default=0)
    carry_amount = db.Column(db.Integer, nullable=False, default=0)
    shares = db.Column(db.JSON, nullable=False, default=list)
    carry_shares = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(16), nullable=False)
    settled_at = db.Column(db.DateTime, nullable=False, default=now)
    __table_args__ = (db.UniqueConstraint('pool_id','month',name='card_period_month'),)

class SettlementCardRemittance(db.Model):
    __tablename__ = 'settlement_card_remittances'
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, nullable=False, unique=True)
    voucher_key = db.Column(db.String(64), nullable=False, unique=True)
    channel = db.Column(db.String(60), nullable=False)
    external_no = db.Column(db.String(128), nullable=False)
    store_id = db.Column(db.Integer, nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    status = db.Column(db.String(16), nullable=False, default='pending')
    payment_ref = db.Column(db.String(200), nullable=False, default='')
    proof_image = db.Column(db.String(512), nullable=True)
    submitted_at = db.Column(db.DateTime)
    submitted_by = db.Column(db.Integer)
    confirmed_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.Integer)

class SettlementReport(db.Model):
    """Immutable calculation snapshot. Only confirmation changes financial state."""
    __tablename__ = 'settlement_reports'
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False, index=True)
    version = db.Column(db.Integer, nullable=False)
    request_key = db.Column(db.String(64), nullable=False, unique=True)
    status = db.Column(db.String(16), nullable=False, default='draft')
    digest = db.Column(db.String(64), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    created_by = db.Column(db.Integer, nullable=False)
    confirmed_at = db.Column(db.DateTime)
    confirmed_by = db.Column(db.Integer)
    confirmation = db.Column(db.JSON)
    __table_args__ = (db.UniqueConstraint('month', 'version', name='report_month_version'),)
