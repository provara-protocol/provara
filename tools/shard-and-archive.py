#!/usr/bin/env python3
import argparse
import json
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path("/home/syncshadow7/.provara/agent-memory")
SQLITE_FILE = VAULT_ROOT / "vault.sqlite"
ARCHIVE_ROOT = VAULT_ROOT / "archives"
LOG_FILE = Path("/home/syncshadow7/provara/logs/vault-maintenance.log")

sys.path.append("/home/syncshadow7/provara/tools/psmc")
import psmc

def log(msg: str) -> None:
    ts = datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] SHARD-ARCHIVE: {msg}\n")
    except Exception:
        pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, help="Force specific year (default: last completed year)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    log("Yearly sharding & archival started" + (" (DRY-RUN)" if args.dry_run else ""))

    ARCHIVE_ROOT.mkdir(exist_ok=True)

    # Determine year to shard
    target_year = args.year or (datetime.now().year - 1)
    # SQLite timestamp format check
    start_ts = f"{target_year}-01-01T00:00:00"
    end_ts = f"{target_year + 1}-01-01T00:00:00"

    shard_name = f"vault-{target_year}.sqlite"
    shard_path = ARCHIVE_ROOT / shard_name

    if args.dry_run:
        print(f"DRY-RUN: Would create shard {shard_name} for {target_year}")
        return

    # Extract year into new DB (using SQLite ATTACH + INSERT)
    # Targeting 'events' table
    cmd = f"""
    sqlite3 {SQLITE_FILE} "
        ATTACH DATABASE '{shard_path}' AS shard;
        CREATE TABLE shard.events AS SELECT * FROM events 
            WHERE timestamp >= '{start_ts}' AND timestamp < '{end_ts}';
        DETACH DATABASE shard;
    "
    """
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print(f"Error creating shard: {e.stderr}")
        sys.exit(1)

    # Check if any records were actually moved
    record_count = subprocess.check_output(["sqlite3", str(shard_path), "SELECT COUNT(*) FROM events;"]).decode().strip()
    if int(record_count) == 0:
        print(f"⚠️ No records found for year {target_year}. Shard is empty.")
        # Optional: remove empty shard
        # shard_path.unlink()
        # return

    # Sign the shard file itself
    with open(shard_path, "rb") as f:
        shard_hash = subprocess.check_output(["sha256sum"], stdin=f).decode().split()[0]

    # Create proper PSMC event
    archive_data = {
        "year": target_year,
        "shard_file": shard_name,
        "sha256": shard_hash,
        "record_count": int(record_count)
    }
    
    # PSMC append logic
    prev_hash = psmc.get_last_hash(VAULT_ROOT)
    with open(VAULT_ROOT / "events/events.ndjson", "r") as f:
        seq = len([l for l in f if l.strip()])
        
    archive_event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "yearly_shard_archive",
        "data": archive_data,
        "seq": seq,
        "prev_hash": prev_hash,
        "id": str(uuid.uuid4())
    }
    
    h = psmc.compute_event_hash(archive_event)
    archive_event["hash"] = h
    
    private_key = psmc.load_private_key(VAULT_ROOT)
    sig = psmc.sign_data(private_key, h)
    
    chain_entry = {
        "seq": seq,
        "hash": h,
        "prev_hash": prev_hash,
        "sig": sig,
        "key_fp": psmc.key_fingerprint(private_key.public_key())
    }

    # Persist event and chain
    with open(VAULT_ROOT / "events/events.ndjson", "a") as f:
        f.write(psmc.canonical_dumps(archive_event) + "\n")
    with open(VAULT_ROOT / "chain/chain.ndjson", "a") as f:
        f.write(psmc.canonical_dumps(chain_entry) + "\n")

    # Compress
    tar_path = ARCHIVE_ROOT / f"vault-{target_year}.tar.gz"
    subprocess.run([
        "tar", "-czf", str(tar_path), "-C", str(ARCHIVE_ROOT), shard_name
    ], check=True)

    log(f"Year {target_year} shard created, signed, and archived ({record_count} records)")

    # Trigger verification
    VERIFY_SCRIPT = Path("/home/syncshadow7/provara/tools/verify-and-optimize.sh")
    if VERIFY_SCRIPT.exists():
        subprocess.run([str(VERIFY_SCRIPT), str(VAULT_ROOT)], check=True)

    print(f"✅ Year {target_year} shard complete. Archive ready at {tar_path}")

if __name__ == "__main__":
    main()
