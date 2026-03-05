"""
sovereign_schema.py — AEE Type System v1.0.0-provara

Hunt-Sovereign Autonomous Economic Entity
Deterministic, zkVM-safe type definitions.

Design constraints enforced:
  - RFC 8785 canonical JSON serialization (sorted keys, no whitespace)
  - NO FLOATS anywhere (wei for amounts, bps for percentages, epoch_ms for time)
  - NO field omission (every field always present, explicit defaults)
  - Pydantic V2 strict mode (no implicit type coercion)
  - Frozen models (immutable after construction)
  - Discriminated union for action types
  - Payload digests for independent verification
  - Two-phase signing (construct → sign → seal via model_copy)

Serialization guarantee:
  Every model produces identical canonical bytes whether serialized by
  Python middleware, Rust policy checker, or on-chain verifier. This is
  the foundational invariant for zkVM proof compatibility.

Usage:
  # Create a swap intent
  intent = SwapIntent(
      asset_in="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
      asset_out="0x4200000000000000000000000000000000000006",
      amount_in_wei=1000000,  # 1 USDC (6 decimals)
      min_amount_out_wei=380000000000000,  # ~0.00038 ETH
      max_slippage_bps=50,
      deadline_epoch_ms=1710000000000,
      receiver="0xYourVaultAddress...",
  )

  # Wrap in a Provara event
  event = ProvaraEvent.from_payload(
      event_type=EventType.ACTION_PROPOSED,
      agent_role="quant",
      payload_model=intent,
      previous_digest="genesis",
      sequence=0,
  )

  # Sign it
  signed = event.seal(signer_pub_hex, signature_hex)

  # Write as NDJSON
  with open("vault.ndjson", "a") as f:
      f.write(signed.to_ndjson_line())
"""

from __future__ import annotations

import json
import time
from enum import Enum
from typing import Annotated, Any, Literal, Union
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from provara.canonical_json import canonical_bytes as canonical_json, sha256_hex


# ════════════════════════════════════════════════════════════════
# BASE MODEL — Strict, Frozen, Deterministic
# ════════════════════════════════════════════════════════════════

EVM_ADDR = r"^0x[0-9a-fA-F]{40}$"
SCHEMA_VERSION = "1.0.0"
GENESIS_DIGEST = "genesis"


class _Base(BaseModel):
    """All AEE models inherit from this.

    Strict mode: "100" won't coerce to 100. Period.
    Frozen: Immutable after construction. Use model_copy(update=...) for derivation.
    """
    model_config = ConfigDict(
        strict=True,
        frozen=True,
        use_enum_values=True,
        ser_json_bytes="hex",
    )

    def canonical_bytes(self) -> bytes:
        """Deterministic byte representation for hashing/signing."""
        return canonical_json(self.model_dump(mode="python"))

    def digest(self) -> str:
        """SHA-256 hex digest of canonical representation."""
        return sha256_hex(self.canonical_bytes())


# ════════════════════════════════════════════════════════════════
# ACTION TYPES — Discriminated Union
#
# These are the ONLY shapes the AI agents can output.
# The VaultGate validates against these before any execution.
# ════════════════════════════════════════════════════════════════

class SwapIntent(_Base):
    """Agent proposes a token swap via CoW Protocol.

    The agent NEVER constructs a raw swap tx. It constructs this intent.
    CoW solvers handle routing, MEV protection, and batch optimization.
    If solvers can't fill within bounds, the order expires. No bad fills.
    """
    action_type: Literal["swap"] = "swap"

    asset_in: str = Field(..., pattern=EVM_ADDR)
    asset_out: str = Field(..., pattern=EVM_ADDR)
    amount_in_wei: int = Field(..., gt=0)
    min_amount_out_wei: int = Field(..., gt=0)
    max_slippage_bps: int = Field(..., gt=0, le=500)  # Hard cap: 5%
    deadline_epoch_ms: int = Field(..., gt=0)
    receiver: str = Field(..., pattern=EVM_ADDR)  # MUST be the vault address

    @model_validator(mode="after")
    def _no_self_swap(self) -> SwapIntent:
        if self.asset_in.lower() == self.asset_out.lower():
            raise ValueError("asset_in and asset_out must differ")
        return self

    @model_validator(mode="after")
    def _deadline_in_future(self) -> SwapIntent:
        now_ms = int(time.time() * 1000)
        if self.deadline_epoch_ms <= now_ms:
            raise ValueError("Deadline must be in the future")
        return self


class LendingAction(_Base):
    """Agent proposes a lending protocol operation (Aave, Morpho V2).

    Direct UserOp via session key. No intent system for lending (yet).
    Health factor monitoring is the Oracle Guardian's responsibility,
    but we enforce a minimum here as a hard floor.
    """
    action_type: Literal["lend"] = "lend"

    operation: Literal["supply", "withdraw", "repay"]
    protocol_address: str = Field(..., pattern=EVM_ADDR)
    asset: str = Field(..., pattern=EVM_ADDR)
    amount_wei: int = Field(..., gt=0)

    # Health factor floor: 15000 bps = 1.50x. Min allowed: 10000 bps = 1.00x.
    # Below 1.0 = liquidation territory. Hard reject.
    min_health_factor_bps: int = Field(default=15000, ge=10000)


class AllocationRebalance(_Base):
    """Strategist proposes vault allocation weight changes.

    Runs via the CVXPY solver output. Weights in basis points.
    Must sum to exactly 10000 (100.00%).
    Trigger and regime label provide context for the attestation trail.
    """
    action_type: Literal["rebalance"] = "rebalance"

    weight_stables_bps: int = Field(..., ge=0, le=10000)
    weight_active_bps: int = Field(..., ge=0, le=10000)
    weight_lending_bps: int = Field(..., ge=0, le=10000)
    weight_reserve_bps: int = Field(..., ge=0, le=10000)

    trigger: Literal["scheduled", "regime_shift", "circuit_breaker", "manual"]
    regime_label: str  # "bull" | "bear" | "high_vol" | "low_vol" | "unknown"
    risk_aversion_bps: int = Field(..., gt=0)  # Lambda * 10000

    @model_validator(mode="after")
    def _weights_sum_to_full(self) -> AllocationRebalance:
        total = (
            self.weight_stables_bps
            + self.weight_active_bps
            + self.weight_lending_bps
            + self.weight_reserve_bps
        )
        if total != 10000:
            raise ValueError(f"Weights must sum to 10000 bps, got {total}")
        return self


class EmergencyHalt(_Base):
    """Circuit breaker activation. Halts all non-defensive operations.

    Can be triggered by system (drawdown breach, oracle divergence)
    or manually by owner. Requires owner hardware sign-off to resume.
    """
    action_type: Literal["emergency_halt"] = "emergency_halt"

    reason: str
    triggered_by: Literal["system", "owner", "auditor", "oracle_guardian"]
    halt_scope: Literal["all", "active_trading", "lending", "rebalancing"]
    resume_requires: Literal["owner_signature", "cooldown_expiry", "manual_review"]
    cooldown_ms: int = Field(default=86400000, ge=0)  # Default: 24h


# The discriminated union — this is what the VaultGate accepts
ActionProposal = Annotated[
    Union[SwapIntent, LendingAction, AllocationRebalance, EmergencyHalt],
    Field(discriminator="action_type"),
]


# ════════════════════════════════════════════════════════════════
# SESSION KEY POLICY — Constitutional Parameter
#
# Encoded into ZeroDev Kernel's policy module at key creation.
# Also stored in the constitution for audit trail.
# ════════════════════════════════════════════════════════════════

class SessionKeyPolicy(_Base):
    """Defines the exact permissions of an agent session key.

    Every parameter here maps to a Kernel policy constraint.
    The middleware ALSO enforces these independently (defense in depth).
    """
    # Contract whitelist — ONLY these addresses can be called
    allowed_contracts: tuple[str, ...] = Field(..., min_length=1)

    # Allowed function selectors per contract (4-byte hex, e.g. "0x38ed1739")
    # Empty tuple = all functions on that contract (NOT recommended)
    allowed_selectors: tuple[str, ...] = Field(default=())

    # Spend limits
    max_wei_per_tx: int = Field(..., gt=0)
    max_wei_per_day: int = Field(..., gt=0)
    max_transactions_per_hour: int = Field(..., gt=0, le=100)

    # Gas
    max_gas_per_tx: int = Field(..., gt=0)

    # Temporal bounds
    valid_from_epoch_ms: int = Field(..., gt=0)
    expires_epoch_ms: int = Field(..., gt=0)

    # What happens when the key expires before renewal
    on_expiry: Literal["halt", "stables_only", "unwind_to_stables"]

    @model_validator(mode="after")
    def _valid_time_window(self) -> SessionKeyPolicy:
        if self.expires_epoch_ms <= self.valid_from_epoch_ms:
            raise ValueError("expires must be after valid_from")
        return self

    @field_validator("allowed_contracts")
    @classmethod
    def _validate_contract_addresses(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        import re
        pattern = re.compile(EVM_ADDR)
        for addr in v:
            if not pattern.match(addr):
                raise ValueError(f"Invalid address in whitelist: {addr}")
        return v

    @field_validator("allowed_selectors")
    @classmethod
    def _validate_selectors(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        import re
        pattern = re.compile(r"^0x[0-9a-fA-F]{8}$")
        for sel in v:
            if not pattern.match(sel):
                raise ValueError(f"Invalid function selector: {sel}")
        return v


# ════════════════════════════════════════════════════════════════
# CONSTITUTION — The AEE's Genesis Manifest
#
# Immutable without owner hardware signature.
# Amendments are versioned, attested schema evolution events.
# This is the "law" the zkVM policy checker enforces.
# ════════════════════════════════════════════════════════════════

class ConstitutionV1(_Base):
    """The AEE's governing document.

    Created at genesis. Every field is a hard constraint.
    Amendments produce a new ConstitutionV1 with bumped version,
    attested as a CONSTITUTION_AMENDED event with the diff.
    """
    version: str = SCHEMA_VERSION
    created_epoch_ms: int = Field(..., gt=0)

    # ── Identity ──
    entity_name: str
    chain_id: int = Field(..., gt=0)
    vault_address: str = Field(..., pattern=EVM_ADDR)
    owner_address: str = Field(..., pattern=EVM_ADDR)

    # ── Risk Bounds ──
    max_portfolio_drawdown_bps: int = Field(..., gt=0, le=10000)
    max_single_trade_pct_bps: int = Field(..., gt=0, le=10000)
    min_stables_reserve_bps: int = Field(..., ge=0, le=10000)
    max_active_trading_bps: int = Field(..., ge=0, le=10000)

    # ── Circuit Breakers ──
    daily_loss_halt_bps: int = Field(..., gt=0, le=10000)
    hourly_trade_limit: int = Field(..., gt=0)

    # ── Session Key Defaults ──
    default_session_policy: SessionKeyPolicy

    # ── Protocol & Token Whitelists ──
    allowed_protocols: tuple[str, ...] = Field(..., min_length=1)
    allowed_tokens: tuple[str, ...] = Field(..., min_length=1)
    sanctioned_token_blocklist: tuple[str, ...] = Field(default=())

    # ── Regime-Dependent Risk Aversion ──
    # Lambda multiplier * 10000. Higher = more conservative.
    risk_aversion_bull_bps: int = Field(default=10000)    # 1.0x
    risk_aversion_bear_bps: int = Field(default=25000)    # 2.5x
    risk_aversion_high_vol_bps: int = Field(default=30000) # 3.0x
    risk_aversion_low_vol_bps: int = Field(default=8000)   # 0.8x

    # ── Dependency Manifest (supply chain attestation) ──
    pinned_dependencies_digest: str  # SHA-256 of the full lockfile

    @model_validator(mode="after")
    def _reserve_plus_active_sane(self) -> ConstitutionV1:
        if self.min_stables_reserve_bps + self.max_active_trading_bps > 10000:
            raise ValueError("Reserve floor + active cap cannot exceed 100%")
        return self

    @field_validator("allowed_protocols", "allowed_tokens", "sanctioned_token_blocklist")
    @classmethod
    def _validate_address_tuples(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        import re
        pattern = re.compile(EVM_ADDR)
        for addr in v:
            if not pattern.match(addr):
                raise ValueError(f"Invalid address: {addr}")
        return v


# ════════════════════════════════════════════════════════════════
# PROVARA EVENT ENVELOPE
#
# The outermost layer. Wraps EVERY decision, action, observation,
# and governance event in the AEE lifecycle.
#
# Signing workflow (two-phase):
#   1. Construct via ProvaraEvent.from_payload(...) → unsigned event
#   2. Call event.signable_bytes() → deterministic bytes to sign
#   3. Sign with Ed25519 externally
#   4. Call event.seal(pub_key, signature) → immutable signed event
#   5. Write event.to_ndjson_line() to the vault log
# ════════════════════════════════════════════════════════════════

class EventType(str, Enum):
    """Semantic event taxonomy for the AEE lifecycle.

    Every event type maps to exactly one pipeline stage.
    The Chronicler enforces completeness — if a SIMULATION_COMPLETE
    exists without a preceding SIGNAL_DETECTED, the pipeline halts.
    """
    # ── Agent Pipeline ──
    SIGNAL_DETECTED      = "signal.detected"
    SENTINEL_OBSERVATION = "sentinel.observation"
    SIMULATION_COMPLETE  = "simulation.complete"
    AUDIT_PASSED         = "audit.passed"
    AUDIT_FAILED         = "audit.failed"
    ACTION_PROPOSED      = "action.proposed"
    ACTION_EXECUTED      = "action.executed"
    ACTION_EXPIRED       = "action.expired"
    ACTION_REJECTED      = "action.rejected"
    OUTCOME_RECORDED     = "outcome.recorded"

    # ── Governance ──
    CONSTITUTION_CREATED = "governance.constitution.created"
    CONSTITUTION_AMENDED = "governance.constitution.amended"
    SESSION_KEY_CREATED  = "governance.session_key.created"
    SESSION_KEY_REVOKED  = "governance.session_key.revoked"
    SESSION_KEY_RENEWED  = "governance.session_key.renewed"

    # ── System ──
    SCHEMA_PUBLISHED         = "system.schema.published"
    MANIFEST_ATTESTED        = "system.manifest.attested"
    CIRCUIT_BREAKER_TRIGGERED = "system.circuit_breaker.triggered"
    CIRCUIT_BREAKER_RESET    = "system.circuit_breaker.reset"
    DEPENDENCY_UPDATED       = "system.dependency.updated"

    # ── Adversarial ──
    ADVERSARIAL_TEST_RUN     = "adversarial.test.run"
    ADVERSARIAL_VULN_FOUND   = "adversarial.vulnerability.found"
    ADVERSARIAL_PATCH_APPLIED = "adversarial.patch.applied"

    # ── Oracle / Data Integrity ──
    ORACLE_READING           = "oracle.reading"
    ORACLE_DIVERGENCE        = "oracle.divergence.detected"
    VAULT_PRICE_ANOMALY      = "oracle.vault_price.anomaly"
    VAULT_4626_GUARD         = "oracle.4626.guard_triggered"


# Valid agent roles for attribution
AgentRole = Literal[
    "scout",
    "sentinel",
    "quant",
    "auditor",
    "strategist",
    "chronicler",
    "oracle_guardian",
    "owner",
    "system",
    "adversary",
]


class ProvaraEvent(_Base):
    """The universal event envelope for the AEE.

    Guarantees:
      - Deterministic serialization for hash chain integrity
      - Payload digest for independent verification
      - Two-phase signing (construct unsigned → seal with signature)
      - NDJSON-compatible output for append-only vault logs
      - zkVM-compatible: signable_bytes() output can be fed directly
        to a Risc Zero / SP1 guest program for proof generation
    """
    # ── Envelope ──
    schema_version: str = SCHEMA_VERSION
    event_id: str                          # UUID v4 as string
    event_type: EventType
    timestamp_epoch_ms: int = Field(..., gt=0)

    # ── Hash Chain ──
    previous_event_digest: str             # SHA-256 hex, or "genesis"
    sequence_number: int = Field(..., ge=0)

    # ── Attribution ──
    agent_role: AgentRole

    # ── Payload ──
    # Polymorphic content, serialized from a typed _Base model.
    # payload_type enables deserialization. payload_digest enables
    # independent verification without trusting the envelope.
    payload: dict[str, Any]
    payload_type: str                      # e.g. "SwapIntent", "LendingAction"
    payload_digest: str                    # SHA-256(canonical_json(payload))

    # ── Signature (empty until sealed) ──
    signer_public_key: str = ""            # Ed25519 public key, hex
    signature: str = ""                    # Ed25519 signature, hex

    # ── Validators ──

    @model_validator(mode="after")
    def _verify_payload_digest(self) -> ProvaraEvent:
        expected = sha256_hex(canonical_json(self.payload))
        if self.payload_digest != expected:
            raise ValueError(
                f"Payload digest mismatch: expected {expected}, "
                f"got {self.payload_digest}"
            )
        return self

    # ── Signing Workflow ──

    def signable_bytes(self) -> bytes:
        """Canonical bytes for Ed25519 signing.

        Excludes signer_public_key and signature fields — these are
        filled AFTER signing. Everything else is covered by the signature.
        """
        d = self.model_dump(mode="python")
        del d["signer_public_key"]
        del d["signature"]
        return canonical_json(d)

    def signable_digest(self) -> str:
        """SHA-256 of signable_bytes(). This is what gets signed."""
        return sha256_hex(self.signable_bytes())

    def seal(self, signer_pub_hex: str, signature_hex: str) -> ProvaraEvent:
        """Return a new immutable event with signature fields populated.

        Does NOT mutate self (frozen model). Returns a sealed copy.
        Verify the signature externally before trusting the sealed event.
        """
        return self.model_copy(update={
            "signer_public_key": signer_pub_hex,
            "signature": signature_hex,
        })

    def is_sealed(self) -> bool:
        """True if both signature fields are populated."""
        return bool(self.signer_public_key and self.signature)

    # ── Serialization ──

    def to_ndjson_line(self) -> str:
        """Single JSON line for append-only vault log. Includes newline."""
        return json.dumps(
            self.model_dump(mode="python"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ) + "\n"

    # ── Factory ──

    @classmethod
    def from_payload(
        cls,
        event_type: EventType,
        agent_role: AgentRole,
        payload_model: _Base,
        previous_digest: str,
        sequence: int,
    ) -> ProvaraEvent:
        """Create an unsigned event from a typed payload model.

        This is the primary construction path. The payload is serialized
        from the typed model, digest is computed, and the event is ready
        for signing via .signable_bytes() → external Ed25519 → .seal().
        """
        payload_dict = payload_model.model_dump(mode="python")
        return cls(
            schema_version=SCHEMA_VERSION,
            event_id=str(uuid4()),
            event_type=event_type,
            timestamp_epoch_ms=int(time.time() * 1000),
            previous_event_digest=previous_digest,
            sequence_number=sequence,
            agent_role=agent_role,
            payload=payload_dict,
            payload_type=type(payload_model).__qualname__,
            payload_digest=sha256_hex(canonical_json(payload_dict)),
            signer_public_key="",
            signature="",
        )


# ════════════════════════════════════════════════════════════════
# CHAIN VERIFICATION HELPERS
# ════════════════════════════════════════════════════════════════

def verify_chain_integrity(events: list[ProvaraEvent]) -> tuple[bool, str]:
    """Verify hash chain continuity across a sequence of events.

    Returns (True, "ok") or (False, "description of break").
    Does NOT verify Ed25519 signatures — that requires the public keys.
    This only checks structural chain integrity.
    """
    if not events:
        return True, "ok"

    for i, event in enumerate(events):
        # Sequence must be monotonically increasing
        if event.sequence_number != i:
            return False, (
                f"Sequence gap at index {i}: "
                f"expected {i}, got {event.sequence_number}"
            )

        # First event must reference genesis
        if i == 0:
            if event.previous_event_digest != GENESIS_DIGEST:
                return False, (
                    f"First event must reference '{GENESIS_DIGEST}', "
                    f"got '{event.previous_event_digest}'"
                )
            continue

        # Subsequent events must reference the signable digest of the previous
        prev_digest = events[i - 1].signable_digest()
        if event.previous_event_digest != prev_digest:
            return False, (
                f"Chain break at sequence {i}: "
                f"expected {prev_digest}, "
                f"got {event.previous_event_digest}"
            )

    return True, "ok"


def verify_pipeline_completeness(
    events: list[ProvaraEvent],
    proposal_index: int,
) -> tuple[bool, str]:
    """Verify that an ACTION_PROPOSED event has the required precursors.

    A valid proposal chain must include:
      SIGNAL_DETECTED → SIMULATION_COMPLETE → AUDIT_PASSED → ACTION_PROPOSED

    Returns (True, "ok") or (False, "missing stage description").
    """
    if proposal_index >= len(events):
        return False, f"Index {proposal_index} out of range"

    target = events[proposal_index]
    if target.event_type != EventType.ACTION_PROPOSED:
        return False, f"Event at {proposal_index} is {target.event_type}, not ACTION_PROPOSED"

    # Walk backwards from the proposal to find precursors
    required_stages = {
        EventType.SIGNAL_DETECTED,
        EventType.SIMULATION_COMPLETE,
        EventType.AUDIT_PASSED,
    }
    found: set[str] = set()

    for i in range(proposal_index - 1, -1, -1):
        evt = events[i]
        if evt.event_type in required_stages:
            found.add(evt.event_type)
        # Stop if we hit a previous proposal (different decision chain)
        if evt.event_type == EventType.ACTION_PROPOSED:
            break

    missing = required_stages - found
    if missing:
        labels = ", ".join(sorted(m.value for m in missing))
        return False, f"Missing precursors: {labels}"

    return True, "ok"


# ════════════════════════════════════════════════════════════════
# CONVENIENCE: Parse NDJSON vault log
# ════════════════════════════════════════════════════════════════

def load_vault_log(path: str) -> list[ProvaraEvent]:
    """Load and parse an NDJSON vault log into typed events.

    Uses non-strict validation for deserialization (strings → enums).
    Construction remains strict (no type coercion from AI output).
    Validates each event's payload digest on load.
    Does NOT verify signatures (requires keys).
    """
    events: list[ProvaraEvent] = []
    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                events.append(
                    ProvaraEvent.model_validate(raw, strict=False)
                )
            except Exception as e:
                raise ValueError(
                    f"Failed to parse vault log line {line_num}: {e}"
                ) from e
    return events
