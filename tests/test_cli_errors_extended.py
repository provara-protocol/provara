import pytest
import argparse
import json
from pathlib import Path
from provara.cli import cmd_append, cmd_init, cmd_verify, cmd_backup, cmd_export

@pytest.fixture
def vault_path(tmp_path):
    path = tmp_path / "err_vault"
    cmd_init(argparse.Namespace(path=str(path), uid="u", actor="a", quorum=False, private_keys=None))
    return path

@pytest.fixture
def keyfile(vault_path):
    return vault_path / "identity" / "private_keys.json"

def test_cmd_append_errors(vault_path, keyfile):
    # Data file not found
    with pytest.raises(SystemExit):
        cmd_append(argparse.Namespace(
            path=str(vault_path), type="T", data="@nonexistent.json",
            keyfile=str(keyfile), key_id=None, actor="a", confidence=None
        ))
        
    # Invalid JSON
    with pytest.raises(SystemExit):
        cmd_append(argparse.Namespace(
            path=str(vault_path), type="T", data="{invalid json}",
            keyfile=str(keyfile), key_id=None, actor="a", confidence=None
        ))

    # Key ID not found
    with pytest.raises(SystemExit):
        cmd_append(argparse.Namespace(
            path=str(vault_path), type="T", data='{}',
            keyfile=str(keyfile), key_id="wrong-id", actor="a", confidence=None
        ))

def test_cmd_backup_missing_vault(tmp_path):
    with pytest.raises(SystemExit):
        cmd_backup(argparse.Namespace(path="nonexistent", to="bak", keep=5))

def test_cmd_export_unsupported_format(vault_path):
    with pytest.raises(SystemExit):
        cmd_export(argparse.Namespace(path=str(vault_path), format="unknown", output="out"))
