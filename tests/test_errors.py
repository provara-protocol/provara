import pytest
from provara.errors import (
    ProvaraError, HashMismatchError, BrokenCausalChainError,
    InvalidSignatureError, HashFormatError, KeyNotFoundError,
    RequiredFieldMissingError, VaultStructureInvalidError
)

def test_provara_error_base():
    err = ProvaraError("CODE", "message", "ctx", ["sec"])
    assert err.code == "CODE"
    assert err.message == "message"
    assert err.context == "ctx"
    assert err.spec_sections == ["sec"]
    assert "https://provara.dev/errors/CODE" in err.doc_url

def test_concrete_errors():
    classes = [
        HashMismatchError, BrokenCausalChainError, InvalidSignatureError,
        HashFormatError, KeyNotFoundError, RequiredFieldMissingError,
        VaultStructureInvalidError
    ]
    for cls in classes:
        err = cls("some context")
        assert err.context == "some context"
        assert err.code.startswith("PROVARA_E")
        assert "some context" in str(err)
