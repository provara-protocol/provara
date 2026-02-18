# Provara Threshold Signatures (t-of-n) Spec

## 1. Overview
Multi-party authorization allows a Provara vault to require consensus from a quorum of participants before an event is considered valid. This eliminates single points of failure and is a requirement for enterprise-grade sovereign identity.

Provara adopts **FROST (Flexible Round-Optimized Schnorr Threshold signatures)** for this purpose.

## 2. Scheme Selection: FROST
FROST was selected over alternatives for the following reasons:
- **Compatibility:** Produces standard Ed25519 signatures. Verifiers do not need to know the signature was produced by a threshold group.
- **Efficiency:** Signing requires only 2 rounds of communication.
- **Security:** Unlike simple Shamir Secret Sharing (which requires reconstructing the private key in memory to sign), FROST participants never reveal their key shares.
- **Robustness:** Handles malicious participants during the signing process.

## 3. Protocol Lifecycle

### 3.1 Key Generation (DKG)
A Distributed Key Generation (DKG) ceremony is performed to create:
1. A **Group Public Key** (the identity of the threshold group).
2. Individual **Key Shares** for each of the $n$ participants.

This ceremony is recorded in the vault via the `com.provara.threshold.keygen` event.

### 3.2 Signing (2-Round)
1. **Round 1:** Each participating signer ($t$ minimum) generates one-time nonces and shares commitments.
2. **Round 2:** Signers produce partial signatures based on the message and the aggregated commitments.
3. **Aggregation:** An aggregator (which can be any participant) combines the partial signatures into a single Ed25519 signature.

## 4. Event Types

### `com.provara.threshold.keygen`
Records the creation of a threshold group.
- **Threshold (t):** Integer.
- **Total (n):** Integer.
- **Group Public Key:** Base64 encoded Ed25519 public key.
- **Participant Registry:** Map of Participant ID to their permanent individual Public Key.
- **Signature:** MUST be signed by all $n$ participants using their individual keys to attest to the group creation.

### `com.provara.threshold.sign_request`
Initiates a signing round.
- **Target Event:** The unsigned Provara event being authorized.
- **Threshold Required:** Copied from policy.
- **Deadline:** UTC timestamp after which the request expires.

### `com.provara.threshold.sign_response`
A participant's contribution to a sign request.
- **Request Event ID:** Reference to the `sign_request`.
- **Nonce Commitment:** The participant's R-value commitment.
- **Partial Signature:** The Schnorr partial signature scalar.

## 5. Vault Policy
Threshold requirements are enforced via the `com.provara.policy.threshold` event. 
- Example: "All events of type `TRANSFER` require 3-of-5 threshold `bp1_group_abc`."
- Policy changes themselves require the current threshold to sign.

## 6. Trust Model
- **Quorum Failure:** If fewer than $t$ signers are available, the vault is "frozen" for protected event types. Evidence can still be merged, but new protected actions cannot be authorized.
- **Share Rotation:** Participants can refresh their shares without changing the Group Public Key.
- **Signer Removal:** Requires a $t$-of-$n$ vote to generate a new $t$-of-$(n-1)$ group key (or similar).
