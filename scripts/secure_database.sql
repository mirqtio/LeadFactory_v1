-- Revoke all permissions and grant only necessary ones
REVOKE ALL ON SCHEMA public FROM leadfactory;
GRANT USAGE ON SCHEMA public TO leadfactory;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO leadfactory;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO leadfactory;

-- Enable row level security on sensitive tables
ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails ENABLE ROW LEVEL SECURITY;
ALTER TABLE purchases ENABLE ROW LEVEL SECURITY;

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    action VARCHAR(100),
    table_name VARCHAR(100),
    record_id VARCHAR(255),
    old_values JSONB,
    new_values JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
