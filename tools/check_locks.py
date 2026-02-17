#!/usr/bin/env python
"""
Simple multi-agent path lock utility.

Usage examples:
  python tools/check_locks.py status
  python tools/check_locks.py check --agent Codex --paths tools/mcp_server docs
  python tools/check_locks.py claim --agent Codex --name mcp-server --paths tools/mcp_server
  python tools/check_locks.py release --name mcp-server
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_DIR = REPO_ROOT / ".locks"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    return datetime.fromisoformat(value)


def _normalize_path(path_text: str) -> str:
    p = Path(path_text).expanduser()
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    else:
        p = p.resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "-", text.strip()).strip("-")
    return s or "lock"


@dataclass
class LockRecord:
    name: str
    agent: str
    created_at: str
    paths: List[str]
    note: str = ""

    @property
    def file_path(self) -> Path:
        return LOCK_DIR / f"{self.name}.lock"

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "created_at": self.created_at,
            "paths": self.paths,
            "note": self.note,
        }


def _iter_locks() -> List[LockRecord]:
    locks: List[LockRecord] = []
    if not LOCK_DIR.exists():
        return locks
    for file in sorted(LOCK_DIR.glob("*.lock")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        locks.append(
            LockRecord(
                name=file.stem,
                agent=str(data.get("agent", "")),
                created_at=str(data.get("created_at", "")),
                paths=[str(p) for p in data.get("paths", [])],
                note=str(data.get("note", "")),
            )
        )
    return locks


def _path_overlap(path_a: str, path_b: str) -> bool:
    a = path_a.rstrip("/")
    b = path_b.rstrip("/")
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def _conflicts(candidate_paths: List[str], agent: str) -> List[LockRecord]:
    out: List[LockRecord] = []
    for lock in _iter_locks():
        if lock.agent == agent:
            continue
        for c in candidate_paths:
            if any(_path_overlap(c, lp) for lp in lock.paths):
                out.append(lock)
                break
    return out


def cmd_status(_: argparse.Namespace) -> int:
    locks = _iter_locks()
    if not locks:
        print("No active locks.")
        return 0
    print(f"Active locks: {len(locks)}")
    now = datetime.now(timezone.utc)
    for lock in locks:
        age = "unknown"
        try:
            created = _parse_iso(lock.created_at)
            age_seconds = int((now - created).total_seconds())
            age = f"{age_seconds}s"
        except Exception:
            pass
        print(f"- {lock.name}: agent={lock.agent} age={age} paths={','.join(lock.paths)}")
        if lock.note:
            print(f"  note={lock.note}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    paths = [_normalize_path(p) for p in args.paths]
    conflicts = _conflicts(paths, args.agent)
    if not conflicts:
        print("LOCK_OK")
        return 0
    print("LOCK_CONFLICT")
    for lock in conflicts:
        print(f"- {lock.name} by {lock.agent}: {', '.join(lock.paths)}")
    return 1


def cmd_claim(args: argparse.Namespace) -> int:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    name = _slug(args.name)
    lock_path = LOCK_DIR / f"{name}.lock"
    if lock_path.exists():
        print(f"Lock already exists: {lock_path}")
        return 1

    paths = [_normalize_path(p) for p in args.paths]
    conflicts = _conflicts(paths, args.agent)
    if conflicts and not args.force:
        print("Cannot claim lock due to conflicts:")
        for lock in conflicts:
            print(f"- {lock.name} by {lock.agent}: {', '.join(lock.paths)}")
        return 1

    rec = LockRecord(
        name=name,
        agent=args.agent,
        created_at=_utc_now_iso(),
        paths=paths,
        note=args.note or "",
    )
    lock_path.write_text(json.dumps(rec.to_dict(), indent=2) + "\n", encoding="utf-8")
    print(f"LOCK_CLAIMED {lock_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


def cmd_release(args: argparse.Namespace) -> int:
    lock_path = LOCK_DIR / f"{_slug(args.name)}.lock"
    if not lock_path.exists():
        print(f"Lock not found: {lock_path.relative_to(REPO_ROOT).as_posix()}")
        return 1
    lock_path.unlink()
    print(f"LOCK_RELEASED {lock_path.relative_to(REPO_ROOT).as_posix()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Check and manage multi-agent path locks")
    sub = p.add_subparsers(dest="command", required=True)

    s_status = sub.add_parser("status", help="List active locks")
    s_status.set_defaults(func=cmd_status)

    s_check = sub.add_parser("check", help="Check whether paths are free")
    s_check.add_argument("--agent", required=True, help="Current agent name")
    s_check.add_argument("--paths", nargs="+", required=True, help="Paths to edit")
    s_check.set_defaults(func=cmd_check)

    s_claim = sub.add_parser("claim", help="Create a lock for paths")
    s_claim.add_argument("--agent", required=True, help="Agent name")
    s_claim.add_argument("--name", required=True, help="Lock name (file stem)")
    s_claim.add_argument("--paths", nargs="+", required=True, help="Paths to lock")
    s_claim.add_argument("--note", default="", help="Optional note")
    s_claim.add_argument("--force", action="store_true", help="Claim even if conflicts exist")
    s_claim.set_defaults(func=cmd_claim)

    s_release = sub.add_parser("release", help="Release a lock by name")
    s_release.add_argument("--name", required=True, help="Lock name (file stem)")
    s_release.set_defaults(func=cmd_release)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
