"""Targeted property-based fuzzing for canonical JSON behavior."""

from __future__ import annotations

import json

from hypothesis import given, settings, strategies as st

from provara.canonical_json import canonical_dumps


json_data = st.recursive(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False, allow_infinity=False),
        st.text(),
    ),
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)


def canonicalize(value: object) -> bytes:
    return canonical_dumps(value).encode("utf-8")


def canonicalize_bytes(data: bytes) -> bytes:
    decoded = data.decode("utf-8")
    parsed = json.loads(decoded)
    return canonicalize(parsed)


@given(st.binary(min_size=1, max_size=1000))
@settings(deadline=5000, max_examples=200)
def test_canonical_rejects_invalid_json(data: bytes) -> None:
    """Canonicalizer handles arbitrary bytes without unexpected crashes."""
    try:
        canonicalize_bytes(data)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        pass
    except Exception as exc:  # pragma: no cover - unexpected crash guard
        raise AssertionError(f"Unexpected exception type: {type(exc).__name__}") from exc


@given(json_data)
@settings(deadline=5000, max_examples=400)
def test_canonical_idempotent(data: object) -> None:
    """Canonicalization is idempotent."""
    c1 = canonicalize(data)
    c2 = canonicalize(json.loads(c1))
    assert c1 == c2


@given(json_data, json_data)
@settings(deadline=5000, max_examples=400)
def test_canonical_deterministic_ordering(a: object, b: object) -> None:
    """Semantically equal values always canonicalize to identical bytes."""
    if a == b:
        assert canonicalize(a) == canonicalize(b)

