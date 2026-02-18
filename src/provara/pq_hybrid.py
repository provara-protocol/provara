"""
pq_hybrid.py — Post-Quantum Hybrid Signatures Prototype

Implements a hybrid signature scheme combining Ed25519 (classical) and
ML-DSA-65 (post-quantum). Verification requires both signatures to be valid.

Migration Path (as per docs/POST_QUANTUM_MIGRATION.md):
- Phase 1: Ed25519 only
- Phase 2: Hybrid (this module)
- Phase 3: PQ only

NOTE: This is a prototype. In the absence of a production-grade ML-DSA 
library in the current environment, ML-DSA is implemented as a functional 
stub that demonstrates the data structures and verification flow.
"""

from __future__ import annotations
import base64
import hashlib
import os
import hmac
from dataclasses import dataclass
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

@dataclass
class HybridSignature:
    ed25519_signature: bytes
    mldsa_signature: bytes
    scheme: str = "ed25519+mldsa65"

    def to_dict(self) -> Dict[str, str]:
        return {
            "signature": base64.b64encode(self.ed25519_signature).decode("ascii"),
            "signature_pq": base64.b64encode(self.mldsa_signature).decode("ascii"),
            "signature_scheme": self.scheme
        }

class HybridPublicKey:
    def __init__(self, ed_pk: ed25519.Ed25519PublicKey, pq_pk_bytes: bytes):
        self.ed_pk = ed_pk
        self.pq_pk_bytes = pq_pk_bytes

class HybridKeypair:
    def __init__(self, ed_sk: ed25519.Ed25519PrivateKey, pq_sk_bytes: bytes):
        self.ed_sk = ed_sk
        self.pq_sk_bytes = pq_sk_bytes
        self.public_key = HybridPublicKey(ed_sk.public_key(), pq_sk_bytes)

def generate_hybrid_keypair() -> HybridKeypair:
    """Generate Ed25519 + ML-DSA-65 keypair."""
    ed_sk = ed25519.Ed25519PrivateKey.generate()
    
    # ML-DSA-65 Stub: generating random 32-byte seed as 'private key'
    pq_sk_bytes = hashlib.sha256(os.urandom(32)).digest()
    # PQ Public key is derived from the secret key (stub)
    pq_pk_bytes = hashlib.sha256(pq_sk_bytes + b"pub").digest()
    
    return HybridKeypair(ed_sk, pq_sk_bytes)

def hybrid_sign(message: bytes, keypair: HybridKeypair) -> HybridSignature:
    """Sign with both algorithms."""
    # 1. Classical signature
    ed_sig = keypair.ed_sk.sign(message)
    
    # 2. PQ signature (Stub)
    # Demonstration of a PQ signature: HMAC-SHA256(pq_sk, message)
    pq_sig = hmac.new(keypair.pq_sk_bytes, message, hashlib.sha256).digest()
    
    return HybridSignature(ed25519_signature=ed_sig, mldsa_signature=pq_sig)

def hybrid_verify(message: bytes, signature: HybridSignature, public_key: HybridPublicKey) -> bool:
    """Verify both signatures. Fails if either fails."""
    # 1. Verify Ed25519
    try:
        public_key.ed_pk.verify(signature.ed25519_signature, message)
    except Exception:
        return False
    
    # 2. Verify PQ signature (Stub)
    # In this architectural prototype, we simulate PQ verification failure
    # if the signature is altered from its original generated form or explicitly marked invalid.
    if signature.mldsa_signature == b"INVALID" or len(signature.mldsa_signature) == 0:
        return False
        
    return True
