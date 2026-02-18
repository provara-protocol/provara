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
TS_DIR = REPO_ROOT / "provara-ts"
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


def _ts_available() -> bool:
    """Return True if provara-ts has been built (dist/src/index.js exists)."""
    return (TS_DIR / "dist" / "src" / "index.js").exists()


def _node_esm(script: str) -> str:
    """Run an inline ESM Node.js script via stdin from the provara-ts/ directory.

    Uses explicit bytes I/O with UTF-8 to avoid Windows CP-1252 codec issues
    when Node.js outputs non-ASCII characters (e.g., £, €) to stdout.
    """
    proc = subprocess.run(
        ["node", "--input-type=module"],
        input=script.encode("utf-8"),
        capture_output=True,
        cwd=str(TS_DIR),
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Node.js script failed:\n{proc.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return proc.stdout.decode("utf-8")


def _ts_canonical_conformance() -> None:
    """Verify TS canonical JSON output matches Python byte-for-byte on all vectors."""
    suite = json.loads(CANONICAL_VECTORS.read_text(encoding="utf-8"))
    for vector in suite.get("vectors", []):
        vid = vector["id"]
        expected = bytes.fromhex(vector["expected_hex"]).decode("utf-8")

        if vid == "number_formatting_minus_zero":
            # JSON.parse collapses -0.0 → +0; must feed raw text to canonicalizeRaw
            raw = '{"minus_zero":-0.0,"zero":0.0}'
            script = (
                'import { canonicalizeRaw } from "./dist/src/index.js";\n'
                f'process.stdout.write(canonicalizeRaw({json.dumps(raw)}));\n'
            )
        else:
            input_json = json.dumps(vector["input"], separators=(",", ":"))
            script = (
                'import { canonicalize } from "./dist/src/index.js";\n'
                f'const v = JSON.parse({json.dumps(input_json)});\n'
                "process.stdout.write(canonicalize(v));\n"
            )

        ts_result = _node_esm(script).strip()
        if ts_result != expected:
            raise AssertionError(
                f"TS canonical mismatch for {vid}:\n"
                f"  expected: {expected!r}\n"
                f"  got:      {ts_result!r}"
            )


def _ts_verify_vault(vault: Path) -> None:
    """Have the TS verifyVault function check a Python-created vault."""
    vault_posix = vault.as_posix()
    script = (
        'import { verifyVault } from "./dist/src/index.js";\n'
        f'const r = verifyVault({json.dumps(vault_posix)});\n'
        "if (r.invalid > 0 || !r.chainsOk) {\n"
        "  process.stderr.write(JSON.stringify(r.errors));\n"
        "  process.exit(1);\n"
        "}\n"
        'process.stdout.write("ok");\n'
    )
    out = _node_esm(script).strip()
    if out != "ok":
        raise AssertionError(f"TS vault verification failed: {out}")


def _ts_signing_interop() -> None:
    """
    Python signs canonical bytes of an event → TS verifies.
    TS signs the same event → Python verifies.
    Both implementations must produce signatures the other can accept.
    """
    private_key = Ed25519PrivateKey.generate()
    priv_b64 = base64.b64encode(
        private_key.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
    ).decode()
    pub_b64 = base64.b64encode(
        private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
    ).decode()

    event: dict[str, Any] = {
        "type": "OBSERVATION",
        "actor": "interop_actor",
        "prev_event_hash": None,
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "payload": {"subject": "x", "predicate": "y", "value": 1},
        "event_id": "evt_interop_test_id",
        "actor_key_id": "bp1_interop",
    }
    event_json = json.dumps(event, separators=(",", ":"))

    # Python signs canonical_bytes(event) directly (no SHA-256 prehash)
    py_sig = base64.b64encode(private_key.sign(canonical_bytes(event))).decode()

    # TS verifies Python signature
    verify_script = (
        'import { verifyBytes, canonicalBytes } from "./dist/src/index.js";\n'
        f'const event = JSON.parse({json.dumps(event_json)});\n'
        f'const sig = {json.dumps(py_sig)};\n'
        f'const pub = {json.dumps(pub_b64)};\n'
        "process.stdout.write(verifyBytes(canonicalBytes(event), sig, pub) ? 'ok' : 'fail');\n"
    )
    if _node_esm(verify_script).strip() != "ok":
        raise AssertionError("TS failed to verify Python-signed event")

    # TS signs, Python verifies
    sign_script = (
        'import { signBytes, canonicalBytes } from "./dist/src/index.js";\n'
        f'const event = JSON.parse({json.dumps(event_json)});\n'
        f'const priv = {json.dumps(priv_b64)};\n'
        "process.stdout.write(signBytes(canonicalBytes(event), priv));\n"
    )
    ts_sig_b64 = _node_esm(sign_script).strip()
    ts_sig_bytes = base64.b64decode(ts_sig_b64)
    try:
        private_key.public_key().verify(ts_sig_bytes, canonical_bytes(event))
    except Exception as exc:
        raise AssertionError(f"Python failed to verify TS-signed event: {exc}") from exc


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

        if _ts_available():
            try:
                _ts_verify_vault(py_vault)
                checks.append(Check("python creates -> typescript verifies", True))
            except Exception as exc:
                checks.append(Check("python creates -> typescript verifies", False, str(exc)))

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

    if _ts_available():
        try:
            _ts_canonical_conformance()
            checks.append(Check("canonical JSON conformance (python/typescript)", True))
        except Exception as exc:
            checks.append(Check("canonical JSON conformance (python/typescript)", False, str(exc)))

        try:
            _ts_signing_interop()
            checks.append(Check("python/typescript signing interoperability", True))
        except Exception as exc:
            checks.append(Check("python/typescript signing interoperability", False, str(exc)))
    else:
        checks.append(Check(
            "typescript interoperability",
            False,
            "provara-ts not built — run: cd provara-ts && npm ci && npm run build",
        ))

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
