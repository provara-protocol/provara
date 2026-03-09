-- Provara Hosted Vault MVP - Initial Schema
-- Migration: 001_initial_schema
-- Date: 2026-03-07

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- VAULTS TABLE
-- ============================================================================

CREATE TABLE vaults (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    owner_id TEXT NOT NULL,  -- Clerk user ID
    name TEXT NOT NULL,
    description TEXT,
    tier TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'active',
    public_key TEXT NOT NULL,  -- PEM-encoded Ed25519 public key
    key_id TEXT NOT NULL UNIQUE,  -- Key fingerprint (bp1_...)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_event_seq INTEGER DEFAULT 0,
    merkle_root TEXT,
    
    CONSTRAINT valid_tier CHECK (tier IN ('free', 'developer', 'team', 'enterprise')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'suspended', 'deleted'))
);

CREATE INDEX idx_vaults_owner ON vaults(owner_id);
CREATE INDEX idx_vaults_status ON vaults(status);
CREATE INDEX idx_vaults_tier ON vaults(tier);
CREATE INDEX idx_vaults_created ON vaults(created_at);

-- Row Level Security for vaults
ALTER TABLE vaults ENABLE ROW LEVEL SECURITY;

-- Users can only see their own vaults
CREATE POLICY vaults_owner_select ON vaults
    FOR SELECT
    USING (owner_id = current_setting('app.settings.clerk_user_id', TRUE));

-- Users can insert their own vaults
CREATE POLICY vaults_owner_insert ON vaults
    FOR INSERT
    WITH CHECK (owner_id = current_setting('app.settings.clerk_user_id', TRUE));

-- Users can update their own vaults
CREATE POLICY vaults_owner_update ON vaults
    FOR UPDATE
    USING (owner_id = current_setting('app.settings.clerk_user_id', TRUE));

-- ============================================================================
-- EVENTS TABLE
-- ============================================================================

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    seq INTEGER NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_data JSONB NOT NULL,
    hash TEXT NOT NULL,
    prev_hash TEXT,
    signature TEXT NOT NULL,
    actor_key_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(vault_id, seq),
    UNIQUE(vault_id, event_id)
);

CREATE INDEX idx_events_vault_seq ON events(vault_id, seq);
CREATE INDEX idx_events_vault_type ON events(vault_id, event_type);
CREATE INDEX idx_events_timestamp ON events(timestamp);
CREATE INDEX idx_events_data ON events USING GIN (event_data);

-- Row Level Security for events
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- Users can only see events from their own vaults
CREATE POLICY events_owner_select ON events
    FOR SELECT
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- Users can only insert events into their own vaults
CREATE POLICY events_owner_insert ON events
    FOR INSERT
    WITH CHECK (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- ============================================================================
-- API KEYS TABLE
-- ============================================================================

CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL UNIQUE,  -- SHA-256 hash of the key
    name TEXT,
    permissions TEXT[] DEFAULT '{write}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    
    CONSTRAINT valid_permissions CHECK (
        permissions <@ ARRAY['read', 'write', 'admin']
    )
);

CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_vault ON api_keys(vault_id);

-- Row Level Security for api_keys
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY api_keys_owner_select ON api_keys
    FOR SELECT
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

CREATE POLICY api_keys_owner_insert ON api_keys
    FOR INSERT
    WITH CHECK (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

CREATE POLICY api_keys_owner_delete ON api_keys
    FOR DELETE
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- ============================================================================
-- USAGE TRACKING TABLE
-- ============================================================================

CREATE TABLE usage_tracking (
    vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    month DATE NOT NULL,  -- First day of month (e.g., 2026-03-01)
    event_count INTEGER DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (vault_id, month),
    CONSTRAINT positive_event_count CHECK (event_count >= 0)
);

CREATE INDEX idx_usage_vault_month ON usage_tracking(vault_id, month);

-- Row Level Security for usage_tracking
ALTER TABLE usage_tracking ENABLE ROW LEVEL SECURITY;

CREATE POLICY usage_owner_select ON usage_tracking
    FOR SELECT
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- ============================================================================
-- STRIPE CUSTOMERS TABLE
-- ============================================================================

CREATE TABLE stripe_customers (
    user_id TEXT PRIMARY KEY,  -- Clerk user ID
    stripe_customer_id TEXT NOT NULL UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    tier TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_stripe_customers_stripe_id ON stripe_customers(stripe_customer_id);

-- Row Level Security for stripe_customers
ALTER TABLE stripe_customers ENABLE ROW LEVEL SECURITY;

CREATE POLICY stripe_customers_owner_select ON stripe_customers
    FOR SELECT
    USING (user_id = current_setting('app.settings.clerk_user_id', TRUE));

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Function to get tier limits
CREATE OR REPLACE FUNCTION get_tier_limits(tier_name TEXT)
RETURNS TABLE (
    max_vaults INTEGER,
    max_events_per_month INTEGER,
    max_storage_bytes BIGINT,
    max_events_per_minute INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE tier_name
            WHEN 'free' THEN 1
            WHEN 'developer' THEN 5
            WHEN 'team' THEN -1  -- unlimited
            WHEN 'enterprise' THEN -1
            ELSE 1
        END AS max_vaults,
        CASE tier_name
            WHEN 'free' THEN 100
            WHEN 'developer' THEN 10000
            WHEN 'team' THEN 100000
            WHEN 'enterprise' THEN -1
            ELSE 100
        END AS max_events_per_month,
        CASE tier_name
            WHEN 'free' THEN 10485760  -- 10MB
            WHEN 'developer' THEN 1073741824  -- 1GB
            WHEN 'team' THEN 10737418240  -- 10GB
            WHEN 'enterprise' THEN -1
            ELSE 10485760
        END AS max_storage_bytes,
        CASE tier_name
            WHEN 'free' THEN 10
            WHEN 'developer' THEN 100
            WHEN 'team' THEN 1000
            WHEN 'enterprise' THEN 5000
            ELSE 10
        END AS max_events_per_minute;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Update updated_at on vaults
CREATE TRIGGER update_vaults_updated_at
    BEFORE UPDATE ON vaults
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Update updated_at on stripe_customers
CREATE TRIGGER update_stripe_customers_updated_at
    BEFORE UPDATE ON stripe_customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SEED DATA (Development Only)
-- ============================================================================

-- This section can be removed in production
-- Uncomment for local development testing:

-- INSERT INTO vaults (owner_id, name, description, tier, public_key, key_id)
-- VALUES (
--     'user_test_123',
--     'Test Vault',
--     'Development testing vault',
--     'free',
--     '-----BEGIN PUBLIC KEY-----\nMFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE...\n-----END PUBLIC KEY-----',
--     'bp1_test123'
-- );

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE vaults IS 'Provara vaults with Ed25519 keypairs';
COMMENT ON TABLE events IS 'Tamper-evident event log with hash chain';
COMMENT ON TABLE api_keys IS 'API keys for programmatic vault access';
COMMENT ON TABLE usage_tracking IS 'Monthly usage tracking for billing tiers';
COMMENT ON TABLE stripe_customers IS 'Stripe customer and subscription linkage';

-- End of migration
