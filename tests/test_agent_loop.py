import pytest
import unittest.mock as mock
import json
from pathlib import Path
from provara.agent_loop import run_alpha_loop
from provara import Vault, bootstrap_backpack

@pytest.fixture
def test_vault_with_keys(tmp_path):
    vault_path = tmp_path / "alpha_vault"
    res = bootstrap_backpack(vault_path)
    
    key_output = {
        res.root_key_id: res.root_private_key_b64
    }
    keyfile = vault_path / "identity" / "private_keys.json"
    keyfile.write_text(json.dumps(key_output))
    
    return vault_path, keyfile

def test_run_alpha_loop_single_cycle(test_vault_with_keys):
    vault_path, keyfile = test_vault_with_keys
    
    with mock.patch("random.choice") as mock_choice:
        mock_choice.side_effect = ["BTC", "LONG"]
        
        with mock.patch("provara.Vault.anchor_to_l2") as mock_anchor:
            mock_anchor.return_value = {
                "event_id": "evt_anchor",
                "payload": {"value": {"tx_hash": "0x1234567890abcdef"}}
            }
            
            with mock.patch("provara.agent_loop.validate_market_alpha") as mock_val:
                mock_val.return_value = [{
                    "event_id": "evt_attest",
                    "type": "ATTESTATION",
                    "payload": {
                        "value": {
                            "performance_pct": 2.5,
                            "status": "SUCCESS"
                        },
                        "target_event_id": "evt_alpha"
                    }
                }]
                
                run_alpha_loop(vault_path, keyfile, actor_name="Alpha_Test_Bot", iterations=1)
                
                assert mock_choice.called
                assert mock_anchor.called

def test_run_alpha_loop_fail_no_anchor(test_vault_with_keys):
    vault_path, keyfile = test_vault_with_keys
    
    with mock.patch("random.choice") as mock_choice:
        mock_choice.side_effect = ["ETH", "SHORT"]
        
        with mock.patch("provara.Vault.anchor_to_l2") as mock_anchor:
            with mock.patch("provara.agent_loop.validate_market_alpha") as mock_val:
                mock_val.return_value = [{
                    "event_id": "evt_attest",
                    "type": "ATTESTATION",
                    "payload": {
                        "value": {
                            "performance_pct": -1.5,
                            "status": "FAIL"
                        }
                    }
                }]
                
                run_alpha_loop(vault_path, keyfile, iterations=1)
                
                assert not mock_anchor.called
