import pytest
import unittest.mock as mock
import sys
import json
from pathlib import Path
from provara.bootstrap_v0 import main

def test_bootstrap_cli_help(capsys):
    with mock.patch.object(sys, "argv", ["bootstrap_v0.py", "--help"]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
        assert "Sovereign Bootstrap" in capsys.readouterr().out

def test_bootstrap_cli_full_run(tmp_path, capsys):
    target = tmp_path / "cli_boot"
    keys_file = tmp_path / "keys.json"
    with mock.patch.object(sys, "argv", [
        "bootstrap_v0.py", str(target), "--uid", "cli-uid", "--actor", "cli-actor",
        "--quorum", "--private-keys", str(keys_file), "--quiet"
    ]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
        assert target.exists()
        assert keys_file.exists()
        
        # Verify keys_file content
        keys_data = json.loads(keys_file.read_text())
        assert "root" in keys_data
        assert "quorum" in keys_data

def test_bootstrap_cli_fail_non_empty(tmp_path):
    target = tmp_path / "non_empty"
    target.mkdir()
    (target / "file.txt").write_text("content")
    
    with mock.patch.object(sys, "argv", ["bootstrap_v0.py", str(target)]):
        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1
