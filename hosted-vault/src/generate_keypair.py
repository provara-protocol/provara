#!/usr/bin/env python3
"""
Provara Hosted Vault - Key Generation Utility

Generates Ed25519 keypairs for new vaults with Provara-compatible fingerprints.
"""

import json
import sys
from pathlib import Path

# Add Provara src to path
project_root = Path(__file__).resolve().parent.parent.parent
src_dir = project_root / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

try:
    from provara.backpack_signing import key_id_from_public_bytes
except ImportError:
    # Fallback if provara not installed
    import hashlib

    def key_id_from_public_bytes(public_bytes: bytes) -> str:
        """Generate bp1_ prefix + 16 hex chars from public key."""
        hash_digest = hashlib.sha256(public_bytes).hexdigest()
        return f"bp1_{hash_digest[:16]}"


def generate_vault_keypair() -> dict:
    """Generate a new Ed25519 keypair for a vault."""
    # Generate keypair
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()

    # PEM encoding
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Key fingerprint (Provara-compatible)
    public_bytes = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    key_id = key_id_from_public_bytes(public_bytes)

    return {
        "key_id": key_id,
        "public_key_pem": public_pem.decode("utf-8"),
        "private_key_pem": private_pem.decode("utf-8"),
        "algorithm": "Ed25519",
        "created_at": json.dumps({"_comment": "Set by server at creation time"})
    }


def main():
    """Generate and output a new keypair."""
    if len(sys.argv) > 1 and sys.argv[1] == "--help":
        print("Provara Vault Key Generator")
        print()
        print("Usage:")
        print("  python generate_keypair.py          # Output JSON to stdout")
        print("  python generate_keypair.py --save   # Save to keypair.json")
        print()
        print("Output:")
        print("  JSON with key_id, public_key_pem, private_key_pem")
        sys.exit(0)

    keypair = generate_vault_keypair()

    if len(sys.argv) > 1 and sys.argv[1] == "--save":
        output_file = Path("keypair.json")
        output_file.write_text(json.dumps(keypair, indent=2), encoding="utf-8")
        print(f"Keypair saved to: {output_file}")
        print(f"Key ID: {keypair['key_id']}")
    else:
        # Output JSON to stdout
        print(json.dumps(keypair, indent=2))


if __name__ == "__main__":
    main()
