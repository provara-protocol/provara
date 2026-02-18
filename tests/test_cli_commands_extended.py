import pytest
import argparse
import json
from pathlib import Path
from provara.cli import (
    cmd_init, cmd_verify, cmd_backup, cmd_manifest, cmd_checkpoint,
    cmd_replay, cmd_append, cmd_redact, cmd_market_alpha, cmd_hedge_fund_sim,
    cmd_oracle_validate, cmd_resume, cmd_check_safety, cmd_wallet_export,
    cmd_wallet_import, cmd_agent_loop, cmd_send_message, cmd_read_messages,
    cmd_timestamp, cmd_export, cmd_scitt_statement, cmd_scitt_receipt
)

@pytest.fixture
def vault_path(tmp_path):
    path = tmp_path / "cli_vault"
    args = argparse.Namespace(path=str(path), uid="cli-test", actor="cli_actor", quorum=True, private_keys=None)
    cmd_init(args)
    (path / "merkle_root.txt").write_text("mock_root")
    return path

@pytest.fixture
def keyfile(vault_path):
    # market.py expects simple {kid: priv} format
    # cli.py saves complex {"keys": [...]} format
    # We create a simple one for market functions
    complex_keys = json.loads((vault_path / "identity" / "private_keys.json").read_text())
    simple_keys = {k["key_id"]: k["private_key_b64"] for k in complex_keys["keys"]}
    
    simple_path = vault_path / "identity" / "simple_keys.json"
    simple_path.write_text(json.dumps(simple_keys))
    return simple_path

@pytest.fixture
def complex_keyfile(vault_path):
    return vault_path / "identity" / "private_keys.json"

def test_all_commands_basic(vault_path, keyfile, complex_keyfile, tmp_path):
    # market-alpha (uses simple format)
    cmd_market_alpha(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), ticker="BTC", signal="LONG",
        conviction=0.9, horizon="1d", rationale="test", actor="analyst"
    ))
    
    # hedge-fund-sim (uses simple format)
    cmd_hedge_fund_sim(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), sim_id="s1", strategy="strat1",
        returns=5.5, ticker="BTC", actor="sim"
    ))
    
    # oracle-validate (uses simple format)
    cmd_oracle_validate(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), actor="oracle"
    ))
    
    # append (uses _load_keys which handles complex format)
    cmd_append(argparse.Namespace(
        path=str(vault_path), type="OBSERVATION", data='{"foo":"bar"}',
        keyfile=str(complex_keyfile), key_id=None, actor="tester", confidence=1.0
    ))
    
    # redact
    events_file = vault_path / "events" / "events.ndjson"
    last_event = json.loads(events_file.read_text().splitlines()[-1])
    target_id = last_event["event_id"]
    
    cmd_redact(argparse.Namespace(
        path=str(vault_path), target=target_id, reason="GDPR_ERASURE",
        authority="admin", detail="test redact", method="TOMBSTONE",
        keyfile=str(complex_keyfile), key_id=None, actor="admin"
    ))
    
    # check-safety
    cmd_check_safety(argparse.Namespace(path=str(vault_path), action="REPLAY"))
    
    # agent-loop (uses simple format)
    cmd_agent_loop(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), actor="bot", cycles=1
    ))
    
    # timestamp
    cmd_timestamp(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), tsa=None, actor="tsa"
    ))
    
    # export
    export_out = tmp_path / "export"
    cmd_export(argparse.Namespace(
        path=str(vault_path), format="scitt-compat", output=str(export_out)
    ))
    
    # scitt statement
    cmd_scitt_statement(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), statement_hash="a"*64,
        content_type="application/json", subject="test", issuer="me",
        cose_envelope_b64=None, actor="scitt"
    ))
    
    # scitt receipt
    last_event = json.loads(events_file.read_text().splitlines()[-1])
    stmt_id = last_event["event_id"]
    cmd_scitt_receipt(argparse.Namespace(
        path=str(vault_path), keyfile=str(keyfile), statement_event_id=stmt_id,
        transparency_service="https://ts.example.com", inclusion_proof='{"root": "abc123"}',
        receipt_b64=None, actor="scitt"
    ))
    
    # send-message
    from cryptography.hazmat.primitives.asymmetric import x25519
    from cryptography.hazmat.primitives import serialization
    import base64
    r_priv = x25519.X25519PrivateKey.generate()
    r_pub = r_priv.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    r_pub_b64 = base64.b64encode(r_pub).decode("utf-8")
    r_priv_b64 = base64.b64encode(r_priv.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())).decode("utf-8")
    
    cmd_send_message(argparse.Namespace(
        path=str(vault_path), keyfile=str(complex_keyfile), key_id=None,
        recipient_id=None, recipient_pubkey=r_pub_b64,
        sender_encryption_private_key=None, message='{"hello":"there"}',
        subject="test sub"
    ))
    
    # read-messages
    cmd_read_messages(argparse.Namespace(
        path=str(vault_path), keyfile=str(complex_keyfile), key_id=None,
        my_encryption_private_key=r_priv_b64
    ))
