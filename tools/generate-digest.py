#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import subprocess
import sys
import uuid
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization

# Defaults
DEFAULT_VAULT_ROOT = Path("/home/syncshadow7/.provara/agent-memory")
VERIFY_SCRIPT = Path("/home/syncshadow7/provara/tools/verify-and-optimize.sh")
LOG_FILE = Path("/home/syncshadow7/provara/logs/vault-maintenance.log")


def log(message: str) -> None:
    timestamp = datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] DIGEST: {message}\n")
    except Exception:
        pass  # Fail silently if log not writable


def load_recent_events(vault_root: Path, days: int = 7):
    events_file = vault_root / "events" / "events.ndjson"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events = []
    if not events_file.exists():
        return events
    with open(events_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
                ts_str = ev.get("timestamp") or ev.get("timestamp_utc")
                if ts_str:
                    # Handle Z suffix
                    clean_ts = ts_str.replace("Z", "+00:00")
                    ts = datetime.fromisoformat(clean_ts)
                    if ts > cutoff:
                        events.append(ev)
            except Exception:
                continue
    return events


def generate_digest_prompt(events):
    event_summaries = []
    for e in events:
        data = e.get("data", e.get("payload", {})) # Support both global and project vault formats
        # Filter out large data
        data_str = str(data)[:100] + "..." if len(str(data)) > 100 else str(data)
        event_summaries.append(f"- {e.get('timestamp') or e.get('timestamp_utc')} [{e.get('type')}]: {data_str}")
        
    events_text = "\n".join(event_summaries)
    return f"""You are the sovereign archivist for a cryptographically secured agent memory vault.
Summarize these {len(events)} events from the past week into a JSON digest.

REQUIRED JSON FORMAT:
{{
  "summary": "Short overall summary",
  "milestones": ["List", "of", "achievements"],
  "outlook": "Strategic outlook"
}}

EVENTS TO SUMMARIZE:
{events_text}

JSON OUTPUT:"""


def call_llm(prompt: str, model: str = "llama3.2:3b") -> dict:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 1024},
        "format": "json"
    }
    resp = requests.post(url, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    response_text = data["response"].strip()
    return json.loads(response_text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=str, help="Path to the vault root")
    parser.add_argument("--dry-run", action="store_true", help="Generate digest but do not append")
    parser.add_argument("--model", default="llama3.2:3b", help="LLM model to use")
    args = parser.parse_args()

    vault_root = Path(args.vault) if args.vault else DEFAULT_VAULT_ROOT
    events_file = vault_root / "events" / "events.ndjson"
    chain_file = vault_root / "chain" / "chain.ndjson"

    log(f"Weekly digest generation started for vault: {vault_root}")

    events = load_recent_events(vault_root)
    if not events:
        msg = "No events in the last 7 days. Digest generation skipped."
        log(msg)
        print(msg)
        return

    print(f"🔄 Processing {len(events)} events for digest...")
    prompt = generate_digest_prompt(events)
    try:
        digest_content = call_llm(prompt, model=args.model)
    except Exception as e:
        msg = f"LLM call failed: {e}"
        log(msg)
        print(msg)
        sys.exit(1)

    digest_event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "weekly_digest",
        "data": digest_content,
        "source_events_count": len(events),
        "window_days": 7
    }

    if args.dry_run:
        print("🧪 DRY-RUN MODE — Digest content preview:")
        print(json.dumps(digest_content, indent=2))
        return

    sys.path.append("/home/syncshadow7/provara/tools/psmc")
    import psmc
    
    prev_hash = psmc.get_last_hash(vault_root)
    with open(events_file, "r") as f: 
        seq = len([l for l in f if l.strip()])
    
    digest_event["seq"] = seq
    digest_event["prev_hash"] = prev_hash
    digest_event["id"] = str(uuid.uuid4())
    h = psmc.compute_event_hash(digest_event)
    digest_event["hash"] = h
    
    private_key = psmc.load_private_key(vault_root)
    sig = psmc.sign_data(private_key, h)
    
    chain_entry = {
        "seq": seq,
        "hash": h,
        "prev_hash": prev_hash,
        "sig": sig,
        "key_fp": psmc.key_fingerprint(private_key.public_key())
    }

    with open(events_file, "a") as f:
        f.write(psmc.canonical_dumps(digest_event) + "\n")
    with open(chain_file, "a") as f:
        f.write(psmc.canonical_dumps(chain_entry) + "\n")

    # === NEW: Materialized Digest + Sub-Merkle Root ===
    digest_dir = vault_root / "digests"
    digest_file = digest_dir / f"digest-{datetime.now().strftime('%Y-W%W')}.json"
    digest_dir.mkdir(exist_ok=True)

    materialized = {
        "timestamp": digest_event["timestamp"],
        "week": datetime.now().strftime('%Y-W%W'),
        "content": digest_content,
        "source_event_count": len(events),
        "merkle_subroot": hashlib.sha256(
            psmc.canonical_dumps(digest_event).encode()
        ).hexdigest(),
        "linked_to_global_merkle": True
    }

    with open(digest_file, "w") as f:
        json.dump(materialized, f, indent=2)

    log(f"Materialized digest written: {digest_file} | Sub-Merkle: {materialized['merkle_subroot'][:16]}...")

    if VERIFY_SCRIPT.exists() and not args.vault:
        # Only run default verify script for default vault
        try:
            subprocess.run([str(VERIFY_SCRIPT), str(vault_root)], check=True, capture_output=True, text=True)
            log("Verification and optimization completed. Global manifest + Merkle root updated.")
            print("✅ Digest pipeline completed. Manifest and Merkle root updated.")
        except subprocess.CalledProcessError as e:
            log(f"Verification warning: {e.stdout} {e.stderr}")
            print("⚠️ Digest appended, but verification reported issues. Review log.")
    else:
        print("✅ Digest appended. Vault updated.")

if __name__ == "__main__":
    main()
