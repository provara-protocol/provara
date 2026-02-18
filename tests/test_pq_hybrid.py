import pytest
import base64
from provara.pq_hybrid import generate_hybrid_keypair, hybrid_sign, hybrid_verify, HybridSignature

def test_hybrid_sign_verify_success():
    keypair = generate_hybrid_keypair()
    message = b"Quantum-resistant event data"
    
    sig = hybrid_sign(message, keypair)
    assert sig.scheme == "ed25519+mldsa65"
    assert len(sig.ed25519_signature) == 64
    
    assert hybrid_verify(message, sig, keypair.public_key) is True

def test_hybrid_verify_ed25519_failure():
    keypair = generate_hybrid_keypair()
    message = b"Original data"
    sig = hybrid_sign(message, keypair)
    
    assert hybrid_verify(b"Tampered data", sig, keypair.public_key) is False

def test_hybrid_verify_mldsa_failure():
    keypair = generate_hybrid_keypair()
    message = b"Data"
    sig = hybrid_sign(message, keypair)
    
    # Tamper with PQ signature (using our stub's 'INVALID' flag)
    sig.mldsa_signature = b"INVALID"
    assert hybrid_verify(message, sig, keypair.public_key) is False

def test_backward_compatibility_ed25519_only():
    keypair = generate_hybrid_keypair()
    message = b"Compatibility test"
    sig = hybrid_sign(message, keypair)
    
    # A Phase 1 verifier only checks the 'signature' field (Ed25519)
    # We can simulate this by using standard Ed25519 verification on that part.
    from cryptography.hazmat.primitives.asymmetric import ed25519
    keypair.public_key.ed_pk.verify(sig.ed25519_signature, message) # Should not raise

def test_hybrid_event_serialization():
    keypair = generate_hybrid_keypair()
    message = b"Roundtrip test"
    sig = hybrid_sign(message, keypair)
    
    event_dict = sig.to_dict()
    assert "signature" in event_dict
    assert "signature_pq" in event_dict
    assert event_dict["signature_scheme"] == "ed25519+mldsa65"
    
    # Restore from dict
    restored_sig = HybridSignature(
        ed25519_signature=base64.b64decode(event_dict["signature"]),
        mldsa_signature=base64.b64decode(event_dict["signature_pq"]),
        scheme=event_dict["signature_scheme"]
    )
    
    assert hybrid_verify(message, restored_sig, keypair.public_key) is True
