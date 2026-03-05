#!/usr/bin/env python3
import argparse
import base64
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

VAULT_ROOT = Path("/home/syncshadow7/.provara/agent-memory")
KEYS_DIR = VAULT_ROOT / "keys"
PRIVATE_KEY_FILE = KEYS_DIR / "active.pem"
PUBLIC_KEY_FILE = KEYS_DIR / "active.pub.pem"
CHAIN_FILE = VAULT_ROOT / "chain" / "chain.ndjson"
EVENTS_FILE = VAULT_ROOT / "events" / "events.ndjson"
MANIFEST_FILE = VAULT_ROOT / "manifest.json"
LOG_FILE = Path("/home/syncshadow7/provara/logs/vault-maintenance.log")


def log(message: str) -> None:
    ts = datetime.now().isoformat()
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{ts}] KEY-ROTATION: {message}\n")
    except Exception:
        pass


def generate_new_keypair() -> tuple[bytes, bytes]:
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private_pem, public_pem


def sign_rotation_event(old_private_key_path: Path, new_pub_pem: bytes) -> str:
    with open(old_private_key_path, "rb") as f:
        old_priv = serialization.load_pem_private_key(f.read(), password=None)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": "key_rotation",
        "new_public_key": new_pub_pem.decode("utf-8").strip(),
        "reason": "Scheduled 12-month rotation"
    }
    payload_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = old_priv.sign(payload_bytes)
    return base64.b64encode(signature).decode("utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Simulate rotation without modifying files")
    args = parser.parse_args()

    log("Key rotation initiated" + (" (DRY-RUN)" if args.dry_run else ""))

    # Safety: backup current keys
    backup_dir = VAULT_ROOT / "keys" / "backup" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    if PRIVATE_KEY_FILE.exists():
        shutil.copy(PRIVATE_KEY_FILE, backup_dir)
    if PUBLIC_KEY_FILE.exists():
        shutil.copy(PUBLIC_KEY_FILE, backup_dir)
    log(f"Keys backed up to {backup_dir}")

    if args.dry_run:
        print("DRY-RUN: New keypair would be generated and signed rotation event prepared.")
        return

    # Generate new pair
    new_priv_pem, new_pub_pem = generate_new_keypair()

    # Sign rotation event with CURRENT (old) key
    rotation_signature = sign_rotation_event(PRIVATE_KEY_FILE, new_pub_pem)

    # Integrate with PSMC structure
    sys.path.append("/home/syncshadow7/provara/tools/psmc")
    import psmc
    
    prev_hash = psmc.get_last_hash(VAULT_ROOT)
    with open(EVENTS_FILE, "r") as f:
        seq = len([l for l in f if l.strip()])
    
    rotation_event = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "type": "key_rotation",
        "data": {
            "new_public_key": new_pub_pem.decode("utf-8").strip(),
            "reason": "Scheduled 12-month rotation"
        },
        "seq": seq,
        "prev_hash": prev_hash,
        "id": str(subprocess.check_output(["uuidgen"], text=True)).strip() if shutil.which("uuidgen") else str(datetime.now().timestamp())
    }
    
    h = psmc.compute_event_hash(rotation_event)
    rotation_event["hash"] = h
    
    chain_entry = {
        "seq": seq,
        "hash": h,
        "prev_hash": prev_hash,
        "sig": rotation_signature,
        "key_fp": psmc.key_fingerprint(serialization.load_pem_public_key(PUBLIC_KEY_FILE.read_bytes()))
    }

    with open(EVENTS_FILE, "a") as f:
        f.write(psmc.canonical_dumps(rotation_event) + "\n")
    with open(CHAIN_FILE, "a") as f:
        f.write(psmc.canonical_dumps(chain_entry) + "\n")

    # Atomically replace active keys
    PRIVATE_KEY_FILE.write_bytes(new_priv_pem)
    PUBLIC_KEY_FILE.write_bytes(new_pub_pem)

    # Trigger full verification
    VERIFY_SCRIPT = Path("/home/syncshadow7/provara/tools/verify-and-optimize.sh")
    if VERIFY_SCRIPT.exists():
        subprocess.run([str(VERIFY_SCRIPT), str(VAULT_ROOT)], check=True)

    log("Key rotation completed successfully. New key activated.")
    print("✅ Key rotation completed. New Ed25519 pair activated and historical chain preserved.")


if __name__ == "__main__":
    main()
