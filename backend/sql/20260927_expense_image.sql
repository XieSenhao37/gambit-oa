-- Apply once; use migrate_receipt_test.py for idempotent test migration.
ALTER TABLE settlement_expenses ADD COLUMN proof_image VARCHAR(512) NULL;
