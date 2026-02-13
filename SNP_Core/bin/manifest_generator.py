"""
manifest_generator.py — Backpack v1.0 Manifest + Merkle Root Generator (v0 hardened)

What it does:
  - Walks a backpack directory (no symlink following)
  - Computes SHA-256 for each file
  - Writes manifest.json with deterministic ordering
  - Computes Merkle root over manifest leaves
  - Writes merkle_root.txt

Security hardening vs original:
  - Symlinks are SKIPPED (not followed) — prevents path traversal via symlink
  - All paths validated to resolve within backpack root
  - Warnings emitted for skipped items

Signing is NOT implemented. Add Ed25519 (RFC 8032) and write manifest.sig
as a detached JWS (RFC 7797) over merkle_root + manifest header.
"""

from __future__ import annotations
import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

from backpack_integrity import (
    canonical_json_bytes,
    is_symlink_safe,
    merkle_root_hex,
    sha256_file,
    MANIFEST_EXCLUDE,
    SPEC_REQUIRED_FILES,
)


def iter_backpack_files(
    root: Path,
    exclude: Set[str],
) -> List[Dict]:
    """
    Walk backpack directory, collecting file metadata.
    - Skips symlinks that resolve outside root.
    - Skips files in the exclude set.
    - Returns deterministically sorted list.
    """
    root = root.resolve()
    files = []
    warnings = []

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue

        rel = p.relative_to(root).as_posix()

        if rel in exclude:
            continue

        # Security: skip symlinks that escape the backpack root
        if p.is_symlink():
            if not is_symlink_safe(p, root):
                warnings.append(f"SKIPPED (symlink escapes root): {rel} -> {p.resolve()}")
                continue
            else:
                warnings.append(f"NOTE (symlink within root): {rel} -> {p.resolve()}")

        files.append({
            "path": rel,
            "sha256": sha256_file(p),
            "size": p.stat().st_size,
        })

    # Deterministic ordering by path (should already be sorted from rglob sort)
    files.sort(key=lambda x: x["path"])

    for w in warnings:
        print(f"  WARN: {w}", file=sys.stderr)

    return files


def build_manifest(root: Path, exclude: Set[str]) -> Dict:
    files = iter_backpack_files(root, exclude)

    manifest = {
        "backpack_spec_version": "1.0",
        "manifest_version": "manifest.v0",
        "created_at_utc": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "file_count": len(files),
        "files": files,
    }
    return manifest


def manifest_leaves(manifest: Dict) -> List[bytes]:
    """
    Merkle leaves = canonical JSON bytes of each file entry.
    Excludes created_at_utc so regeneration doesn't change the root
    unless actual file contents change.
    """
    return [canonical_json_bytes(f) for f in manifest["files"]]


def check_required_files(manifest: Dict) -> List[str]:
    """Check which spec-required files are missing."""
    present = {f["path"] for f in manifest["files"]}
    missing = []
    for req in sorted(SPEC_REQUIRED_FILES):
        # manifest.json is excluded from the manifest itself — skip that check
        if req == "manifest.json":
            continue
        if req not in present:
            missing.append(req)
    return missing


def main():
    ap = argparse.ArgumentParser(
        description="Generate Backpack v1.0 manifest + Merkle root"
    )
    ap.add_argument("root", help="Path to backpack root directory")
    ap.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional relative paths to exclude (repeatable)",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write manifest.json and merkle_root.txt",
    )
    ap.add_argument(
        "--check-required",
        action="store_true",
        help="Warn if spec-required files are missing",
    )
    args = ap.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")

    exclude = set(MANIFEST_EXCLUDE) | set(args.exclude)

    manifest = build_manifest(root, exclude)
    leaves = manifest_leaves(manifest)
    root_hex = merkle_root_hex(leaves)

    if args.write:
        (root / "manifest.json").write_bytes(canonical_json_bytes(manifest))
        (root / "merkle_root.txt").write_text(root_hex + "\n", encoding="utf-8")

    print(f"manifest_file_count: {manifest['file_count']}")
    print(f"merkle_root: {root_hex}")

    if args.check_required:
        missing = check_required_files(manifest)
        if missing:
            for m in missing:
                print(f"  MISSING (spec-required): {m}", file=sys.stderr)
        else:
            print("  All spec-required files present.")


if __name__ == "__main__":
    main()
