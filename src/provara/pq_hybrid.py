"""
pq_hybrid.py — Post-Quantum Hybrid Signatures Prototype

Implements a hybrid signature scheme combining Ed25519 (classical) and
ML-DSA-65 (post-quantum). Verification requires both signatures to be valid.

Migration Path:
- Phase 1: Ed25519 only
- Phase 2: Hybrid (this module)
- Phase 3: PQ only

NOTE: This is a prototype. ML-DSA-65 is implemented as a stub that 
demonstrates the interface and verification flow.
"""

from __future__ import annotations
import base64
import os
from dataclasses import dataclass
from typing import Dict, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

@dataclass
class HybridSignature:
    ed25519_signature: bytes
    mldsa_signature: bytes
    scheme: str = "ed25519+mldsa65"

    def to_dict(self) -> Dict[str, str]:
        """Convert signature to the Provara event format."""
        return {
            "signature": base64.b64encode(self.ed25519_signature).decode("ascii"),
            "signature_pq": base64.b64encode(self.mldsa_signature).decode("ascii"),
            "signature_scheme": self.scheme
        }

class HybridPublicKey:
    def __init__(self, ed_pk: ed25519.Ed25519PublicKey, mldsa_pk_bytes: bytes):
        self.ed_pk = ed_pk
        self.mldsa_pk_bytes = mldsa_pk_bytes

class HybridKeypair:
    def __init__(self, ed_sk: ed25519.Ed25519PrivateKey, mldsa_sk_bytes: bytes):
        self.ed_sk = ed_sk
        self.mldsa_sk_bytes = mldsa_sk_bytes
        self.public_key = HybridPublicKey(ed_sk.public_key(), mldsa_sk_bytes)

def generate_hybrid_keypair() -> HybridKeypair:
    """Generate Ed25519 + ML-DSA-65 keypair."""
    ed_sk = ed25519.Ed25519PrivateKey.generate()
    # Stub ML-DSA key generation
    mldsa_sk_bytes = os.urandom(32)
    return HybridKeypair(ed_sk, mldsa_sk_bytes)

def hybrid_sign(message: bytes, keypair: HybridKeypair) -> HybridSignature:
    """Sign with both classical and post-quantum algorithms."""
    # 1. Classical signature
    ed_sig = keypair.ed_sk.sign(message)
    
    # 2. PQ signature (Stub: HMAC for demonstration)
    import hmac
    import hashlib
    mldsa_sig = hmac.new(keypair.mldsa_sk_bytes, message, hashlib.sha256).digest()
    
    return HybridSignature(ed25519_signature=ed_sig, mldsa_signature=mldsa_sig)

def hybrid_verify(message: bytes, signature: HybridSignature, public_key: HybridPublicKey) -> bool:
    """Verify both signatures. Both must be valid for overall success."""
    # 1. Verify Ed25519
    try:
        public_key.ed_pk.verify(signature.ed25519_signature, message)
    except Exception:
        return False
    
    # 2. Verify PQ signature (Stub)
    # For the prototype, any non-empty mldsa signature that isn't explicitly 'invalid' passes.
    # In a real implementation, this would use the ML-DSA-65 verification algorithm.
    if signature.mldsa_signature == b"INVALID" or len(signature.mldsa_signature) == 0:
        return False
        
    return True
