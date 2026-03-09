# Provara Hosted Vault MVP — Technical Specification

**Version:** 0.1.0  
**Status:** In Development  
**Target Deploy:** March 2026  
**Owner:** Hunt Information Systems LLC

---

## Executive Summary

**Thesis:** Developers want Provara's cryptographic guarantees without managing keys, vaults, or infrastructure. The Hosted Vault MVP delivers tamper-evident event logging as a service — $0-99/mo tiers, 5-minute integration, zero ops burden.

**Key Insight:** The MCP server already exists. PSMC proves the protocol supports application layers. The hosted vault is simply: *PSMC + managed infrastructure + billing*.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│  (AI Agents, CLI tools, Web apps, Mobile apps)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTPS (JWT-authenticated)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    API Layer (Vercel Edge Functions)             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ POST /vaults │  │ GET /vaults  │  │ POST /events │          │
│  │ /:id         │  │ /:id/verify  │  │ /:id         │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  Auth: Clerk JWT verification (middleware on every request)     │
│  Rate limiting: Vercel KV / Supabase rate_limit table           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Internal (VPC)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Storage Layer (Supabase)                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ PostgreSQL (Metadata & Index)                            │  │
│  │ - vaults table: id, owner_id, created_at, tier, status   │  │
│  │ - events table: id, vault_id, event_data, hash, seq      │  │
│  │ - api_keys table: key_hash, vault_id, permissions        │  │
│  │ - usage_tracking: vault_id, month, event_count           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Storage Buckets (Raw Vault Files)                        │  │
│  │ - vaults/:vault_id/identity/genesis.json                 │  │
│  │ - vaults/:vault_id/events/events.ndjson                  │  │
│  │ - vaults/:vault_id/manifest.json                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Secrets (Vault Keys)                                     │  │
│  │ - Ed25519 keypairs per vault (encrypted at rest)         │  │
│  │ - Key ID → encrypted PEM mapping                         │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    External Services                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Clerk        │  │ Stripe       │  │ Sentry       │          │
│  │ (Auth/JWT)   │  │ (Billing)    │  │ (Monitoring) │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Specification

### Authentication

All requests require `Authorization: Bearer <JWT>` header.

Clerk JWT claims used:
- `sub` → User ID (maps to `vaults.owner_id`)
- `exp` → Expiration (auto-rejected if expired)
- `iat` → Issued-at (audit trail)

### Endpoints

#### `POST /api/v1/vaults` — Create Vault

**Request:**
```json
{
  "name": "my-agent-memory",
  "description": "AI agent cognitive audit trail"
}
```

**Response (201 Created):**
```json
{
  "vault_id": "vlt_abc123...",
  "name": "my-agent-memory",
  "created_at": "2026-03-07T14:30:00Z",
  "tier": "free",
  "api_key": "pk_live_xyz789...",
  "events_url": "/api/v1/vaults/vlt_abc123.../events"
}
```

**Server-side actions:**
1. Generate Ed25519 keypair (using `cryptography` library)
2. Store encrypted private key in Supabase Secrets
3. Write `genesis.json` to Storage bucket
4. Insert row in `vaults` table
5. Return public key + vault ID to client

---

#### `POST /api/v1/vaults/:id/events` — Append Event

**Request:**
```json
{
  "event_type": "OBSERVATION",
  "data": {
    "subject": "model_output",
    "predicate": "generated",
    "value": {"response": "...", "tokens": 450},
    "confidence": 0.92
  },
  "metadata": {
    "source": "claude-desktop",
    "session_id": "sess_..."
  }
}
```

**Constraints:**
- Max payload size: 10KB
- Rate limit: 100 events/min (free), 1000/min (paid)
- `event_type` must be valid Provara type

**Response (201 Created):**
```json
{
  "event_id": "evt_def456...",
  "hash": "sha256:abc123...",
  "seq": 42,
  "timestamp": "2026-03-07T14:35:22Z",
  "state_hash": "sha256:xyz789..."
}
```

**Server-side actions:**
1. Verify JWT → extract `sub` → check `vaults.owner_id` matches
2. Check usage quota (Supabase `usage_tracking` table)
3. Load vault's private key from Secrets
4. Build Provara-compatible event (RFC 8785 canonical JSON)
5. Sign with Ed25519, compute SHA-256 hash
6. Append to `events` table + update `events.ndjson` in Storage
7. Increment usage counter
8. Return event receipt

---

#### `GET /api/v1/vaults/:id/events` — Query Events

**Query params:**
- `last` (int): Return last N events (default: 50, max: 1000)
- `type` (string): Filter by event type
- `since` (ISO8601): Filter by timestamp
- `format` (string): `json` (default) or `ndjson`

**Response (200 OK):**
```json
{
  "vault_id": "vlt_abc123...",
  "count": 50,
  "events": [
    {
      "event_id": "evt_...",
      "type": "OBSERVATION",
      "seq": 42,
      "timestamp": "2026-03-07T14:35:22Z",
      "data": {...},
      "hash": "sha256:...",
      "prev_hash": "sha256:..."
    }
  ],
  "merkle_root": "sha256:..."
}
```

---

#### `GET /api/v1/vaults/:id/verify` — Verify Integrity

**Response (200 OK):**
```json
{
  "valid": true,
  "events_checked": 1247,
  "merkle_root": "sha256:abc...",
  "last_event_hash": "sha256:def...",
  "verified_at": "2026-03-07T14:40:00Z"
}
```

**Server-side actions:**
1. Load all events from Storage bucket
2. Verify hash chain linkage (prev_hash → hash)
3. Verify Ed25519 signatures against stored public key
4. Recompute Merkle root, compare to stored value
5. Return verification report

---

#### `GET /api/v1/vaults/:id/export` — Export Vault

**Query params:**
- `format`: `zip` (default), `ndjson`, `json`

**Response:** File download (Content-Disposition: attachment)

**ZIP contents:**
```
vault-export-20260307/
├── identity/
│   ├── genesis.json
│   └── public_key.pem
├── events/
│   └── events.ndjson
├── manifest.json
└── verification_report.json
```

**Note:** Private keys are NEVER exported. User must rotate keys and download new keypair separately (high-security operation).

---

## Database Schema (Supabase PostgreSQL)

```sql
-- Vaults table
CREATE TABLE vaults (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    
    CONSTRAINT valid_tier CHECK (tier IN ('free', 'developer', 'team')),
    CONSTRAINT valid_status CHECK (status IN ('active', 'suspended', 'deleted'))
);

CREATE INDEX idx_vaults_owner ON vaults(owner_id);
CREATE INDEX idx_vaults_status ON vaults(status);

-- Events table (indexed query layer, source of truth is events.ndjson)
CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- API keys (for programmatic access without JWT)
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- Usage tracking (for billing tiers)
CREATE TABLE usage_tracking (
    vault_id UUID NOT NULL REFERENCES vaults(id) ON DELETE CASCADE,
    month DATE NOT NULL,  -- First day of month (e.g., 2026-03-01)
    event_count INTEGER DEFAULT 0,
    storage_bytes BIGINT DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    PRIMARY KEY (vault_id, month),
    CONSTRAINT positive_event_count CHECK (event_count >= 0)
);

-- Stripe customer linkage
CREATE TABLE stripe_customers (
    user_id TEXT PRIMARY KEY,  -- Clerk user ID
    stripe_customer_id TEXT NOT NULL UNIQUE,
    stripe_subscription_id TEXT UNIQUE,
    tier TEXT NOT NULL DEFAULT 'free',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Storage Bucket Structure (Supabase Storage)

```
Bucket: vaults
├── :vault_id/
│   ├── identity/
│   │   ├── genesis.json
│   │   └── public_key.pem
│   ├── events/
│   │   └── events.ndjson
│   ├── checkpoints/
│   │   └── :seq.chk (optional, for fast replay)
│   ├── manifest.json
│   └── merkle_root.txt
```

**Access policy:**
- Service role only (no public access)
- RLS enabled as defense-in-depth
- Signed URLs for export downloads (5-minute expiry)

---

## Key Management

### Key Generation (Per Vault)

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

# PEM encoding for storage
private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()  # Encrypted by Supabase Secrets
)
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
)

# Key fingerprint (Provara-compatible)
from provara.backpack_signing import key_id_from_public_bytes
public_bytes = public_key.public_bytes(
    encoding=serialization.Encoding.Raw,
    format=serialization.PublicFormat.Raw
)
key_id = key_id_from_public_bytes(public_bytes)  # bp1_...
```

### Key Storage

- **Private keys:** Supabase Secrets (encrypted at rest with AES-256)
- **Public keys:** Stored in `vaults.public_key` column (plaintext PEM)
- **Key IDs:** Stored in `vaults.key_id` (for signature verification)

### Key Rotation (Post-MVP)

Future feature: Allow users to rotate keys via `KEY_ROTATION` ceremony:
1. Generate new keypair
2. Sign rotation event with OLD key
3. Cross-sign (old → new) for continuity
4. Update `vaults.key_id` and move old key to retired state

---

## Billing & Tiers (Stripe)

### Pricing

| Tier | Price | Vaults | Events/mo | Storage | Support |
|------|-------|--------|-----------|---------|---------|
| Free | $0 | 1 | 100 | 10MB | Community |
| Developer | $29/mo | 5 | 10,000 | 1GB | Email |
| Team | $99/mo | Unlimited | 100,000 | 10GB | Priority |
| Enterprise | Custom | Custom | Custom | Custom | SLA |

### Stripe Integration

**Products & Prices:**
- `prod_developer` → `price_developer_monthly` ($29)
- `prod_team` → `price_team_monthly` ($99)

**Webhook handlers:**
- `customer.subscription.created` → Update `stripe_customers` table
- `customer.subscription.updated` → Sync tier changes
- `customer.subscription.deleted` → Downgrade to free tier
- `invoice.payment_failed` → Flag account, grace period

**Usage-based billing (future):**
- Track `events` and `storage_bytes` in `usage_tracking`
- Report to Stripe Metered Billing at month-end
- Overage charges: $0.01 per 1000 events beyond tier limit

---

## Rate Limiting

**Per-tier limits:**

| Tier | Events/min | Events/day | API calls/min |
|------|------------|------------|---------------|
| Free | 10 | 100 | 60 |
| Developer | 100 | 10,000 | 300 |
| Team | 1000 | 100,000 | 1000 |

**Implementation:**
- Vercel KV (Redis) for fast counter lookups
- Sliding window algorithm
- Return `429 Too Many Requests` with `Retry-After` header

---

## Security Considerations

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Stolen API key | Key hash stored, not plaintext; rotation supported |
| Compromised private key | Keys encrypted at rest; future: HSM integration |
| Data tampering | Cryptographic hash chain detects modification |
| Unauthorized access | Clerk JWT on every request; RLS on Supabase |
| Replay attacks | Event `seq` is monotonic; duplicates rejected |
| Data exfiltration | Egress monitoring; signed URLs with expiry |

### Security Checklist

- [ ] All private keys encrypted at rest (Supabase Secrets)
- [ ] JWT verification on every API request
- [ ] Row Level Security (RLS) enabled on all Supabase tables
- [ ] Rate limiting enforced at API layer
- [ ] CORS configured for allowed origins only
- [ ] HTTPS enforced (HSTS header)
- [ ] Private keys never logged or exposed in error messages
- [ ] Export requires re-authentication
- [ ] Audit trail: all admin actions logged to separate vault

---

## Monitoring & Observability

### Sentry Integration

- Capture all unhandled exceptions
- Track error rates per endpoint
- Alert on >1% error rate

### Usage Metrics (Log to Provara Vault)

- Vaults created per day
- Events appended per hour
- Verification failures (alert immediately)
- API latency p95/p99

### Health Checks

- `GET /api/health` → Database connection, Storage access, Clerk API
- `GET /api/health/vault/:id` → Vault-specific integrity check

---

## Development & Deployment

### Local Development

```bash
# Environment variables (.env.local)
CLERK_SECRET_KEY=sk_test_...
SUPABASE_URL=https://....supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Run API locally
npm install
npm run dev  # Vercel dev server on localhost:3000
```

### Deployment (Vercel)

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod
```

**Environment variables in Vercel dashboard:**
- All `.env.local` values
- Set for Production and Preview environments

### CI/CD (GitHub Actions)

```yaml
name: Deploy to Vercel
on:
  push:
    branches: [main]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: amondnet/vercel-action@v25
        with:
          vercel-token: ${{ secrets.VERCEL_TOKEN }}
          vercel-org-id: ${{ secrets.VERCEL_ORG_ID }}
          vercel-project-id: ${{ secrets.VERCEL_PROJECT_ID }}
          vercel-args: '--prod'
```

---

## Implementation Roadmap (Two-Stage Rollout)

### Stage 1: Fly.io FastAPI MVP (v0.1.0) — **LOCKED**
*Objective: Functional managed vaults for internal testing and early adopters.*
- [x] Persistent FastAPI backend on Fly.io (`provara-managed-vault.fly.dev`)
- [x] Initial `saas://` URI support in MCP server
- [x] Docker-based deployment with persistent volume storage
- [x] Basic health monitoring and logging

### Stage 2: Vercel/Supabase Hosted Vault (v0.2.0) — **IN PROGRESS**
*Objective: Scale to 100+ vaults with user auth, billing, and tiered performance.*
- [x] **Database Schema:** Supabase migrations for `vaults`, `events`, `api_keys`, `usage_tracking`.
- [x] **Key Generation:** Python service for Ed25519 vault keypair automation.
- [ ] **Auth:** Clerk JWT verification integration (Currently placeholder).
- [ ] **Billing:** Stripe webhook handler for subscription sync (Currently skeleton).
- [ ] **Infrastructure:** Vercel serverless function deployment.

---

## MVP Scope (Finalized v0.1.0)

### In Scope
- **Vault Management:** Creation, details, listing, and soft-delete via API.
- **Evidence Logging:** Signed event append with causal hash chaining (Ed25519/SHA-256).
- **Audit Access:** Query events by type/time and full cryptographic verification.
- **Portability:** Full vault export as ZIP (NDJSON + Manifest + Public Key).
- **Billing:** Basic 3-tier structure (Free / Developer / Team) synced with Stripe.

### Out of Scope (Post-MVP)
- **HSM Integration:** Hardware-backed key protection.
- **Multi-user RBAC:** Shared vault access across teams.
- **Post-Quantum:** Dilithium/Kyber migration path.
- **Web UI:** Full-featured dashboard (API-first for MVP).

---

## Technical Debt & Remaining Tasks
1. **JWT Lockdown:** Implement `clerk-sdk-python` or manual RS256 verification in Vercel functions.
2. **KMS Strategy:** Move vault private keys from `vault_keys` table to a proper KMS (AWS KMS or Supabase Secrets).
3. **Usage Enforcement:** Wire `check_usage_quota` into the `/events` append flow.
4. **Documentation:** Update `provara.dev` with Hosted Vault API reference.

---

## Success Metrics
| Metric | Target (Month 1) | Target (Month 3) |
|--------|------------------|------------------|
| Vaults created | 50 | 200 |
| Active vaults (7-day) | 20 | 100 |
| Paying customers | 5 | 25 |
| Verification failures | 0 | 0 |

---

## References

- [Provara Protocol Spec](docs/BACKPACK_PROTOCOL_v1.0.md)
- [PSMC Implementation](tools/psmc/psmc.py)
- [MCP Server](tools/mcp_server/README.md)
- [Provara Blueprint](provara\ blueprint.md)
- [Supabase Documentation](https://supabase.com/docs)
- [Clerk JWT Template](https://clerk.com/docs/backend-requests/overview)
- [Stripe Billing Integration](https://stripe.com/docs/billing)

---

*End of Hosted Vault MVP Specification*
