import pytest
import json
import base64
from pathlib import Path
from provara.rekey_backpack import rotate_key, verify_rotation_events, main
from provara.bootstrap_v0 import bootstrap_backpack
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import unittest.mock as mock
import sys

@pytest.fixture
def backpack_with_quorum(tmp_path):
    target = tmp_path / "rekey_bp"
    res = bootstrap_backpack(target, include_quorum=True)
    return target, res

def test_rotate_key_success(backpack_with_quorum):
    root, res = backpack_with_quorum
    
    q_priv_bytes = base64.b64decode(res.quorum_private_key_b64)
    q_priv_obj = Ed25519PrivateKey.from_private_bytes(q_priv_bytes)
    
    rot_res = rotate_key(
        root, 
        compromised_key_id=res.root_key_id,
        signing_private_key=q_priv_obj,
        signing_key_id=res.quorum_key_id
    )
    
    assert rot_res.success is True
    assert rot_res.promotion_event_id is not None
    
    v_results = verify_rotation_events(root)
    assert len(v_results) == 2
    assert all(r["signature_valid"] for r in v_results)

def test_rotate_key_security_violations(backpack_with_quorum):
    root, res = backpack_with_quorum
    
    root_priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(res.root_private_key_b64))
    
    rot_res = rotate_key(
        root,
        compromised_key_id=res.root_key_id,
        signing_private_key=root_priv,
        signing_key_id=res.root_key_id
    )
    assert rot_res.success is False
    assert "SECURITY VIOLATION" in rot_res.errors[0]

def test_rekey_cli_verify(backpack_with_quorum, capsys):
    root, res = backpack_with_quorum
    with mock.patch.object(sys, "argv", ["rekey_backpack.py", "verify", str(root)]):
        main()
    captured = capsys.readouterr()
    assert "No rotation events found" in captured.out
    
    q_priv = Ed25519PrivateKey.from_private_bytes(base64.b64decode(res.quorum_private_key_b64))
    rotate_key(root, res.root_key_id, q_priv, res.quorum_key_id)
    
    with mock.patch.object(sys, "argv", ["rekey_backpack.py", "verify", str(root)]):
        main()
    captured = capsys.readouterr()
    assert "[OK] KEY_REVOCATION" in captured.out
    assert "[OK] KEY_PROMOTION" in captured.out
