import pytest
import provara
import json
from pathlib import Path
from provara import (
    Vault, bootstrap_backpack, canonical_dumps, canonical_hash, 
    load_private_key_b64, BackpackKeypair, key_id_from_public_bytes
)

def save_test_keys(vault_path):
    # Vault.create doesn't save private_keys.json, so we do it for tests
    # We can't easily get the keys from Vault.create result if we use the classmethod
    # So we might need to bootstrap manually in tests or reach into the vault
    # Actually, we can just use bootstrap_backpack directly or mock it
    pass

@pytest.fixture
def vault_with_keys(tmp_path):
    vault_dir = tmp_path / "test_vault"
    res = bootstrap_backpack(vault_dir, actor="tester")
    
    key_output = {
        "keys": [
            {
                "key_id": res.root_key_id,
                "private_key_b64": res.root_private_key_b64,
                "algorithm": "Ed25519"
            }
        ]
    }
    keys_file = vault_dir / "identity" / "private_keys.json"
    keys_file.parent.mkdir(exist_ok=True, parents=True)
    keys_file.write_text(json.dumps(key_output))
    
    return Vault(vault_dir), res.root_key_id, res.root_private_key_b64

def test_public_api_exports():
    assert "Vault" in provara.__all__
    assert "SovereignReducer" in provara.__all__

def test_lazy_exports():
    from provara import export_to_solana
    assert export_to_solana is not None
    
    with pytest.raises(AttributeError):
        getattr(provara, "nonexistent_attribute")

def test_vault_create_happy_path(tmp_path):
    vault_dir = tmp_path / "facade_vault"
    v = Vault.create(vault_dir, actor="facade_actor")
    
    assert vault_dir.exists()
    state = v.replay_state()
    # bootstrap_v0 creates 2 events: GENESIS and OBSERVATION
    assert state["metadata"]["event_count"] == 2

def test_vault_append_event(vault_with_keys):
    v, kid, priv = vault_with_keys
    
    event = v.append_event("TEST_EVENT", {"foo": "bar"}, kid, priv, actor="tester")
    assert event["type"] == "TEST_EVENT"
    
    state = v.replay_state()
    assert state["metadata"]["event_count"] == 3

def test_vault_checkpoint(vault_with_keys):
    v, kid, priv = vault_with_keys
    cp_path = v.checkpoint(kid, priv)
    assert cp_path.exists()

def test_vault_anchor_to_l2(vault_with_keys):
    v, kid, priv = vault_with_keys
    
    # Create merkle_root.txt
    (v.path / "merkle_root.txt").write_text("mock_merkle_root")
    
    anchor = v.anchor_to_l2(kid, priv, network="mock-net")
    assert anchor["type"] == "ATTESTATION"

def test_vault_create_agent(vault_with_keys):
    v, kid, priv = vault_with_keys
    child_info = v.create_agent("child_agent", kid, priv)
    assert Path(child_info["vault_path"]).exists()

def test_vault_log_task(vault_with_keys):
    v, kid, priv = vault_with_keys
    task = v.log_task(kid, priv, "task-1", "SUCCESS", "hash-1")
    assert task["payload"]["value"]["task_id"] == "task-1"

def test_vault_messaging(vault_with_keys):
    v, kid, priv = vault_with_keys
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import serialization
    import base64
    
    enc_priv = x25519.X25519PrivateKey.generate()
    enc_pub = enc_priv.public_key()
    enc_priv_b64 = base64.b64encode(enc_priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption()
    )).decode("utf-8")
    enc_pub_b64 = base64.b64encode(enc_pub.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )).decode("utf-8")
    
    v.send_message(kid, priv, enc_priv_b64, enc_pub_b64, {"msg": "hi"})
    inbox = v.get_messages(enc_priv_b64)
    assert len(inbox) == 1

def test_vault_check_safety(tmp_path):
    vault_dir = tmp_path / "safe_vault"
    v = Vault.create(vault_dir)
    
    # Approved by default
    assert v.check_safety("REPLAY")["status"] == "APPROVED"
    
    # Create a policy with L0 defined
    policy_file = vault_dir / "policies" / "safety_policy.json"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text(json.dumps({
        "action_classes": {
            "L0": {"approval": "local", "description": "Safe"},
            "L3": {"approval": "none", "description": "Blocked"}
        }
    }))
    
    assert v.check_safety("REPLAY")["status"] == "APPROVED"
    assert v.check_safety("DELETE_VAULT")["status"] == "BLOCKED"
