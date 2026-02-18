import pytest
import base64
import json
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization
from provara.messaging import send_encrypted_message, receive_encrypted_message

def generate_x25519_keypair_b64():
    priv = x25519.X25519PrivateKey.generate()
    pub = priv.public_key()
    
    priv_b64 = base64.b64encode(
        priv.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
    ).decode("utf-8")
    
    pub_b64 = base64.b64encode(
        pub.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
    ).decode("utf-8")
    
    return priv_b64, pub_b64

def test_messaging_roundtrip():
    # Sender and Receiver Keypairs
    sender_priv, sender_pub = generate_x25519_keypair_b64()
    receiver_priv, receiver_pub = generate_x25519_keypair_b64()
    
    message = {"hello": "world", "status": "secure"}
    
    # 1. Send
    wrapper = send_encrypted_message(
        sender_encryption_private_key_b64=sender_priv,
        recipient_encryption_public_key_b64=receiver_pub,
        message_dict=message
    )
    
    assert "sender_pubkey_b64" in wrapper
    assert "nonce" in wrapper
    assert "ciphertext" in wrapper
    assert wrapper["sender_pubkey_b64"] == sender_pub
    
    # 2. Receive
    decrypted = receive_encrypted_message(
        recipient_encryption_private_key_b64=receiver_priv,
        sender_encryption_public_key_b64=sender_pub,
        message_wrapper=wrapper
    )
    
    assert decrypted == message

def test_messaging_wrong_key_fails():
    sender_priv, sender_pub = generate_x25519_keypair_b64()
    receiver_priv, receiver_pub = generate_x25519_keypair_b64()
    wrong_priv, wrong_pub = generate_x25519_keypair_b64()
    
    message = {"top": "secret"}
    wrapper = send_encrypted_message(sender_priv, receiver_pub, message)
    
    # Decrypt with wrong private key (should fail tag check)
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):
        receive_encrypted_message(wrong_priv, sender_pub, wrapper)
        
    # Decrypt with wrong sender public key (should fail tag check)
    with pytest.raises(InvalidTag):
        receive_encrypted_message(receiver_priv, wrong_pub, wrapper)

def test_messaging_invalid_payload_type():
    # This tests the case where the decrypted payload is not a dict
    # (though send_encrypted_message enforces message_dict: Dict[str, Any])
    # We have to mock the ciphertext to produce a non-dict JSON string
    
    sender_priv, sender_pub = generate_x25519_keypair_b64()
    receiver_priv, receiver_pub = generate_x25519_keypair_b64()
    
    # Manually encrypt a string instead of a dict
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os
    
    priv_bytes = base64.b64decode(sender_priv)
    s_priv_obj = x25519.X25519PrivateKey.from_private_bytes(priv_bytes)
    pub_bytes = base64.b64decode(receiver_pub)
    r_pub_obj = x25519.X25519PublicKey.from_public_bytes(pub_bytes)
    shared_key = s_priv_obj.exchange(r_pub_obj)
    
    derived_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"provara-sovereign-messaging-v1",
    ).derive(shared_key)
    
    aesgcm = AESGCM(derived_key)
    nonce = os.urandom(12)
    plaintext = json.dumps("not-a-dict").encode("utf-8") # String payload
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    
    wrapper = {
        "nonce": base64.b64encode(nonce).decode("utf-8"),
        "ciphertext": base64.b64encode(ciphertext).decode("utf-8")
    }
    
    with pytest.raises(ValueError, match="ERROR: Decrypted message payload is not a JSON object"):
        receive_encrypted_message(receiver_priv, sender_pub, wrapper)

def test_messaging_corrupted_ciphertext():
    sender_priv, sender_pub = generate_x25519_keypair_b64()
    receiver_priv, receiver_pub = generate_x25519_keypair_b64()
    
    message = {"data": "test"}
    wrapper = send_encrypted_message(sender_priv, receiver_pub, message)
    
    # Corrupt ciphertext
    wrapper["ciphertext"] = base64.b64encode(b"garbage").decode("utf-8")
    
    from cryptography.exceptions import InvalidTag
    with pytest.raises(InvalidTag):
        receive_encrypted_message(receiver_priv, sender_pub, wrapper)
