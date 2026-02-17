#!/usr/bin/env python
"""
Lightweight docs consistency checks for spec source-of-truth hygiene.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPEN_DECISIONS = REPO_ROOT / "docs" / "OPEN_DECISIONS.md"
SPEC_DECISIONS = REPO_ROOT / "docs" / "SPEC_DECISIONS.md"
PROTOCOL_DOC = REPO_ROOT / "docs" / "BACKPACK_PROTOCOL_v1.0.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    # 1) OPEN_DECISIONS should contain exactly 8 numbered decisions.
    open_text = _read(OPEN_DECISIONS)
    decisions = re.findall(r"^##\s+\d+\)\s+", open_text, flags=re.MULTILINE)
    if len(decisions) != 8:
        errors.append(
            f"OPEN_DECISIONS count mismatch: expected 8, found {len(decisions)}"
        )

    # 2) SPEC_DECISIONS should be a deprecation pointer.
    spec_text = _read(SPEC_DECISIONS)
    if "Deprecated" not in spec_text:
        errors.append("SPEC_DECISIONS.md must include deprecation status")
    if "OPEN_DECISIONS.md" not in spec_text:
        errors.append("SPEC_DECISIONS.md must point to docs/OPEN_DECISIONS.md")

    # 3) Protocol doc should declare normative precedence and profile primacy.
    proto_text = _read(PROTOCOL_DOC)
    if "Normative Precedence" not in proto_text:
        errors.append("BACKPACK_PROTOCOL_v1.0.md missing 'Normative Precedence' section")
    if "PROTOCOL_PROFILE.txt" not in proto_text:
        errors.append("BACKPACK_PROTOCOL_v1.0.md missing profile source reference")
    if "OPEN_DECISIONS.md" not in proto_text:
        errors.append("BACKPACK_PROTOCOL_v1.0.md should reference OPEN_DECISIONS.md")
    if "profile wins" not in proto_text.lower():
        errors.append("BACKPACK_PROTOCOL_v1.0.md must state profile conflict resolution")

    if errors:
        print("DOCS_CONSISTENCY_FAIL")
        for e in errors:
            print(f"- {e}")
        return 1

    print("DOCS_CONSISTENCY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
