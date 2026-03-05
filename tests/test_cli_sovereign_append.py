"""Test sovereign schema append path in CLI."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_vault(tmp_path):
    """Create a minimal vault structure for testing."""
    events_dir = tmp_path / "events"
    events_dir.mkdir()
    (events_dir / "events.ndjson").touch()
    # Create a minimal keyfile
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    import base64
    key = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    keyfile = tmp_path / "keys.json"
    keyfile.write_text(json.dumps({"test_key": priv_b64}))
    return tmp_path, keyfile


def _make_swap_data():
    return json.dumps({
        "action_type": "swap",
        "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "asset_out": "0x4200000000000000000000000000000000000006",
        "amount_in_wei": 1000000,
        "min_amount_out_wei": 380000000000000,
        "max_slippage_bps": 50,
        "deadline_epoch_ms": 4102444800000,
        "receiver": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    })


def _make_args(vault_path, keyfile, **overrides):
    import argparse
    defaults = dict(
        path=str(vault_path),
        type="action.proposed",
        data=_make_swap_data(),
        keyfile=str(keyfile),
        key_id=None,
        actor="quant",
        confidence=None,
        timestamp=False,
        tsa_url=None,
        schema="sovereign",
        payload_type="SwapIntent",
        agent_role="quant",
    )
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


def test_sovereign_append_creates_valid_event(tmp_vault):
    """Sovereign append writes a valid ProvaraEvent to the NDJSON log."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append

    cmd_append(_make_args(vault_path, keyfile))

    events_file = vault_path / "events" / "events.ndjson"
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 1

    event_data = json.loads(lines[0])
    assert "schema_version" in event_data
    assert event_data["event_type"] == "action.proposed"
    assert event_data["payload_type"] == "SwapIntent"
    assert event_data["payload"]["action_type"] == "swap"
    assert event_data["signer_public_key"] != ""
    assert event_data["signature"] != ""
    assert event_data["previous_event_digest"] == "genesis"
    assert event_data["sequence_number"] == 0


def test_sovereign_append_rejects_invalid_payload(tmp_vault):
    """Sovereign append rejects payload that doesn't match the declared type."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append

    with pytest.raises(SystemExit):
        cmd_append(_make_args(vault_path, keyfile, data=json.dumps({"bad_field": "nope"})))


def test_sovereign_append_chains_prev_hash(tmp_vault):
    """Second sovereign event references digest of the first."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append

    cmd_append(_make_args(vault_path, keyfile))
    cmd_append(_make_args(vault_path, keyfile))

    lines = (vault_path / "events" / "events.ndjson").read_text().strip().split("\n")
    event1 = json.loads(lines[0])
    event2 = json.loads(lines[1])

    assert event2["previous_event_digest"] != "genesis"
    assert event2["sequence_number"] == 1
