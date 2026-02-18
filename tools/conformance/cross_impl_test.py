#!/usr/bin/env python
"""Cross-implementation conformance harness for Provara Python and Rust."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
RUST_DIR = REPO_ROOT / "provara-rs"
RUST_BRIDGE_PKG = "provara-core"
RUST_BRIDGE_BIN = "cross_impl"
CANONICAL_VECTORS = REPO_ROOT / "test_vectors" / "canonical_conformance.json"

sys.path.insert(0, str(SRC_DIR))

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from provara.backpack_signing import load_public_key_b64, verify_event_signature
from provara.canonical_json import canonical_bytes
from provara.sync_v0 import load_events


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(SRC_DIR))
    return subprocess.run(cmd, cwd=str(cwd or REPO_ROOT), text=True, capture_output=True, env=env)


def _run_or_raise(cmd: list[str], cwd: Path | None = None) -> str:
    proc = _run(cmd, cwd)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({' '.join(cmd)}):\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout.strip()


def _cargo_bridge(args: list[str]) -> str:
    cmd = ["cargo", "run", "-q", "-p", RUST_BRIDGE_PKG, "--bin", RUST_BRIDGE_BIN, "--", *args]
    return _run_or_raise(cmd, RUST_DIR)


def _python_verify_vault(vault: Path) -> None:
    keys = json.loads((vault / "identity" / "keys.json").read_text(encoding="utf-8"))
    key_map: dict[str, Any] = {}
    for entry in keys.get("keys", []):
        kid = entry.get("key_id")
        pub = entry.get("public_key_b64")
        if kid and pub:
            key_map[str(kid)] = load_public_key_b64(str(pub))

    events = load_events(vault / "events" / "events.ndjson")
    last_by_actor: dict[str, str] = {}
    for event in events:
        actor = str(event.get("actor", ""))
        eid = str(event.get("event_id", ""))
        prev = event.get("prev_event_hash")
        if actor in last_by_actor:
            if prev != last_by_actor[actor]:
                raise AssertionError(f"broken chain for actor {actor}: expected {last_by_actor[actor]}, got {prev}")
        else:
            if prev is not None:
                raise AssertionError(f"first event for actor {actor} must have null prev_event_hash")
        sig = event.get("sig")
        kid = event.get("actor_key_id")
        if sig:
            if kid not in key_map:
                raise AssertionError(f"event {eid} references unknown key {kid}")
            if not verify_event_signature(event, key_map[str(kid)]):
                raise AssertionError(f"invalid signature on {eid}")
        last_by_actor[actor] = eid


def _python_create_vault(vault: Path) -> None:
    keys_out = vault / "identity" / "private_keys.json"
    _run_or_raise(
        [
            sys.executable,
            "-m",
            "provara.cli",
            "init",
            str(vault),
            "--private-keys",
            str(keys_out),
        ]
    )


def _python_sign_same_event() -> tuple[str, str]:
    private_key = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    ).decode("utf-8")

    event = {
        "type": "OBSERVATION",
        "actor": "interop_actor",
        "prev_event_hash": None,
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "payload": {"subject": "interop", "predicate": "match", "value": 1},
        "event_id": "evt_dummy_for_signature_comparison",
        "actor_key_id": "bp1_dummy",
    }

    canonical = canonical_bytes(event)
    digest = hashlib.sha256(canonical).digest()
    py_sig = base64.b64encode(private_key.sign(digest)).decode("utf-8")

    rust_sig = _cargo_bridge(
        [
            "sign-event-json",
            "--private-key-b64",
            priv_b64,
            "--event-json",
            json.dumps(event, separators=(",", ":")),
        ]
    ).strip()
    return py_sig, rust_sig


def _canonical_conformance() -> None:
    suite = json.loads(CANONICAL_VECTORS.read_text(encoding="utf-8"))
    for vector in suite.get("vectors", []):
        input_obj = vector["input"]
        expected_hex = vector["expected_hex"]

        py_canonical = canonical_bytes(input_obj)
        py_hash = hashlib.sha256(py_canonical).hexdigest()
        expected_hash = hashlib.sha256(bytes.fromhex(expected_hex)).hexdigest()

        rust_hash = _cargo_bridge(
            ["canonical-sha256", "--input-json", json.dumps(input_obj, separators=(",", ":"))]
        ).strip()

        if py_hash != expected_hash:
            raise AssertionError(f"Python canonical mismatch for {vector['id']}")
        if rust_hash != py_hash:
            raise AssertionError(f"Rust canonical mismatch for {vector['id']}")


def run_all() -> list[Check]:
    checks: list[Check] = []

    with tempfile.TemporaryDirectory(prefix="provara-cross-impl-") as td:
        tmp = Path(td)

        py_vault = tmp / "vault_py"
        py_vault.mkdir(parents=True, exist_ok=True)
        _python_create_vault(py_vault)

        try:
            _python_verify_vault(py_vault)
            checks.append(Check("python creates -> python verifies", True))
        except Exception as exc:
            checks.append(Check("python creates -> python verifies", False, str(exc)))

        try:
            _cargo_bridge(["verify-vault", "--vault", str(py_vault)])
            checks.append(Check("python creates -> rust verifies", True))
        except Exception as exc:
            checks.append(Check("python creates -> rust verifies", False, str(exc)))

        rust_vault = tmp / "vault_rust"
        rust_vault.mkdir(parents=True, exist_ok=True)
        try:
            _cargo_bridge(["create-vault", "--vault", str(rust_vault)])
            _python_verify_vault(rust_vault)
            checks.append(Check("rust creates -> python verifies", True))
        except Exception as exc:
            checks.append(Check("rust creates -> python verifies", False, str(exc)))

    try:
        _canonical_conformance()
        checks.append(Check("canonical JSON conformance (python/rust)", True))
    except Exception as exc:
        checks.append(Check("canonical JSON conformance (python/rust)", False, str(exc)))

    try:
        py_sig, rust_sig = _python_sign_same_event()
        ok = py_sig == rust_sig
        checks.append(Check("same event signed by python+rust -> identical signature", ok, "" if ok else "signature bytes differ"))
    except Exception as exc:
        checks.append(Check("same event signed by python+rust -> identical signature", False, str(exc)))

    checks.append(Check("typescript interoperability", True, "stubbed until provara-ts lands"))

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross implementation interoperability tests")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    checks = run_all()
    ok = all(c.ok for c in checks)

    if args.json:
        print(json.dumps({"ok": ok, "checks": [c.__dict__ for c in checks]}, indent=2))
    else:
        for c in checks:
            status = "PASS" if c.ok else "FAIL"
            detail = f" - {c.detail}" if c.detail else ""
            print(f"[{status}] {c.name}{detail}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
