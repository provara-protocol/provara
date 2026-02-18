import pytest
import unittest.mock as mock
from provara.cli import _fail_with_error, _cli_error
from provara.errors import ProvaraError

def test_fail_with_error(capsys):
    err = ProvaraError(code="TEST_ERR", message="Test message", context="test context")
    with pytest.raises(SystemExit) as e:
        _fail_with_error(err)
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "ERROR: TEST_ERR. Test message. Context: test context." in captured.out

def test_cli_error(capsys):
    with pytest.raises(SystemExit) as e:
        _cli_error("What", "Why", "Fix", "See")
    assert e.value.code == 1
    captured = capsys.readouterr()
    assert "ERROR: What. Why. Fix: Fix. (See: See)" in captured.out
