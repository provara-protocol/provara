import pytest
import json
import base64
from pathlib import Path
from provara.privacy import PrivacyKeyStore, PrivacyWrapper

def test_keystore_init_and_operations(tmp_path):
    vault_path = tmp_path / "vault"
    identity_path = vault_path / "identity"
    identity_path.mkdir(parents=True)
    
    keystore = PrivacyKeyStore(vault_path)
    db_file = identity_path / "privacy_keys.db"
    assert db_file.exists()
    
    key_id = "test-key-1"
    key_bytes = b"0" * 32
    
    # Store key
    keystore.store_key(key_id, key_bytes)
    
    # Get key
    retrieved = keystore.get_key(key_id)
    assert retrieved == key_bytes
    
    # Get nonexistent key
    assert keystore.get_key("nonexistent") is None
    
    # Shred key
    assert keystore.shred_key(key_id) is True
    assert keystore.get_key(key_id) is None
    
    # Shred nonexistent key
    assert keystore.shred_key("nonexistent") is False

def test_wrapper_encrypt_decrypt_happy_path(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "identity").mkdir(parents=True)
    
    wrapper = PrivacyWrapper(vault_path)
    payload = {"secret": "data", "count": 42}
    
    encrypted = wrapper.encrypt(payload)
    assert encrypted["_privacy"] == "aes-gcm-v1"
    assert "kid" in encrypted
    assert "nonce" in encrypted
    assert "ciphertext" in encrypted
    
    decrypted = wrapper.decrypt(encrypted)
    assert decrypted == payload

def test_wrapper_shred(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "identity").mkdir(parents=True)
    
    wrapper = PrivacyWrapper(vault_path)
    payload = {"sensitive": "information"}
    
    encrypted = wrapper.encrypt(payload)
    kid = encrypted["kid"]
    
    # Decrypt works before shredding
    assert wrapper.decrypt(encrypted) == payload
    
    # Shred
    assert wrapper.shred(kid) is True
    
    # Decrypt returns None after shredding
    assert wrapper.decrypt(encrypted) is None

def test_wrapper_decrypt_errors(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "identity").mkdir(parents=True)
    
    wrapper = PrivacyWrapper(vault_path)
    
    # Unsupported scheme
    with pytest.raises(ValueError, match="Unsupported privacy scheme"):
        wrapper.decrypt({"_privacy": "unknown"})
    
    # Missing scheme
    with pytest.raises(ValueError, match="Unsupported privacy scheme"):
        wrapper.decrypt({"kid": "some-kid"})

def test_wrapper_corrupted_data(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "identity").mkdir(parents=True)
    
    wrapper = PrivacyWrapper(vault_path)
    payload = {"data": "to-be-corrupted"}
    
    encrypted = wrapper.encrypt(payload)
    
    # Corrupt ciphertext
    corrupted = encrypted.copy()
    corrupted["ciphertext"] = base64.b64encode(b"garbage").decode("utf-8")
    
    assert wrapper.decrypt(corrupted) is None
    
    # Corrupt nonce
    corrupted_nonce = encrypted.copy()
    corrupted_nonce["nonce"] = base64.b64encode(b"short").decode("utf-8")
    assert wrapper.decrypt(corrupted_nonce) is None

def test_wrapper_invalid_json_payload(tmp_path):
    vault_path = tmp_path / "vault"
    (vault_path / "identity").mkdir(parents=True)
    
    wrapper = PrivacyWrapper(vault_path)
    
    # Try to encrypt something not JSON serializable (like a set)
    # json.dumps raises TypeError for sets
    with pytest.raises(TypeError):
        wrapper.encrypt({"set": {1, 2, 3}})
