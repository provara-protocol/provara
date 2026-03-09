-- Provara Hosted Vault - Vault Keys Table
-- Migration: 002_vault_keys
-- Date: 2026-03-07

-- ============================================================================
-- VAULT KEYS TABLE (Encrypted private keys)
-- ============================================================================

CREATE TABLE vault_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vault_id UUID NOT NULL UNIQUE REFERENCES vaults(id) ON DELETE CASCADE,
    encrypted_private_key TEXT NOT NULL,  -- PEM-encoded, encrypted with KMS
    key_id TEXT NOT NULL,  -- Key fingerprint (bp1_...)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT unique_key_id UNIQUE (key_id)
);

CREATE INDEX idx_vault_keys_vault ON vault_keys(vault_id);
CREATE INDEX idx_vault_keys_key_id ON vault_keys(key_id);

-- Row Level Security
ALTER TABLE vault_keys ENABLE ROW LEVEL SECURITY;

-- Users can only see keys for their own vaults
CREATE POLICY vault_keys_owner_select ON vault_keys
    FOR SELECT
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- Users can only insert keys for their own vaults
CREATE POLICY vault_keys_owner_insert ON vault_keys
    FOR INSERT
    WITH CHECK (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

-- Users can only delete keys for their own vaults
CREATE POLICY vault_keys_owner_delete ON vault_keys
    FOR DELETE
    USING (
        vault_id IN (
            SELECT id FROM vaults 
            WHERE owner_id = current_setting('app.settings.clerk_user_id', TRUE)
        )
    );

COMMENT ON TABLE vault_keys IS 'Encrypted Ed25519 private keys for Provara vaults';
COMMENT ON COLUMN vault_keys.encrypted_private_key IS 'PEM-encoded private key, encrypted at rest via Supabase Secrets or KMS';

-- End of migration
