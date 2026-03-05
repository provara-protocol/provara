# Sovereign Schema Integration — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Wire the AEE type system into Provara's CLI append, verify, and replay pipeline as a first-class citizen alongside existing backpack events.

**Architecture:** Extend `cmd_append()` with `--schema sovereign --payload-type X` flags that route through Pydantic validation and `ProvaraEvent.from_payload()`. Extend `cmd_verify()` to auto-detect sovereign events and validate payload digests + sequence numbers. Extend `SovereignReducerV0` to dispatch sovereign event types into new state namespaces.

**Tech Stack:** Python 3.10+, Pydantic V2, Ed25519 (cryptography lib), existing canonical_json module

**Design Doc:** `docs/plans/2026-03-05-sovereign-schema-integration-design.md`

---

## Task 1: Consolidate canonical_json imports in sovereign_schema.py

**Files:**
- Modify: `src/provara/sovereign_schema.py` (lines ~52-65, the inline `canonical_json` and `sha256_hex` functions)

**Step 1: Write the failing test**

```python
# tests/test_sovereign_canonical_compat.py
"""Verify sovereign_schema uses provara.canonical_json, not its own copy."""

from provara.canonical_json import canonical_bytes, sha256_hex as cj_sha256
from provara.sovereign_schema import canonical_json, sha256_hex


def test_canonical_json_is_same_function():
    """Both modules produce identical bytes for the same input."""
    obj = {"z": 1, "a": [3, 2, 1], "m": {"nested": True}}
    assert canonical_json(obj) == canonical_bytes(obj)


def test_sha256_hex_matches():
    """Both sha256_hex functions produce identical digests."""
    data = b"test data for hashing"
    assert sha256_hex(data) == cj_sha256(data)
```

**Step 2: Run test to verify it passes (baseline)**

Run: `PYTHONPATH=src python3 -m pytest tests/test_sovereign_canonical_compat.py -v`
Expected: PASS (both currently produce identical output)

**Step 3: Replace inline functions with imports**

In `src/provara/sovereign_schema.py`, replace the inline `canonical_json()` and `sha256_hex()` definitions with imports from `provara.canonical_json`:

```python
# Replace the inline definitions with:
from provara.canonical_json import canonical_bytes as canonical_json, sha256_hex
```

Keep the public names (`canonical_json`, `sha256_hex`) so existing test imports don't break.

**Step 4: Run full sovereign schema tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_sovereign_schema.py tests/test_sovereign_canonical_compat.py -v`
Expected: All 64 + 2 tests PASS

**Step 5: Commit**

```bash
git add src/provara/sovereign_schema.py tests/test_sovereign_canonical_compat.py
git commit -m "refactor: consolidate canonical_json in sovereign_schema to shared module"
```

---

## Task 2: Add PAYLOAD_TYPE_MAP registry to sovereign_schema.py

**Files:**
- Modify: `src/provara/sovereign_schema.py` (after EmergencyHalt class, ~line 240)
- Test: `tests/test_sovereign_schema.py` (append new tests)

**Step 1: Write the failing test**

```python
# Append to tests/test_sovereign_schema.py

class TestPayloadTypeMap:
    def test_map_contains_all_payload_types(self):
        from provara.sovereign_schema import PAYLOAD_TYPE_MAP
        assert "SwapIntent" in PAYLOAD_TYPE_MAP
        assert "LendingAction" in PAYLOAD_TYPE_MAP
        assert "AllocationRebalance" in PAYLOAD_TYPE_MAP
        assert "EmergencyHalt" in PAYLOAD_TYPE_MAP

    def test_map_values_are_classes(self):
        from provara.sovereign_schema import PAYLOAD_TYPE_MAP, SwapIntent
        assert PAYLOAD_TYPE_MAP["SwapIntent"] is SwapIntent

    def test_resolve_payload_from_map(self):
        from provara.sovereign_schema import PAYLOAD_TYPE_MAP
        cls = PAYLOAD_TYPE_MAP["SwapIntent"]
        intent = cls(
            action_type="swap",
            asset_in="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            asset_out="0x4200000000000000000000000000000000000006",
            amount_in_wei=1000000,
            min_amount_out_wei=380000000000000,
            max_slippage_bps=50,
            deadline_epoch_ms=1710000000000,
            receiver="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        )
        assert intent.action_type == "swap"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_sovereign_schema.py::TestPayloadTypeMap -v`
Expected: FAIL with `ImportError: cannot import name 'PAYLOAD_TYPE_MAP'`

**Step 3: Add the map**

In `src/provara/sovereign_schema.py`, after the EmergencyHalt class (~line 240), add:

```python
PAYLOAD_TYPE_MAP: dict[str, type] = {
    "SwapIntent": SwapIntent,
    "LendingAction": LendingAction,
    "AllocationRebalance": AllocationRebalance,
    "EmergencyHalt": EmergencyHalt,
}
```

**Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_sovereign_schema.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add src/provara/sovereign_schema.py tests/test_sovereign_schema.py
git commit -m "feat: add PAYLOAD_TYPE_MAP registry for CLI payload resolution"
```

---

## Task 3: Extend CLI append with sovereign schema path

**Files:**
- Modify: `src/provara/cli.py` (argparse at ~line 1377, cmd_append at ~line 585)
- Test: `tests/test_cli_sovereign_append.py` (new file)

**Step 1: Write the failing test**

```python
# tests/test_cli_sovereign_append.py
"""Test sovereign schema append path in CLI."""
import json
import tempfile
from pathlib import Path

import pytest

from provara.sovereign_schema import ProvaraEvent, EventType


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


def test_sovereign_append_creates_valid_event(tmp_vault):
    """Sovereign append writes a valid ProvaraEvent to the NDJSON log."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append
    import argparse

    args = argparse.Namespace(
        path=str(vault_path),
        type="action.proposed",
        data=json.dumps({
            "action_type": "swap",
            "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "asset_out": "0x4200000000000000000000000000000000000006",
            "amount_in_wei": 1000000,
            "min_amount_out_wei": 380000000000000,
            "max_slippage_bps": 50,
            "deadline_epoch_ms": 1710000000000,
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
    )

    cmd_append(args)

    # Read the written event
    events_file = vault_path / "events" / "events.ndjson"
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 1

    event_data = json.loads(lines[0])
    assert event_data["schema_version"] == "1.0.0-provara"
    assert event_data["event_type"] == "action.proposed"
    assert event_data["payload_type"] == "SwapIntent"
    assert event_data["payload"]["action_type"] == "swap"
    assert event_data["signer_public_key"] != ""
    assert event_data["signature"] != ""


def test_sovereign_append_rejects_invalid_payload(tmp_vault):
    """Sovereign append rejects payload that doesn't match the declared type."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append
    import argparse

    args = argparse.Namespace(
        path=str(vault_path),
        type="action.proposed",
        data=json.dumps({"bad_field": "not a swap intent"}),
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

    with pytest.raises(SystemExit):
        cmd_append(args)


def test_sovereign_append_chains_prev_hash(tmp_vault):
    """Second sovereign event references digest of the first."""
    vault_path, keyfile = tmp_vault
    from provara.cli import cmd_append
    import argparse

    base_data = json.dumps({
        "action_type": "swap",
        "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "asset_out": "0x4200000000000000000000000000000000000006",
        "amount_in_wei": 1000000,
        "min_amount_out_wei": 380000000000000,
        "max_slippage_bps": 50,
        "deadline_epoch_ms": 1710000000000,
        "receiver": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
    })

    for i in range(2):
        args = argparse.Namespace(
            path=str(vault_path),
            type="action.proposed",
            data=base_data,
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
        cmd_append(args)

    lines = (vault_path / "events" / "events.ndjson").read_text().strip().split("\n")
    event1 = json.loads(lines[0])
    event2 = json.loads(lines[1])

    # Event 2's previous_event_digest should NOT be "genesis"
    assert event2["previous_event_digest"] != "genesis"
    assert event2["sequence_number"] == 1
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_cli_sovereign_append.py -v`
Expected: FAIL — `cmd_append` doesn't recognize `--schema` or `--payload-type`

**Step 3: Add argparse flags**

In `src/provara/cli.py`, after the existing append argparse setup (~line 1387), add:

```python
    p_app.add_argument("--schema", choices=["sovereign"], help="Use sovereign event schema")
    p_app.add_argument("--payload-type", help="Sovereign payload type (e.g. SwapIntent)")
    p_app.add_argument("--agent-role", help="Agent role for sovereign events (e.g. quant, strategist)")
```

**Step 4: Add sovereign path to cmd_append()**

In `src/provara/cli.py`, inside `cmd_append()`, after the sealed vault check (~line 600) and before the existing event building logic, add a sovereign branch:

```python
    # Sovereign schema path
    if getattr(args, "schema", None) == "sovereign":
        _append_sovereign(args, vault, keys_data, kid, priv)
        return
```

Then add the new function (before `cmd_append` or after it):

```python
def _append_sovereign(
    args: argparse.Namespace,
    vault: Path,
    keys_data: dict,
    kid: str,
    priv: Ed25519PrivateKey,
) -> None:
    """Sovereign schema append path — typed, validated, two-phase signed."""
    from .sovereign_schema import (
        PAYLOAD_TYPE_MAP,
        EventType,
        ProvaraEvent,
    )
    from .canonical_json import canonical_bytes, sha256_hex

    # Validate payload type
    payload_type = getattr(args, "payload_type", None)
    if not payload_type or payload_type not in PAYLOAD_TYPE_MAP:
        valid = ", ".join(PAYLOAD_TYPE_MAP.keys())
        _cli_error(
            f"Unknown payload type: {payload_type}",
            f"sovereign events require --payload-type to be one of: {valid}",
            "use a valid payload type or omit --schema for backpack events",
            "docs/plans/2026-03-05-sovereign-schema-integration-design.md",
        )

    # Validate event type
    try:
        event_type = EventType(args.type)
    except ValueError:
        valid_types = [e.value for e in EventType]
        _cli_error(
            f"Invalid sovereign event type: {args.type}",
            f"sovereign events require --type to be a valid EventType value",
            f"valid types include: {', '.join(valid_types[:5])}... (see EventType enum)",
            "docs/plans/2026-03-05-sovereign-schema-integration-design.md",
        )

    # Parse and validate payload through Pydantic
    if args.data.startswith("@"):
        data_str = Path(args.data[1:]).resolve().read_text(encoding="utf-8")
    else:
        data_str = args.data

    try:
        payload_data = json.loads(data_str)
    except json.JSONDecodeError as e:
        _cli_error(
            f"Invalid JSON payload: {e}",
            "event payload must be valid JSON",
            "fix JSON syntax and retry",
            "PROTOCOL_PROFILE.txt §1",
        )

    payload_cls = PAYLOAD_TYPE_MAP[payload_type]
    try:
        payload_model = payload_cls(**payload_data)
    except Exception as e:
        _cli_error(
            f"Payload validation failed for {payload_type}: {e}",
            f"the provided JSON does not match the {payload_type} schema",
            "check field names, types, and constraints for this payload type",
            "src/provara/sovereign_schema.py",
        )

    # Determine chain position
    events_file = vault / "events" / "events.ndjson"
    all_lines = events_file.read_text(encoding="utf-8").strip().split("\n") if events_file.stat().st_size > 0 else []

    # Find previous sovereign event for chain linking
    prev_digest = "genesis"
    sequence = 0
    for line in reversed(all_lines):
        if not line.strip():
            continue
        evt = json.loads(line)
        if "schema_version" in evt:
            # Previous sovereign event — use its signable digest
            prev_event = ProvaraEvent.model_validate(evt)
            prev_digest = prev_event.signable_digest()
            sequence = prev_event.sequence_number + 1
            break

    # Agent role
    agent_role = getattr(args, "agent_role", None) or args.actor or "system"

    # Build unsigned event
    event = ProvaraEvent.from_payload(
        event_type=event_type,
        agent_role=agent_role,
        payload_model=payload_model,
        previous_digest=prev_digest,
        sequence=sequence,
    )

    # Sign: Ed25519 over signable_digest
    digest_bytes = bytes.fromhex(event.signable_digest())
    sig = priv.sign(digest_bytes)
    pub_hex = priv.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw
    ).hex()

    # Seal
    sealed = event.seal(pub_hex, sig.hex())

    # Append to shared NDJSON
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(sealed.to_ndjson_line())

    print(f"Appended sovereign event {sealed.event_id} (type={sealed.event_type.value}, payload={payload_type})")
```

Add the necessary imports at the top of `_append_sovereign`:
```python
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
```

**Step 5: Run tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_cli_sovereign_append.py -v`
Expected: All 3 tests PASS

**Step 6: Run full suite regression**

Run: `PYTHONPATH=src python3 -m pytest --tb=short -q`
Expected: 646+ passed, 0 failures

**Step 7: Commit**

```bash
git add src/provara/cli.py tests/test_cli_sovereign_append.py
git commit -m "feat: add sovereign schema append path to CLI with --schema and --payload-type flags"
```

---

## Task 4: Extend verify to auto-detect and validate sovereign events

**Files:**
- Modify: `src/provara/cli.py` (cmd_verify at ~line 159)
- Test: `tests/test_cli_sovereign_verify.py` (new file)

**Step 1: Write the failing test**

```python
# tests/test_cli_sovereign_verify.py
"""Test sovereign event verification in the verify pipeline."""
import json
import time
from pathlib import Path
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
    """Helper to create a sealed sovereign event for testing."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    intent = SwapIntent(
        action_type="swap",
        asset_in="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        asset_out="0x4200000000000000000000000000000000000006",
        amount_in_wei=1000000,
        min_amount_out_wei=380000000000000,
        max_slippage_bps=50,
        deadline_epoch_ms=1710000000000,
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


def test_verify_sovereign_payload_digest(tmp_path):
    """verify_sovereign_events detects payload digest mismatch."""
    from provara.cli import verify_sovereign_events

    event = _make_sealed_event(0)
    event_dict = json.loads(event.to_ndjson_line())
    # Tamper with payload
    event_dict["payload"]["amount_in_wei"] = 999999

    errors = verify_sovereign_events([event_dict])
    assert len(errors) > 0
    assert "payload_digest" in errors[0].lower() or "digest" in errors[0].lower()


def test_verify_sovereign_sequence(tmp_path):
    """verify_sovereign_events detects sequence gap."""
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
    """verify_sovereign_events accepts a valid chain."""
    from provara.cli import verify_sovereign_events

    e0 = _make_sealed_event(0)
    e1 = _make_sealed_event(1, prev_digest=e0.signable_digest())

    events = [
        json.loads(e0.to_ndjson_line()),
        json.loads(e1.to_ndjson_line()),
    ]

    errors = verify_sovereign_events(events)
    assert errors == []
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_cli_sovereign_verify.py -v`
Expected: FAIL with `ImportError: cannot import name 'verify_sovereign_events'`

**Step 3: Add verify_sovereign_events function**

In `src/provara/cli.py`, add a new function:

```python
def verify_sovereign_events(events: list[dict]) -> list[str]:
    """Validate sovereign events in a mixed event log.

    Checks payload_digest integrity and sequence_number ordering.
    Returns a list of error strings (empty = valid).
    """
    from .sovereign_schema import canonical_json, sha256_hex

    errors = []
    sovereign_events = [e for e in events if "schema_version" in e]

    prev_seq = -1
    for evt in sovereign_events:
        # Check payload digest
        payload = evt.get("payload", {})
        expected_digest = sha256_hex(canonical_json(payload))
        actual_digest = evt.get("payload_digest", "")
        if actual_digest != expected_digest:
            eid = evt.get("event_id", "unknown")
            errors.append(
                f"Payload digest mismatch on {eid}: "
                f"expected {expected_digest[:16]}..., got {actual_digest[:16]}..."
            )

        # Check sequence
        seq = evt.get("sequence_number")
        if seq is not None:
            if seq != prev_seq + 1:
                eid = evt.get("event_id", "unknown")
                errors.append(
                    f"Sequence gap on {eid}: expected {prev_seq + 1}, got {seq}"
                )
            prev_seq = seq

    return errors
```

**Step 4: Wire into cmd_verify()**

In `cmd_verify()`, after the compliance suite passes (~line 209, after `"PASS: All 17 integrity checks passed."`), add:

```python
        # Sovereign event verification (auto-detect)
        from .sync_v0 import iter_events
        events_path = target / "events" / "events.ndjson"
        if events_path.exists():
            all_events = list(iter_events(events_path))
            sovereign_count = sum(1 for e in all_events if "schema_version" in e)
            if sovereign_count > 0:
                sov_errors = verify_sovereign_events(all_events)
                if sov_errors:
                    print(f"\nSOVEREIGN VERIFICATION FAILED:")
                    for err in sov_errors:
                        print(f"  - {err}")
                    sys.exit(1)
                else:
                    print(f"\nPASS: {sovereign_count} sovereign events verified (payload digest + sequence).")
```

Also add `--pipeline` flag to argparse for verify:

```python
    p_verify.add_argument("--pipeline", action="store_true", help="Check sovereign pipeline completeness for ACTION_PROPOSED events")
```

And in the verify flow, after the sovereign verification block:

```python
                if getattr(args, "pipeline", False) and sovereign_count > 0:
                    from .sovereign_schema import verify_pipeline_completeness, ProvaraEvent
                    sov_events_parsed = []
                    for e in all_events:
                        if "schema_version" in e:
                            sov_events_parsed.append(ProvaraEvent.model_validate(e))
                    for i, evt in enumerate(sov_events_parsed):
                        if evt.event_type.value == "action.proposed":
                            ok, msg = verify_pipeline_completeness(sov_events_parsed, i)
                            if not ok:
                                print(f"\n  Pipeline incomplete for {evt.event_id}: {msg}")
```

**Step 5: Run tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_cli_sovereign_verify.py -v`
Expected: All 3 tests PASS

**Step 6: Regression**

Run: `PYTHONPATH=src python3 -m pytest --tb=short -q`
Expected: All passing

**Step 7: Commit**

```bash
git add src/provara/cli.py tests/test_cli_sovereign_verify.py
git commit -m "feat: auto-detect and verify sovereign events in provara verify"
```

---

## Task 5: Extend SovereignReducerV0 for sovereign event dispatch

**Files:**
- Modify: `src/provara/reducer_v0.py` (~line 154, `_apply_event_internal`)
- Test: `tests/test_reducer_sovereign.py` (new file)

**Step 1: Write the failing test**

```python
# tests/test_reducer_sovereign.py
"""Test SovereignReducerV0 dispatch for sovereign schema events."""
import json
import time
from uuid import uuid4

import pytest

from provara.reducer_v0 import SovereignReducerV0
from provara.sovereign_schema import canonical_json, sha256_hex


def _sovereign_event(event_type, payload, sequence=0, prev_digest="genesis"):
    """Build a minimal sovereign event dict for reducer testing."""
    payload_bytes = canonical_json(payload)
    return {
        "schema_version": "1.0.0-provara",
        "event_id": str(uuid4()),
        "event_type": event_type,
        "timestamp_epoch_ms": int(time.time() * 1000),
        "previous_event_digest": prev_digest,
        "sequence_number": sequence,
        "agent_role": "quant",
        "payload": payload,
        "payload_type": "SwapIntent",
        "payload_digest": sha256_hex(payload_bytes),
        "signer_public_key": "ab" * 32,
        "signature": "cd" * 64,
    }


class TestReducerSovereignDispatch:
    def test_action_proposed_goes_to_pending(self):
        reducer = SovereignReducerV0()
        evt = _sovereign_event("action.proposed", {"action_type": "swap", "asset_in": "0xUSDC"})
        reducer.apply_event(evt)
        state = reducer.export_state()
        assert len(state.get("pending_actions", [])) == 1
        assert state["pending_actions"][0]["payload"]["action_type"] == "swap"

    def test_action_executed_moves_to_executed(self):
        reducer = SovereignReducerV0()
        proposed = _sovereign_event("action.proposed", {"action_type": "swap", "id": "tx1"})
        executed = _sovereign_event("action.executed", {"action_type": "swap", "id": "tx1"}, sequence=1)
        reducer.apply_events([proposed, executed])
        state = reducer.export_state()
        assert len(state.get("executed_actions", [])) == 1
        assert len(state.get("pending_actions", [])) == 0

    def test_circuit_breaker_sets_halted(self):
        reducer = SovereignReducerV0()
        evt = _sovereign_event("system.circuit_breaker.triggered", {"reason": "price crash"})
        reducer.apply_event(evt)
        state = reducer.export_state()
        assert state.get("halted") is True

    def test_circuit_breaker_reset_clears_halted(self):
        reducer = SovereignReducerV0()
        trigger = _sovereign_event("system.circuit_breaker.triggered", {"reason": "crash"})
        reset = _sovereign_event("system.circuit_breaker.reset", {"reason": "recovered"}, sequence=1)
        reducer.apply_events([trigger, reset])
        state = reducer.export_state()
        assert state.get("halted") is False

    def test_constitution_stored(self):
        reducer = SovereignReducerV0()
        evt = _sovereign_event("governance.constitution.created", {"max_single_trade_bps": 500})
        reducer.apply_event(evt)
        state = reducer.export_state()
        assert state.get("constitution") is not None
        assert state["constitution"]["max_single_trade_bps"] == 500

    def test_signal_appended_to_pipeline_log(self):
        reducer = SovereignReducerV0()
        evt = _sovereign_event("signal.detected", {"indicator": "RSI_oversold"})
        reducer.apply_event(evt)
        state = reducer.export_state()
        assert len(state.get("pipeline_log", [])) == 1

    def test_unknown_sovereign_type_goes_to_catch_all(self):
        reducer = SovereignReducerV0()
        evt = _sovereign_event("adversarial.test.run", {"test": "fuzz"})
        reducer.apply_event(evt)
        state = reducer.export_state()
        assert len(state.get("sovereign_events", [])) == 1

    def test_mixed_backpack_and_sovereign(self):
        reducer = SovereignReducerV0()
        backpack = {
            "type": "OBSERVATION",
            "event_id": "evt_abc123",
            "actor": "scout",
            "payload": {"subject": "BTC", "predicate": "price", "value": {"usd": 60000}, "confidence": 0.9},
        }
        sovereign = _sovereign_event("action.proposed", {"action_type": "swap"})
        reducer.apply_events([backpack, sovereign])
        state = reducer.export_state()
        # Backpack went to local namespace
        assert len(state["local"]) > 0
        # Sovereign went to pending_actions
        assert len(state.get("pending_actions", [])) == 1
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_reducer_sovereign.py -v`
Expected: FAIL — reducer doesn't handle sovereign events, they fall into `_ignored_types`

**Step 3: Add sovereign dispatch to reducer**

In `src/provara/reducer_v0.py`, modify `_apply_event_internal()` (~line 154). Add sovereign detection before the existing dispatch:

```python
    def _apply_event_internal(self, event: Dict[str, Any]) -> None:
        """Core logic for applying an event without recomputing the state hash."""
        if not isinstance(event, dict):
            return

        # Sovereign schema dispatch (auto-detect by schema_version field)
        if "schema_version" in event:
            self._handle_sovereign_event(event)
            # Update metadata
            event_id = event.get("event_id") or "unknown_event"
            self.state["metadata"]["last_event_id"] = event_id
            self.state["metadata"]["event_count"] += 1
            return

        # ... existing backpack dispatch unchanged ...
```

Then add the sovereign handler method:

```python
    def _handle_sovereign_event(self, event: Dict[str, Any]) -> None:
        """Dispatch a sovereign schema event into appropriate state namespaces."""
        e_type = event.get("event_type", "")
        payload = event.get("payload", {})
        event_id = event.get("event_id", "unknown")

        # Initialize sovereign state namespaces if needed
        if "pending_actions" not in self.state:
            self.state["pending_actions"] = []
        if "executed_actions" not in self.state:
            self.state["executed_actions"] = []
        if "pipeline_log" not in self.state:
            self.state["pipeline_log"] = []
        if "sovereign_events" not in self.state:
            self.state["sovereign_events"] = []

        if e_type == "action.proposed":
            self.state["pending_actions"].append(event)

        elif e_type == "action.executed":
            # Move matching action from pending to executed
            self.state["executed_actions"].append(event)
            self.state["pending_actions"] = [
                a for a in self.state["pending_actions"]
                if a.get("payload", {}).get("id") != payload.get("id")
                or payload.get("id") is None
            ]

        elif e_type in ("action.rejected", "action.expired"):
            self.state["pending_actions"] = [
                a for a in self.state["pending_actions"]
                if a.get("payload", {}).get("id") != payload.get("id")
                or payload.get("id") is None
            ]

        elif e_type == "system.circuit_breaker.triggered":
            self.state["halted"] = True

        elif e_type == "system.circuit_breaker.reset":
            self.state["halted"] = False

        elif e_type == "governance.constitution.created":
            self.state["constitution"] = payload

        elif e_type == "governance.constitution.amended":
            if "constitution" in self.state and self.state["constitution"]:
                self.state["constitution"].update(payload)
            else:
                self.state["constitution"] = payload

        elif e_type in ("signal.detected", "simulation.complete", "audit.passed", "audit.failed"):
            self.state["pipeline_log"].append(event)

        else:
            # Catch-all for other sovereign event types
            self.state["sovereign_events"].append(event)
```

Also update `export_state()` to include sovereign namespaces:

```python
    def export_state(self) -> Dict[str, Any]:
        """Deterministic, JSON-serializable snapshot of all namespaces."""
        exported = {
            "canonical": self.state["canonical"],
            "local": self.state["local"],
            "contested": self.state["contested"],
            "archived": self.state["archived"],
            "metadata": self.state["metadata"],
        }
        # Include sovereign namespaces if they exist
        for key in ("pending_actions", "executed_actions", "pipeline_log",
                     "sovereign_events", "constitution", "halted"):
            if key in self.state:
                exported[key] = self.state[key]
        return exported
```

**Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_reducer_sovereign.py -v`
Expected: All 8 tests PASS

**Step 5: Regression**

Run: `PYTHONPATH=src python3 -m pytest --tb=short -q`
Expected: All passing

**Step 6: Commit**

```bash
git add src/provara/reducer_v0.py tests/test_reducer_sovereign.py
git commit -m "feat: extend SovereignReducerV0 with sovereign event dispatch"
```

---

## Task 6: Extend SQLite schema for sovereign event indexing

**Files:**
- Modify: `src/provara/storage_sqlite.py` (~line 51, SCHEMA_SQL)
- Test: `tests/test_storage_sqlite.py` (extend existing)

**Step 1: Write the failing test**

```python
# Append to tests/test_storage_sqlite.py (or create if needed)

def test_sovereign_event_columns_exist(tmp_path):
    """SQLite schema includes schema_version and payload_type columns."""
    from provara.storage_sqlite import Vault
    vault = Vault(tmp_path / "test.db")
    # Check columns exist
    cursor = vault.conn.execute("PRAGMA table_info(events)")
    columns = {row[1] for row in cursor.fetchall()}
    assert "schema_version" in columns
    assert "payload_type" in columns


def test_query_by_payload_type(tmp_path):
    """Can query sovereign events by payload_type."""
    from provara.storage_sqlite import Vault
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    vault = Vault(tmp_path / "test.db")
    key = Ed25519PrivateKey.generate()

    vault.append("action.proposed", {"action_type": "swap"}, key,
                 schema_version="1.0.0-provara", payload_type="SwapIntent")

    results = vault.conn.execute(
        "SELECT * FROM events WHERE payload_type = ?", ("SwapIntent",)
    ).fetchall()
    assert len(results) == 1
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_storage_sqlite.py::test_sovereign_event_columns_exist -v`
Expected: FAIL — columns don't exist

**Step 3: Add columns to schema**

In `src/provara/storage_sqlite.py`, modify `SCHEMA_SQL` to add the new columns:

```sql
CREATE TABLE IF NOT EXISTS events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    event_type      TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    prev_hash       TEXT    NOT NULL,
    event_hash      TEXT    NOT NULL UNIQUE,
    signature       TEXT    NOT NULL,
    signer_pub      TEXT    NOT NULL,
    schema_version  TEXT,
    payload_type    TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_payload_type ON events(payload_type);
```

Update the `append()` method to accept optional `schema_version` and `payload_type` kwargs and include them in the INSERT.

**Step 4: Run tests**

Run: `PYTHONPATH=src python3 -m pytest tests/test_storage_sqlite.py -v`
Expected: All PASS

**Step 5: Regression**

Run: `PYTHONPATH=src python3 -m pytest --tb=short -q`
Expected: All passing

**Step 6: Commit**

```bash
git add src/provara/storage_sqlite.py tests/test_storage_sqlite.py
git commit -m "feat: add schema_version and payload_type columns to SQLite index"
```

---

## Task 7: End-to-end round-trip integration test

**Files:**
- Test: `tests/test_sovereign_roundtrip.py` (new file)

**Step 1: Write the integration test**

```python
# tests/test_sovereign_roundtrip.py
"""End-to-end: append sovereign events -> verify -> replay -> check state."""
import json
from pathlib import Path

import pytest

from provara.sovereign_schema import EventType


@pytest.fixture
def sovereign_vault(tmp_path):
    """Create a vault with 3 sovereign events forming a valid pipeline."""
    from provara.cli import cmd_append
    import argparse

    events_dir = tmp_path / "events"
    events_dir.mkdir()
    (events_dir / "events.ndjson").touch()

    # Create keyfile
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
    import base64

    key = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    keyfile = tmp_path / "keys.json"
    keyfile.write_text(json.dumps({"test_key": priv_b64}))

    # Append a signal, then a swap proposal
    events_to_create = [
        ("signal.detected", "quant", json.dumps({"indicator": "RSI_oversold", "asset": "ETH", "value_bps": 2500})),
        ("action.proposed", "quant", json.dumps({
            "action_type": "swap",
            "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "asset_out": "0x4200000000000000000000000000000000000006",
            "amount_in_wei": 1000000,
            "min_amount_out_wei": 380000000000000,
            "max_slippage_bps": 50,
            "deadline_epoch_ms": 1710000000000,
            "receiver": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        })),
    ]

    # signal.detected has no strict payload type, use EmergencyHalt as generic or skip type validation
    # Actually, for the signal we need a payload type that exists. Let's use the generic dict approach:
    # We'll append the signal as a backpack event and the swap as sovereign
    # This tests the mixed-chain scenario

    # Backpack signal
    args_signal = argparse.Namespace(
        path=str(tmp_path),
        type="OBSERVATION",
        data=json.dumps({"subject": "ETH", "predicate": "RSI_oversold", "value": {"bps": 2500}}),
        keyfile=str(keyfile),
        key_id=None,
        actor="quant",
        confidence=0.95,
        timestamp=False,
        tsa_url=None,
        schema=None,
        payload_type=None,
        agent_role=None,
    )
    cmd_append(args_signal)

    # Sovereign swap proposal
    args_swap = argparse.Namespace(
        path=str(tmp_path),
        type="action.proposed",
        data=json.dumps({
            "action_type": "swap",
            "asset_in": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            "asset_out": "0x4200000000000000000000000000000000000006",
            "amount_in_wei": 1000000,
            "min_amount_out_wei": 380000000000000,
            "max_slippage_bps": 50,
            "deadline_epoch_ms": 1710000000000,
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
    )
    cmd_append(args_swap)

    return tmp_path


def test_roundtrip_mixed_chain(sovereign_vault):
    """Mixed backpack + sovereign events form a valid chain and reduce correctly."""
    events_file = sovereign_vault / "events" / "events.ndjson"
    lines = events_file.read_text().strip().split("\n")
    assert len(lines) == 2

    # Parse both events
    backpack_evt = json.loads(lines[0])
    sovereign_evt = json.loads(lines[1])

    # Backpack event is classic format
    assert "type" in backpack_evt
    assert backpack_evt["type"] == "OBSERVATION"

    # Sovereign event has schema_version
    assert sovereign_evt["schema_version"] == "1.0.0-provara"
    assert sovereign_evt["event_type"] == "action.proposed"
    assert sovereign_evt["signer_public_key"] != ""

    # Verify sovereign events
    from provara.cli import verify_sovereign_events
    all_events = [json.loads(l) for l in lines]
    errors = verify_sovereign_events(all_events)
    assert errors == []

    # Reduce
    from provara.reducer_v0 import SovereignReducerV0
    reducer = SovereignReducerV0()
    reducer.apply_events(all_events)
    state = reducer.export_state()

    # Backpack observation went to local
    assert state["metadata"]["event_count"] == 2
    # Sovereign went to pending_actions
    assert len(state.get("pending_actions", [])) == 1
    assert state["pending_actions"][0]["payload"]["action_type"] == "swap"
```

**Step 2: Run test**

Run: `PYTHONPATH=src python3 -m pytest tests/test_sovereign_roundtrip.py -v`
Expected: PASS (if Tasks 1-5 are implemented correctly)

**Step 3: Run full regression**

Run: `PYTHONPATH=src python3 -m pytest --tb=short -q`
Expected: All passing, zero failures

**Step 4: Commit**

```bash
git add tests/test_sovereign_roundtrip.py
git commit -m "test: add end-to-end sovereign schema round-trip integration test"
```

---

## Summary

| Task | Component | Tests Added |
|------|-----------|-------------|
| 1 | Consolidate canonical_json | 2 |
| 2 | PAYLOAD_TYPE_MAP registry | 3 |
| 3 | CLI append sovereign path | 3 |
| 4 | Verify sovereign events | 3 |
| 5 | Reducer sovereign dispatch | 8 |
| 6 | SQLite schema extension | 2 |
| 7 | Round-trip integration | 1 |
| **Total** | **7 tasks, 7 commits** | **22 new tests** |
