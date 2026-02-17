#!/usr/bin/env python
"""
Conformance Kit v1 verifier for Provara-compatible outputs.

Checks:
1. Event schema sanity (core envelope + per-type payload requirements)
2. Chain and signature integrity
3. Reducer hash parity (replay hash vs state/current_state.json when present)
4. Optional normative vectors and compliance suite execution
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
TEST_DIR = REPO_ROOT / "tests"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from provara.canonical_json import canonical_hash  # type: ignore
from provara.reducer_v0 import SovereignReducerV0  # type: ignore
from provara.backpack_signing import load_public_key_b64, verify_event_signature  # type: ignore


CORE_TYPES = {
    "GENESIS",
    "OBSERVATION",
    "ASSERTION",
    "ATTESTATION",
    "RETRACTION",
    "KEY_REVOCATION",
    "KEY_PROMOTION",
    "REDUCER_EPOCH",
}
EVENT_ID_PATTERN = re.compile(r"^evt_[0-9a-f]{24}$")

PAYLOAD_REQUIRED: Dict[str, Tuple[str, ...]] = {
    "GENESIS": ("uid", "root_key_id", "birth_timestamp"),
    "OBSERVATION": ("subject", "predicate"),
    "ASSERTION": ("subject", "predicate"),
    "ATTESTATION": ("subject", "predicate", "value"),
    "RETRACTION": ("subject", "predicate"),
    "KEY_REVOCATION": ("revoked_key_id",),
    "KEY_PROMOTION": ("new_key_id", "new_public_key_b64", "algorithm", "replaces_key_id"),
    "REDUCER_EPOCH": ("epoch_id", "reducer_hash"),
}

TYPE_NAMESPACE_REQUIRED = {
    "GENESIS": "canonical",
    "OBSERVATION": "local",
    "ATTESTATION": "canonical",
    "KEY_REVOCATION": "canonical",
    "KEY_PROMOTION": "canonical",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: List[str] = field(default_factory=list)


def _load_ndjson(path: Path) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            raw = line.strip()
            if not raw:
                continue
            try:
                evt = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"MALFORMED_JSON at line {idx}: {exc}") from exc
            if not isinstance(evt, dict):
                raise ValueError(f"Line {idx} is not a JSON object")
            events.append(evt)
    return events


def _build_pubkeys(vault: Path) -> Dict[str, Any]:
    keys_path = vault / "identity" / "keys.json"
    data = json.loads(keys_path.read_text(encoding="utf-8"))
    out: Dict[str, Any] = {}
    for entry in data.get("keys", []):
        kid = entry.get("key_id")
        pub = entry.get("public_key_b64")
        if not kid or not pub:
            continue
        try:
            out[kid] = load_public_key_b64(pub)
        except Exception:
            continue
    return out


def check_schema(events: List[Dict[str, Any]]) -> CheckResult:
    errors: List[str] = []
    seen_ids = set()
    for i, e in enumerate(events):
        eid = e.get("event_id")
        et = e.get("type")
        payload = e.get("payload")
        if not isinstance(eid, str):
            errors.append(f"event[{i}] missing/invalid event_id")
            continue
        if eid in seen_ids:
            errors.append(f"duplicate event_id: {eid}")
        seen_ids.add(eid)
        if not isinstance(et, str):
            errors.append(f"event[{i}] {eid} missing/invalid type")
            continue
        if not isinstance(e.get("actor"), str):
            errors.append(f"event[{i}] {eid} missing/invalid actor")
        if not isinstance(e.get("timestamp_utc"), str):
            errors.append(f"event[{i}] {eid} missing/invalid timestamp_utc")
        if not isinstance(payload, dict):
            errors.append(f"event[{i}] {eid} missing/invalid payload")
            continue

        # Core types must be unprefixed; custom types must be reverse-domain.
        if et not in CORE_TYPES and "." not in et:
            errors.append(f"event[{i}] {eid} custom type is not reverse-domain: {et}")

        required_payload = PAYLOAD_REQUIRED.get(et, ())
        for field in required_payload:
            if field not in payload:
                errors.append(f"event[{i}] {eid} payload missing {field}")

        req_ns = TYPE_NAMESPACE_REQUIRED.get(et)
        if req_ns is not None and e.get("namespace") != req_ns:
            errors.append(
                f"event[{i}] {eid} type {et} requires namespace={req_ns}, got={e.get('namespace')}"
            )

    return CheckResult("schema", ok=not errors, details=errors)


def check_chain_and_signatures(vault: Path, events: List[Dict[str, Any]]) -> CheckResult:
    errors: List[str] = []
    notes: List[str] = []
    # Validate per-event derived event_id.
    for e in events:
        eid = e.get("event_id", "unknown")
        if isinstance(eid, str) and EVENT_ID_PATTERN.match(eid):
            hashable = {k: v for k, v in e.items() if k not in ("event_id", "sig")}
            derived = f"evt_{canonical_hash(hashable)[:24]}"
            if derived != eid:
                errors.append(f"HASH_MISMATCH: {eid} derived={derived}")
        else:
            notes.append(f"legacy_event_id_not_derived: {eid}")

    # Validate per-actor chain based on file order.
    by_actor: Dict[str, List[Dict[str, Any]]] = {}
    for e in events:
        actor = e.get("actor")
        if isinstance(actor, str):
            by_actor.setdefault(actor, []).append(e)

    for actor, actor_events in by_actor.items():
        for idx, e in enumerate(actor_events):
            prev = e.get("prev_event_hash")
            if idx == 0:
                if prev is not None:
                    errors.append(
                        f"BROKEN_CAUSAL_CHAIN: actor={actor} first event {e.get('event_id')} prev_event_hash must be null"
                    )
            else:
                exp = actor_events[idx - 1].get("event_id")
                if prev != exp:
                    errors.append(
                        f"BROKEN_CAUSAL_CHAIN: actor={actor} event {e.get('event_id')} prev={prev} expected={exp}"
                    )

    # Validate signatures against registered public keys (including revoked keys for historical events).
    pubkeys = _build_pubkeys(vault)
    for e in events:
        sig = e.get("sig")
        kid = e.get("actor_key_id")
        eid = e.get("event_id", "unknown")
        if not sig:
            continue
        if not kid or kid not in pubkeys:
            errors.append(f"UNKNOWN_KEY_ID: event {eid} key {kid}")
            continue
        if not verify_event_signature(e, pubkeys[kid]):
            errors.append(f"INVALID_SIGNATURE: event {eid}")

    return CheckResult("chain_and_signatures", ok=not errors, details=errors + notes)


def check_reducer_hash(vault: Path, events: List[Dict[str, Any]]) -> CheckResult:
    errors: List[str] = []
    reducer = SovereignReducerV0()
    reducer.apply_events(events)
    replay_hash = reducer.state["metadata"]["state_hash"]

    state_file = vault / "state" / "current_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
            stored_hash = state.get("metadata", {}).get("state_hash")
        except Exception as exc:
            return CheckResult("reducer_hash", ok=False, details=[f"failed to parse state/current_state.json: {exc}"])
        if stored_hash != replay_hash:
            errors.append(f"state hash mismatch: stored={stored_hash} replay={replay_hash}")

    return CheckResult("reducer_hash", ok=not errors, details=errors or [f"replay_state_hash={replay_hash}"])


def _run_subprocess(cmd: List[str]) -> Tuple[bool, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC_DIR)
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode == 0, output.strip()


def check_vectors() -> CheckResult:
    ok, out = _run_subprocess([sys.executable, str(TEST_DIR / "test_vectors.py")])
    return CheckResult("vectors", ok=ok, details=[out] if out else [])


def check_compliance(vault: Path) -> CheckResult:
    ok, out = _run_subprocess(
        [
            sys.executable,
            str(TEST_DIR / "backpack_compliance_v1.py"),
            str(vault),
            "-q",
        ]
    )
    return CheckResult("compliance", ok=ok, details=[out] if out else [])


def run_conformance(vault: Path, run_vectors: bool, run_compliance_suite: bool) -> List[CheckResult]:
    events_path = vault / "events" / "events.ndjson"
    if not events_path.exists():
        return [CheckResult("load_events", ok=False, details=[f"missing file: {events_path}"])]

    try:
        events = _load_ndjson(events_path)
    except Exception as exc:
        return [CheckResult("load_events", ok=False, details=[str(exc)])]

    results = [
        check_schema(events),
        check_chain_and_signatures(vault, events),
        check_reducer_hash(vault, events),
    ]
    if run_vectors:
        results.append(check_vectors())
    if run_compliance_suite:
        results.append(check_compliance(vault))
    return results


def _print_results(results: List[CheckResult], as_json: bool) -> int:
    ok = all(r.ok for r in results)
    if as_json:
        payload = {
            "ok": ok,
            "checks": [
                {"name": r.name, "ok": r.ok, "details": r.details}
                for r in results
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        for r in results:
            status = "PASS" if r.ok else "FAIL"
            print(f"[{status}] {r.name}")
            if r.details:
                for d in r.details:
                    if d:
                        print(f"  - {d}")
    return 0 if ok else 1


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Provara Conformance Kit v1 verifier")
    ap.add_argument("--vault", required=True, help="Path to candidate backpack/vault")
    ap.add_argument("--skip-vectors", action="store_true", help="Skip test_vectors execution")
    ap.add_argument("--skip-compliance", action="store_true", help="Skip backpack_compliance_v1 execution")
    ap.add_argument("--json", action="store_true", help="Emit JSON summary")
    args = ap.parse_args(argv)

    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        print(f"Vault path is not a directory: {vault}", file=sys.stderr)
        return 2

    results = run_conformance(
        vault=vault,
        run_vectors=not args.skip_vectors,
        run_compliance_suite=not args.skip_compliance,
    )
    return _print_results(results, as_json=args.json)


if __name__ == "__main__":
    raise SystemExit(main())
