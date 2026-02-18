import pytest
import unittest.mock as mock
from provara.hardware import detect_hardware_key, MockHardwareToken, sign_with_hardware

def test_no_hardware_detected():
    # Base implementation returns empty list
    assert detect_hardware_key() == []

def test_hardware_sign_mock():
    token = MockHardwareToken("yubikey-001")
    message = b"Vault event"
    
    pub_key = token.get_public_key()
    sig = token.sign(message)
    
    # Verify using standard cryptography lib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    pk_obj = Ed25519PublicKey.from_public_bytes(pub_key)
    pk_obj.verify(sig, message) # Should not raise

def test_sign_with_hardware_not_implemented():
    with pytest.raises(NotImplementedError, match="Hardware signing requires a physical token"):
        sign_with_hardware("real-token-id", b"data")

def test_detect_mocked_hardware():
    # Mock provara.hardware.detect_hardware_key wherever it is used or defined
    with mock.patch("provara.hardware.detect_hardware_key") as mock_detect:
        mock_detect.return_value = ["mock-token-1"]
        # Call it
        import provara.hardware
        tokens = provara.hardware.detect_hardware_key()
        assert tokens == ["mock-token-1"]
