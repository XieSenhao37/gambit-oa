-- Existing orders keep 0 (legacy calendar term); new orders snapshot N * 30 days.
SET @card_terms_sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE()
         AND table_name='month_card_orders' AND column_name='duration_days'),
  'SELECT 1',
  'ALTER TABLE month_card_orders ADD COLUMN duration_days INT NOT NULL DEFAULT 0'
);
PREPARE card_terms_statement FROM @card_terms_sql;
EXECUTE card_terms_statement;
DEALLOCATE PREPARE card_terms_statement;

SET @card_request_sql = IF(
  EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE()
         AND table_name='month_card_orders' AND column_name='request_key'),
  'SELECT 1',
  'ALTER TABLE month_card_orders ADD COLUMN request_key VARCHAR(64) NULL, ADD UNIQUE KEY uq_month_card_request_key (request_key)'
);
PREPARE card_request_statement FROM @card_request_sql;
EXECUTE card_request_statement;
DEALLOCATE PREPARE card_request_statement;
