import pytest
import argparse
import json
import os
from pathlib import Path
from provara.cli import (
    cmd_init, cmd_manifest, cmd_replay, cmd_append, cmd_verify, 
    cmd_backup, cmd_checkpoint, cmd_resume, cmd_wallet_export, cmd_wallet_import
)

@pytest.fixture
def empty_vault_path(tmp_path):
    return tmp_path / "test_vault"

@pytest.fixture
def initialized_vault(empty_vault_path):
    args = argparse.Namespace(
        path=str(empty_vault_path),
        uid="test-uid-123",
        actor="test_actor",
        quorum=True,
        private_keys=None,
        encrypted=False,
        mode="per-event",
    )
    cmd_init(args)
    return empty_vault_path

@pytest.fixture
def keyfile_path(initialized_vault):
    return initialized_vault / "identity" / "private_keys.json"

def test_cmd_init(empty_vault_path):
    args = argparse.Namespace(
        path=str(empty_vault_path),
        uid="test-uid",
        actor="gen_actor",
        quorum=True,
        private_keys=None,
        encrypted=False,
        mode="per-event",
    )
    cmd_init(args)
    
    assert empty_vault_path.exists()
    assert (empty_vault_path / "identity" / "private_keys.json").exists()
    assert (empty_vault_path / "events" / "events.ndjson").exists()

def test_cmd_manifest(initialized_vault):
    args = argparse.Namespace(path=str(initialized_vault))
    cmd_manifest(args)
    
    assert (initialized_vault / "manifest.json").exists()
    assert (initialized_vault / "merkle_root.txt").exists()

def test_cmd_replay(initialized_vault, capsys):
    args = argparse.Namespace(path=str(initialized_vault))
    cmd_replay(args)
    
    captured = capsys.readouterr()
    state = json.loads(captured.out)
    # Replay state should have namespaces like 'local' or 'canonical'
    assert "local" in state or "canonical" in state

def test_cmd_append(initialized_vault, keyfile_path):
    args = argparse.Namespace(
        path=str(initialized_vault),
        type="OBSERVATION",
        data=json.dumps({"subject": "test", "predicate": "is", "object": "true"}),
        keyfile=str(keyfile_path),
        key_id=None,
        actor="test_actor",
        confidence=0.8
    )
    cmd_append(args)
    
    events_file = initialized_vault / "events" / "events.ndjson"
    lines = events_file.read_text().splitlines()
    assert len(lines) == 3 # GENESIS + OBSERVATION(init) + new OBSERVATION
    last_event = json.loads(lines[-1])
    assert last_event["type"] == "OBSERVATION"

def test_cmd_checkpoint(initialized_vault, keyfile_path):
    args = argparse.Namespace(path=str(initialized_vault), keyfile=str(keyfile_path))
    cmd_checkpoint(args)
    
    # Checkpoint saved to vault/checkpoints/ (not identity/checkpoints)
    cp_dir = initialized_vault / "checkpoints"
    assert cp_dir.exists()
    assert len(list(cp_dir.glob("*.chk"))) > 0

def test_cmd_backup(initialized_vault, tmp_path):
    backup_to = tmp_path / "backups"
    args = argparse.Namespace(path=str(initialized_vault), to=str(backup_to), keep=2)
    cmd_backup(args)
    
    assert backup_to.exists()
    assert len(list(backup_to.glob("Backup_*.zip"))) == 1

def test_cmd_resume(initialized_vault, capsys):
    args = argparse.Namespace(path=str(initialized_vault))
    cmd_resume(args)
    captured = capsys.readouterr()
    assert "Provara Verified Resume" in captured.out

def test_cmd_wallet_export_import(initialized_vault, keyfile_path, tmp_path):
    solana_id_path = tmp_path / "solana_id.json"
    export_args = argparse.Namespace(keyfile=str(keyfile_path), key_id=None, out=str(solana_id_path))
    cmd_wallet_export(export_args)
    assert solana_id_path.exists()
    
    import_args = argparse.Namespace(file=str(solana_id_path))
    cmd_wallet_import(import_args)
