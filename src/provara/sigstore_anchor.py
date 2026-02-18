"""sigstore_anchor.py -- Sigstore Transparency Log Anchoring.

Optional integration — requires: pip install 'provara-protocol[sigstore]'

Provides public, tamper-evident proof that a vault state existed at a
specific time.  Complements RFC 3161 (private TSA) with a public log:
anyone can verify the Rekor entry without contacting the original TSA.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


_SIGSTORE_AVAILABLE = False
_SIGSTORE_IMPORT_ERROR: str = ""

try:
    import sigstore as _sigstore_module  # noqa: F401  (presence-check only)
    _SIGSTORE_AVAILABLE = True
except ImportError as _exc:
    _SIGSTORE_IMPORT_ERROR = str(_exc)


ANCHORS_DIR = "anchors"
ANCHOR_FORMAT = "provara-sigstore-anchor-v1"


def _require_sigstore() -> None:
    if not _SIGSTORE_AVAILABLE:
        raise ImportError(
            "Sigstore anchoring requires: pip install 'provara-protocol[sigstore]'\n"
            f"  Underlying error: {_SIGSTORE_IMPORT_ERROR}"
        )


@dataclass
class AnchorResult:
    """Result of anchoring a vault state to Sigstore's transparency log."""

    log_index: int
    log_id: str
    integrated_time: datetime
    verification_url: str
    merkle_root: str
    vault_event_count: int
    anchor_path: Optional[Path] = None
    identity: str = ""
    issuer: str = ""


def _current_merkle_root(vault_path: Path) -> str:
    """Return the vault Merkle root (from cache or computed on demand)."""
    mr_file = vault_path / "merkle_root.txt"
    if mr_file.exists():
        return mr_file.read_text(encoding="utf-8").strip()
    from provara.manifest_generator import build_manifest, manifest_leaves
    from provara.backpack_integrity import merkle_root_hex, MANIFEST_EXCLUDE
    manifest = build_manifest(vault_path, set(MANIFEST_EXCLUDE))
    leaves = manifest_leaves(manifest)
    return merkle_root_hex(leaves)


def _current_event_count(vault_path: Path) -> int:
    """Return the current event count from the vault SQLite index."""
    try:
        from provara.query import VaultIndex
        with VaultIndex(vault_path) as idx:
            idx.update()
            return sum(idx.get_actor_summary().values())
    except Exception:
        return 0


def _build_payload(vault_path: Path, event_id: Optional[str]) -> bytes:
    """Return the bytes to anchor: a specific event hash or the Merkle root."""
    if event_id is not None:
        from provara.sync_v0 import load_events
        from provara.canonical_json import canonical_hash
        events_file = vault_path / "events" / "events.ndjson"
        for ev in load_events(events_file):
            if ev.get("event_id") == event_id:
                return canonical_hash(ev).encode("utf-8")
        raise ValueError(f"Event not found in vault: {event_id!r}")
    return _current_merkle_root(vault_path).encode("utf-8")

def _sigstore_sign(payload: bytes, staging: bool = False) -> Any:
    """Internal: sign *payload* with Sigstore. Extracted for testability."""
    from sigstore.sign import SigningContext
    from sigstore.oidc import detect_credential
    token = detect_credential()
    ctx_factory = SigningContext.staging if staging else SigningContext.production
    with ctx_factory() as ctx:
        with ctx.signer(token, transparent=True) as signer:
            result = signer.sign_artifact(io.BytesIO(payload))
            return result.bundle


def _extract_log_entry(bundle: Any) -> dict[str, Any]:
    """Extract {log_index, log_id, integrated_time} from a Sigstore bundle."""
    # sigstore-python v3.x primary shape
    try:
        entries = bundle.verification_material.tlog_entries
        e = entries[0]
        return {
            "log_index": int(e.log_index),
            "log_id": str(e.log_id),
            "integrated_time": int(e.integrated_time),
        }
    except (AttributeError, IndexError, TypeError):
        pass
    # Fallback for alternate bundle shapes
    try:
        e = bundle.log_entry
        return {
            "log_index": int(e.log_index),
            "log_id": str(e.log_id),
            "integrated_time": int(e.integrated_time),
        }
    except (AttributeError, TypeError):
        pass
    raise RuntimeError(
        "Cannot extract Rekor log entry from Sigstore bundle — "
        "check sigstore-python version compatibility."
    )

def anchor_to_sigstore(
    vault_path: Path,
    event_id: Optional[str] = None,
    staging: bool = False,
) -> AnchorResult:
    """Anchor vault Merkle root (or specific event hash) to Sigstore.

    Requires an OIDC identity.  In GitHub Actions, ambient credentials are
    detected automatically.  Locally, a browser opens for the OIDC flow.

    Args:
        vault_path:  Absolute path to a Provara vault directory.
        event_id:    If supplied, anchors this event's canonical hash
                     instead of the full Merkle root.
        staging:     Use Sigstore staging environment (for development).

    Returns:
        AnchorResult with Rekor log entry metadata and path to the stored
        anchor JSON file.

    Raises:
        ImportError:  if sigstore is not installed.
        ValueError:   if vault_path is not a directory, or event_id is given
                      but not found in the vault.
    """
    _require_sigstore()

    if not vault_path.is_dir():
        raise ValueError(f"Vault path is not a directory: {vault_path}")

    payload = _build_payload(vault_path, event_id)
    merkle_root = _current_merkle_root(vault_path)
    event_count = _current_event_count(vault_path)

    bundle = _sigstore_sign(payload, staging=staging)
    entry = _extract_log_entry(bundle)

    log_index: int = entry["log_index"]
    log_id: str = entry["log_id"]
    integrated_dt = datetime.fromtimestamp(
        int(entry["integrated_time"]), tz=timezone.utc
    )
    verification_url = (
        f"https://search.sigstore.dev/?logIndex={log_index}"
    )

    # Persist anchor file
    anchors_dir = vault_path / ANCHORS_DIR
    anchors_dir.mkdir(exist_ok=True)
    ts_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    anchor_file = anchors_dir / f"{ts_str}_{log_index}.json"

    bundle_data: Any = {}
    if hasattr(bundle, "to_json"):
        bundle_data = bundle.to_json()

    anchor_doc: dict[str, Any] = {
        "format": ANCHOR_FORMAT,
        "event_id": event_id,
        "merkle_root": merkle_root,
        "vault_event_count": event_count,
        "anchor_timestamp": datetime.now(timezone.utc).isoformat(),
        "log_index": log_index,
        "log_id": log_id,
        "integrated_time": integrated_dt.isoformat(),
        "verification_url": verification_url,
        "sigstore_bundle": bundle_data,
    }
    anchor_file.write_text(json.dumps(anchor_doc, indent=2), encoding="utf-8")

    return AnchorResult(
        log_index=log_index,
        log_id=log_id,
        integrated_time=integrated_dt,
        verification_url=verification_url,
        merkle_root=merkle_root,
        vault_event_count=event_count,
        anchor_path=anchor_file,
    )

def _sigstore_verify(payload: bytes, bundle_data: Any) -> bool:
    """Internal: verify *payload* against a serialised Sigstore bundle."""
    from sigstore.models import Bundle
    from sigstore.verify import Verifier
    bundle_json = (
        json.dumps(bundle_data) if isinstance(bundle_data, dict) else bundle_data
    )
    bundle = Bundle.from_json(bundle_json)
    verifier = Verifier.production()
    try:
        # Import UnsafeNoOp if available (sigstore >= 2.x), else use a
        # permissive alternative.
        try:
            from sigstore.verify.policy import UnsafeNoOp
            policy: Any = UnsafeNoOp()
        except ImportError:
            policy = None
        if policy is not None:
            verifier.verify_artifact(
                input=io.BytesIO(payload),
                bundle=bundle,
                policy=policy,
            )
        else:
            verifier.verify_artifact(
                input=io.BytesIO(payload),
                bundle=bundle,
            )
        return True
    except Exception:
        return False

def verify_sigstore_anchor(
    vault_path: Path,
    anchor_path: Path,
) -> bool:
    """Verify a Sigstore anchor against the vault.

    Checks that the anchor file is well-formed, the Sigstore bundle parses
    correctly, and the original payload can be reconstructed and verified
    against the Rekor transparency log.

    Args:
        vault_path:   Path to the Provara vault (needed to reconstruct the
                      payload if the anchor was for a specific event).
        anchor_path:  Path to the .json anchor file to verify.

    Returns:
        True if the anchor is valid, False otherwise.

    Raises:
        ImportError:       if sigstore is not installed.
        FileNotFoundError: if anchor_path does not exist.
        ValueError:        if the anchor file is malformed or the event
                           referenced by event_id is not found.
    """
    _require_sigstore()

    if not anchor_path.exists():
        raise FileNotFoundError(f"Anchor file not found: {anchor_path}")

    try:
        anchor_doc = json.loads(anchor_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Cannot parse anchor file: {exc}") from exc

    if anchor_doc.get("format") != ANCHOR_FORMAT:
        raise ValueError(
            f"Unrecognised anchor format: {anchor_doc.get('format')!r}"
        )

    event_id: Optional[str] = anchor_doc.get("event_id")
    try:
        payload = _build_payload(vault_path, event_id)
    except (ValueError, FileNotFoundError) as exc:
        raise ValueError(
            f"Cannot reconstruct anchor payload: {exc}"
        ) from exc

    bundle_data = anchor_doc.get("sigstore_bundle")
    if not bundle_data:
        raise ValueError("Anchor file is missing sigstore_bundle field")

    return _sigstore_verify(payload, bundle_data)


def list_anchors(vault_path: Path) -> list[dict[str, Any]]:
    """List all Sigstore anchors in the vault.

    Does NOT require sigstore to be installed.

    Returns:
        List of anchor metadata dicts (sigstore_bundle omitted for brevity),
        sorted by anchor_timestamp ascending.
    """
    anchors_dir = vault_path / ANCHORS_DIR
    if not anchors_dir.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for f in sorted(anchors_dir.glob("*.json")):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            summary = {k: v for k, v in doc.items() if k != "sigstore_bundle"}
            summary["anchor_file"] = str(f)
            results.append(summary)
        except (json.JSONDecodeError, OSError):
            continue

    results.sort(key=lambda d: str(d.get("anchor_timestamp", "")))
    return results
