"""Vault format migration tooling with audit event emission."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .canonical_json import canonical_dumps, canonical_hash
from .manifest_generator import build_manifest, manifest_leaves
from .backpack_integrity import MANIFEST_EXCLUDE, canonical_json_bytes, merkle_root_hex


@dataclass
class MigrationReport:
    source_version: str
    target_version: str
    events_migrated: int
    changes: list[str]
    migration_event_id: str


_SUPPORTED_VERSIONS = ["1.0", "1.1", "1.2"]


def _events_path(vault_path: Path) -> Path:
    return vault_path / "events" / "events.ndjson"


def _read_current_version(vault_path: Path) -> str:
    genesis_path = vault_path / "identity" / "genesis.json"
    if genesis_path.exists():
        try:
            genesis = json.loads(genesis_path.read_text(encoding="utf-8"))
            if isinstance(genesis, dict):
                direct = genesis.get("spec_version")
                if isinstance(direct, str) and direct:
                    return direct
        except json.JSONDecodeError:
            pass

    events_path = _events_path(vault_path)
    if events_path.exists():
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "GENESIS":
                    payload = event.get("payload") or {}
                    spec = payload.get("spec_version")
                    if isinstance(spec, str) and spec:
                        return spec
                    break

    return "1.0"


def _set_genesis_version(vault_path: Path, version: str) -> None:
    genesis_path = vault_path / "identity" / "genesis.json"
    if not genesis_path.exists():
        return
    try:
        genesis = json.loads(genesis_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not isinstance(genesis, dict):
        return
    genesis["spec_version"] = version
    genesis_path.write_text(json.dumps(genesis, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _migrate_v1_0_to_v1_1(vault_path: Path) -> list[str]:
    _set_genesis_version(vault_path, "1.1")
    return [
        "Set identity/genesis.json spec_version to 1.1",
        "Prepared vault metadata for v1.1-compatible readers",
    ]


def _migrate_v1_1_to_v1_2(vault_path: Path) -> list[str]:
    _set_genesis_version(vault_path, "1.2")
    return [
        "Set identity/genesis.json spec_version to 1.2",
        "Prepared vault metadata for v1.2-compatible readers",
    ]


_MIGRATIONS: dict[tuple[str, str], Callable[[Path], list[str]]] = {
    ("1.0", "1.1"): _migrate_v1_0_to_v1_1,
    ("1.1", "1.2"): _migrate_v1_1_to_v1_2,
}


def _migration_path(source: str, target: str) -> list[tuple[str, str]]:
    if source not in _SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported source version: {source}")
    if target not in _SUPPORTED_VERSIONS:
        raise ValueError(f"Unsupported target version: {target}")

    s_idx = _SUPPORTED_VERSIONS.index(source)
    t_idx = _SUPPORTED_VERSIONS.index(target)

    if s_idx > t_idx:
        raise ValueError(f"Downgrade is not supported: {source} -> {target}")

    path: list[tuple[str, str]] = []
    for i in range(s_idx, t_idx):
        path.append((_SUPPORTED_VERSIONS[i], _SUPPORTED_VERSIONS[i + 1]))
    return path


def _append_migration_event(
    vault_path: Path,
    from_version: str,
    to_version: str,
    changes: list[str],
) -> str:
    events_path = _events_path(vault_path)
    events_path.parent.mkdir(parents=True, exist_ok=True)

    prev_by_actor: str | None = None
    last_logical = 0

    if events_path.exists():
        with events_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts_logical = event.get("ts_logical")
                if isinstance(ts_logical, int) and ts_logical > last_logical:
                    last_logical = ts_logical
                if event.get("actor") == "migration_tool":
                    eid = event.get("event_id")
                    if isinstance(eid, str) and eid:
                        prev_by_actor = eid

    event = {
        "type": "com.provara.migration",
        "namespace": "local",
        "actor": "migration_tool",
        "actor_key_id": "migration_tool",
        "prev_event_hash": prev_by_actor,
        "ts_logical": last_logical + 1,
        "payload": {
            "from_version": from_version,
            "to_version": to_version,
            "changes": changes,
            "tool_version": "1.0.1",
        },
    }
    event["event_id"] = f"evt_{canonical_hash(event)[:24]}"

    with events_path.open("a", encoding="utf-8") as f:
        f.write(canonical_dumps(event) + "\n")

    return event["event_id"]


def _regenerate_manifest(vault_path: Path) -> None:
    manifest = build_manifest(vault_path, set(MANIFEST_EXCLUDE))
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)

    (vault_path / "manifest.json").write_bytes(canonical_json_bytes(manifest))
    (vault_path / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")


def migrate_vault(
    vault_path: Path,
    target_version: str = "latest",
    dry_run: bool = False,
) -> MigrationReport:
    """Migrate vault format from current version to target version."""
    vp = Path(vault_path)
    if target_version == "latest":
        target_version = _SUPPORTED_VERSIONS[-1]

    source_version = _read_current_version(vp)
    path = _migration_path(source_version, target_version)

    if not path:
        return MigrationReport(
            source_version=source_version,
            target_version=target_version,
            events_migrated=0,
            changes=["Vault already at target version; no migration needed"],
            migration_event_id="",
        )

    all_changes: list[str] = []
    if not dry_run:
        for step in path:
            step_fn = _MIGRATIONS.get(step)
            if step_fn is None:
                raise ValueError(f"No migration function for {step[0]} -> {step[1]}")
            all_changes.extend(step_fn(vp))

        migration_event_id = _append_migration_event(
            vp,
            from_version=source_version,
            to_version=target_version,
            changes=all_changes,
        )
        _regenerate_manifest(vp)
    else:
        for step in path:
            all_changes.append(f"Would migrate {step[0]} -> {step[1]}")
        migration_event_id = ""

    return MigrationReport(
        source_version=source_version,
        target_version=target_version,
        events_migrated=len(path),
        changes=all_changes,
        migration_event_id=migration_event_id,
    )
