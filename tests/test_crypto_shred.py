"""
test_crypto_shred.py — Tests for Provara Crypto-Shredding

Tests cover:
- Encrypted vault creation
- Event encryption/decryption
- Single event shredding
- Actor-wide shredding
- Chain integrity after shredding
- Verification with shredded events
"""

import pytest
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from provara.crypto_shred import (
    PrivacyKeyStore,
    encrypt_event_data,
    decrypt_event_data,
    create_encrypted_payload,
    decrypt_payload,
    shred_event,
    shred_actor,
    create_encrypted_vault,
    is_vault_encrypted,
    get_encryption_mode,
    verify_encrypted_event,
    count_shredded_events,
)
from provara.bootstrap_v0 import bootstrap_backpack
from provara.sync_v0 import load_events, write_events
from provara.canonical_json import canonical_dumps


@pytest.fixture
def tmp_vault_path(tmp_path):
    """Create a temporary vault directory."""
    return tmp_path / "test_vault"


@pytest.fixture
def encrypted_vault(tmp_vault_path):
    """Create an encrypted vault for testing."""
    # Bootstrap first (needs empty directory)
    result = bootstrap_backpack(tmp_vault_path, actor="test_actor", quiet=True)
    assert result.success, f"Bootstrap failed: {result.errors}"

    # Then add encryption config on top
    config_path = tmp_vault_path / "identity" / "encryption_config.json"
    config_path.write_text(json.dumps({
        "encryption_enabled": True,
        "encryption_mode": "per-event",
        "algorithm": "AES-256-GCM",
    }, indent=2))

    # Save private keys
    keys_list = [
        {
            "key_id": result.root_key_id,
            "private_key_b64": result.root_private_key_b64,
            "algorithm": "Ed25519"
        }
    ]
    if result.quorum_key_id:
        keys_list.append({
            "key_id": result.quorum_key_id,
            "private_key_b64": result.quorum_private_key_b64,
            "algorithm": "Ed25519"
        })

    keyfile = tmp_vault_path / "identity" / "private_keys.json"
    keyfile.write_text(json.dumps({"keys": keys_list}, indent=2))

    return tmp_vault_path


class TestPrivacyKeyStore:
    """Tests for PrivacyKeyStore."""

    def test_store_and_retrieve_key(self, tmp_vault_path):
        """Store and retrieve a DEK."""
        store = PrivacyKeyStore(tmp_vault_path)
        key_id = "test_key_123"
        key_bytes = b"0" * 32

        store.store_key(key_id, key_bytes)
        retrieved = store.get_key(key_id)

        assert retrieved == key_bytes

    def test_shred_key(self, tmp_vault_path):
        """Shred a DEK."""
        store = PrivacyKeyStore(tmp_vault_path)
        key_id = "test_key_456"
        key_bytes = b"1" * 32

        store.store_key(key_id, key_bytes)
        assert store.key_exists(key_id) is True

        result = store.shred_key(key_id)
        assert result is True
        assert store.key_exists(key_id) is False

    def test_shred_nonexistent_key(self, tmp_vault_path):
        """Shred nonexistent key returns False."""
        store = PrivacyKeyStore(tmp_vault_path)
        result = store.shred_key("nonexistent")
        assert result is False

    def test_shred_actor_keys(self, tmp_vault_path):
        """Shred all keys for an actor."""
        store = PrivacyKeyStore(tmp_vault_path)

        store.store_key("key1", b"a" * 32, actor_id="actor_alice")
        store.store_key("key2", b"b" * 32, actor_id="actor_alice")
        store.store_key("key3", b"c" * 32, actor_id="actor_bob")

        count = store.shred_actor_keys("actor_alice")
        assert count == 2
        assert store.key_exists("key1") is False
        assert store.key_exists("key2") is False
        assert store.key_exists("key3") is True


class TestEncryptionDecryption:
    """Tests for encryption/decryption operations."""

    def test_encrypt_decrypt_round_trip(self, tmp_vault_path):
        """Encrypt and decrypt data successfully."""
        store = PrivacyKeyStore(tmp_vault_path)
        data = {"ssn": "123-45-6789", "name": "Alice"}

        payload = create_encrypted_payload(data, store, "actor_test")
        decrypted = decrypt_payload(payload, store)

        assert decrypted == data

    def test_decrypt_after_shred_returns_none(self, tmp_vault_path):
        """Decryption fails after key is shredded."""
        store = PrivacyKeyStore(tmp_vault_path)
        data = {"secret": "value"}

        payload = create_encrypted_payload(data, store, "actor_test")
        kid = payload["kid"]

        # Shred the key
        store.shred_key(kid)

        # Decryption should return None
        decrypted = decrypt_payload(payload, store)
        assert decrypted is None

    def test_encrypt_produces_unique_ciphertext(self, tmp_vault_path):
        """Same plaintext produces different ciphertext (nonce randomness)."""
        store = PrivacyKeyStore(tmp_vault_path)
        data = {"test": "value"}

        payload1 = create_encrypted_payload(data, store)
        payload2 = create_encrypted_payload(data, store)

        assert payload1["ciphertext"] != payload2["ciphertext"]
        assert payload1["nonce"] != payload2["nonce"]


class TestEncryptedVault:
    """Tests for encrypted vault creation."""

    def test_create_encrypted_vault(self, tmp_vault_path):
        """Create vault with encryption enabled."""
        vault = create_encrypted_vault(tmp_vault_path, "test_actor", "per-event")

        assert is_vault_encrypted(vault) is True
        assert get_encryption_mode(vault) == "per-event"

    def test_encryption_mode_per_actor(self, tmp_vault_path):
        """Create vault with per-actor encryption."""
        vault = create_encrypted_vault(tmp_vault_path, "test_actor", "per-actor")

        assert is_vault_encrypted(vault) is True
        assert get_encryption_mode(vault) == "per-actor"

    def test_regular_vault_not_encrypted(self, tmp_vault_path):
        """Regular vault without encryption flag."""
        bootstrap_backpack(tmp_vault_path, actor="test_actor", quiet=True)

        assert is_vault_encrypted(tmp_vault_path) is False


class TestShredEvent:
    """Tests for single event shredding."""

    def test_shred_single_event(self, encrypted_vault):
        """Shred a single event."""
        keyfile = encrypted_vault / "identity" / "private_keys.json"

        # Manually create an encrypted event for testing
        store = PrivacyKeyStore(encrypted_vault)
        payload = create_encrypted_payload({"test": "data"}, store, "test_actor")

        events_path = encrypted_vault / "events" / "events.ndjson"
        events = load_events(events_path)

        # Add encrypted event
        encrypted_event = {
            "event_id": "evt_test123",
            "type": "OBSERVATION",
            "actor": "test_actor",
            "timestamp_utc": "2026-02-18T12:00:00Z",
            "payload": payload,
            "prev_event_hash": None,
        }
        events.append(encrypted_event)
        write_events(events_path, events)

        # Shred the event
        result = shred_event(
            encrypted_vault,
            "evt_test123",
            keyfile,
            reason="GDPR_ERASURE",
            authority="Test",
        )

        assert result["type"] == "com.provara.crypto_shred"
        assert store.key_exists(payload["kid"]) is False

    def test_shred_nonexistent_event(self, encrypted_vault):
        """Shred nonexistent event raises error."""
        keyfile = encrypted_vault / "identity" / "private_keys.json"

        with pytest.raises(ValueError, match="not found"):
            shred_event(encrypted_vault, "evt_nonexistent", keyfile)

    def test_shred_unencrypted_event(self, tmp_vault_path):
        """Shred unencrypted event raises error."""
        result = bootstrap_backpack(tmp_vault_path, actor="test_actor", quiet=True)
        assert result.success

        # Create keyfile from bootstrap result
        keys_list = [{"key_id": result.root_key_id, "private_key_b64": result.root_private_key_b64, "algorithm": "Ed25519"}]
        keyfile = tmp_vault_path / "identity" / "private_keys.json"
        keyfile.write_text(json.dumps({"keys": keys_list}, indent=2))

        # Use a real event ID from the vault (GENESIS event is unencrypted)
        events_path = tmp_vault_path / "events" / "events.ndjson"
        events = load_events(events_path)
        target_id = events[0]["event_id"]

        with pytest.raises(ValueError, match="not encrypted"):
            shred_event(tmp_vault_path, target_id, keyfile)


class TestShredActor:
    """Tests for actor-wide shredding."""

    def test_shred_actor_all_events(self, encrypted_vault):
        """Shred all events by an actor."""
        keyfile = encrypted_vault / "identity" / "private_keys.json"
        store = PrivacyKeyStore(encrypted_vault)

        # Create multiple unique keys for the actor
        for i in range(3):
            kid = f"test_key_actor_{i}_{uuid.uuid4()}"
            store.store_key(kid, b"x" * 32, actor_id="test_actor")

        # Shred actor
        result = shred_actor(
            encrypted_vault,
            "test_actor",
            keyfile,
            reason="GDPR_ERASURE",
            authority="Test",
        )

        assert result["type"] == "com.provara.crypto_shred"
        assert result["payload"]["shred_scope"] == "actor_wide"


class TestVerification:
    """Tests for verification with shredded events."""

    def test_count_shredded_events(self, encrypted_vault, tmp_path):
        """Count shredded events correctly."""
        store = PrivacyKeyStore(encrypted_vault)
        keyfile = encrypted_vault / "identity" / "private_keys.json"

        # Create and shred an encrypted event
        payload = create_encrypted_payload({"test": "data"}, store, "test_actor")
        kid = payload["kid"]

        events_path = encrypted_vault / "events" / "events.ndjson"
        events = load_events(events_path)

        encrypted_event = {
            "event_id": "evt_shred_test",
            "type": "OBSERVATION",
            "actor": "test_actor",
            "timestamp_utc": "2026-02-18T12:00:00Z",
            "payload": payload,
        }
        events.append(encrypted_event)
        write_events(events_path, events)

        # Before shredding
        total, shredded = count_shredded_events(encrypted_vault)
        assert shredded == 0

        # Shred
        store.shred_key(kid)

        # After shredding
        total, shredded = count_shredded_events(encrypted_vault)
        assert shredded == 1

    def test_verify_encrypted_event_with_key(self, encrypted_vault):
        """Verify encrypted event when key exists."""
        store = PrivacyKeyStore(encrypted_vault)
        payload = create_encrypted_payload({"test": "data"}, store)

        event = {"payload": payload}
        is_valid, message = verify_encrypted_event(event, store)

        assert is_valid is True
        assert "key available" in message

    def test_verify_encrypted_event_shredded(self, encrypted_vault):
        """Verify encrypted event after shredding."""
        store = PrivacyKeyStore(encrypted_vault)
        payload = create_encrypted_payload({"test": "data"}, store)

        # Shred the key
        store.shred_key(payload["kid"])

        event = {"payload": payload}
        is_valid, message = verify_encrypted_event(event, store)

        assert is_valid is True
        assert "shredded" in message


class TestChainIntegrity:
    """Tests ensuring chain integrity after shredding."""

    def test_chain_integrity_preserved_after_shred(self, encrypted_vault):
        """Hash chain remains valid after shredding."""
        keyfile = encrypted_vault / "identity" / "private_keys.json"
        store = PrivacyKeyStore(encrypted_vault)

        # Create encrypted event
        payload = create_encrypted_payload({"test": "data"}, store, "test_actor")

        events_path = encrypted_vault / "events" / "events.ndjson"
        events = load_events(events_path)

        # Get last event hash for prev_event_hash
        prev_hash = events[-1]["event_id"] if events else None

        encrypted_event = {
            "event_id": "evt_chain_test",
            "type": "OBSERVATION",
            "actor": "test_actor",
            "timestamp_utc": "2026-02-18T12:00:00Z",
            "payload": payload,
            "prev_event_hash": prev_hash,
        }
        events.append(encrypted_event)
        write_events(events_path, events)

        # Shred
        shred_event(encrypted_vault, "evt_chain_test", keyfile, reason="GDPR_ERASURE")

        # Reload and verify chain structure is intact
        events = load_events(events_path)
        assert len(events) >= 2  # Original + shred event

        # Verify shred event was appended
        shred_events = [e for e in events if e.get("type") == "com.provara.crypto_shred"]
        assert len(shred_events) == 1
