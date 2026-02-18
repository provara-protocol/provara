# Claude Agent with Provara Vault Memory

**Demo: AI Research Assistant with Verifiable Notes**

A step-by-step walkthrough showing Claude using Provara as persistent, verifiable memory. Follow along to see what trustworthy AI memory looks like.

---

## Setup

### 1. Install Provara

```bash
pip install provara-protocol
```

### 2. Initialize Vault

```bash
provara init claude_research_vault --actor "claude_desktop"
```

**Output:**
```
[bootstrap] Generating Ed25519 root keypair...
[bootstrap] Creating directory structure...
[bootstrap] Bootstrap complete. UID=claude_research_001
[bootstrap] Root key: bp1_abc123...
```

### 3. Configure Claude Desktop

Add to `claude_desktop_config.json` (location varies by OS):

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`  
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Linux:** `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": [
        "-m",
        "provara.mcp",
        "--transport",
        "stdio",
        "--vault-path",
        "/absolute/path/to/claude_research_vault"
      ]
    }
  }
}
```

**Restart Claude Desktop** after saving the config.

---

## Demo Scenario: Research Assistant

### Step 1: Initial Research Request

**User:**
> Research the current state of verifiable AI memory systems. Store your findings.

**Claude's Tool Call:**
```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault",
    "event_type": "OBSERVATION",
    "data": {
      "subject": "research_topic",
      "predicate": "initiated",
      "value": "Verifiable AI memory systems research",
      "confidence": 1.0
    }
  }
}
```

**Vault State After:**
```json
// events.ndjson (line 2 - genesis is line 1)
{
  "type": "OBSERVATION",
  "actor": "claude_desktop",
  "event_id": "evt_research_001",
  "prev_event_hash": "evt_genesis...",
  "timestamp_utc": "2026-02-18T10:00:00Z",
  "payload": {
    "subject": "research_topic",
    "predicate": "initiated",
    "value": "Verifiable AI memory systems research",
    "confidence": 1.0
  },
  "sig": "base64_ed25519_signature..."
}
```

---

### Step 2: Store Research Findings

**Claude:**
> I'll research verifiable AI memory systems. Let me store my findings as I go.
>
> **Finding 1:** Current AI agent memory systems (vector databases, RAG) are mutable and cannot be independently verified.

**Tool Call:**
```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault",
    "event_type": "OBSERVATION",
    "data": {
      "subject": "ai_memory",
      "predicate": "finding",
      "value": "Current AI agent memory systems (vector DBs, RAG) are mutable and unverifiable",
      "confidence": 0.90,
      "source": "analysis"
    }
  }
}
```

**Claude:**
> **Finding 2:** Cryptographic event logs (like Provara) provide tamper-evident storage with Ed25519 signatures and SHA-256 hash chains.

**Tool Call:**
```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault",
    "event_type": "OBSERVATION",
    "data": {
      "subject": "ai_memory",
      "predicate": "finding",
      "value": "Cryptographic event logs provide tamper-evident storage with Ed25519 + SHA-256",
      "confidence": 0.95,
      "source": "protocol_analysis"
    }
  }
}
```

---

### Step 3: Verify Memory Integrity

**User:**
> How do I know you haven't altered your research notes?

**Claude:**
> Let me verify the integrity of my memory vault.

**Tool Call:**
```json
{
  "tool": "verify_chain",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault"
  }
}
```

**Response:**
```json
{
  "valid": true
}
```

**Claude:**
> My memory vault has been verified. The cryptographic chain shows:
> - 3 events recorded
> - All Ed25519 signatures valid
> - SHA-256 hash chain intact
> - No tampering detected
>
> Every finding I stored is cryptographically anchored and cannot be silently altered.

---

### Step 4: Query Past Observations

**User:**
> What did you find about vector databases?

**Claude:**
> Let me query my research notes.

**Tool Call:**
```json
{
  "tool": "query_timeline",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault",
    "event_type": "OBSERVATION",
    "limit": 10
  }
}
```

**Response:**
```json
{
  "events": [
    {
      "event_id": "evt_research_001",
      "type": "OBSERVATION",
      "timestamp": "2026-02-18T10:00:00Z",
      "data": {
        "subject": "research_topic",
        "predicate": "initiated",
        "value": "Verifiable AI memory systems research"
      }
    },
    {
      "event_id": "evt_finding_001",
      "type": "OBSERVATION",
      "timestamp": "2026-02-18T10:01:00Z",
      "data": {
        "subject": "ai_memory",
        "predicate": "finding",
        "value": "Current AI agent memory systems (vector DBs, RAG) are mutable and unverifiable",
        "confidence": 0.90
      }
    },
    {
      "event_id": "evt_finding_002",
      "type": "OBSERVATION",
      "timestamp": "2026-02-18T10:02:00Z",
      "data": {
        "subject": "ai_memory",
        "predicate": "finding",
        "value": "Cryptographic event logs provide tamper-evident storage with Ed25519 + SHA-256",
        "confidence": 0.95
      }
    }
  ]
}
```

**Claude:**
> Based on my research notes, I found that:
>
> 1. **Vector databases and RAG systems are mutable** — they can be edited without detection (confidence: 90%)
> 2. **Cryptographic event logs provide tamper-evidence** — using Ed25519 signatures and SHA-256 hash chains (confidence: 95%)

---

### Step 5: User Correction

**User:**
> That's not quite right. Vector databases themselves aren't inherently mutable — it's the way they're typically deployed without audit logs. The immutability issue is about the deployment architecture, not the technology itself.

**Claude:**
> You're absolutely right. Let me store a correction that preserves the original claim.

**Tool Call:**
```json
{
  "tool": "append_event",
  "arguments": {
    "vault_path": "/path/to/claude_research_vault",
    "event_type": "CORRECTION",
    "data": {
      "subject": "ai_memory",
      "predicate": "corrected",
      "value": "Vector databases are not inherently mutable; the issue is deployment architecture without audit logs",
      "corrects_event": "evt_finding_001",
      "correction_source": "user_feedback",
      "confidence": 0.98
    }
  }
}
```

**Vault State After:**
```json
// events.ndjson now has 5 events:
// 1. genesis
// 2. research_topic initiated
// 3. ai_memory finding (original claim)
// 4. ai_memory finding (cryptographic logs)
// 5. ai_memory corrected (preserves original, adds correction)
```

**Claude:**
> I've recorded your correction. The vault now shows:
>
> 1. **Original claim** (10:01:00Z): "Vector DBs are mutable" (confidence: 90%)
> 2. **Correction** (10:05:00Z): "Issue is deployment architecture, not the technology" (confidence: 98%)
>
> The original is preserved for audit purposes — I can't silently edit my past statements.

---

### Step 6: Export and Independent Verification

**User:**
> Can I verify this myself?

**Claude:**
> Absolutely. Here's how:

**Export the vault:**
```bash
# Create a backup
provara backup /path/to/claude_research_vault --output research_backup.zip

# Verify the backup
provara verify research_backup.zip

# Export to markdown for review
provara export-markdown /path/to/claude_research_vault --output research_notes.md
```

**Output:**
```
[verify] Checking causal chains...
[verify] Checking signatures...
[verify] Checking Merkle root...
[verify] Vault integrity: VALID
[verify] Events verified: 5
```

**Claude:**
> You can independently verify:
> 1. Download the backup ZIP
> 2. Run `provara verify research_backup.zip`
> 3. Check that all 5 events have valid Ed25519 signatures
> 4. Verify the SHA-256 hash chain is unbroken
> 5. Confirm the correction references the original event
>
> No need to trust me — the cryptography proves the audit trail.

---

## Key Moments Highlighted

### 1. Claude Can't Silently Edit Past Observations

When the user provided a correction, Claude couldn't just update the original event. Instead:
- Original claim preserved at `evt_finding_001`
- Correction added as new event `evt_correction_001`
- Full audit trail maintained

### 2. Every Claim Has Cryptographic Timestamp

Each event includes:
- `timestamp_utc`: When the observation was made
- `event_id`: Content-addressed identifier (SHA-256)
- `sig`: Ed25519 signature proving authorship
- `prev_event_hash`: Links to previous event (hash chain)

### 3. Correction Preserves Original

The vault shows the evolution of understanding:
```
10:01:00Z — Original claim (confidence: 90%)
10:05:00Z — Correction (confidence: 98%, references original)
```

### 4. Independent Verification

Anyone can:
1. Download the vault backup
2. Run `provara verify`
3. Check all signatures and hash chains
4. Confirm the audit trail is intact

### 5. This Is Trustworthy AI Memory

Unlike mutable databases or vector stores:
- **Tamper-evident:** Any alteration breaks the hash chain
- **Non-repudiable:** Ed25519 signatures prove authorship
- **Auditable:** Full history preserved, corrections append-only
- **Verifiable:** Anyone can independently verify integrity

---

## Verify It Yourself

### 1. Get the Vault

Ask Claude to export the vault from the demo and share the ZIP file.

### 2. Install Provara

```bash
pip install provara-protocol
```

### 3. Verify Integrity

```bash
provara verify research_backup.zip
```

**Expected output:**
```
[verify] Vault integrity: VALID
[verify] Events verified: 5
[verify] Chain integrity: OK
```

### 4. Inspect Events

```bash
provara replay research_backup.zip
```

**Expected output:**
```json
{
  "canonical": {},
  "local": {
    "research_topic": {...},
    "ai_memory": {...}
  },
  "contested": {},
  "archived": {}
}
```

### 5. Check the Correction

Open `events.ndjson` in any text editor. Find the CORRECTION event:

```json
{
  "type": "CORRECTION",
  "payload": {
    "subject": "ai_memory",
    "predicate": "corrected",
    "corrects_event": "evt_finding_001",
    ...
  }
}
```

The original event is still there — preserved, not deleted.

---

## What This Demonstrates

| Property | How It's Shown |
|----------|----------------|
| **Tamper-evidence** | `verify_chain` confirms hash chain integrity |
| **Non-repudiation** | Ed25519 signatures on every event |
| **Append-only** | Correction adds new event, doesn't delete original |
| **Audit trail** | Full history visible in `events.ndjson` |
| **Independent verification** | Anyone can run `provara verify` |

---

**This is what trustworthy AI memory looks like.**

Not a mutable database. Not a vector store that can be edited. A cryptographic event log where every claim is signed, chained, and independently verifiable.

---

**Next Steps:**
- [MCP Server README](../tools/mcp_server/README.md) — Full tool documentation
- [Provara Quickstart](../docs/QUICKSTART.md) — 60-second vault creation
- [Cookbook](../docs/cookbook/) — Real-world recipes
