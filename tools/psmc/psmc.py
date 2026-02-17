#!/usr/bin/env python3
"""
Personal Sovereign Memory Container (PSMC) v1.0
================================================
A minimal, file-first, append-only event log with cryptographic integrity.
Built on Provara Protocol primitives. Designed for 20+ year durability.

No database. No blockchain. No cloud.

Cryptographic foundation: Provara SNP_Core (Ed25519 + SHA-256 + RFC 8785 canonical JSON)
Single external dependency: cryptography >= 41.0
Formats: UTF-8 NDJSON, PEM keys, plain text digests
License: Apache 2.0

Usage:
    python psmc.py init
    python psmc.py append --type identity --data '{"name":"Alice"}'
    python psmc.py verify
    python psmc.py digest --weeks 1
    python psmc.py show [--last N] [--type TYPE]
    python psmc.py export --format markdown
    python psmc.py rotate-key
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Provara core imports (shared cryptographic primitives)
# ---------------------------------------------------------------------------
_project_root = Path(__file__).resolve().parent.parent.parent
_snp_core_bin = _project_root / "SNP_Core" / "bin"
if str(_snp_core_bin) not in sys.path:
    sys.path.insert(0, str(_snp_core_bin))

from canonical_json import canonical_dumps, canonical_hash  # noqa: E402
from backpack_signing import (  # noqa: E402
    key_id_from_public_bytes,
    sign_event,
    resolve_public_key,
    load_keys_registry,
)
from reducer_v0 import SovereignReducerV0  # noqa: E402
from checkpoint_v0 import (  # noqa: E402
    create_checkpoint,
    save_checkpoint,
    load_latest_checkpoint,
    verify_checkpoint,
)

from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: E402
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives import serialization  # noqa: E402
from cryptography.exceptions import InvalidSignature  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VERSION = "1.0.0"
HASH_ALGO = "sha256"
SIG_ALGO = "ed25519"
GENESIS_PREV = "0" * 64  # null hash for first event


def _get_provara_prev_hash(vault: Path) -> str | None:
    """Read the last event_id from provara.ndjson."""
    provara_file = vault_path(vault, "events", "provara.ndjson")
    if not provara_file.exists():
        return None
    last_line = ""
    with open(provara_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return None
    try:
        entry = json.loads(last_line)
        return entry.get("event_id")
    except json.JSONDecodeError:
        return None


def emit_provara_event(vault: Path, psmc_event: dict):
    """Create and append a Provara-native event reflecting the PSMC event."""
    # 1. Map PSMC type to Provara type
    p_type = "OBSERVATION"
    if psmc_event["type"] in ["belief", "decision", "reflection"]:
        p_type = "ASSERTION"

    # 2. Prepare payload
    data = psmc_event["data"]
    subject = data.get("subject") or data.get("title") or data.get("name") or "psmc_node"
    
    # 3. Load keys
    priv = load_private_key(vault)
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kid = key_id_from_public_bytes(pub_bytes)

    # 4. Build Provara event (without event_id and sig)
    prev_hash = _get_provara_prev_hash(vault)
    
    event = {
        "type": p_type,
        "actor": kid,
        "prev_event_hash": prev_hash,
        "payload": {
            "subject": str(subject),
            "predicate": psmc_event["type"],
            "value": data,
            "timestamp": psmc_event["timestamp"],
            "confidence": _safe_float(data.get("confidence"), 0.5 if p_type == "ASSERTION" else 1.0)
        }
    }

    # 5. Compute event_id (evt_ + SHA256(canonical_json(event_without_id_sig))[:24])
    # Note: canonical_hash uses canonical_dumps internally
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"
    
    # 6. Sign it (adds actor_key_id and sig)
    # backpack_signing.sign_event expects (event, private_key, key_id)
    signed_event = sign_event(event, priv, kid)

    # 7. Write to provara.ndjson
    provara_file = vault_path(vault, "events", "provara.ndjson")
    _append_line(provara_file, canonical_dumps(signed_event))


def run_provara_reducer(vault: Path) -> dict:
    """Run SovereignReducerV0 over all Provara events and write state to disk."""
    provara_file = vault_path(vault, "events", "provara.ndjson")
    
    # Read all Provara events
    if not provara_file.exists():
        # No provara events yet, return empty state
        reducer = SovereignReducerV0()
        state = reducer.export_state()
    else:
        events = []
        with open(provara_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    try:
                        events.append(json.loads(stripped))
                    except json.JSONDecodeError:
                        # Skip malformed lines
                        continue
        
        # Run reducer
        reducer = SovereignReducerV0()
        reducer.apply_events(events)
        state = reducer.export_state()
    
    # Write state to disk
    state_dir = vault_path(vault, "state")
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "current_state.json"
    state_file.write_text(canonical_dumps(state) + "\n", encoding="utf-8")
    
    return state


def _safe_float(val: Any, default: float) -> float:
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


VALID_TYPES = [
    "identity", "decision", "belief", "promotion", "note",
    "milestone", "reflection", "correction", "migration",
]

# ---------------------------------------------------------------------------
# Directory Layout
# ---------------------------------------------------------------------------
# vault/
# ├── psmc.json              <- vault metadata (version, created, key fingerprint)
# ├── keys/
# │   ├── active.pem         <- current Ed25519 private key (PEM)
# │   ├── active.pub.pem     <- current Ed25519 public key (PEM)
# │   └── retired/           <- rotated keys with timestamp prefix
# ├── events/
# │   └── events.ndjson      <- append-only event log (one JSON per line)
# ├── chain/
# │   └── chain.ndjson       <- hash chain entries (parallel to events)
# └── digests/
#     └── YYYY-WNN.md        <- weekly digest files (human-readable)

def vault_path(base: Path, *parts) -> Path:
    return base.joinpath(*parts)


# ---------------------------------------------------------------------------
# Hashing (delegates to Provara canonical_json module)
# ---------------------------------------------------------------------------
def compute_event_hash(event: dict) -> str:
    """Hash the canonical form of an event (excluding the hash field itself)."""
    hashable = {k: v for k, v in event.items() if k != "hash"}
    return canonical_hash(hashable)


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------
def load_private_key(vault: Path) -> Ed25519PrivateKey:
    pem = vault_path(vault, "keys", "active.pem").read_bytes()
    return serialization.load_pem_private_key(pem, password=None)


def load_public_key(vault: Path) -> Ed25519PublicKey:
    pem = vault_path(vault, "keys", "active.pub.pem").read_bytes()
    return serialization.load_pem_public_key(pem)


def load_public_key_from_pem(pem_bytes: bytes) -> Ed25519PublicKey:
    return serialization.load_pem_public_key(pem_bytes)


def sign_data(private_key, data: str) -> str:
    """Sign UTF-8 data, return hex-encoded signature."""
    sig = private_key.sign(data.encode("utf-8"))
    return sig.hex()


def verify_signature(public_key, data: str, sig_hex: str) -> bool:
    try:
        public_key.verify(bytes.fromhex(sig_hex), data.encode("utf-8"))
        return True
    except InvalidSignature:
        return False


def key_fingerprint(public_key) -> str:
    """Provara-compatible key fingerprint (bp1_ prefix + 16 hex chars)."""
    raw = public_key.public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return key_id_from_public_bytes(raw)


# ---------------------------------------------------------------------------
# Schema Validation
# ---------------------------------------------------------------------------
def validate_event(event: dict) -> list[str]:
    """Returns list of validation errors (empty = valid)."""
    errors = []
    required = ["id", "type", "timestamp", "data", "prev_hash"]
    for field in required:
        if field not in event:
            errors.append(f"Missing required field: {field}")

    if "type" in event and event["type"] not in VALID_TYPES:
        errors.append(f"Invalid type '{event['type']}'. Valid: {VALID_TYPES}")

    if "timestamp" in event:
        try:
            datetime.fromisoformat(event["timestamp"])
        except ValueError:
            errors.append(f"Invalid ISO timestamp: {event['timestamp']}")

    if "data" in event and not isinstance(event["data"], dict):
        errors.append("'data' must be a JSON object")

    if "id" in event:
        try:
            uuid.UUID(event["id"])
        except ValueError:
            errors.append(f"Invalid UUID: {event['id']}")

    return errors


# ---------------------------------------------------------------------------
# Vault Operations
# ---------------------------------------------------------------------------
def init_vault(vault: Path) -> None:
    """Create a new vault with keypair and empty event log."""
    if vault_path(vault, "psmc.json").exists():
        print(f"ERROR: Vault already exists at {vault}", file=sys.stderr)
        sys.exit(1)

    # Create directory structure
    for d in ["keys/retired", "events", "chain", "digests"]:
        vault_path(vault, d).mkdir(parents=True, exist_ok=True)

    # Generate Ed25519 keypair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # Write keys (PEM format for human readability and 20-year durability)
    vault_path(vault, "keys", "active.pem").write_bytes(
        private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    vault_path(vault, "keys", "active.pub.pem").write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    # Set restrictive permissions on private key (Unix)
    try:
        os.chmod(vault_path(vault, "keys", "active.pem"), 0o600)
    except OSError:
        pass  # Windows doesn't support Unix permissions

    fp = key_fingerprint(public_key)

    # Write vault metadata
    meta = {
        "version": VERSION,
        "created": datetime.now(timezone.utc).isoformat(),
        "hash_algo": HASH_ALGO,
        "sig_algo": SIG_ALGO,
        "key_fingerprint": fp,
        "description": "Personal Sovereign Memory Container",
        "provara_compatible": True,
    }
    vault_path(vault, "psmc.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )

    # Create empty event log and chain
    vault_path(vault, "events", "events.ndjson").touch()
    vault_path(vault, "chain", "chain.ndjson").touch()

    # Write README for future readers
    readme = vault_path(vault, "README.txt")
    readme.write_text(
        "PERSONAL SOVEREIGN MEMORY CONTAINER\n"
        "====================================\n"
        f"Created: {meta['created']}\n"
        f"Version: {VERSION}\n"
        f"Hash: SHA-256 | Signature: Ed25519\n"
        f"Built on: Provara Protocol primitives\n\n"
        "FORMAT:\n"
        "  events/events.ndjson - One JSON object per line (append-only)\n"
        "  chain/chain.ndjson   - Hash chain entries (parallel to events)\n"
        "  keys/active.pub.pem  - Ed25519 public key for verification\n"
        "  digests/             - Human-readable weekly summaries\n\n"
        "VERIFICATION:\n"
        "  python psmc.py verify --vault <path>\n"
        "  Or manually: SHA-256 each event line, check prev_hash linkage,\n"
        "  verify Ed25519 signatures against the public key.\n\n"
        "This vault uses no database, no proprietary formats, no cloud.\n"
        "Every file is UTF-8 text. Readable with any text editor in 2046.\n",
        encoding="utf-8",
    )

    print(f"Vault initialized at: {vault}")
    print(f"Key fingerprint: {fp}")
    print(f"Event log: {vault_path(vault, 'events', 'events.ndjson')}")


def get_last_hash(vault: Path) -> str:
    """Read the hash of the last event, or GENESIS if log is empty."""
    chain_file = vault_path(vault, "chain", "chain.ndjson")
    last_line = ""
    with open(chain_file, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if not last_line:
        return GENESIS_PREV
    entry = json.loads(last_line)
    return entry["hash"]


def count_events(vault: Path) -> int:
    events_file = vault_path(vault, "events", "events.ndjson")
    count = 0
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def append_event(vault: Path, event_type: str, data: dict, tags: list[str] | None = None, emit_provara: bool = False) -> dict:
    """Create, sign, and append a new event."""
    prev_hash = get_last_hash(vault)
    seq = count_events(vault)

    event = {
        "id": str(uuid.uuid4()),
        "seq": seq,
        "type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prev_hash": prev_hash,
        "data": data,
    }
    if tags:
        event["tags"] = tags

    # Validate
    errors = validate_event(event)
    if errors:
        print(f"Validation failed: {errors}", file=sys.stderr)
        sys.exit(1)

    # Compute hash over canonical form (uses Provara's canonical_hash)
    event_hash = compute_event_hash(event)
    event["hash"] = event_hash

    # Sign the hash
    private_key = load_private_key(vault)
    signature = sign_data(private_key, event_hash)

    # Build chain entry
    chain_entry = {
        "seq": seq,
        "hash": event_hash,
        "prev_hash": prev_hash,
        "sig": signature,
        "key_fp": key_fingerprint(private_key.public_key()),
    }

    # Append atomically (write + flush + fsync)
    events_file = vault_path(vault, "events", "events.ndjson")
    chain_file = vault_path(vault, "chain", "chain.ndjson")

    _append_line(events_file, canonical_dumps(event))
    _append_line(chain_file, canonical_dumps(chain_entry))

    # Also emit Provara-native event if requested
    if emit_provara:
        emit_provara_event(vault, event)
        # Run reducer to update state
        run_provara_reducer(vault)

    return event


def _append_line(filepath: Path, line: str) -> None:
    """Append a single line with fsync for durability."""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        os.fsync(f.fileno())


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify_chain(vault: Path, verbose: bool = False) -> bool:
    """Verify the full integrity of the event log and hash chain."""
    events_file = vault_path(vault, "events", "events.ndjson")
    chain_file = vault_path(vault, "chain", "chain.ndjson")

    # Load all public keys (active + retired) for signature verification
    pub_keys = {}
    active_pub = vault_path(vault, "keys", "active.pub.pem")
    if active_pub.exists():
        pk = load_public_key(vault)
        pub_keys[key_fingerprint(pk)] = pk

    retired_dir = vault_path(vault, "keys", "retired")
    if retired_dir.exists():
        for f in retired_dir.iterdir():
            if f.suffix == ".pem" and "pub" in f.name:
                pk = load_public_key_from_pem(f.read_bytes())
                pub_keys[key_fingerprint(pk)] = pk

    events = _read_ndjson(events_file)
    chain = _read_ndjson(chain_file)

    if len(events) != len(chain):
        print(f"FAIL: Event count ({len(events)}) != chain count ({len(chain)})")
        return False

    if len(events) == 0:
        print("OK: Empty vault (no events)")
        return True

    expected_prev = GENESIS_PREV
    ok = True

    for i, (event, link) in enumerate(zip(events, chain)):
        # 1. Check prev_hash linkage
        if event.get("prev_hash") != expected_prev:
            print(f"FAIL @ seq {i}: prev_hash mismatch in event")
            print(f"  expected: {expected_prev}")
            print(f"  got:      {event.get('prev_hash')}")
            ok = False

        if link.get("prev_hash") != expected_prev:
            print(f"FAIL @ seq {i}: prev_hash mismatch in chain")
            ok = False

        # 2. Recompute event hash
        recomputed = compute_event_hash(event)
        stored_hash = event.get("hash", "")
        if recomputed != stored_hash:
            print(f"FAIL @ seq {i}: hash mismatch")
            print(f"  recomputed: {recomputed}")
            print(f"  stored:     {stored_hash}")
            ok = False

        if link.get("hash") != stored_hash:
            print(f"FAIL @ seq {i}: chain hash doesn't match event hash")
            ok = False

        # 3. Verify signature
        fp = link.get("key_fp", "")
        if fp in pub_keys:
            if not verify_signature(pub_keys[fp], stored_hash, link.get("sig", "")):
                print(f"FAIL @ seq {i}: invalid signature")
                ok = False
        else:
            print(f"WARN @ seq {i}: unknown key fingerprint {fp}, cannot verify sig")

        # 4. Check sequence
        if event.get("seq") != i:
            print(f"FAIL @ seq {i}: sequence mismatch (got {event.get('seq')})")
            ok = False

        if verbose and ok:
            print(f"  OK seq {i}: {event.get('type', '?')} [{stored_hash[:12]}...]")

        expected_prev = stored_hash

    status = "PASS" if ok else "FAIL"
    print(f"\nVerification {status}: {len(events)} events checked")
    return ok


# ---------------------------------------------------------------------------
# Read / Show
# ---------------------------------------------------------------------------
def _read_ndjson(filepath: Path) -> list[dict]:
    entries = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def show_events(vault: Path, last_n: int | None = None, event_type: str | None = None) -> None:
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))

    if event_type:
        events = [e for e in events if e.get("type") == event_type]

    if last_n:
        events = events[-last_n:]

    for e in events:
        ts = e.get("timestamp", "?")[:19]
        etype = e.get("type", "?")
        seq = e.get("seq", "?")
        data_preview = json.dumps(e.get("data", {}), ensure_ascii=False)
        if len(data_preview) > 80:
            data_preview = data_preview[:77] + "..."
        print(f"[{seq:>4}] {ts}  {etype:<12}  {data_preview}")


# ---------------------------------------------------------------------------
# Weekly Digest Generator
# ---------------------------------------------------------------------------
def generate_digest(vault: Path, weeks: int = 1) -> str:
    """Generate a human-readable Markdown digest of the last N weeks."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(weeks=weeks)

    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))
    recent = []
    for e in events:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
            if ts >= cutoff:
                recent.append(e)
        except (KeyError, ValueError):
            continue

    # Build digest
    week_label = now.strftime("%Y-W%W")
    lines = [
        f"# Memory Digest: {week_label}",
        f"Generated: {now.isoformat()}",
        f"Period: {cutoff.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
        f"Events: {len(recent)}",
        "",
    ]

    # Group by type
    by_type: dict[str, list] = {}
    for e in recent:
        by_type.setdefault(e.get("type", "unknown"), []).append(e)

    for etype, group in sorted(by_type.items()):
        lines.append(f"## {etype.title()} ({len(group)})")
        lines.append("")
        for e in group:
            ts = e.get("timestamp", "?")[:10]
            summary = _summarize_data(e.get("data", {}))
            lines.append(f"- **{ts}** — {summary}")
        lines.append("")

    # Integrity footer
    last_hash = get_last_hash(vault) if recent else "n/a"
    lines.append("---")
    lines.append(f"Chain head: `{last_hash[:16]}...`")
    lines.append(f"Total events in vault: {len(events)}")

    digest_text = "\n".join(lines) + "\n"

    # Save to digests/
    digest_file = vault_path(vault, "digests", f"{week_label}.md")
    digest_file.write_text(digest_text, encoding="utf-8")
    print(f"Digest written: {digest_file}")
    return digest_text


def _summarize_data(data: dict) -> str:
    """Best-effort one-line summary of event data."""
    for key in ["summary", "title", "name", "description", "reason", "content"]:
        if key in data:
            val = str(data[key])
            return val[:100] + ("..." if len(val) > 100 else "")
    s = json.dumps(data, ensure_ascii=False)
    return s[:100] + ("..." if len(s) > 100 else "")


# ---------------------------------------------------------------------------
# Markdown Export
# ---------------------------------------------------------------------------
def export_markdown(vault: Path) -> str:
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))
    meta_file = vault_path(vault, "psmc.json")
    meta = json.loads(meta_file.read_text(encoding="utf-8")) if meta_file.exists() else {}

    lines = [
        f"# Sovereign Memory Export",
        f"Vault version: {meta.get('version', '?')}",
        f"Created: {meta.get('created', '?')}",
        f"Events: {len(events)}",
        f"Exported: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]

    for e in events:
        ts = e.get("timestamp", "?")[:19]
        lines.append(f"## [{e.get('seq', '?')}] {e.get('type', '?').title()} — {ts}")
        lines.append("")
        lines.append(f"ID: `{e.get('id', '?')}`")
        lines.append(f"Hash: `{e.get('hash', '?')[:16]}...`")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(e.get("data", {}), indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Key Rotation
# ---------------------------------------------------------------------------
def rotate_key(vault: Path) -> None:
    """Rotate signing key. Retire old key, generate new one, log migration event."""
    old_pub = load_public_key(vault)
    old_fp = key_fingerprint(old_pub)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

    # Retire old keys
    retired_dir = vault_path(vault, "keys", "retired")
    retired_dir.mkdir(parents=True, exist_ok=True)

    old_priv_path = vault_path(vault, "keys", "active.pem")
    old_pub_path = vault_path(vault, "keys", "active.pub.pem")

    old_priv_path.rename(retired_dir / f"{timestamp}_private.pem")
    old_pub_path.rename(retired_dir / f"{timestamp}_public.pub.pem")

    # Generate new keypair
    new_private = Ed25519PrivateKey.generate()
    new_public = new_private.public_key()
    new_fp = key_fingerprint(new_public)

    vault_path(vault, "keys", "active.pem").write_bytes(
        new_private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    vault_path(vault, "keys", "active.pub.pem").write_bytes(
        new_public.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )

    try:
        os.chmod(vault_path(vault, "keys", "active.pem"), 0o600)
    except OSError:
        pass

    # Update metadata
    meta_file = vault_path(vault, "psmc.json")
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    meta["key_fingerprint"] = new_fp
    meta["last_rotation"] = datetime.now(timezone.utc).isoformat()
    meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Log migration event (signed with NEW key)
    append_event(vault, "migration", {
        "action": "key_rotation",
        "old_key_fingerprint": old_fp,
        "new_key_fingerprint": new_fp,
        "reason": "scheduled rotation",
        "retired_key_path": f"keys/retired/{timestamp}_public.pub.pem",
    })

    print(f"Key rotated successfully")
    print(f"  Old fingerprint: {old_fp}")
    print(f"  New fingerprint: {new_fp}")
    print(f"  Retired keys in: keys/retired/")


# ---------------------------------------------------------------------------
# Reducer Integration
# ---------------------------------------------------------------------------
def compute_vault_state(vault: Path) -> dict:
    """Run the Provara reducer over PSMC events to derive current state (optimized)."""
    events_file = vault_path(vault, "events", "events.ndjson")
    if not events_file.exists():
        return {}

    reducer = SovereignReducerV0()
    
    # 1. Try to load latest checkpoint
    cp_dict = load_latest_checkpoint(vault)
    if cp_dict:
        # Load active public key for verification
        active_pub = load_public_key(vault)
        if verify_checkpoint(cp_dict, active_pub):
            # Load state
            cp_state = cp_dict["state"]
            reducer.state["canonical"] = cp_state.get("canonical", {})
            reducer.state["local"] = cp_state.get("local", {})
            reducer.state["contested"] = cp_state.get("contested", {})
            reducer.state["archived"] = cp_state.get("archived", {})
            
            meta_p = cp_state.get("metadata_partial", {})
            reducer.state["metadata"]["last_event_id"] = meta_p.get("last_event_id")
            reducer.state["metadata"]["event_count"] = meta_p.get("event_count", 0)
            reducer.state["metadata"]["current_epoch"] = meta_p.get("current_epoch")
            reducer.state["metadata"]["reducer"] = meta_p.get("reducer")
            reducer.state["metadata"]["state_hash"] = reducer._compute_state_hash()

    # 2. Replay events after checkpoint
    psmc_events = _read_ndjson(events_file)
    last_id = reducer.state["metadata"]["last_event_id"]
    
    start_idx = 0
    if last_id:
        for i, pe in enumerate(psmc_events):
            if (pe.get("hash") or pe.get("id")) == last_id:
                start_idx = i + 1
                break
    
    provara_events = []
    for pe in psmc_events[start_idx:]:
        # Map PSMC types to Provara types
        p_type = "OBSERVATION"
        if pe["type"] in ["belief", "decision", "reflection"]:
            p_type = "ASSERTION"
        elif pe["type"] == "correction":
            p_type = "ASSERTION"

        data = pe.get("data", {})
        subject = data.get("subject") or data.get("title") or data.get("name") or "psmc_node"

        provara_events.append({
            "type": p_type,
            "event_id": pe.get("hash") or pe.get("id"),
            "actor": "psmc_user",
            "payload": {
                "subject": str(subject),
                "predicate": pe["type"],
                "value": data,
                "timestamp": pe.get("timestamp"),
                "confidence": _safe_float(data.get("confidence"), 0.5 if p_type == "ASSERTION" else 1.0)
            }
        })

    reducer.apply_events(provara_events)
    return reducer.export_state()


def checkpoint_vault(vault: Path) -> dict:
    """Create and sign a new state checkpoint."""
    state = compute_vault_state(vault)
    priv = load_private_key(vault)
    pub = priv.public_key()
    pub_bytes = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    kid = key_id_from_public_bytes(pub_bytes)
    
    cp = create_checkpoint(vault, state, priv, kid)
    cp_path = save_checkpoint(vault, cp)
    
    return {"path": str(cp_path), "event_count": cp.event_count}


# ---------------------------------------------------------------------------
# Sync Integration
# ---------------------------------------------------------------------------
def sync_vaults(local_vault: Path, remote_vault: Path) -> dict:
    """
    Sync events and chain entries from a remote vault.
    Uses a union-merge strategy with deduplication by event ID.
    """
    local_events_file = vault_path(local_vault, "events", "events.ndjson")
    remote_events_file = vault_path(remote_vault, "events", "events.ndjson")
    local_chain_file = vault_path(local_vault, "chain", "chain.ndjson")
    remote_chain_file = vault_path(remote_vault, "chain", "chain.ndjson")

    if not remote_events_file.exists():
        return {"error": f"Remote vault events not found: {remote_events_file}"}

    # Load all
    local_events = _read_ndjson(local_events_file)
    remote_events = _read_ndjson(remote_events_file)
    local_chain = _read_ndjson(local_chain_file)
    remote_chain = _read_ndjson(remote_chain_file)

    # Dedup by PSMC 'id' (UUID)
    seen_ids = {e.get("id") for e in local_events if e.get("id")}
    
    new_events = []
    new_chain_map = {} # hash -> chain_entry
    
    # Map all chain entries by hash for easy lookup
    for c in local_chain + remote_chain:
        h = c.get("hash")
        if h:
            new_chain_map[h] = c

    for e in remote_events:
        eid = e.get("id")
        if eid and eid not in seen_ids:
            new_events.append(e)
            seen_ids.add(eid)

    if not new_events:
        return {"success": True, "merged": 0}

    # Combine and sort by timestamp
    all_events = local_events + new_events
    all_events.sort(key=lambda e: e.get("timestamp", ""))

    # Re-sequence
    for i, e in enumerate(all_events):
        e["seq"] = i

    # Build updated chain
    all_chain = []
    for i, e in enumerate(all_events):
        h = e.get("hash")
        chain_entry = new_chain_map.get(h)
        if chain_entry:
            chain_entry["seq"] = i
            all_chain.append(chain_entry)
        else:
            # Should not happen if vaults are healthy
            pass

    # Write back
    _write_ndjson(local_events_file, all_events)
    _write_ndjson(local_chain_file, all_chain)

    return {"success": True, "merged": len(new_events)}


def _write_ndjson(filepath: Path, entries: list[dict]) -> None:
    """Write list of dicts to NDJSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(canonical_dumps(entry) + "\n")


def query_timeline(
    vault: Path,
    event_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Query vault events with filters."""
    events = _read_ndjson(vault_path(vault, "events", "events.ndjson"))

    if event_type:
        events = [e for e in events if e.get("type") == event_type]

    if start_time:
        start_dt = datetime.fromisoformat(start_time)
        events = [e for e in events if datetime.fromisoformat(e["timestamp"]) >= start_dt]

    if end_time:
        end_dt = datetime.fromisoformat(end_time)
        events = [e for e in events if datetime.fromisoformat(e["timestamp"]) <= end_dt]

    if limit:
        events = events[-limit:]

    return events


def list_conflicts(vault: Path) -> Dict[str, Any]:
    """List all contested beliefs in the vault."""
    state = compute_vault_state(vault)
    return state.get("contested", {})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="psmc",
        description="Personal Sovereign Memory Container — append-only event log with integrity",
    )
    parser.add_argument("--vault", default="./vault", help="Path to vault directory")
    sub = parser.add_subparsers(dest="command")

    # init
    sub.add_parser("init", help="Create a new vault")

    # append
    p_append = sub.add_parser("append", help="Append a new event")
    p_append.add_argument("--type", required=True, choices=VALID_TYPES, help="Event type")
    p_append.add_argument("--data", required=True, help="JSON object for event data")
    p_append.add_argument("--tags", nargs="*", help="Optional tags")
    p_append.add_argument("--provara", action="store_true", help="Also emit Provara-native event")

    # verify
    p_verify = sub.add_parser("verify", help="Verify full chain integrity")
    p_verify.add_argument("--verbose", "-v", action="store_true")

    # show
    p_show = sub.add_parser("show", help="Display events")
    p_show.add_argument("--last", type=int, help="Show last N events")
    p_show.add_argument("--type", dest="filter_type", help="Filter by event type")

    # digest
    p_digest = sub.add_parser("digest", help="Generate weekly digest")
    p_digest.add_argument("--weeks", type=int, default=1, help="Number of weeks to cover")

    # export
    p_export = sub.add_parser("export", help="Export as Markdown")
    p_export.add_argument("--format", default="markdown", choices=["markdown"])

    # state
    sub.add_parser("state", help="Compute and show derived belief state")

    # sync
    p_sync = sub.add_parser("sync", help="Sync with another PSMC vault")
    p_sync.add_argument("remote_vault", help="Path to remote vault directory")

    # checkpoint
    sub.add_parser("checkpoint", help="Sign and save a new state snapshot")

    # rotate-key
    sub.add_parser("rotate-key", help="Rotate signing key")

    # seed (convenience: populate example entries)
    sub.add_parser("seed", help="Populate vault with example entries")

    args = parser.parse_args()
    vault = Path(args.vault).resolve()

    if args.command == "init":
        init_vault(vault)

    elif args.command == "append":
        try:
            data = json.loads(args.data)
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)
        event = append_event(vault, args.type, data, args.tags, emit_provara=args.provara)
        print(f"Appended seq={event['seq']} type={event['type']} hash={event['hash'][:16]}...")

    elif args.command == "verify":
        ok = verify_chain(vault, verbose=args.verbose)
        sys.exit(0 if ok else 1)

    elif args.command == "show":
        show_events(vault, last_n=args.last, event_type=args.filter_type)

    elif args.command == "digest":
        text = generate_digest(vault, weeks=args.weeks)
        print(text)

    elif args.command == "export":
        text = export_markdown(vault)
        out = vault / "export.md"
        out.write_text(text, encoding="utf-8")
        print(f"Exported to: {out}")

    elif args.command == "state":
        state = compute_vault_state(vault)
        print(json.dumps(state, indent=2))

    elif args.command == "sync":
        remote_vault = Path(args.remote_vault).resolve()
        result = sync_vaults(vault, remote_vault)
        if "error" in result:
            print(f"ERROR: {result['error']}", file=sys.stderr)
            sys.exit(1)
        print(f"Sync complete. Merged {result['merged']} new events.")

    elif args.command == "checkpoint":
        result = checkpoint_vault(vault)
        print(f"Checkpoint saved: {result['path']} (events={result['event_count']})")

    elif args.command == "rotate-key":
        rotate_key(vault)

    elif args.command == "seed":
        seed_examples(vault)

    else:
        parser.print_help()


# ---------------------------------------------------------------------------
# Example Seeding
# ---------------------------------------------------------------------------
def seed_examples(vault: Path) -> None:
    """Append example entries for each major event type."""
    examples = [
        ("identity", {
            "name": "Alice Nakamoto",
            "born": "1990-03-15",
            "summary": "Founder, systems architect, sovereign tech builder",
            "values": ["truth", "durability", "sovereignty", "simplicity"],
        }),
        ("decision", {
            "title": "Adopt append-only architecture for memory system",
            "context": "Evaluated relational DB, flat files, and event log approaches",
            "choice": "NDJSON event log with hash chain",
            "reason": "Maximum durability, portability, and simplicity. No server dependency.",
            "alternatives_rejected": ["SQLite", "PostgreSQL", "custom binary format"],
            "reversible": False,
        }),
        ("belief", {
            "domain": "technology",
            "statement": "Cryptographic integrity is more important than encryption for personal records",
            "confidence": 0.85,
            "evidence": "Encryption keys get lost over decades; tamper-evidence preserves trust",
            "last_reviewed": "2025-01-15",
        }),
        ("promotion", {
            "title": "Senior Systems Architect",
            "organization": "Sovereign Systems Inc.",
            "effective_date": "2025-06-01",
            "summary": "Promoted to lead all infrastructure and protocol development",
            "prior_role": "Systems Engineer",
        }),
        ("reflection", {
            "summary": "First week running the sovereign memory system",
            "insight": "The constraint of append-only changes how you think about records. "
                       "You can't fix the past, only annotate it. This is a feature.",
            "mood": "focused",
        }),
        ("correction", {
            "corrects_event_seq": 2,
            "field": "confidence",
            "old_value": 0.85,
            "new_value": 0.90,
            "reason": "After 6 months of use, confidence in this belief increased",
        }),
    ]

    for etype, data in examples:
        event = append_event(vault, etype, data)
        print(f"  Seeded: seq={event['seq']} type={etype}")

    print(f"\n{len(examples)} example events appended.")


if __name__ == "__main__":
    main()
