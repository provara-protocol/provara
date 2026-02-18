import pytest
import argparse
import unittest.mock as mock
from provara.cli import _get_timestamp, _fail_with_error, cmd_verify, cmd_init
from provara.errors import ProvaraError
from pathlib import Path

def test_get_timestamp():
    ts = _get_timestamp()
    assert len(ts) == 17 # YYYY-MM-DD_HHMMSS

def test_fail_with_error_no_context(capsys):
    err = ProvaraError(code="ERR", message="msg")
    with pytest.raises(SystemExit):
        _fail_with_error(err)
    captured = capsys.readouterr()
    assert "Context:" not in captured.out

def test_cmd_verify_fail(tmp_path):
    # Empty dir - should fail structural check
    with pytest.raises(SystemExit):
        cmd_verify(argparse.Namespace(path=str(tmp_path), verbose=True, show_redacted=True))

def test_cmd_init_fail(tmp_path):
    # Target not empty
    (tmp_path / "file.txt").write_text("stuff")
    with pytest.raises(SystemExit):
        cmd_init(argparse.Namespace(path=str(tmp_path), uid="u", actor="a", quorum=False, private_keys=None, encrypted=False, mode="per-event"))
