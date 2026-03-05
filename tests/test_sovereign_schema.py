"""
test_sovereign_schema.py — AEE Type System Test Suite

Validates every invariant the schema enforces:
  - Strict type enforcement (no coercion)
  - Address validation
  - Cross-field validation (weights sum, time windows, self-swap)
  - Canonical JSON determinism
  - Hash chain integrity
  - Pipeline completeness
  - Two-phase signing workflow
  - NDJSON round-trip
  - Constitution constraints

Run: pytest test_sovereign_schema.py -v
"""

import json
import os
import tempfile
import time

import pytest

from sovereign_schema import (
    GENESIS_DIGEST,
    SCHEMA_VERSION,
    ActionProposal,
    AllocationRebalance,
    ConstitutionV1,
    EmergencyHalt,
    EventType,
    LendingAction,
    ProvaraEvent,
    SessionKeyPolicy,
    SwapIntent,
    canonical_json,
    load_vault_log,
    sha256_hex,
    verify_chain_integrity,
    verify_pipeline_completeness,
)
from pydantic import ValidationError


# ════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
WETH_BASE = "0x4200000000000000000000000000000000000006"
AAVE_V3_BASE = "0xA238Dd80C259a72e81d7e4664a9801593F98d1c5"
COW_SETTLEMENT = "0x9008D19f58AAbD9eD0D60971565AA8510560ab41"
VAULT_ADDR = "0x1111111111111111111111111111111111111111"
OWNER_ADDR = "0x2222222222222222222222222222222222222222"

FUTURE_MS = int(time.time() * 1000) + 3_600_000  # 1 hour from now
NOW_MS = int(time.time() * 1000)


def make_swap(**overrides) -> SwapIntent:
    defaults = dict(
        asset_in=USDC_BASE,
        asset_out=WETH_BASE,
        amount_in_wei=1_000_000,
        min_amount_out_wei=380_000_000_000_000,
        max_slippage_bps=50,
        deadline_epoch_ms=FUTURE_MS,
        receiver=VAULT_ADDR,
    )
    defaults.update(overrides)
    return SwapIntent(**defaults)


def make_lending(**overrides) -> LendingAction:
    defaults = dict(
        operation="supply",
        protocol_address=AAVE_V3_BASE,
        asset=USDC_BASE,
        amount_wei=5_000_000,
    )
    defaults.update(overrides)
    return LendingAction(**defaults)


def make_rebalance(**overrides) -> AllocationRebalance:
    defaults = dict(
        weight_stables_bps=1000,
        weight_active_bps=3000,
        weight_lending_bps=5000,
        weight_reserve_bps=1000,
        trigger="scheduled",
        regime_label="bull",
        risk_aversion_bps=10000,
    )
    defaults.update(overrides)
    return AllocationRebalance(**defaults)


def make_session_policy(**overrides) -> SessionKeyPolicy:
    defaults = dict(
        allowed_contracts=(COW_SETTLEMENT, AAVE_V3_BASE),
        allowed_selectors=("0x38ed1739", "0xe8e33700"),
        max_wei_per_tx=10_000_000,
        max_wei_per_day=50_000_000,
        max_transactions_per_hour=20,
        max_gas_per_tx=500_000,
        valid_from_epoch_ms=NOW_MS,
        expires_epoch_ms=NOW_MS + 604_800_000,  # 7 days
        on_expiry="stables_only",
    )
    defaults.update(overrides)
    return SessionKeyPolicy(**defaults)


def make_constitution(**overrides) -> ConstitutionV1:
    defaults = dict(
        created_epoch_ms=NOW_MS,
        entity_name="hunt-sovereign-aee-alpha",
        chain_id=8453,  # Base mainnet
        vault_address=VAULT_ADDR,
        owner_address=OWNER_ADDR,
        max_portfolio_drawdown_bps=500,
        max_single_trade_pct_bps=2000,
        min_stables_reserve_bps=1000,
        max_active_trading_bps=3000,
        daily_loss_halt_bps=300,
        hourly_trade_limit=10,
        default_session_policy=make_session_policy(),
        allowed_protocols=(COW_SETTLEMENT, AAVE_V3_BASE),
        allowed_tokens=(USDC_BASE, WETH_BASE),
        sanctioned_token_blocklist=(),
        pinned_dependencies_digest="a" * 64,
    )
    defaults.update(overrides)
    return ConstitutionV1(**defaults)


def make_event_chain(n: int = 3) -> list[ProvaraEvent]:
    """Build a valid chain of n events: signal → sim → audit."""
    types = [
        (EventType.SIGNAL_DETECTED, "scout"),
        (EventType.SIMULATION_COMPLETE, "quant"),
        (EventType.AUDIT_PASSED, "auditor"),
        (EventType.ACTION_PROPOSED, "quant"),
        (EventType.ACTION_EXECUTED, "system"),
    ]
    events: list[ProvaraEvent] = []
    prev_digest = GENESIS_DIGEST

    for i in range(min(n, len(types))):
        etype, role = types[i]
        payload = make_swap() if etype == EventType.ACTION_PROPOSED else make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=etype,
            agent_role=role,
            payload_model=payload,
            previous_digest=prev_digest,
            sequence=i,
        )
        events.append(evt)
        prev_digest = evt.signable_digest()

    return events


# ════════════════════════════════════════════════════════════════
# SWAP INTENT TESTS
# ════════════════════════════════════════════════════════════════

class TestSwapIntent:
    def test_valid_swap(self):
        s = make_swap()
        assert s.action_type == "swap"
        assert s.amount_in_wei == 1_000_000

    def test_rejects_self_swap(self):
        with pytest.raises(ValidationError, match="must differ"):
            make_swap(asset_out=USDC_BASE)

    def test_rejects_case_insensitive_self_swap(self):
        with pytest.raises(ValidationError, match="must differ"):
            make_swap(asset_out=USDC_BASE.lower())

    def test_rejects_past_deadline(self):
        with pytest.raises(ValidationError, match="future"):
            make_swap(deadline_epoch_ms=1000)

    def test_rejects_zero_amount(self):
        with pytest.raises(ValidationError):
            make_swap(amount_in_wei=0)

    def test_rejects_negative_amount(self):
        with pytest.raises(ValidationError):
            make_swap(amount_in_wei=-1)

    def test_rejects_zero_min_out(self):
        with pytest.raises(ValidationError):
            make_swap(min_amount_out_wei=0)

    def test_slippage_hard_cap(self):
        make_swap(max_slippage_bps=500)  # 5% — max allowed
        with pytest.raises(ValidationError):
            make_swap(max_slippage_bps=501)

    def test_rejects_string_coercion(self):
        """Strict mode: string '100' must NOT coerce to int 100."""
        with pytest.raises(ValidationError):
            SwapIntent(
                asset_in=USDC_BASE,
                asset_out=WETH_BASE,
                amount_in_wei="1000000",  # type: ignore
                min_amount_out_wei=380000000000000,
                max_slippage_bps=50,
                deadline_epoch_ms=FUTURE_MS,
                receiver=VAULT_ADDR,
            )

    def test_rejects_invalid_address(self):
        with pytest.raises(ValidationError):
            make_swap(asset_in="not_an_address")

    def test_rejects_short_address(self):
        with pytest.raises(ValidationError):
            make_swap(asset_in="0x1234")

    def test_frozen_immutability(self):
        s = make_swap()
        with pytest.raises(ValidationError):
            s.amount_in_wei = 999  # type: ignore


# ════════════════════════════════════════════════════════════════
# LENDING ACTION TESTS
# ════════════════════════════════════════════════════════════════

class TestLendingAction:
    def test_valid_supply(self):
        la = make_lending()
        assert la.operation == "supply"
        assert la.min_health_factor_bps == 15000  # default 1.5x

    def test_valid_withdraw(self):
        la = make_lending(operation="withdraw")
        assert la.operation == "withdraw"

    def test_valid_repay(self):
        la = make_lending(operation="repay")
        assert la.operation == "repay"

    def test_rejects_invalid_operation(self):
        with pytest.raises(ValidationError):
            make_lending(operation="borrow")

    def test_health_factor_floor(self):
        make_lending(min_health_factor_bps=10000)  # 1.0x — minimum
        with pytest.raises(ValidationError):
            make_lending(min_health_factor_bps=9999)  # Below liquidation

    def test_custom_health_factor(self):
        la = make_lending(min_health_factor_bps=20000)  # 2.0x
        assert la.min_health_factor_bps == 20000


# ════════════════════════════════════════════════════════════════
# ALLOCATION REBALANCE TESTS
# ════════════════════════════════════════════════════════════════

class TestAllocationRebalance:
    def test_valid_rebalance(self):
        r = make_rebalance()
        total = (
            r.weight_stables_bps + r.weight_active_bps
            + r.weight_lending_bps + r.weight_reserve_bps
        )
        assert total == 10000

    def test_rejects_weights_over_100(self):
        with pytest.raises(ValidationError, match="10000"):
            make_rebalance(weight_stables_bps=5000, weight_active_bps=6000)

    def test_rejects_weights_under_100(self):
        with pytest.raises(ValidationError, match="10000"):
            make_rebalance(
                weight_stables_bps=1000,
                weight_active_bps=1000,
                weight_lending_bps=1000,
                weight_reserve_bps=1000,
            )

    def test_all_in_stables(self):
        """100% stables is a valid defensive allocation."""
        r = make_rebalance(
            weight_stables_bps=10000,
            weight_active_bps=0,
            weight_lending_bps=0,
            weight_reserve_bps=0,
            trigger="circuit_breaker",
            regime_label="bear",
        )
        assert r.weight_stables_bps == 10000

    def test_regime_shift_trigger(self):
        r = make_rebalance(trigger="regime_shift", regime_label="high_vol")
        assert r.trigger == "regime_shift"


# ════════════════════════════════════════════════════════════════
# EMERGENCY HALT TESTS
# ════════════════════════════════════════════════════════════════

class TestEmergencyHalt:
    def test_valid_halt(self):
        h = EmergencyHalt(
            reason="Daily drawdown exceeded 3%",
            triggered_by="system",
            halt_scope="all",
            resume_requires="owner_signature",
        )
        assert h.action_type == "emergency_halt"
        assert h.cooldown_ms == 86400000  # default 24h

    def test_scoped_halt(self):
        h = EmergencyHalt(
            reason="Oracle divergence on USDC price",
            triggered_by="oracle_guardian",
            halt_scope="active_trading",
            resume_requires="cooldown_expiry",
            cooldown_ms=3600000,
        )
        assert h.halt_scope == "active_trading"


# ════════════════════════════════════════════════════════════════
# DISCRIMINATED UNION TESTS
# ════════════════════════════════════════════════════════════════

class TestActionProposal:
    def test_discriminates_swap(self):
        from pydantic import TypeAdapter
        ta = TypeAdapter(ActionProposal)
        raw = make_swap().model_dump()
        parsed = ta.validate_python(raw)
        assert isinstance(parsed, SwapIntent)

    def test_discriminates_lending(self):
        from pydantic import TypeAdapter
        ta = TypeAdapter(ActionProposal)
        raw = make_lending().model_dump()
        parsed = ta.validate_python(raw)
        assert isinstance(parsed, LendingAction)

    def test_discriminates_rebalance(self):
        from pydantic import TypeAdapter
        ta = TypeAdapter(ActionProposal)
        raw = make_rebalance().model_dump()
        parsed = ta.validate_python(raw)
        assert isinstance(parsed, AllocationRebalance)

    def test_discriminates_halt(self):
        from pydantic import TypeAdapter
        ta = TypeAdapter(ActionProposal)
        raw = EmergencyHalt(
            reason="test",
            triggered_by="owner",
            halt_scope="all",
            resume_requires="manual_review",
        ).model_dump()
        parsed = ta.validate_python(raw)
        assert isinstance(parsed, EmergencyHalt)

    def test_rejects_unknown_action_type(self):
        from pydantic import TypeAdapter
        ta = TypeAdapter(ActionProposal)
        with pytest.raises(ValidationError):
            ta.validate_python({"action_type": "steal_funds", "amount": 999})


# ════════════════════════════════════════════════════════════════
# SESSION KEY POLICY TESTS
# ════════════════════════════════════════════════════════════════

class TestSessionKeyPolicy:
    def test_valid_policy(self):
        p = make_session_policy()
        assert len(p.allowed_contracts) == 2

    def test_rejects_invalid_contract_address(self):
        with pytest.raises(ValidationError):
            make_session_policy(allowed_contracts=("not_an_address",))

    def test_rejects_invalid_selector(self):
        with pytest.raises(ValidationError):
            make_session_policy(allowed_selectors=("0xZZZZ",))

    def test_rejects_expired_before_start(self):
        with pytest.raises(ValidationError, match="after valid_from"):
            make_session_policy(
                valid_from_epoch_ms=NOW_MS,
                expires_epoch_ms=NOW_MS - 1000,
            )

    def test_rejects_empty_whitelist(self):
        with pytest.raises(ValidationError):
            make_session_policy(allowed_contracts=())

    def test_expiry_behavior(self):
        p = make_session_policy(on_expiry="unwind_to_stables")
        assert p.on_expiry == "unwind_to_stables"


# ════════════════════════════════════════════════════════════════
# CONSTITUTION TESTS
# ════════════════════════════════════════════════════════════════

class TestConstitution:
    def test_valid_constitution(self):
        c = make_constitution()
        assert c.chain_id == 8453
        assert c.entity_name == "hunt-sovereign-aee-alpha"

    def test_rejects_reserve_plus_active_over_100(self):
        with pytest.raises(ValidationError, match="cannot exceed 100%"):
            make_constitution(
                min_stables_reserve_bps=8000,
                max_active_trading_bps=3000,
            )

    def test_regime_risk_aversion(self):
        c = make_constitution()
        assert c.risk_aversion_bear_bps > c.risk_aversion_bull_bps
        assert c.risk_aversion_high_vol_bps > c.risk_aversion_bear_bps

    def test_nested_session_policy_validated(self):
        """Constitution validates the embedded session policy too."""
        with pytest.raises(ValidationError):
            make_constitution(
                default_session_policy=SessionKeyPolicy(
                    allowed_contracts=(),  # Empty — should fail
                    max_wei_per_tx=1,
                    max_wei_per_day=1,
                    max_transactions_per_hour=1,
                    max_gas_per_tx=1,
                    valid_from_epoch_ms=NOW_MS,
                    expires_epoch_ms=NOW_MS + 1000,
                    on_expiry="halt",
                )
            )


# ════════════════════════════════════════════════════════════════
# CANONICAL JSON & DETERMINISM TESTS
# ════════════════════════════════════════════════════════════════

class TestCanonicalJson:
    def test_sorted_keys(self):
        result = canonical_json({"z": 1, "a": 2, "m": 3})
        assert result == b'{"a":2,"m":3,"z":1}'

    def test_no_whitespace(self):
        result = canonical_json({"key": "value", "num": 42})
        assert b" " not in result
        assert b"\n" not in result

    def test_nested_sorted(self):
        result = canonical_json({"b": {"z": 1, "a": 2}, "a": 0})
        assert result == b'{"a":0,"b":{"a":2,"z":1}}'

    def test_deterministic_across_calls(self):
        """Same input always produces identical bytes."""
        obj = {"c": 3, "a": 1, "b": {"y": 25, "x": 24}}
        assert canonical_json(obj) == canonical_json(obj)

    def test_swap_deterministic(self):
        """Two identical SwapIntents produce identical digests."""
        s1 = make_swap()
        s2 = make_swap()
        assert s1.digest() == s2.digest()

    def test_swap_different_amount_different_digest(self):
        s1 = make_swap(amount_in_wei=1000)
        s2 = make_swap(amount_in_wei=2000)
        assert s1.digest() != s2.digest()


# ════════════════════════════════════════════════════════════════
# PROVARA EVENT TESTS
# ════════════════════════════════════════════════════════════════

class TestProvaraEvent:
    def test_from_payload_creates_unsigned_event(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=EventType.ACTION_PROPOSED,
            agent_role="quant",
            payload_model=swap,
            previous_digest=GENESIS_DIGEST,
            sequence=0,
        )
        assert evt.schema_version == SCHEMA_VERSION
        assert evt.event_type == EventType.ACTION_PROPOSED
        assert evt.agent_role == "quant"
        assert evt.payload_type == "SwapIntent"
        assert not evt.is_sealed()

    def test_payload_digest_verified_on_construction(self):
        """Tampered payload dict should fail validation."""
        swap = make_swap()
        payload_dict = swap.model_dump(mode="python")
        good_digest = sha256_hex(canonical_json(payload_dict))

        # Tamper with the payload
        payload_dict["amount_in_wei"] = 999999999

        with pytest.raises(ValidationError, match="Payload digest mismatch"):
            ProvaraEvent(
                schema_version=SCHEMA_VERSION,
                event_id="test-id",
                event_type=EventType.ACTION_PROPOSED,
                timestamp_epoch_ms=NOW_MS,
                previous_event_digest=GENESIS_DIGEST,
                sequence_number=0,
                agent_role="quant",
                payload=payload_dict,
                payload_type="SwapIntent",
                payload_digest=good_digest,  # Digest from ORIGINAL payload
                signer_public_key="",
                signature="",
            )

    def test_seal_returns_new_event(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=EventType.ACTION_PROPOSED,
            agent_role="quant",
            payload_model=swap,
            previous_digest=GENESIS_DIGEST,
            sequence=0,
        )
        sealed = evt.seal("deadbeef" * 8, "cafebabe" * 16)
        assert sealed.is_sealed()
        assert not evt.is_sealed()  # Original unchanged (frozen)

    def test_signable_bytes_excludes_signature(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=EventType.ACTION_PROPOSED,
            agent_role="quant",
            payload_model=swap,
            previous_digest=GENESIS_DIGEST,
            sequence=0,
        )
        sb = json.loads(evt.signable_bytes())
        assert "signer_public_key" not in sb
        assert "signature" not in sb

    def test_signable_digest_deterministic(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=EventType.ACTION_PROPOSED,
            agent_role="quant",
            payload_model=swap,
            previous_digest=GENESIS_DIGEST,
            sequence=0,
        )
        assert evt.signable_digest() == evt.signable_digest()

    def test_ndjson_roundtrip(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            event_type=EventType.ACTION_PROPOSED,
            agent_role="quant",
            payload_model=swap,
            previous_digest=GENESIS_DIGEST,
            sequence=0,
        )
        sealed = evt.seal("aa" * 32, "bb" * 64)

        line = sealed.to_ndjson_line()
        assert line.endswith("\n")

        parsed = json.loads(line)
        restored = ProvaraEvent.model_validate(parsed, strict=False)
        assert restored.event_id == sealed.event_id
        assert restored.payload_digest == sealed.payload_digest
        assert restored.is_sealed()


# ════════════════════════════════════════════════════════════════
# CHAIN INTEGRITY TESTS
# ════════════════════════════════════════════════════════════════

class TestChainIntegrity:
    def test_valid_chain(self):
        events = make_event_chain(4)
        ok, msg = verify_chain_integrity(events)
        assert ok, msg

    def test_empty_chain_valid(self):
        ok, msg = verify_chain_integrity([])
        assert ok

    def test_single_event_chain(self):
        events = make_event_chain(1)
        ok, msg = verify_chain_integrity(events)
        assert ok, msg

    def test_detects_broken_chain(self):
        events = make_event_chain(3)
        # Tamper: replace middle event's previous_digest
        tampered = events[1].model_copy(
            update={"previous_event_digest": "0" * 64}
        )
        events[1] = tampered
        ok, msg = verify_chain_integrity(events)
        assert not ok
        assert "Chain break" in msg

    def test_detects_sequence_gap(self):
        events = make_event_chain(3)
        # Tamper: wrong sequence number
        tampered = events[2].model_copy(update={"sequence_number": 99})
        events[2] = tampered
        ok, msg = verify_chain_integrity(events)
        assert not ok
        assert "Sequence gap" in msg

    def test_detects_missing_genesis(self):
        events = make_event_chain(2)
        tampered = events[0].model_copy(
            update={"previous_event_digest": "not_genesis"}
        )
        events[0] = tampered
        ok, msg = verify_chain_integrity(events)
        assert not ok
        assert "genesis" in msg


# ════════════════════════════════════════════════════════════════
# PIPELINE COMPLETENESS TESTS
# ════════════════════════════════════════════════════════════════

class TestPipelineCompleteness:
    def test_complete_pipeline(self):
        events = make_event_chain(4)  # signal → sim → audit → proposal
        ok, msg = verify_pipeline_completeness(events, 3)
        assert ok, msg

    def test_missing_audit(self):
        """Pipeline without AUDIT_PASSED should fail."""
        swap = make_swap()
        events = [
            ProvaraEvent.from_payload(
                EventType.SIGNAL_DETECTED, "scout", swap, GENESIS_DIGEST, 0
            ),
            ProvaraEvent.from_payload(
                EventType.SIMULATION_COMPLETE, "quant", swap, "x", 1
            ),
            # No AUDIT_PASSED
            ProvaraEvent.from_payload(
                EventType.ACTION_PROPOSED, "quant", swap, "y", 2
            ),
        ]
        ok, msg = verify_pipeline_completeness(events, 2)
        assert not ok
        assert "audit.passed" in msg

    def test_missing_simulation(self):
        swap = make_swap()
        events = [
            ProvaraEvent.from_payload(
                EventType.SIGNAL_DETECTED, "scout", swap, GENESIS_DIGEST, 0
            ),
            ProvaraEvent.from_payload(
                EventType.AUDIT_PASSED, "auditor", swap, "x", 1
            ),
            ProvaraEvent.from_payload(
                EventType.ACTION_PROPOSED, "quant", swap, "y", 2
            ),
        ]
        ok, msg = verify_pipeline_completeness(events, 2)
        assert not ok
        assert "simulation.complete" in msg


# ════════════════════════════════════════════════════════════════
# NDJSON VAULT LOG TESTS
# ════════════════════════════════════════════════════════════════

class TestVaultLog:
    def test_write_and_load(self):
        events = make_event_chain(3)
        sealed_events = [
            e.seal("aa" * 32, "bb" * 64) for e in events
        ]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ndjson", delete=False
        ) as f:
            for evt in sealed_events:
                f.write(evt.to_ndjson_line())
            path = f.name

        try:
            loaded = load_vault_log(path)
            assert len(loaded) == 3
            for orig, restored in zip(sealed_events, loaded):
                assert orig.event_id == restored.event_id
                assert orig.payload_digest == restored.payload_digest
                assert restored.is_sealed()
        finally:
            os.unlink(path)

    def test_rejects_tampered_log_entry(self):
        swap = make_swap()
        evt = ProvaraEvent.from_payload(
            EventType.ACTION_PROPOSED, "quant", swap, GENESIS_DIGEST, 0
        )
        sealed = evt.seal("aa" * 32, "bb" * 64)

        # Tamper: modify payload in the JSON line
        raw = json.loads(sealed.to_ndjson_line())
        raw["payload"]["amount_in_wei"] = 1  # Changed!
        tampered_line = json.dumps(raw, sort_keys=True, separators=(",", ":"))

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ndjson", delete=False
        ) as f:
            f.write(tampered_line + "\n")
            path = f.name

        try:
            with pytest.raises(ValueError, match="Failed to parse"):
                load_vault_log(path)
        finally:
            os.unlink(path)


# ════════════════════════════════════════════════════════════════
# FULL PIPELINE INTEGRATION TEST
# ════════════════════════════════════════════════════════════════

class TestFullPipeline:
    def test_end_to_end_decision_chain(self):
        """Simulate a complete decision chain:
        Scout detects → Quant simulates → Auditor approves → Action proposed.
        Then verify chain integrity and pipeline completeness.
        """
        swap = make_swap()

        # Scout detects a signal
        e0 = ProvaraEvent.from_payload(
            EventType.SIGNAL_DETECTED, "scout", swap, GENESIS_DIGEST, 0
        )

        # Sentinel confirms on-chain observation
        e1 = ProvaraEvent.from_payload(
            EventType.SENTINEL_OBSERVATION, "sentinel", swap,
            e0.signable_digest(), 1
        )

        # Quant runs simulation
        e2 = ProvaraEvent.from_payload(
            EventType.SIMULATION_COMPLETE, "quant", swap,
            e1.signable_digest(), 2
        )

        # Auditor validates
        e3 = ProvaraEvent.from_payload(
            EventType.AUDIT_PASSED, "auditor", swap,
            e2.signable_digest(), 3
        )

        # Action proposed
        e4 = ProvaraEvent.from_payload(
            EventType.ACTION_PROPOSED, "quant", swap,
            e3.signable_digest(), 4
        )

        chain = [e0, e1, e2, e3, e4]

        # Verify chain integrity
        ok, msg = verify_chain_integrity(chain)
        assert ok, msg

        # Verify pipeline completeness for the proposal
        ok, msg = verify_pipeline_completeness(chain, 4)
        assert ok, msg

        # Seal all events (simulating Ed25519 signing)
        sealed = [e.seal("aa" * 32, "bb" * 64) for e in chain]
        assert all(e.is_sealed() for e in sealed)

        # Write to NDJSON and reload
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".ndjson", delete=False
        ) as f:
            for evt in sealed:
                f.write(evt.to_ndjson_line())
            path = f.name

        try:
            reloaded = load_vault_log(path)
            assert len(reloaded) == 5

            # Re-verify chain integrity on reloaded events
            ok, msg = verify_chain_integrity(reloaded)
            assert ok, msg
        finally:
            os.unlink(path)
