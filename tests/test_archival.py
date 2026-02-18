import pytest
import json
import shutil
from pathlib import Path
from provara.archival import seal_vault, create_successor, verify_vault_chain, is_vault_sealed
from provara.bootstrap_v0 import bootstrap_backpack
from provara.cli import cmd_append
import argparse

@pytest.fixture
def vault_path(tmp_path):
    path = tmp_path / "test_vault"
    bootstrap_backpack(path, actor="tester", quiet=True)
    return path

@pytest.fixture
def keyfile_path(vault_path, tmp_path):
    # Create a keyfile for the vault
    # bootstrap_v0 doesn't save private keys by default in a file we can easily find
    # unless we use --private-keys.
    # Actually, we can just use the one from bootstrap result if we had it.
    # Let's just create a dummy one that matches the vault's root key.
    keys_json = vault_path / "identity" / "keys.json"
    keys_data = json.loads(keys_json.read_text())
    root_kid = keys_data["keys"][0]["key_id"]
    
    # We need the actual private key. 
    # Let's re-bootstrap with a known keyfile.
    keyfile = tmp_path / "keys.json"
    shutil.rmtree(vault_path)
    from provara.bootstrap_v0 import bootstrap_backpack
    res = bootstrap_backpack(vault_path, actor="tester", quiet=True)
    
    key_output = {
        res.root_key_id: res.root_private_key_b64
    }
    keyfile.write_text(json.dumps(key_output))
    return keyfile

def test_seal_vault_and_append_fails(vault_path, keyfile_path):
    assert not is_vault_sealed(vault_path)
    
    # Seal the vault
    seal_event = seal_vault(vault_path, keyfile_path)
    assert seal_event["type"] == "com.provara.vault.seal"
    assert is_vault_sealed(vault_path)
    
    # Try to append - should fail
    args = argparse.Namespace(
        path=str(vault_path),
        type="OBSERVATION",
        data='{"foo":"bar"}',
        keyfile=str(keyfile_path),
        key_id=None,
        actor="tester",
        confidence=1.0
    )
    with pytest.raises(SystemExit):
        cmd_append(args)

def test_seal_already_sealed_fails(vault_path, keyfile_path):
    seal_vault(vault_path, keyfile_path)
    with pytest.raises(ValueError, match="already sealed"):
        seal_vault(vault_path, keyfile_path)

def test_create_successor_linked_to_predecessor(vault_path, keyfile_path, tmp_path):
    seal_vault(vault_path, keyfile_path)
    
    successor_path = tmp_path / "successor_vault"
    create_successor(vault_path, successor_path, keyfile_path)
    
    # Check genesis of successor
    genesis_path = successor_path / "identity" / "genesis.json"
    genesis_data = json.loads(genesis_path.read_text())
    assert "predecessor_vault" in genesis_data
    assert genesis_data["predecessor_vault"]["final_event_count"] > 0
    
    # Verify linkage
    merkle_root_path = vault_path / "merkle_root.txt"
    expected_merkle = merkle_root_path.read_text().strip()
    assert genesis_data["predecessor_vault"]["merkle_root"] == expected_merkle

def test_successor_of_unsealed_fails(vault_path, keyfile_path, tmp_path):
    successor_path = tmp_path / "successor_vault"
    with pytest.raises(ValueError, match="NOT sealed"):
        create_successor(vault_path, successor_path, keyfile_path)

def test_verify_vault_chain(vault_path, keyfile_path, tmp_path):
    # Chain of 3 vaults: V1 -> V2 -> V3
    v1_path = vault_path
    seal_vault(v1_path, keyfile_path)
    
    v2_path = tmp_path / "v2"
    create_successor(v1_path, v2_path, keyfile_path)
    seal_vault(v2_path, keyfile_path)
    
    v3_path = tmp_path / "v3"
    create_successor(v2_path, v3_path, keyfile_path)
    
    # Get Merkle roots for registry
    def get_merkle(p):
        return (p / "merkle_root.txt").read_text().strip()
    
    registry = {
        get_merkle(v1_path): v1_path,
        get_merkle(v2_path): v2_path,
        get_merkle(v3_path): v3_path
    }
    
    results = verify_vault_chain(v3_path, registry)
    assert len(results) == 3
    assert all(r["status"] == "PASS" for r in results)
