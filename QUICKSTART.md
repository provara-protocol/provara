# Provara Protocol — Quick Start Guide

Get up and running with Provara in 5 minutes.

## Prerequisites

- **Python 3.10+** — [Download](https://python.org)
- **Git** (optional, for cloning)

## Installation

### Option 1: Clone the repository

```bash
git clone https://github.com/provara-protocol/provara.git
cd provara
pip install cryptography
```

### Option 2: Download the release

Download the latest release from GitHub and extract it.

```bash
cd provara
pip install cryptography
```

## Create Your First Vault

```bash
# Using the CLI wrapper
python mcp/provara_cli.py init ./my_vault --quorum

# Or using the bootstrap script directly
cd SNP_Core/bin
python bootstrap_v0.py /path/to/my_vault --quorum --self-test
```

This creates:
- A new vault with cryptographic identity
- Ed25519 keypairs (root + quorum for recovery)
- Genesis event (your vault's birth certificate)
- Signed manifest and Merkle root
- Policy files (safety, retention, sync governance)

⚠️ **Important:** Your private keys are written to `my_private_keys.json` in the parent directory. **Store them securely!** Without these keys, you cannot sign new events.

## Verify Your Vault

```bash
# Check integrity
python mcp/provara_cli.py verify ./my_vault

# Or run full compliance tests
cd SNP_Core/test
PYTHONPATH=../bin python backpack_compliance_v1.py ../../my_vault -v
```

You should see:
- ✅ All causal chains valid
- ✅ Merkle root verified
- ✅ Event signatures valid

## View State

```bash
# Show belief state summary
python mcp/provara_cli.py state ./my_vault

# Get full state as JSON
python mcp/provara_cli.py state ./my_vault --json > state.json
```

Output shows:
- Event count
- State hash (deterministic fingerprint)
- Beliefs in each namespace (canonical, local, contested, archived)

## Add Events (Using PSMC)

The Personal Sovereign Memory Container (PSMC) is the first application layer built on Provara.

```bash
cd tools/psmc

# Create a PSMC vault
python psmc.py init --vault ./my_psmc

# Append an event
python psmc.py append --vault ./my_psmc \
  --type note \
  --data '{"content":"First memory recorded"}'

# With Provara integration (creates belief state)
python psmc.py append --vault ./my_psmc \
  --type belief \
  --data '{"statement":"Cryptographic integrity matters","confidence":0.9}' \
  --provara

# View events
python psmc.py show --vault ./my_psmc

# Verify integrity
python psmc.py verify --vault ./my_psmc
```

## Multi-Device Sync

Provara vaults can be synced across devices using union merge.

```bash
# On Device A: export delta
python mcp/provara_cli.py export ./vault_a --output delta.ndjson

# Transfer delta.ndjson to Device B (USB, email, etc.)

# On Device B: import delta
python mcp/provara_cli.py import ./vault_b --delta delta.ndjson

# Or sync directly if both vaults are accessible
python mcp/provara_cli.py sync ./vault_a ./vault_b
```

**How it works:**
- Events are merged by union (no duplicates)
- Causal chains are verified
- Forks are detected (divergent offline histories)
- Reducer recomputes belief state from merged events
- Deterministic: same events → same state hash, always

## Use with Claude Desktop (MCP)

Add to your Claude Desktop config:

**macOS/Linux:**  
`~/Library/Application Support/Claude/claude_desktop_config.json`

**Windows:**  
`%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "provara": {
      "command": "python",
      "args": ["C:/provara/mcp/provara_server.py"]
    }
  }
}
```

Restart Claude Desktop. You'll now have access to Provara tools:
- bootstrap_vault
- verify_vault
- export_state
- sync_vaults
- export_delta
- import_delta
- verify_chain

## Run HTTP Server (for Smithery.ai)

```bash
cd mcp

# Install HTTP dependencies
pip install flask flask-cors

# Start server
python provara_server_http.py --port 8080

# Test it
curl http://localhost:8080/health
```

Endpoints:
- `GET /health` — Health check
- `POST /mcp` — JSON-RPC requests
- `GET /sse` — Server-Sent Events stream

## Run Tests

```bash
# All unit tests (94)
cd SNP_Core/test
PYTHONPATH=../bin python -m unittest test_reducer_v0 test_rekey test_bootstrap test_sync_v0 -v

# Compliance tests (17)
PYTHONPATH=../bin python backpack_compliance_v1.py ../examples/reference_backpack -v

# PSMC tests (60)
cd ../..
python -m pytest tools/psmc/test_psmc.py -v

# MCP integration tests
cd mcp
python test_integration.py
```

**Test counts:**
- 94 unit tests
- 7 vector tests  
- 17 compliance tests (10 pass on Windows due to CRLF)
- 60 PSMC tests
- **Total: 178 tests**

## Next Steps

### Learn More
- Read [`BACKPACK_PROTOCOL_v1.0.md`](docs/BACKPACK_PROTOCOL_v1.0.md) for the full protocol spec
- Check [`docs/GOVERNANCE_ALIGNMENT.md`](docs/GOVERNANCE_ALIGNMENT.md) for AI governance use cases
- See [`PROTOCOL_PROFILE.txt`](PROTOCOL_PROFILE.txt) for normative crypto spec

### Build on Provara
- Create your own event types (OBSERVATION, ASSERTION, ATTESTATION)
- Build application layers like PSMC
- Implement the protocol in other languages (test vectors provided)

### Integrate
- Add Provara as memory substrate for AI agents
- Use for audit trails and compliance logging
- Build multi-device sync for your app

## Common Issues

### "cryptography module not found"
```bash
pip install cryptography
```

### "PYTHONPATH not set"
When running tests or scripts, set PYTHONPATH to SNP_Core/bin:
```bash
cd SNP_Core/test
PYTHONPATH=../bin python ...
```

### "Compliance tests fail on Windows"
Known issue: 7 sub-tests in `test_09` fail due to CRLF line ending size mismatches. This is cosmetic and doesn't affect functionality. The core compliance tests (1-8, 10-17) pass.

### "Private keys lost"
If you lose `my_private_keys.json` and didn't use `--quorum`:
- ✅ Your vault is still **readable** (plain JSON)
- ❌ You **cannot sign new events**
- Solution: Use `--quorum` flag at bootstrap for recovery options

## Getting Help

- **GitHub Issues:** https://github.com/provara-protocol/provara/issues
- **Documentation:** [`docs/`](docs/)
- **Source Code:** Well-commented in [`SNP_Core/bin/`](SNP_Core/bin/)

---

**Welcome to Provara!** 🦞

You now have a sovereign, tamper-evident memory system that:
- Works offline
- Has no vendor lock-in
- Will be readable in 2076
- Cannot be silently modified
- Proves what you knew, when you knew it

Start recording your truth.
