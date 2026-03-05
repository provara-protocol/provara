"""Test sovereign event verification."""
import json
import time
from uuid import uuid4

import pytest

from provara.sovereign_schema import (
    EventType,
    ProvaraEvent,
    SwapIntent,
    canonical_json,
    sha256_hex,
)


def _make_sealed_event(sequence, prev_digest="genesis"):
    """Helper to create a sealed sovereign event."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    intent = SwapIntent(
        action_type="swap",
        asset_in="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        asset_out="0x4200000000000000000000000000000000000006",
        amount_in_wei=1000000,
        min_amount_out_wei=380000000000000,
        max_slippage_bps=50,
        deadline_epoch_ms=4102444800000,
        receiver="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    )
    event = ProvaraEvent.from_payload(
        event_type=EventType.ACTION_PROPOSED,
        agent_role="quant",
        payload_model=intent,
        previous_digest=prev_digest,
        sequence=sequence,
    )
    key = Ed25519PrivateKey.generate()
    digest_bytes = bytes.fromhex(event.signable_digest())
    sig = key.sign(digest_bytes)
    pub_hex = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return event.seal(pub_hex, sig.hex())


def test_verify_sovereign_payload_digest():
    """Detects payload digest mismatch."""
    from provara.cli import verify_sovereign_events

    event = _make_sealed_event(0)
    event_dict = json.loads(event.to_ndjson_line())
    # Tamper with payload
    event_dict["payload"]["amount_in_wei"] = 999999

    errors = verify_sovereign_events([event_dict])
    assert len(errors) > 0
    assert "digest" in errors[0].lower()


def test_verify_sovereign_sequence():
    """Detects sequence gap."""
    from provara.cli import verify_sovereign_events

    e0 = _make_sealed_event(0)
    e2 = _make_sealed_event(2, prev_digest=e0.signable_digest())  # gap: skipped 1

    events = [
        json.loads(e0.to_ndjson_line()),
        json.loads(e2.to_ndjson_line()),
    ]

    errors = verify_sovereign_events(events)
    assert len(errors) > 0
    assert "sequence" in errors[0].lower()


def test_verify_sovereign_valid_chain():
    """Accepts a valid chain."""
    from provara.cli import verify_sovereign_events

    e0 = _make_sealed_event(0)
    e1 = _make_sealed_event(1, prev_digest=e0.signable_digest())

    events = [
        json.loads(e0.to_ndjson_line()),
        json.loads(e1.to_ndjson_line()),
    ]

    errors = verify_sovereign_events(events)
    assert errors == []
