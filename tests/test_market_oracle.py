import pytest
import json
from pathlib import Path
from provara.market import record_market_alpha, record_hedge_fund_sim
from provara.oracle import validate_market_alpha
from provara import Vault, bootstrap_backpack

@pytest.fixture
def vault_with_keys(tmp_path):
    vault_path = tmp_path / "market_vault"
    res = bootstrap_backpack(vault_path)
    
    key_output = {
        res.root_key_id: res.root_private_key_b64
    }
    keyfile = vault_path / "identity" / "private_keys.json"
    keyfile.write_text(json.dumps(key_output))
    
    return vault_path, keyfile

def test_market_record_alpha(vault_with_keys):
    vault_path, keyfile = vault_with_keys
    
    event = record_market_alpha(
        vault_path, keyfile, "BTC", "LONG", 0.95, "24h", rationale="Bullish divergence"
    )
    
    assert event["type"] == "OBSERVATION"
    assert event["payload"]["value"]["ticker"] == "BTC"

def test_market_record_sim(vault_with_keys):
    vault_path, keyfile = vault_with_keys
    
    event = record_hedge_fund_sim(
        vault_path, keyfile, "sim-001", "strat-v4", 12.5, ticker="ETH"
    )
    
    assert event["type"] == "OBSERVATION"
    assert event["payload"]["value"]["simulation_id"] == "sim-001"

def test_oracle_validation_flow(vault_with_keys):
    vault_path, keyfile = vault_with_keys
    
    # 1. Record an alpha signal
    alpha = record_market_alpha(vault_path, keyfile, "SOL", "LONG", 0.8, "1h")
    
    # 2. Validate it
    results = validate_market_alpha(vault_path, keyfile, actor="Oracle_Node")
    
    assert len(results) == 1
    attestation = results[0]
    assert attestation["type"] == "ATTESTATION"
    assert attestation["payload"]["target_event_id"] == alpha["event_id"]
