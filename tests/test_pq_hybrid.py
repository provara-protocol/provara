import pytest
import base64
import json
from provara.pq_hybrid import (
    generate_hybrid_keypair, 
    hybrid_sign, 
    hybrid_verify, 
    HybridSignature
)

def test_hybrid_sign_verify_roundtrip():
    keypair = generate_hybrid_keypair()
    message = b"Test message for PQ hybrid signature"
    
    # Sign
    signature = hybrid_sign(message, keypair)
    assert signature.scheme == "ed25519+mldsa65"
    assert len(signature.ed25519_signature) == 64
    
    # Verify
    assert hybrid_verify(message, signature, keypair.public_key) is True

def test_hybrid_verify_fails_on_tampered_ed25519():
    keypair = generate_hybrid_keypair()
    message = b"Test message"
    signature = hybrid_sign(message, keypair)
    
    # Tamper Ed25519
    tampered_ed = list(signature.ed25519_signature)
    tampered_ed[0] ^= 0xFF
    signature.ed25519_signature = bytes(tampered_ed)
    
    assert hybrid_verify(message, signature, keypair.public_key) is False

def test_hybrid_verify_fails_on_tampered_mldsa():
    keypair = generate_hybrid_keypair()
    message = b"Test message"
    signature = hybrid_sign(message, keypair)
    
    # Tamper ML-DSA (using our stub's 'INVALID' logic)
    signature.mldsa_signature = b"INVALID"
    
    assert hybrid_verify(message, signature, keypair.public_key) is False

def test_hybrid_verify_fails_on_wrong_message():
    keypair = generate_hybrid_keypair()
    signature = hybrid_sign(b"Message A", keypair)
    
    assert hybrid_verify(b"Message B", signature, keypair.public_key) is False

def test_backward_compatibility_ed25519_only():
    keypair = generate_hybrid_keypair()
    message = b"Backward compat test"
    
    # Phase 1 verifier (classical) checks Ed25519 only
    signature = hybrid_sign(message, keypair)
    
    # Verify Ed25519 signature separately
    from cryptography.hazmat.primitives.asymmetric import ed25519
    keypair.public_key.ed_pk.verify(signature.ed25519_signature, message) # Should not raise

def test_hybrid_signature_to_dict():
    keypair = generate_hybrid_keypair()
    message = b"Metadata test"
    signature = hybrid_sign(message, keypair)
    
    d = signature.to_dict()
    assert "signature" in d
    assert "signature_pq" in d
    assert "signature_scheme" in d
    assert d["signature_scheme"] == "ed25519+mldsa65"
    
    # Roundtrip from dict
    sig_restored = HybridSignature(
        ed25519_signature=base64.b64decode(d["signature"]),
        mldsa_signature=base64.b64decode(d["signature_pq"]),
        scheme=d["signature_scheme"]
    )
    assert hybrid_verify(message, sig_restored, keypair.public_key) is True
