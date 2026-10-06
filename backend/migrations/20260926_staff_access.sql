-- Additive schema only; creates no accounts or grants. Explicit target DB required.
CREATE TABLE IF NOT EXISTS staff_accounts (
	user_id INTEGER NOT NULL,
	phone_cipher VARCHAR(100) NOT NULL,
	enabled BOOL NOT NULL,
	headquarters BOOL NOT NULL,
	phone_verified_at DATETIME,
	version INTEGER NOT NULL,
	updated_at DATETIME,
	PRIMARY KEY (user_id),
	UNIQUE (phone_cipher)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS staff_store_grants (
	user_id INTEGER NOT NULL,
	store_id INTEGER NOT NULL,
	`role` VARCHAR(20) NOT NULL,
	PRIMARY KEY (user_id, store_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS staff_role_pages (
	`role` VARCHAR(20) NOT NULL,
	page_id VARCHAR(80) NOT NULL,
	allowed BOOL NOT NULL,
	PRIMARY KEY (`role`, page_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS oa_login_challenges (
	id VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	account_version INTEGER NOT NULL,
	code_digest VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	attempts INTEGER NOT NULL,
	consumed BOOL NOT NULL,
	sent BOOL NOT NULL,
	PRIMARY KEY (id),
 INDEX ix_oa_login_challenges_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS oa_login_throttles (
	`key` VARCHAR(64) NOT NULL,
	window_start DATETIME NOT NULL,
	count INTEGER NOT NULL,
	PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS oa_sessions (
	token_digest VARCHAR(64) NOT NULL,
	user_id INTEGER NOT NULL,
	account_version INTEGER NOT NULL,
	created_at DATETIME NOT NULL,
	expires_at DATETIME NOT NULL,
	revoked BOOL NOT NULL,
	PRIMARY KEY (token_digest),
 INDEX ix_oa_sessions_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS oa_access_audits (
	id INTEGER NOT NULL AUTO_INCREMENT,
	actor_id INTEGER NOT NULL,
	store_id INTEGER,
	action VARCHAR(160) NOT NULL,
	target VARCHAR(255),
	detail JSON,
	created_at DATETIME NOT NULL,
	PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
