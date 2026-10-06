-- Additive migration only. Existing financial entries must never be reset implicitly.
CREATE TABLE IF NOT EXISTS settlement_reports (
 id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
 month VARCHAR(7) NOT NULL,
 version INT NOT NULL,
 request_key VARCHAR(64) NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'draft',
 digest VARCHAR(64) NOT NULL,
 payload JSON NOT NULL,
 created_at DATETIME NOT NULL,
 created_by INT NOT NULL,
 confirmed_at DATETIME NULL,
 confirmed_by INT NULL,
 confirmation JSON NULL,
 UNIQUE KEY report_month_version (month, version),
 UNIQUE KEY report_request_key (request_key),
 KEY report_month (month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
