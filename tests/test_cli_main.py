import pytest
import unittest.mock as mock
import sys
from provara.cli import main

def test_cli_main_help(capsys):
    with mock.patch.object(sys, "argv", ["provara", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
        captured = capsys.readouterr()
        assert "Provara Protocol CLI" in captured.out

def test_cli_main_init_call(tmp_path):
    vault_path = tmp_path / "main_vault"
    with mock.patch.object(sys, "argv", ["provara", "init", str(vault_path), "--uid", "main-test"]):
        with mock.patch("provara.cli.cmd_init") as mock_init:
            main()
            assert mock_init.called
            args = mock_init.call_args[0][0]
            assert args.path == str(vault_path)
            assert args.uid == "main-test"

def test_cli_main_verify_call():
    with mock.patch.object(sys, "argv", ["provara", "verify", "some_path", "-v"]):
        with mock.patch("provara.cli.cmd_verify") as mock_verify:
            main()
            assert mock_verify.called
            args = mock_verify.call_args[0][0]
            assert args.path == "some_path"
            assert args.verbose is True
