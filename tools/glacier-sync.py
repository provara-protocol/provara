#!/usr/bin/env python3
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

VAULT_ROOT = Path("/home/syncshadow7/.provara/agent-memory")
ARCHIVE_DIR = VAULT_ROOT / "archives"
LOG_FILE = Path("/home/syncshadow7/provara/logs/vault-maintenance.log")
CONFIG_FILE = Path("/home/syncshadow7/.provara/glacier-config.json")


def log(msg: str) -> None:
    ts = datetime.now().isoformat()
    with open(LOG_FILE, "a") as f:
        f.write(f"[{ts}] GLACIER-SYNC: {msg}\n")


def load_config() -> str:
    if not CONFIG_FILE.exists():
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        config = {"bucket": "provara-vault-backups", "prefix": "archives/"}
        CONFIG_FILE.write_text(json.dumps(config, indent=2))
        log("Created default glacier-config.json – edit bucket name")
    return json.loads(CONFIG_FILE.read_text())["bucket"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Upload even if already synced")
    args = parser.parse_args()

    bucket = load_config()
    log("Glacier sync started" + (" (DRY-RUN)" if args.dry_run else ""))

    # Ensure archive dir exists
    if not ARCHIVE_DIR.exists():
        log("Archive directory not found – skipping sync")
        return

    # Find all un-synced archives (shards + materialized digests)
    # Note: searching for .tar.gz.age as per user delivery
    archives = list(ARCHIVE_DIR.glob("*.tar.gz.age"))
    if not archives:
        print("No archives found to sync.")
        return

    for archive in sorted(archives):
        s3_key = f"archives/{archive.name}"
        marker = ARCHIVE_DIR / f"{archive.name}.synced"

        if marker.exists() and not args.force:
            continue

        if args.dry_run:
            print(f"DRY-RUN: would upload {archive} → s3://{bucket}/{s3_key}")
            continue

        # Upload to Glacier Deep Archive (cheapest long-term)
        try:
            subprocess.run([
                "aws", "s3", "cp", str(archive),
                f"s3://{bucket}/{s3_key}",
                "--storage-class", "DEEP_ARCHIVE",
                "--no-progress"
            ], check=True, capture_output=True)

            # Record ETag for future integrity
            etag_raw = subprocess.check_output([
                "aws", "s3api", "head-object",
                "--bucket", bucket, "--key", s3_key
            ])
            etag = json.loads(etag_raw.decode())["ETag"].strip('"')

            sync_event = {
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "type": "glacier_archive_sync",
                "data": {
                    "file": archive.name,
                    "s3_key": s3_key,
                    "etag": etag,
                    "storage_class": "DEEP_ARCHIVE"
                }
            }

            # Append via existing vault path
            # Using PSMC logic if available for sequence/hashing
            with open(VAULT_ROOT / "events/events.ndjson", "a") as f:
                f.write(json.dumps(sync_event) + "\n")

            marker.touch()
            log(f"Uploaded {archive.name} → Glacier (ETag: {etag[:8]}...)")

        except subprocess.CalledProcessError as e:
            log(f"Upload failed for {archive.name}: {e.stderr.decode()}")
            continue
        except Exception as e:
            log(f"An error occurred: {str(e)}")
            continue

    # Final verification trigger
    verify_script = Path("/home/syncshadow7/provara/tools/verify-and-optimize.sh")
    if verify_script.exists():
        subprocess.run([str(verify_script)], check=False)
    
    log("Glacier sync cycle completed")


if __name__ == "__main__":
    main()
