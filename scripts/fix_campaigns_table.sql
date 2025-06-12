-- Add missing columns to campaigns table to match d1_targeting.models.Campaign

-- Add description column
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS description TEXT;

-- Add target_universe_id column
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS target_universe_id VARCHAR(36);

-- Add campaign_type column
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS campaign_type VARCHAR(50) DEFAULT 'lead_generation';

-- Add scheduling columns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS scheduled_start TIMESTAMP;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS scheduled_end TIMESTAMP;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS actual_start TIMESTAMP;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS actual_end TIMESTAMP;

-- Add batch_settings column
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS batch_settings JSON;

-- Add metrics columns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_targets INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS contacted_targets INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS responded_targets INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS converted_targets INTEGER DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS excluded_targets INTEGER DEFAULT 0;

-- Add cost tracking columns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS total_cost FLOAT DEFAULT 0.0;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cost_per_contact FLOAT;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cost_per_conversion FLOAT;

-- Add metadata columns
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW();
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS created_by VARCHAR(255);

-- Create index on status
CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);