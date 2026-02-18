import pytest
import base64
from provara.wallet import export_to_solana, import_from_solana
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

def test_wallet_roundtrip():
    # 1. Generate a Provara-style private key (32-byte seed b64)
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    priv_b64 = base64.b64encode(priv_bytes).decode("utf-8")
    
    # 2. Export to Solana
    solana_keypair = export_to_solana(priv_b64)
    assert len(solana_keypair) == 64
    assert all(isinstance(x, int) for x in solana_keypair)
    
    # 3. Import from Solana
    imported = import_from_solana(solana_keypair)
    assert imported["private_key_b64"] == priv_b64
    
    # Verify key_id matches
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    from provara.backpack_signing import key_id_from_public_bytes
    expected_kid = key_id_from_public_bytes(pub_bytes)
    assert imported["key_id"] == expected_kid

def test_import_invalid_length():
    with pytest.raises(ValueError, match="Invalid Solana keypair length"):
        import_from_solana([0] * 63)
    
    with pytest.raises(ValueError, match="Invalid Solana keypair length"):
        import_from_solana([0] * 65)

def test_export_invalid_b64():
    # Depending on how load_private_key_b64 handles it
    with pytest.raises(Exception):
        export_to_solana("not-base64-!!!")

def test_solana_concatenation_logic():
    # Explicitly check if it's priv + pub
    priv = Ed25519PrivateKey.generate()
    priv_bytes = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )
    pub_bytes = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    
    priv_b64 = base64.b64encode(priv_bytes).decode("utf-8")
    solana_keypair = export_to_solana(priv_b64)
    
    assert bytes(solana_keypair[:32]) == priv_bytes
    assert bytes(solana_keypair[32:]) == pub_bytes
