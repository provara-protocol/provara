# Provara Hardware Key Support Spec

## 1. Overview
Hardware-backed identity provides the highest tier of protection for Provara keys. By storing private material in a tamper-resistant Secure Element (SE) or HSM, Provara ensures that keys cannot be cloned or exfiltrated even if the host machine is compromised.

## 2. Supported Hardware Standards

### 2.1 FIDO2 / WebAuthn
Consumer-grade security keys (e.g., YubiKey 5, SoloKeys, Google Titan).
- **Mechanism:** Ed25519 is supported via the `hmac-secret` extension or resident keys.
- **Protocol:** Uses `python-fido2` for communication.

### 2.2 PIV / PKCS#11
Enterprise smart cards and hardware security modules (HSMs).
- **Mechanism:** Ed25519 support depends on the card applet (e.g., YubiKey PIV supports ECC but Ed25519 requires specific firmware).

## 3. Workflow Integration

### 3.1 Initialization
`provara init --hardware-sign`
1. Prompt the user to insert and touch the hardware token.
2. Hardware generates a new Ed25519 keypair.
3. Hardware exports the **Public Key**.
4. Provara derives the `bp1_` Key ID from the public key.
5. Vault is initialized using the hardware identity.

### 3.2 Signing
`provara append --hardware-sign`
1. Provara prepares the canonical JSON event.
2. Event hash is sent to the hardware token.
3. Hardware prompts for user presence (LED flash/touch).
4. Hardware signs the hash internally.
5. Signature is returned and appended to the vault event.

## 4. Key ID Derivation
The Provara Key ID derivation algorithm remains identical:
`SHA-256(Public Key bytes) -> Base64 -> Prefix bp1_`
Since Key IDs depend only on public material, hardware keys are first-class citizens in the Provara registry.

## 5. Security & UX Challenges

- **Performance:** Hardware tokens are optimized for security, not speed. Signing typically takes 200ms - 500ms. Batch processing 10,000 events will require session-based caching or high-speed HSMs.
- **Presence:** Physical interaction (touch) is required for most FIDO2 keys. This prevents automated signing but ensures "Kinetic Authorization."
- **Longevity:** A lost token is a lost key. Unlike mnemonic-based wallets, Provara hardware keys are generally non-clonable.
- **Mitigation:** **Threshold Multi-sig** is the recommended strategy. A user should hold 3 hardware keys and require 2-of-3 for critical vault operations.

## 6. Implementation Sketch (src/provara/hardware.py)
The hardware module provides an abstract interface for token interaction:
- `detect_hardware_key()`: Scan USB/NFC for available tokens.
- `sign_with_hardware(key_id, message_hash)`: Trigger the hardware signing flow.
- `export_public_key()`: Fetch the public key for registry enrollment.
