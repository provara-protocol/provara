#!/usr/bin/env python
"""
Validate that test command references align with current repo layout.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAKEFILE = ROOT / "Makefile"
TEST_MATRIX = ROOT / "docs" / "TEST_MATRIX.md"


def main() -> int:
    errors: list[str] = []

    required_paths = [
        ROOT / "tests",
        ROOT / "tests" / "backpack_compliance_v1.py",
        ROOT / "tests" / "fixtures" / "reference_backpack",
        ROOT / "tests" / "test_reducer_v0.py",
        ROOT / "tests" / "test_sync_v0.py",
        ROOT / "tests" / "test_vectors.py",
        ROOT / "src" / "provara" / "__init__.py",
    ]
    for path in required_paths:
        if not path.exists():
            errors.append(f"Missing required path: {path.relative_to(ROOT).as_posix()}")

    make_text = MAKEFILE.read_text(encoding="utf-8")
    required_make_snippets = [
        "TEST_DIR := tests",
        "REF_BACKPACK := tests/fixtures/reference_backpack",
        "PYTHONPATH=../src:..",
        "tests/backpack_compliance_v1.py $(REF_BACKPACK)",
    ]
    for snippet in required_make_snippets:
        if snippet not in make_text:
            errors.append(f"Makefile missing expected snippet: {snippet}")

    matrix_text = TEST_MATRIX.read_text(encoding="utf-8")
    required_matrix_snippets = [
        "cd tests && PYTHONPATH=../src:.. python -m unittest",
        "python tests/backpack_compliance_v1.py tests/fixtures/reference_backpack -q",
        "cd tests && PYTHONPATH=../src:.. python test_vectors.py",
    ]
    for snippet in required_matrix_snippets:
        if snippet not in matrix_text:
            errors.append(f"TEST_MATRIX missing expected command: {snippet}")

    if errors:
        print("TEST_LAYOUT_FAIL")
        for err in errors:
            print(f"- {err}")
        return 1

    print("TEST_LAYOUT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
