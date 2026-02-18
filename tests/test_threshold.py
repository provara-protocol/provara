import pytest
from provara.threshold import distribute_keys, threshold_sign, verify_threshold_signature

def test_threshold_2_of_2():
    group = distribute_keys(t=2, n=2)
    message = b"Vault event data"
    
    # Sign with both participants
    indices = [1, 2]
    sig = threshold_sign(group, indices, message)
    
    assert len(sig) == 64
    assert verify_threshold_signature(group.group_public_key, message, sig) is True

def test_threshold_3_of_3():
    group = distribute_keys(t=3, n=3)
    message = b"Another event"
    
    indices = [1, 2, 3]
    sig = threshold_sign(group, indices, message)
    
    assert verify_threshold_signature(group.group_public_key, message, sig) is True

def test_insufficient_participants():
    group = distribute_keys(t=2, n=2)
    message = b"Fail"
    
    with pytest.raises(ValueError, match="requires all 2 participants"):
        threshold_sign(group, [1], message)

def test_wrong_message():
    group = distribute_keys(t=2, n=2)
    message = b"Message A"
    sig = threshold_sign(group, [1, 2], message)
    
    assert verify_threshold_signature(group.group_public_key, b"Message B", sig) is False
