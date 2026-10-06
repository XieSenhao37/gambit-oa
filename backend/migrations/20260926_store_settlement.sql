-- Additive schema; safe to rerun. Enable after opening initialization.
-- Also run 20260926_month_card_terms.sql before deploying fixed-30-day issuance.

CREATE TABLE IF NOT EXISTS settlement_allocations (
	id INTEGER NOT NULL AUTO_INCREMENT,
	created_at DATETIME NOT NULL,
	biz_key VARCHAR(220) NOT NULL,
	batch_id INTEGER NOT NULL,
	kind VARCHAR(16) NOT NULL,
	open_id VARCHAR(60) NOT NULL,
	reference VARCHAR(180) NOT NULL,
	expense_key VARCHAR(100) NOT NULL,
	store_id INTEGER NOT NULL,
	amount INTEGER NOT NULL,
	principal INTEGER NOT NULL,
	state VARCHAR(16) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (biz_key),
  KEY ix_settlement_allocations_batch_id (batch_id),
  KEY ix_settlement_allocations_expense_key (expense_key),
  KEY ix_settlement_allocations_reference (reference)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_batches (
	id INTEGER NOT NULL AUTO_INCREMENT,
	created_at DATETIME NOT NULL,
	kind VARCHAR(16) NOT NULL,
	open_id VARCHAR(60) NOT NULL,
	source_key VARCHAR(180) NOT NULL,
	source_store_id INTEGER NOT NULL,
	responsible_store_id INTEGER NOT NULL,
	face_total INTEGER NOT NULL,
	principal_total INTEGER NOT NULL,
	remaining INTEGER NOT NULL,
	principal_remaining INTEGER NOT NULL,
	frozen INTEGER NOT NULL,
	legacy BOOL NOT NULL,
	PRIMARY KEY (id),
	CHECK (remaining >= 0 AND frozen >= 0 AND frozen <= remaining AND principal_remaining >= 0 AND principal_remaining <= remaining),
	UNIQUE (source_key),
  KEY ix_settlement_batches_open_id (open_id),
  KEY ix_settlement_batches_kind (kind)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_card_periods (
	id INTEGER NOT NULL AUTO_INCREMENT,
	pool_id INTEGER NOT NULL,
	month VARCHAR(7) NOT NULL,
	starts_at DATETIME NOT NULL,
	ends_at DATETIME NOT NULL,
	amount INTEGER NOT NULL,
	allocated_amount INTEGER NOT NULL,
	carry_amount INTEGER NOT NULL,
	shares JSON NOT NULL,
	carry_shares JSON NOT NULL,
	status VARCHAR(16) NOT NULL,
	settled_at DATETIME NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT card_period_month UNIQUE (pool_id, month),
  KEY ix_settlement_card_periods_pool_id (pool_id),
  KEY ix_settlement_card_periods_month (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_card_pools (
	id INTEGER NOT NULL AUTO_INCREMENT,
	source_key VARCHAR(100) NOT NULL,
	order_id INTEGER NOT NULL,
	open_id VARCHAR(60) NOT NULL,
	starts_at DATETIME NOT NULL,
	ends_at DATETIME NOT NULL,
	amount INTEGER NOT NULL,
	payer_id INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	legacy BOOL NOT NULL,
	closed_at DATETIME,
	PRIMARY KEY (id),
	UNIQUE (source_key),
  KEY ix_settlement_card_pools_order_id (order_id),
  KEY ix_settlement_card_pools_open_id (open_id),
  KEY ix_settlement_card_pools_ends_at (ends_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_card_remittances (
	id INTEGER NOT NULL AUTO_INCREMENT,
	order_id INTEGER NOT NULL,
	voucher_key VARCHAR(64) NOT NULL,
	channel VARCHAR(60) NOT NULL,
	external_no VARCHAR(128) NOT NULL,
	store_id INTEGER NOT NULL,
	amount INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	status VARCHAR(16) NOT NULL,
	payment_ref VARCHAR(200) NOT NULL,
	submitted_at DATETIME,
	submitted_by INTEGER,
	confirmed_at DATETIME,
	confirmed_by INTEGER,
	PRIMARY KEY (id),
	UNIQUE (order_id),
	UNIQUE (voucher_key),
  KEY ix_settlement_card_remittances_store_id (store_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_card_usages (
	id INTEGER NOT NULL AUTO_INCREMENT,
	pool_id INTEGER NOT NULL,
	play_order_id INTEGER NOT NULL,
	store_id INTEGER NOT NULL,
	started_at DATETIME NOT NULL,
	ended_at DATETIME NOT NULL,
	seconds INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	note VARCHAR(500) NOT NULL,
	PRIMARY KEY (id),
	CONSTRAINT usage_pool UNIQUE (pool_id, play_order_id),
  KEY ix_settlement_card_usages_pool_id (pool_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_controls (
	id INTEGER NOT NULL AUTO_INCREMENT,
	cutoff DATETIME NOT NULL,
	initialized_at DATETIME,
	legacy_wallet_payer INTEGER NOT NULL,
	legacy_card_policy VARCHAR(32) NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_cost_rules (
	`key` VARCHAR(100) NOT NULL,
	amount INTEGER NOT NULL,
	note VARCHAR(500) NOT NULL,
	updated_at DATETIME NOT NULL,
	PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_entries (
	id INTEGER NOT NULL AUTO_INCREMENT,
	created_at DATETIME NOT NULL,
	event_at DATETIME NOT NULL,
	month VARCHAR(7) NOT NULL,
	biz_key VARCHAR(240) NOT NULL,
	kind VARCHAR(32) NOT NULL,
	reference VARCHAR(180) NOT NULL,
	payer_id INTEGER NOT NULL,
	receiver_id INTEGER NOT NULL,
	amount INTEGER NOT NULL,
	face_amount INTEGER NOT NULL,
	detail TEXT NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (biz_key),
  KEY ix_settlement_entries_month (month),
  KEY ix_settlement_entries_receiver_id (receiver_id),
  KEY ix_settlement_entries_payer_id (payer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_expenses (
	id INTEGER NOT NULL AUTO_INCREMENT,
	expense_key VARCHAR(100) NOT NULL,
	kind VARCHAR(16) NOT NULL,
	source_id INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	completed_at DATETIME,
	amount INTEGER,
	provider_id INTEGER NOT NULL,
	status VARCHAR(16) NOT NULL,
	note VARCHAR(500) NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (expense_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_periods (
	month VARCHAR(7) NOT NULL,
	status VARCHAR(16) NOT NULL,
	locked_at DATETIME,
	locked_by INTEGER,
	PRIMARY KEY (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS settlement_statements (
	id INTEGER NOT NULL AUTO_INCREMENT,
	month VARCHAR(7) NOT NULL,
	store_id INTEGER NOT NULL,
	amount INTEGER NOT NULL,
	paid_at DATETIME,
	payment_ref VARCHAR(200) NOT NULL,
	paid_by INTEGER,
	PRIMARY KEY (id),
	CONSTRAINT statement_store UNIQUE (month, store_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
