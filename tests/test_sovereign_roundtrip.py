"""End-to-end: append mixed events -> verify -> reduce -> check state."""
import json
from pathlib import Path

import pytest


@pytest.fixture
def mixed_vault(tmp_path):
    """Create a vault with 1 backpack + 1 sovereign event."""
    from provara.cli import cmd_append
    import argparse
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    (events_dir / "events.ndjson").touch()

    key = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    keyfile = tmp_path / "keys.json"
    keyfile.write_text(json.dumps({"test_key": priv_b64}))

    # 1. Backpack observation
    cmd_append(argparse.Namespace(
        path=str(tmp_path),
        type="OBSERVATION",
        data=json.dumps({"subject": "ETH", "predicate": "RSI_oversold", "value": {"bps": 2500}}),
        keyfile=str(keyfile),
        key_id=None,
        actor="scout",
        confidence=0.95,
        timestamp=False,
        tsa_url=None,
        schema=None,
        payload_type=None,
        agent_role=None,
    ))

    # 2. Sovereign swap proposal
    cmd_append(argparse.Namespace(
        path=str(tmp_path),
        type="action.proposed",
        data=json.dumps({
            "action_type": "swap",
            "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "asset_out": "0x4200000000000000000000000000000000000006",
            "amount_in_wei": 1000000,
            "min_amount_out_wei": 380000000000000,
            "max_slippage_bps": 50,
            "deadline_epoch_ms": 4102444800000,
            "receiver": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        }),
        keyfile=str(keyfile),
        key_id=None,
        actor="quant",
        confidence=None,
        timestamp=False,
        tsa_url=None,
        schema="sovereign",
        payload_type="SwapIntent",
        agent_role="quant",
    ))

    return tmp_path


def test_roundtrip_mixed_chain(mixed_vault):
    """Mixed backpack + sovereign events: verify and reduce correctly."""
    events_file = mixed_vault / "events" / "events.ndjson"
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 2

    backpack_evt = json.loads(lines[0])
    sovereign_evt = json.loads(lines[1])

    # Backpack is classic format
    assert backpack_evt["type"] == "OBSERVATION"
    assert "schema_version" not in backpack_evt

    # Sovereign has schema_version
    assert sovereign_evt["schema_version"] == "1.0.0"
    assert sovereign_evt["event_type"] == "action.proposed"
    assert sovereign_evt["signer_public_key"] != ""
    assert sovereign_evt["signature"] != ""

    # Verify sovereign events
    from provara.cli import verify_sovereign_events
    all_events = [json.loads(l) for l in lines]
    errors = verify_sovereign_events(all_events)
    assert errors == [], f"Verification errors: {errors}"

    # Reduce
    from provara.reducer_v0 import SovereignReducerV0
    reducer = SovereignReducerV0()
    reducer.apply_events(all_events)
    state = reducer.export_state()

    # Both events counted
    assert state["metadata"]["event_count"] == 2

    # Backpack observation went to local namespace
    assert len(state["local"]) > 0

    # Sovereign event went to pending_actions
    assert len(state.get("pending_actions", [])) == 1
    assert state["pending_actions"][0]["payload"]["action_type"] == "swap"
