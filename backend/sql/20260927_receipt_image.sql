-- Additive migration. Check information_schema.COLUMNS first if running manually.
-- No opening initialization or data rewrite is required.
ALTER TABLE settlement_card_remittances ADD COLUMN proof_image VARCHAR(512) NULL;
