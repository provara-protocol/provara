"""Test SovereignReducerV0 dispatch for sovereign schema events."""
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
        assert len(state["local"]) > 0
        assert len(state.get("pending_actions", [])) == 1
