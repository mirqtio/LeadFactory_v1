-- Create all necessary tables for LeadFactory production

-- Create alembic_version table
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- D1 Targeting tables
CREATE TABLE IF NOT EXISTS target_universes (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    verticals JSON NOT NULL,
    geography_config JSON NOT NULL,
    qualification_rules JSON,
    estimated_size INTEGER,
    actual_size INTEGER NOT NULL DEFAULT 0,
    qualified_count INTEGER NOT NULL DEFAULT 0,
    last_refresh TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS campaigns (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    target_universe_id VARCHAR(36) NOT NULL REFERENCES target_universes(id),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    campaign_type VARCHAR(50) NOT NULL DEFAULT 'lead_generation',
    scheduled_start TIMESTAMP,
    scheduled_end TIMESTAMP,
    actual_start TIMESTAMP,
    actual_end TIMESTAMP,
    batch_settings JSON,
    total_targets INTEGER NOT NULL DEFAULT 0,
    contacted_targets INTEGER NOT NULL DEFAULT 0,
    responded_targets INTEGER NOT NULL DEFAULT 0,
    converted_targets INTEGER NOT NULL DEFAULT 0,
    excluded_targets INTEGER NOT NULL DEFAULT 0,
    total_cost FLOAT NOT NULL DEFAULT 0.0,
    cost_per_contact FLOAT,
    cost_per_conversion FLOAT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(255)
);

-- D2 Sourcing tables (already exists)
-- sourced_businesses already created

-- D3 Assessment tables
CREATE TABLE IF NOT EXISTS assessments (
    id VARCHAR(36) PRIMARY KEY,
    business_id VARCHAR(36) NOT NULL,
    assessment_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    assessment_data JSON,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- D7 Storefront tables
CREATE TABLE IF NOT EXISTS products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price INTEGER NOT NULL,
    currency VARCHAR(3) NOT NULL DEFAULT 'usd',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Insert default product
INSERT INTO products (id, name, description, price, currency) 
VALUES ('audit_report', 'Website Audit Report', 'Comprehensive website audit and optimization report', 19900, 'usd')
ON CONFLICT (id) DO NOTHING;

-- D10 Analytics tables
CREATE TABLE IF NOT EXISTS analytics_events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    event_data JSON,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_schedule ON campaigns(scheduled_start, scheduled_end);
CREATE INDEX IF NOT EXISTS idx_target_universes_active ON target_universes(is_active);
CREATE INDEX IF NOT EXISTS idx_assessments_business ON assessments(business_id);
CREATE INDEX IF NOT EXISTS idx_assessments_status ON assessments(status);