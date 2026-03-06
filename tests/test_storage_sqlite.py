"""
test_storage_sqlite.py — SQLiteVault storage backend tests.

Tests: schema init, append/read, chain verification, canonical JSON,
       edge cases, and Provara error integration.

Run: python -m pytest tests/test_storage_sqlite.py -v
"""

from dataclasses import fields

import pytest

from provara.storage_sqlite import SQLiteVault, generate_keypair, Event
from provara.canonical_json import canonical_bytes
from provara.errors import HashMismatchError, BrokenCausalChainError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_vault(tmp_path):
    path = tmp_path / "test.vault.sqlite"
    with SQLiteVault(path) as v:
        yield v


@pytest.fixture
def keypair():
    sk, pk_hex = generate_keypair()
    return sk, pk_hex


# ---------------------------------------------------------------------------
# Schema & initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_file(self, tmp_path):
        path = tmp_path / "new.vault.sqlite"
        assert not path.exists()
        v = SQLiteVault(path)
        assert path.exists()
        v.close()

    def test_wal_mode(self, tmp_vault):
        mode = tmp_vault.conn.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode == "wal"

    def test_schema_version(self, tmp_vault):
        row = tmp_vault.conn.execute(
            "SELECT value FROM vault_meta WHERE key='schema_version'"
        ).fetchone()
        assert row[0] == "1"

    def test_idempotent_init(self, tmp_path):
        path = tmp_path / "idem.vault.sqlite"
        v1 = SQLiteVault(path)
        v1.close()
        v2 = SQLiteVault(path)
        count = v2.conn.execute("SELECT COUNT(*) FROM vault_meta").fetchone()[0]
        assert count == 2  # schema_version + created_at
        v2.close()


# ---------------------------------------------------------------------------
# Append & read
# ---------------------------------------------------------------------------

class TestAppendRead:
    def test_append_single(self, tmp_vault, keypair):
        sk, _ = keypair
        ev = tmp_vault.append("test.created", {"foo": "bar"}, sk)
        assert ev.seq == 1
        assert ev.event_type == "test.created"
        assert ev.payload == {"foo": "bar"}
        assert ev.prev_hash == "GENESIS"

    def test_append_chain(self, tmp_vault, keypair):
        sk, _ = keypair
        e1 = tmp_vault.append("a", {"n": 1}, sk)
        e2 = tmp_vault.append("b", {"n": 2}, sk)
        assert e2.prev_hash == e1.event_hash
        assert e2.seq == 2

    def test_get_by_id(self, tmp_vault, keypair):
        sk, _ = keypair
        e1 = tmp_vault.append("lookup", {"key": "val"}, sk)
        fetched = tmp_vault.get(e1.event_id)
        assert fetched is not None
        assert fetched.event_hash == e1.event_hash

    def test_get_missing(self, tmp_vault):
        assert tmp_vault.get("nonexistent-id") is None

    def test_count(self, tmp_vault, keypair):
        sk, _ = keypair
        assert tmp_vault.count() == 0
        tmp_vault.append("x", {}, sk)
        tmp_vault.append("y", {}, sk)
        assert tmp_vault.count() == 2

    def test_chain_order(self, tmp_vault, keypair):
        sk, _ = keypair
        ids = []
        for i in range(5):
            ev = tmp_vault.append("seq", {"i": i}, sk)
            ids.append(ev.event_id)
        chain = tmp_vault.chain()
        assert [e.event_id for e in chain] == ids

    def test_query_by_type(self, tmp_vault, keypair):
        sk, _ = keypair
        tmp_vault.append("alpha", {"x": 1}, sk)
        tmp_vault.append("beta", {"x": 2}, sk)
        tmp_vault.append("alpha", {"x": 3}, sk)
        results = tmp_vault.query("alpha")
        assert len(results) == 2
        assert all(e.event_type == "alpha" for e in results)


# ---------------------------------------------------------------------------
# Chain verification
# ---------------------------------------------------------------------------

class TestVerification:
    def test_valid_chain(self, tmp_vault, keypair):
        sk, _ = keypair
        for i in range(10):
            tmp_vault.append("verify", {"step": i}, sk)
        valid, msg = tmp_vault.verify_chain()
        assert valid is True
        assert "10 events" in msg

    def test_empty_chain_valid(self, tmp_vault):
        valid, msg = tmp_vault.verify_chain()
        assert valid is True
        assert "0 events" in msg

    def test_detects_hash_tampering(self, tmp_vault, keypair):
        sk, _ = keypair
        tmp_vault.append("tamper", {"data": "original"}, sk)

        tmp_vault.conn.execute(
            """UPDATE events SET payload = '{"corrupted": true}' WHERE seq = 1"""
        )
        tmp_vault.conn.commit()

        valid, msg = tmp_vault.verify_chain()
        assert valid is False
        assert "Hash mismatch" in msg or "Chain break" in msg or "invalid" in msg.lower()

    def test_detects_chain_break(self, tmp_vault, keypair):
        sk, _ = keypair
        tmp_vault.append("a", {}, sk)
        tmp_vault.append("b", {}, sk)

        tmp_vault.conn.execute(
            "UPDATE events SET prev_hash = 'deadbeef' WHERE seq = 2"
        )
        tmp_vault.conn.commit()

        valid, _ = tmp_vault.verify_chain()
        assert valid is False

    def test_multi_signer(self, tmp_vault):
        sk1, _ = generate_keypair()
        sk2, _ = generate_keypair()

        tmp_vault.append("from_alice", {"who": "alice"}, sk1)
        tmp_vault.append("from_bob", {"who": "bob"}, sk2)

        valid, _ = tmp_vault.verify_chain()
        assert valid is True


# ---------------------------------------------------------------------------
# Canonical JSON
# ---------------------------------------------------------------------------

class TestCanonicalJson:
    def test_sorted_keys(self):
        result = canonical_bytes({"z": 1, "a": 2})
        assert result == b'{"a":2,"z":1}'

    def test_no_whitespace(self):
        result = canonical_bytes({"key": "value"})
        assert b" " not in result

    def test_deterministic(self):
        obj = {"b": [3, 1, 2], "a": {"nested": True}}
        assert canonical_bytes(obj) == canonical_bytes(obj)

    def test_unicode(self):
        result = canonical_bytes({"emoji": "\U0001f510"})
        assert "\U0001f510".encode("utf-8") in result


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_large_payload(self, tmp_vault, keypair):
        sk, _ = keypair
        big = {"data": "x" * 100_000}
        ev = tmp_vault.append("big", big, sk)
        fetched = tmp_vault.get(ev.event_id)
        assert len(fetched.payload["data"]) == 100_000

    def test_nested_payload(self, tmp_vault, keypair):
        sk, _ = keypair
        nested = {"level1": {"level2": {"level3": [1, 2, {"deep": True}]}}}
        ev = tmp_vault.append("nested", nested, sk)
        fetched = tmp_vault.get(ev.event_id)
        assert fetched.payload["level1"]["level2"]["level3"][2]["deep"] is True

    def test_empty_payload(self, tmp_vault, keypair):
        sk, _ = keypair
        ev = tmp_vault.append("empty", {}, sk)
        assert ev.payload == {}

    def test_concurrent_file_access(self, tmp_path, keypair):
        sk, _ = keypair
        path = tmp_path / "shared.vault.sqlite"
        v1 = SQLiteVault(path)
        v2 = SQLiteVault(path)
        v1.append("from_v1", {"src": 1}, sk)
        v2.append("from_v2", {"src": 2}, sk)
        assert v1.count() == 2
        assert v2.count() == 2
        valid, _ = v1.verify_chain()
        assert valid is True
        v1.close()
        v2.close()


# ---------------------------------------------------------------------------
# Provara integration
# ---------------------------------------------------------------------------

class TestProvaraIntegration:
    def test_strict_verify_raises_hash_mismatch(self, tmp_vault, keypair):
        sk, _ = keypair
        tmp_vault.append("tamper", {"data": "original"}, sk)

        tmp_vault.conn.execute(
            """UPDATE events SET payload = '{"corrupted": true}' WHERE seq = 1"""
        )
        tmp_vault.conn.commit()

        with pytest.raises(HashMismatchError):
            tmp_vault.verify_chain(strict=True)

    def test_strict_verify_raises_chain_break(self, tmp_vault, keypair):
        sk, _ = keypair
        tmp_vault.append("a", {}, sk)
        tmp_vault.append("b", {}, sk)

        tmp_vault.conn.execute(
            "UPDATE events SET prev_hash = 'deadbeef' WHERE seq = 2"
        )
        tmp_vault.conn.commit()

        with pytest.raises(BrokenCausalChainError):
            tmp_vault.verify_chain(strict=True)

    def test_event_dataclass_fields(self):
        expected = {
            "seq", "event_id", "event_type", "timestamp",
            "payload", "prev_hash", "event_hash", "signature", "signer_pub",
            "schema_version", "payload_type",
        }
        actual = {f.name for f in fields(Event)}
        assert actual == expected

    def test_sovereign_columns_exist(self, tmp_vault):
        cursor = tmp_vault.conn.execute("PRAGMA table_info(events)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "schema_version" in columns
        assert "payload_type" in columns

    def test_sovereign_append_and_query(self, tmp_vault, keypair):
        sk, _ = keypair
        ev = tmp_vault.append(
            "action.proposed", {"action_type": "swap"}, sk,
            schema_version="1.0.0-provara", payload_type="SwapIntent",
        )
        assert ev.schema_version == "1.0.0-provara"
        assert ev.payload_type == "SwapIntent"
        results = tmp_vault.conn.execute(
            "SELECT * FROM events WHERE payload_type = ?", ("SwapIntent",)
        ).fetchall()
        assert len(results) == 1

    def test_backpack_append_leaves_sovereign_fields_null(self, tmp_vault, keypair):
        sk, _ = keypair
        ev = tmp_vault.append("OBSERVATION", {"subject": "test"}, sk)
        assert ev.schema_version is None
        assert ev.payload_type is None

    def test_generate_keypair_returns_valid_key(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        sk, pk_hex = generate_keypair()
        assert isinstance(sk, Ed25519PrivateKey)
        assert isinstance(pk_hex, str)
        assert len(pk_hex) == 64  # 32-byte Ed25519 public key = 64 hex chars
        # Round-trip: signing and verifying should succeed
        msg = b"test message"
        sig = sk.sign(msg)
        sk.public_key().verify(sig, msg)  # raises if invalid
