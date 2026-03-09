# Provara Hosted Vault MVP

**Tamper-evident event logging as a service.**

Managed Provara vaults with cryptographic guarantees — zero infrastructure required.

---

## Quick Start

### 1. Create a Vault

```bash
curl -X POST https://api.provara.dev/api/v1/vaults \
  -H "Authorization: Bearer <clerk_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent-memory", "description": "AI agent audit trail"}'
```

**Response:**
```json
{
  "vault_id": "vlt_abc123...",
  "name": "my-agent-memory",
  "key_id": "bp1_def456...",
  "created_at": "2026-03-07T14:30:00Z",
  "tier": "free"
}
```

### 2. Append an Event

```bash
curl -X POST https://api.provara.dev/api/v1/vaults/vlt_abc123.../events \
  -H "Authorization: Bearer <clerk_jwt_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "observation",
    "data": {
      "subject": "model_output",
      "predicate": "generated",
      "value": {"tokens": 450, "model": "claude-3.5"},
      "confidence": 0.92
    }
  }'
```

**Response:**
```json
{
  "event_id": "evt_ghi789...",
  "hash": "sha256:jkl012...",
  "seq": 0,
  "timestamp": "2026-03-07T14:35:22Z",
  "state_hash": "sha256:mno345..."
}
```

### 3. Verify Vault Integrity

```bash
curl https://api.provara.dev/api/v1/vaults/vlt_abc123.../events?action=verify \
  -H "Authorization: Bearer <clerk_jwt_token>"
```

**Response:**
```json
{
  "valid": true,
  "events_checked": 42,
  "merkle_root": "sha256:pqr678...",
  "verified_at": "2026-03-07T14:40:00Z"
}
```

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/vaults` | POST | Create a new vault |
| `/api/v1/vaults` | GET | List user's vaults |
| `/api/v1/vaults/:id` | GET | Get vault details |
| `/api/v1/vaults/:id` | DELETE | Delete a vault |
| `/api/v1/vaults/:id/events` | POST | Append event to vault |
| `/api/v1/vaults/:id/events` | GET | Query events (params: `last`, `type`, `since`, `format`) |
| `/api/v1/vaults/:id/events?action=verify` | GET | Verify vault integrity |
| `/api/v1/vaults/:id/export` | GET | Export vault as ZIP |
| `/api/health` | GET | Health check |

---

## Pricing Tiers

| Tier | Price | Vaults | Events/mo | Storage | Rate Limit |
|------|-------|--------|-----------|---------|------------|
| Free | $0 | 1 | 100 | 10MB | 10/min |
| Developer | $29/mo | 5 | 10,000 | 1GB | 100/min |
| Team | $99/mo | Unlimited | 100,000 | 10GB | 1000/min |

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌──────────────┐
│   Client    │ ───► │ Vercel Edge  │ ───► │   Supabase   │
│ (AI Agent)  │ JWT  │  Functions   │      │ (Postgres +  │
└─────────────┘      └──────────────┘      │   Storage)   │
                                            └──────────────┘
```

- **Auth:** Clerk JWT verification on every request
- **Storage:** Supabase Postgres (indexed queries) + Storage (events.ndjson)
- **Signing:** Ed25519 per vault, keys encrypted at rest
- **Hosting:** Vercel serverless functions

---

## Development

### Prerequisites

- Node.js 20+
- Python 3.11+
- Supabase account
- Clerk account
- Stripe account (for billing)

### Local Setup

```bash
# Clone repo
cd hosted-vault

# Install dependencies
npm install

# Copy environment variables
cp .env.example .env.local

# Edit .env.local with your credentials
# - CLERK_SECRET_KEY
# - SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
# - STRIPE_SECRET_KEY

# Run database migrations
npx supabase db push

# Start local dev server
npm run dev
```

### Run Tests

```bash
# Python API tests
python -m pytest src/api/test_*.py -v

# TypeScript tests
npm test
```

### Deploy

```bash
# Deploy to Vercel
npm run deploy
```

---

## Event Types

| Type | Description | Example Use |
|------|-------------|-------------|
| `identity` | Identity or profile information | Agent name, capabilities |
| `decision` | Decision made by agent | Action selection, tool choice |
| `belief` | Belief or conclusion | Inferred fact, confidence update |
| `note` | General observation | Log entry, debug info |
| `milestone` | Significant event | Task completion, goal reached |
| `reflection` | Self-analysis | Performance review, learning |
| `correction` | Error correction | Retracted belief, fixed mistake |

---

## Security

- **Ed25519 signatures** on every event
- **SHA-256 hash chain** for tamper evidence
- **Clerk JWT** authentication on all requests
- **Encrypted keys** at rest (Supabase Secrets)
- **Row Level Security** on all database tables
- **Rate limiting** per tier

---

## Export Your Data

Download your complete vault at any time:

```bash
curl -X GET https://api.provara.dev/api/v1/vaults/:id/export \
  -H "Authorization: Bearer <token>" \
  --output vault-export.zip
```

**ZIP contents:**
```
vault-export/
├── identity/
│   ├── genesis.json
│   └── public_key.pem
├── events/
│   └── events.ndjson
├── manifest.json
└── verification_report.json
```

---

## Roadmap

- [ ] Key rotation ceremonies
- [ ] Webhook notifications
- [ ] MCP server hosting
- [ ] Compliance reports (EU AI Act, ISO 42001)
- [ ] Multi-region replication
- [ ] Team collaboration (multi-user vaults)

---

## License

Apache 2.0 — Hunt Information Systems LLC

---

## Support

- **Docs:** https://provara.dev/docs/hosted-vault
- **Status:** https://status.provara.dev
- **Email:** support@provara.dev
