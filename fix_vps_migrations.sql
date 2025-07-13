-- Fix VPS migration state
-- Run this on the VPS PostgreSQL database to mark migrations as applied

-- Insert the migrations that are failing because tables already exist
INSERT INTO alembic_version (version_num) VALUES ('lead_explorer_001')
ON CONFLICT (version_num) DO NOTHING;

INSERT INTO alembic_version (version_num) VALUES ('governance_tables_001')
ON CONFLICT (version_num) DO NOTHING;

-- Verify the current state
SELECT * FROM alembic_version ORDER BY version_num;