"""
test_psmc.py — Test suite for Personal Sovereign Memory Container
=================================================================
Tests PSMC tool integration with Provara Protocol primitives.

Run:
    cd /c/provara && python -m pytest tools/psmc/test_psmc.py -v
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Set up import paths
_project_root = Path(__file__).resolve().parent.parent.parent
_snp_core_bin = _project_root / "SNP_Core" / "bin"
_psmc_dir = Path(__file__).resolve().parent
for p in [str(_snp_core_bin), str(_psmc_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import psmc  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def vault(tmp_path):
    """Create a fresh vault for testing."""
    v = tmp_path / "vault"
    psmc.init_vault(v)
    return v


@pytest.fixture
def seeded_vault(vault):
    """Vault with example seed data."""
    psmc.seed_examples(vault)
    return vault


# ---------------------------------------------------------------------------
# Vault Initialization
# ---------------------------------------------------------------------------
class TestInit:
    def test_creates_directory_structure(self, vault):
        assert (vault / "psmc.json").exists()
        assert (vault / "keys" / "active.pem").exists()
        assert (vault / "keys" / "active.pub.pem").exists()
        assert (vault / "keys" / "retired").is_dir()
        assert (vault / "events" / "events.ndjson").exists()
        assert (vault / "chain" / "chain.ndjson").exists()
        assert (vault / "digests").is_dir()
        assert (vault / "README.txt").exists()

    def test_metadata_contents(self, vault):
        meta = json.loads((vault / "psmc.json").read_text(encoding="utf-8"))
        assert meta["version"] == "1.0.0"
        assert meta["hash_algo"] == "sha256"
        assert meta["sig_algo"] == "ed25519"
        assert meta["provara_compatible"] is True
        assert "key_fingerprint" in meta
        assert meta["key_fingerprint"].startswith("bp1_")

    def test_key_fingerprint_format(self, vault):
        """Key fingerprint uses Provara's bp1_ prefix scheme."""
        meta = json.loads((vault / "psmc.json").read_text(encoding="utf-8"))
        fp = meta["key_fingerprint"]
        assert fp.startswith("bp1_")
        assert len(fp) == 20  # "bp1_" (4) + 16 hex chars

    def test_empty_event_log(self, vault):
        events_file = vault / "events" / "events.ndjson"
        assert events_file.read_text(encoding="utf-8").strip() == ""

    def test_duplicate_init_fails(self, vault):
        with pytest.raises(SystemExit):
            psmc.init_vault(vault)

    def test_readme_mentions_provara(self, vault):
        readme = (vault / "README.txt").read_text(encoding="utf-8")
        assert "Provara" in readme


# ---------------------------------------------------------------------------
# Event Appending
# ---------------------------------------------------------------------------
class TestAppend:
    def test_append_single_event(self, vault):
        event = psmc.append_event(vault, "note", {"content": "test"})
        assert event["seq"] == 0
        assert event["type"] == "note"
        assert event["prev_hash"] == psmc.GENESIS_PREV
        assert "hash" in event
        assert "id" in event
        uuid.UUID(event["id"])  # valid UUID

    def test_append_increments_sequence(self, vault):
        e0 = psmc.append_event(vault, "note", {"content": "first"})
        e1 = psmc.append_event(vault, "note", {"content": "second"})
        assert e0["seq"] == 0
        assert e1["seq"] == 1

    def test_hash_chain_linkage(self, vault):
        e0 = psmc.append_event(vault, "note", {"content": "first"})
        e1 = psmc.append_event(vault, "note", {"content": "second"})
        assert e1["prev_hash"] == e0["hash"]

    def test_all_event_types(self, vault):
        for etype in psmc.VALID_TYPES:
            event = psmc.append_event(vault, etype, {"test": True})
            assert event["type"] == etype

    def test_event_with_tags(self, vault):
        event = psmc.append_event(
            vault, "note", {"content": "tagged"}, tags=["important", "test"]
        )
        assert event["tags"] == ["important", "test"]

    def test_events_written_to_ndjson(self, vault):
        psmc.append_event(vault, "note", {"content": "test"})
        lines = (vault / "events" / "events.ndjson").read_text(
            encoding="utf-8"
        ).strip().split("\n")
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "note"

    def test_chain_written_parallel(self, vault):
        psmc.append_event(vault, "note", {"content": "test"})
        events_lines = (vault / "events" / "events.ndjson").read_text(
            encoding="utf-8"
        ).strip().split("\n")
        chain_lines = (vault / "chain" / "chain.ndjson").read_text(
            encoding="utf-8"
        ).strip().split("\n")
        assert len(events_lines) == len(chain_lines)


# ---------------------------------------------------------------------------
# Hashing (Provara Integration)
# ---------------------------------------------------------------------------
class TestHashing:
    def test_event_hash_deterministic(self):
        """Same event dict always produces same hash."""
        event = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "seq": 0,
            "type": "note",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "prev_hash": psmc.GENESIS_PREV,
            "data": {"content": "test"},
        }
        h1 = psmc.compute_event_hash(event)
        h2 = psmc.compute_event_hash(event)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_excludes_hash_field(self):
        """compute_event_hash excludes the hash field itself."""
        event = {
            "id": "test-id",
            "seq": 0,
            "type": "note",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "prev_hash": psmc.GENESIS_PREV,
            "data": {"content": "test"},
        }
        h1 = psmc.compute_event_hash(event)
        event["hash"] = "should-be-ignored"
        h2 = psmc.compute_event_hash(event)
        assert h1 == h2

    def test_uses_provara_canonical_json(self):
        """Verify PSMC uses Provara's canonical_json module."""
        from provara.canonical_json import canonical_dumps as provara_canonical
        obj = {"b": 2, "a": 1}
        assert psmc.canonical_dumps(obj) == provara_canonical(obj)

    def test_canonical_json_sorted_keys(self):
        """Keys are sorted lexicographically per RFC 8785."""
        obj = {"z": 1, "a": 2, "m": 3}
        result = psmc.canonical_dumps(obj)
        assert result == '{"a":2,"m":3,"z":1}'

    def test_hash_changes_with_data(self):
        """Different data produces different hashes."""
        base = {
            "id": "test-id",
            "seq": 0,
            "type": "note",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "prev_hash": psmc.GENESIS_PREV,
        }
        e1 = {**base, "data": {"content": "alpha"}}
        e2 = {**base, "data": {"content": "beta"}}
        assert psmc.compute_event_hash(e1) != psmc.compute_event_hash(e2)


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
class TestVerify:
    def test_verify_empty_vault(self, vault):
        assert psmc.verify_chain(vault) is True

    def test_verify_after_appends(self, vault):
        for i in range(5):
            psmc.append_event(vault, "note", {"content": f"event {i}"})
        assert psmc.verify_chain(vault) is True

    def test_verify_seeded_vault(self, seeded_vault):
        assert psmc.verify_chain(seeded_vault) is True

    def test_tamper_detection_event_data(self, vault):
        """Modifying event data breaks verification."""
        psmc.append_event(vault, "note", {"content": "original"})

        events_file = vault / "events" / "events.ndjson"
        content = events_file.read_text(encoding="utf-8")
        tampered = content.replace("original", "tampered")
        events_file.write_text(tampered, encoding="utf-8")

        assert psmc.verify_chain(vault) is False

    def test_tamper_detection_chain_hash(self, vault):
        """Modifying chain hash breaks verification."""
        psmc.append_event(vault, "note", {"content": "test"})

        chain_file = vault / "chain" / "chain.ndjson"
        lines = chain_file.read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        entry["hash"] = "0" * 64
        lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert psmc.verify_chain(vault) is False

    def test_verify_chain_linkage_break(self, vault):
        """Breaking prev_hash chain is detected."""
        psmc.append_event(vault, "note", {"content": "first"})
        psmc.append_event(vault, "note", {"content": "second"})

        events_file = vault / "events" / "events.ndjson"
        lines = events_file.read_text(encoding="utf-8").strip().split("\n")
        event = json.loads(lines[1])
        event["prev_hash"] = "0" * 64
        lines[1] = json.dumps(event, sort_keys=True, separators=(",", ":"))
        events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert psmc.verify_chain(vault) is False

    def test_verify_signature_tampering(self, vault):
        """Modifying a signature breaks verification."""
        psmc.append_event(vault, "note", {"content": "test"})

        chain_file = vault / "chain" / "chain.ndjson"
        lines = chain_file.read_text(encoding="utf-8").strip().split("\n")
        entry = json.loads(lines[0])
        # Flip one hex char in the signature
        sig = entry["sig"]
        flipped = ("1" if sig[0] == "0" else "0") + sig[1:]
        entry["sig"] = flipped
        lines[0] = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        chain_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert psmc.verify_chain(vault) is False

    def test_event_chain_count_mismatch(self, vault):
        """Mismatched event/chain counts detected."""
        psmc.append_event(vault, "note", {"content": "test"})

        # Delete chain entry but keep event
        chain_file = vault / "chain" / "chain.ndjson"
        chain_file.write_text("", encoding="utf-8")

        assert psmc.verify_chain(vault) is False


# ---------------------------------------------------------------------------
# Key Rotation
# ---------------------------------------------------------------------------
class TestKeyRotation:
    def test_rotate_key(self, vault):
        psmc.append_event(vault, "note", {"content": "before rotation"})
        old_meta = json.loads((vault / "psmc.json").read_text(encoding="utf-8"))
        old_fp = old_meta["key_fingerprint"]

        psmc.rotate_key(vault)

        new_meta = json.loads((vault / "psmc.json").read_text(encoding="utf-8"))
        new_fp = new_meta["key_fingerprint"]
        assert old_fp != new_fp
        assert new_fp.startswith("bp1_")

    def test_retired_keys_preserved(self, vault):
        psmc.append_event(vault, "note", {"content": "before"})
        psmc.rotate_key(vault)
        retired = list((vault / "keys" / "retired").iterdir())
        assert len(retired) == 2  # private + public

    def test_verify_after_rotation(self, vault):
        """Chain remains valid after key rotation."""
        psmc.append_event(vault, "note", {"content": "before rotation"})
        psmc.rotate_key(vault)
        psmc.append_event(vault, "note", {"content": "after rotation"})
        assert psmc.verify_chain(vault) is True

    def test_migration_event_logged(self, vault):
        psmc.append_event(vault, "note", {"content": "before"})
        psmc.rotate_key(vault)
        events = psmc._read_ndjson(vault / "events" / "events.ndjson")
        migration_events = [e for e in events if e.get("type") == "migration"]
        assert len(migration_events) == 1
        assert migration_events[0]["data"]["action"] == "key_rotation"

    def test_double_rotation(self, vault):
        """Two consecutive rotations work correctly."""
        psmc.append_event(vault, "note", {"content": "original"})
        psmc.rotate_key(vault)
        psmc.append_event(vault, "note", {"content": "middle"})
        psmc.rotate_key(vault)
        psmc.append_event(vault, "note", {"content": "final"})

        assert psmc.verify_chain(vault) is True

        retired = list((vault / "keys" / "retired").iterdir())
        assert len(retired) == 4  # 2 rotations x 2 files each


# ---------------------------------------------------------------------------
# Digest Generation
# ---------------------------------------------------------------------------
class TestDigest:
    def test_generate_digest(self, seeded_vault):
        text = psmc.generate_digest(seeded_vault, weeks=52)
        assert "Memory Digest" in text
        assert "Chain head:" in text

    def test_digest_file_created(self, seeded_vault):
        psmc.generate_digest(seeded_vault, weeks=52)
        digests = list((seeded_vault / "digests").iterdir())
        assert len(digests) == 1
        assert digests[0].suffix == ".md"

    def test_digest_groups_by_type(self, seeded_vault):
        text = psmc.generate_digest(seeded_vault, weeks=52)
        assert "Identity" in text
        assert "Decision" in text
        assert "Belief" in text


# ---------------------------------------------------------------------------
# Markdown Export
# ---------------------------------------------------------------------------
class TestExport:
    def test_export_markdown(self, seeded_vault):
        text = psmc.export_markdown(seeded_vault)
        assert "Sovereign Memory Export" in text
        assert "```json" in text

    def test_export_contains_all_events(self, seeded_vault):
        events = psmc._read_ndjson(seeded_vault / "events" / "events.ndjson")
        text = psmc.export_markdown(seeded_vault)
        for e in events:
            assert e["id"] in text


# ---------------------------------------------------------------------------
# Show Events
# ---------------------------------------------------------------------------
class TestShow:
    def test_show_all(self, seeded_vault, capsys):
        psmc.show_events(seeded_vault)
        out = capsys.readouterr().out
        assert "identity" in out
        assert "decision" in out

    def test_show_filtered_by_type(self, seeded_vault, capsys):
        psmc.show_events(seeded_vault, event_type="identity")
        out = capsys.readouterr().out
        assert "identity" in out
        assert "decision" not in out

    def test_show_last_n(self, seeded_vault, capsys):
        psmc.show_events(seeded_vault, last_n=1)
        out = capsys.readouterr().out
        lines = [line for line in out.strip().split("\n") if line.strip()]
        assert len(lines) == 1


# ---------------------------------------------------------------------------
# Seed Examples
# ---------------------------------------------------------------------------
class TestSeed:
    def test_seed_creates_events(self, vault):
        psmc.seed_examples(vault)
        events = psmc._read_ndjson(vault / "events" / "events.ndjson")
        assert len(events) == 6

    def test_seed_all_types_present(self, vault):
        psmc.seed_examples(vault)
        events = psmc._read_ndjson(vault / "events" / "events.ndjson")
        types = {e["type"] for e in events}
        expected = {"identity", "decision", "belief", "promotion", "reflection", "correction"}
        assert types == expected

    def test_seed_verifies(self, vault):
        psmc.seed_examples(vault)
        assert psmc.verify_chain(vault) is True

    def test_seed_no_opsec_leaks(self, vault):
        """Seed data must not contain private entity references."""
        psmc.seed_examples(vault)
        events = psmc._read_ndjson(vault / "events" / "events.ndjson")
        full_text = json.dumps(events)
        assert "Hunt Information Systems" not in full_text


# ---------------------------------------------------------------------------
# Schema Validation
# ---------------------------------------------------------------------------
class TestValidation:
    def test_valid_event_passes(self):
        event = {
            "id": str(uuid.uuid4()),
            "type": "note",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {"content": "test"},
            "prev_hash": psmc.GENESIS_PREV,
        }
        assert psmc.validate_event(event) == []

    def test_missing_fields(self):
        errors = psmc.validate_event({})
        assert len(errors) == 5  # all required fields missing

    def test_invalid_type(self):
        event = {
            "id": str(uuid.uuid4()),
            "type": "INVALID",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "prev_hash": psmc.GENESIS_PREV,
        }
        errors = psmc.validate_event(event)
        assert any("Invalid type" in e for e in errors)

    def test_invalid_uuid(self):
        event = {
            "id": "not-a-uuid",
            "type": "note",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {},
            "prev_hash": psmc.GENESIS_PREV,
        }
        errors = psmc.validate_event(event)
        assert any("Invalid UUID" in e for e in errors)

    def test_data_must_be_dict(self):
        event = {
            "id": str(uuid.uuid4()),
            "type": "note",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": "not a dict",
            "prev_hash": psmc.GENESIS_PREV,
        }
        errors = psmc.validate_event(event)
        assert any("must be a JSON object" in e for e in errors)

    def test_invalid_timestamp(self):
        event = {
            "id": str(uuid.uuid4()),
            "type": "note",
            "timestamp": "not-a-timestamp",
            "data": {},
            "prev_hash": psmc.GENESIS_PREV,
        }
        errors = psmc.validate_event(event)
        assert any("Invalid ISO timestamp" in e for e in errors)


# ---------------------------------------------------------------------------
# Key Fingerprint (Provara Compatibility)
# ---------------------------------------------------------------------------
class TestKeyFingerprint:
    def test_fingerprint_uses_provara_format(self, vault):
        """Fingerprint matches Provara's key_id_from_public_bytes output."""
        from backpack_signing import key_id_from_public_bytes
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

        pk = psmc.load_public_key(vault)
        raw = pk.public_bytes(Encoding.Raw, PublicFormat.Raw)
        expected = key_id_from_public_bytes(raw)
        actual = psmc.key_fingerprint(pk)
        assert actual == expected

    def test_fingerprint_stable(self, vault):
        """Same key always produces same fingerprint."""
        pk = psmc.load_public_key(vault)
        fp1 = psmc.key_fingerprint(pk)
        fp2 = psmc.key_fingerprint(pk)
        assert fp1 == fp2

    def test_different_keys_different_fingerprints(self, vault):
        """Two different keys produce different fingerprints."""
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        pk1 = psmc.load_public_key(vault)
        pk2 = Ed25519PrivateKey.generate().public_key()
        assert psmc.key_fingerprint(pk1) != psmc.key_fingerprint(pk2)


# ---------------------------------------------------------------------------
# Provara Reducer Integration
# ---------------------------------------------------------------------------
class TestProvaraReducerIntegration:
    def test_reducer_runs_after_provara_event(self, vault):
        """When --provara flag is used, reducer runs and creates state file."""
        # Append with provara flag
        psmc.append_event(vault, "note", {"content": "test"}, emit_provara=True)
        
        # Check state file exists
        state_file = vault / "state" / "current_state.json"
        assert state_file.exists()
        
        # Check state structure
        state = json.loads(state_file.read_text(encoding="utf-8"))
        assert "canonical" in state
        assert "local" in state
        assert "contested" in state
        assert "archived" in state
        assert "metadata" in state
        
    def test_reducer_state_has_correct_metadata(self, vault):
        """Reducer state includes metadata with event count and state hash."""
        psmc.append_event(vault, "note", {"content": "test1"}, emit_provara=True)
        psmc.append_event(vault, "note", {"content": "test2"}, emit_provara=True)
        
        state_file = vault / "state" / "current_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        meta = state["metadata"]
        assert meta["event_count"] == 2
        assert "state_hash" in meta
        assert meta["state_hash"] is not None
        assert "reducer" in meta
        assert meta["reducer"]["name"] == "SovereignReducerV0"
        
    def test_reducer_creates_local_beliefs(self, vault):
        """Observations should appear in local/ namespace."""
        psmc.append_event(vault, "note", {"content": "test", "subject": "door_01"}, emit_provara=True)
        
        state_file = vault / "state" / "current_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        # Should have at least one local belief
        assert len(state["local"]) > 0
        
    def test_reducer_beliefs_use_assertions(self, vault):
        """Belief/decision/reflection types should create ASSERTION events (confidence 0.5)."""
        psmc.append_event(
            vault, 
            "belief", 
            {"statement": "Testing is important", "confidence": 0.85, "subject": "testing"}, 
            emit_provara=True
        )
        
        state_file = vault / "state" / "current_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        # Check that local beliefs exist
        assert len(state["local"]) > 0
        
        # Find the testing belief
        testing_key = None
        for key in state["local"]:
            if "testing" in key:
                testing_key = key
                break
                
        assert testing_key is not None, "Should have a belief key containing 'testing'"
        belief = state["local"][testing_key]
        assert "confidence" in belief
        
    def test_reducer_state_hash_deterministic(self, vault):
        """Same events should produce same state hash on re-run."""
        psmc.append_event(vault, "note", {"content": "test"}, emit_provara=True)
        
        state_file = vault / "state" / "current_state.json"
        state1 = json.loads(state_file.read_text(encoding="utf-8"))
        hash1 = state1["metadata"]["state_hash"]
        
        # Re-run reducer manually
        state2 = psmc.run_provara_reducer(vault)
        hash2 = state2["metadata"]["state_hash"]
        
        assert hash1 == hash2
        
    def test_no_reducer_without_provara_flag(self, vault):
        """Without --provara flag, no state file should be created."""
        psmc.append_event(vault, "note", {"content": "test"}, emit_provara=False)
        
        state_file = vault / "state" / "current_state.json"
        assert not state_file.exists()
        
    def test_reducer_handles_multiple_events(self, vault):
        """Reducer correctly processes multiple events in sequence."""
        for i in range(5):
            psmc.append_event(vault, "note", {"content": f"test{i}"}, emit_provara=True)
        
        state_file = vault / "state" / "current_state.json"
        state = json.loads(state_file.read_text(encoding="utf-8"))
        
        assert state["metadata"]["event_count"] == 5
        
    def test_provara_events_written_to_separate_file(self, vault):
        """Provara events go to events/provara.ndjson, not events.ndjson."""
        psmc.append_event(vault, "note", {"content": "test"}, emit_provara=True)
        
        provara_file = vault / "events" / "provara.ndjson"
        assert provara_file.exists()
        
        # Read and validate Provara event format
        content = provara_file.read_text(encoding="utf-8").strip()
        provara_event = json.loads(content)
        
        assert "event_id" in provara_event
        assert provara_event["event_id"].startswith("evt_")
        assert "type" in provara_event
        assert provara_event["type"] in ["OBSERVATION", "ASSERTION"]
        assert "actor" in provara_event
        assert "sig" in provara_event
