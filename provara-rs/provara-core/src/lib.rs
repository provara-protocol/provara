//! provara-core — Provara Protocol v1.0 Core Implementation
//!
//! This crate provides the core cryptographic primitives and data structures
//! for the Provara Protocol, including:
//!
//! - Ed25519 signing and verification (RFC 8032)
//! - SHA-256 hashing (FIPS 180-4)
//! - Event creation and validation
//! - Causal chain verification
//! - Key ID derivation
//!
//! ## Example
//!
//! ```rust
//! use provara_core::{KeyPair, create_event, verify_event_signature};
//! use rand::thread_rng;
//!
//! // Generate a new keypair
//! let mut rng = thread_rng();
//! let keypair = KeyPair::generate(&mut rng);
//!
//! // Create an event
//! let event = create_event(
//!     "OBSERVATION",
//!     &keypair,
//!     None,
//!     serde_json::json!({"subject": "test", "value": "ok"})
//! ).unwrap();
//!
//! // Verify the signature
//! assert!(verify_event_signature(&event, &keypair.public_key()).unwrap());
//! ```

#[cfg(feature = "wasm")]
use wasm_bindgen::prelude::*;

use ed25519_dalek::{SigningKey, VerifyingKey, Signature, Signer, Verifier};
use rand_core::{CryptoRng, RngCore};
use sha2::{Digest, Sha256};
use serde::{Deserialize, Serialize};
use serde_json::{Value, Map, json};
use thiserror::Error;

pub use jcs_rs::{canonicalize, canonical_to_string, canonical_hash, canonical_hash_hex};

pub mod reducer;
pub use reducer::{SovereignReducerV0, ReducerState, ReducerMetadata, StateMetadata};

#[cfg(test)]
mod test_vectors;
#[cfg(test)]
mod conformance;

/// Errors that can occur in provara-core operations
#[derive(Debug, Error, PartialEq)]
pub enum ProvaraError {
    #[error("Cryptographic error: {0}")]
    Crypto(String),
    #[error("Invalid event: {0}")]
    InvalidEvent(String),
    #[error("Chain validation failed: {0}")]
    ChainValidation(String),
    #[error("Key derivation error: {0}")]
    KeyDerivation(String),
    #[error("Serialization error: {0}")]
    Serialization(String),
    #[error("Encoding error: {0}")]
    Encoding(String),
}

impl From<jcs_rs::CanonicalizeError> for ProvaraError {
    fn from(e: jcs_rs::CanonicalizeError) -> Self {
        ProvaraError::Serialization(e.to_string())
    }
}

/// A public/private keypair for Ed25519 signing
pub struct KeyPair {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl KeyPair {
    /// Generate a new random keypair
    pub fn generate<R: CryptoRng + RngCore>(rng: &mut R) -> Self {
        let signing_key = SigningKey::generate(rng);
        let verifying_key = VerifyingKey::from(&signing_key);
        
        KeyPair {
            signing_key,
            verifying_key,
        }
    }
    
    /// Create a keypair from raw bytes
    pub fn from_bytes(seed: &[u8; 32]) -> Result<Self, ProvaraError> {
        let signing_key = SigningKey::from_bytes(seed);
        let verifying_key = VerifyingKey::from(&signing_key);
        
        Ok(KeyPair {
            signing_key,
            verifying_key,
        })
    }
    
    /// Get the public key bytes
    pub fn public_key(&self) -> [u8; 32] {
        self.verifying_key.to_bytes()
    }
    
    /// Get the key ID (bp1_ prefix + first 16 hex chars of SHA-256(public_key))
    pub fn key_id(&self) -> Result<String, ProvaraError> {
        derive_key_id(&self.public_key())
    }
    
    /// Sign a message
    pub fn sign(&self, message: &[u8]) -> Signature {
        self.signing_key.sign(message)
    }

    /// Get the raw seed bytes (32-byte private key material)
    pub fn seed_bytes(&self) -> [u8; 32] {
        self.signing_key.to_bytes()
    }
}

/// Derive a key ID from public key bytes according to Provara spec
///
/// key_id = "bp1_" + SHA-256(raw_public_key_bytes)[:16 hex chars]
pub fn derive_key_id(public_key_bytes: &[u8; 32]) -> Result<String, ProvaraError> {
    let mut hasher = Sha256::new();
    hasher.update(public_key_bytes);
    let hash = hasher.finalize();
    
    // Take first 8 bytes (16 hex chars)
    let hex_chars = hex::encode(&hash[0..8]);
    
    Ok(format!("bp1_{}", hex_chars))
}

/// Compute SHA-256 hash of bytes
pub fn sha256_hash(data: &[u8]) -> [u8; 32] {
    let mut hasher = Sha256::new();
    hasher.update(data);
    let result = hasher.finalize();
    
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    hash
}

/// Compute SHA-256 hash as hex string
pub fn sha256_hash_hex(data: &[u8]) -> String {
    hex::encode(sha256_hash(data))
}

/// Provara Event structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Event {
    /// Event type (OBSERVATION, ATTESTATION, RETRACTION, etc.)
    #[serde(rename = "type")]
    pub event_type: String,
    
    /// Content-addressed event ID
    pub event_id: String,
    
    /// Actor identifier (key ID)
    pub actor: String,
    
    /// Hash of previous event by same actor (null for genesis)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub prev_event_hash: Option<String>,
    
    /// Event timestamp (ISO 8601 UTC)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub timestamp_utc: Option<String>,
    
    /// Event payload
    pub payload: Value,
    
    /// Ed25519 signature (Base64 encoded)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub signature: Option<String>,
}

impl Event {
    /// Create a new event without computing event_id or signature
    pub fn new(
        event_type: &str,
        actor: &str,
        prev_event_hash: Option<String>,
        payload: Value,
    ) -> Self {
        Event {
            event_type: event_type.to_string(),
            event_id: String::new(), // Will be computed
            actor: actor.to_string(),
            prev_event_hash,
            payload,
            timestamp_utc: None,
            signature: None,
        }
    }
    
    /// Get the signing payload (event without signature field)
    pub fn signing_payload(&self) -> Result<Value, ProvaraError> {
        let mut map = Map::new();
        map.insert("type".to_string(), json!(self.event_type));
        map.insert("event_id".to_string(), json!(self.event_id));
        map.insert("actor".to_string(), json!(self.actor));
        
        if let Some(ref prev) = self.prev_event_hash {
            map.insert("prev_event_hash".to_string(), json!(prev));
        }
        
        if let Some(ref ts) = self.timestamp_utc {
            map.insert("timestamp_utc".to_string(), json!(ts));
        }
        
        map.insert("payload".to_string(), self.payload.clone());
        
        Ok(Value::Object(map))
    }
}

/// Derive event ID from event content
///
/// event_id = "evt_" + SHA-256(canonical_json(event_without_id_and_sig))[:24 hex chars]
pub fn derive_event_id(event: &Event) -> Result<String, ProvaraError> {
    // Create event without event_id and signature
    let mut event_data = Map::new();
    event_data.insert("type".to_string(), json!(event.event_type));
    event_data.insert("actor".to_string(), json!(event.actor));
    
    if let Some(ref prev) = event.prev_event_hash {
        event_data.insert("prev_event_hash".to_string(), json!(prev));
    }
    
    if let Some(ref ts) = event.timestamp_utc {
        event_data.insert("timestamp_utc".to_string(), json!(ts));
    }
    
    event_data.insert("payload".to_string(), event.payload.clone());
    
    let value = Value::Object(event_data);
    let hash = canonical_hash(&value)?;
    
    // Take first 12 bytes (24 hex chars)
    let hex_chars = hex::encode(&hash[0..12]);
    
    Ok(format!("evt_{}", hex_chars))
}

/// Create a fully signed event with optional timestamp
pub fn create_event_full(
    event_type: &str,
    keypair: &KeyPair,
    prev_event_hash: Option<String>,
    payload: Value,
    timestamp_utc: Option<String>,
) -> Result<Event, ProvaraError> {
    let actor = keypair.key_id()?;

    let mut event = Event::new(event_type, &actor, prev_event_hash, payload);
    event.timestamp_utc = timestamp_utc;

    // Compute event_id
    event.event_id = derive_event_id(&event)?;

    // Compute signing payload (event without signature, but WITH event_id)
    let signing_payload = event.signing_payload()?;
    let canonical_bytes = canonicalize(&signing_payload)?;

    // Hash the canonical bytes
    let hash = sha256_hash(&canonical_bytes);

    // Sign the hash
    let signature = keypair.sign(&hash);

    // Encode signature as Base64
    use base64::Engine as _;
    event.signature = Some(base64::engine::general_purpose::STANDARD.encode(signature.to_bytes()));

    Ok(event)
}

/// Create a fully signed event (no timestamp)
pub fn create_event(
    event_type: &str,
    keypair: &KeyPair,
    prev_event_hash: Option<String>,
    payload: Value,
) -> Result<Event, ProvaraError> {
    create_event_full(event_type, keypair, prev_event_hash, payload, None)
}

/// Verify an event's signature
pub fn verify_event_signature(event: &Event, public_key: &[u8; 32]) -> Result<bool, ProvaraError> {
    let signature_b64 = event.signature.as_ref()
        .ok_or_else(|| ProvaraError::InvalidEvent("Missing signature".to_string()))?;
    
    // Decode Base64 signature
    use base64::Engine as _;
    let sig_bytes = base64::engine::general_purpose::STANDARD
        .decode(signature_b64)
        .map_err(|e| ProvaraError::Encoding(format!("Base64 decode failed: {}", e)))?;
    
    if sig_bytes.len() != 64 {
        return Err(ProvaraError::InvalidEvent(format!(
            "Invalid signature length: expected 64, got {}",
            sig_bytes.len()
        )));
    }
    
    let signature = Signature::from_slice(&sig_bytes)
        .map_err(|e| ProvaraError::Crypto(format!("Invalid signature: {}", e)))?;
    
    // Parse public key
    let verifying_key = VerifyingKey::from_bytes(public_key)
        .map_err(|e| ProvaraError::Crypto(format!("Invalid public key: {}", e)))?;
    
    // Compute signing payload hash
    let signing_payload = event.signing_payload()?;
    let canonical_bytes = canonicalize(&signing_payload)?;
    let hash = sha256_hash(&canonical_bytes);
    
    // Verify signature
    verifying_key.verify(&hash, &signature)
        .map_err(|e| ProvaraError::Crypto(format!("Signature verification failed: {}", e)))?;
    
    Ok(true)
}

/// Verify causal chain integrity
///
/// Checks that:
/// - First event by actor has prev_event_hash = null
/// - Subsequent events reference previous event by same actor
pub fn verify_causal_chain(events: &[Event]) -> Result<(), ProvaraError> {
    use std::collections::BTreeMap;
    
    // Track last event hash per actor
    let mut actor_last_event: BTreeMap<String, String> = BTreeMap::new();
    
    for event in events {
        let actor = &event.actor;
        
        match &event.prev_event_hash {
            None => {
                // First event by this actor
                if actor_last_event.contains_key(actor) {
                    return Err(ProvaraError::ChainValidation(format!(
                        "Actor {} has multiple genesis events",
                        actor
                    )));
                }
            }
            Some(prev_hash) => {
                // Check that prev_hash matches last event by this actor
                let expected = actor_last_event.get(actor)
                    .ok_or_else(|| ProvaraError::ChainValidation(format!(
                        "Actor {} references non-existent previous event",
                        actor
                    )))?;
                
                if prev_hash != expected {
                    return Err(ProvaraError::ChainValidation(format!(
                        "Broken chain for actor {}: expected {}, got {}",
                        actor, expected, prev_hash
                    )));
                }
            }
        }
        
        // Update last event for this actor
        actor_last_event.insert(actor.clone(), event.event_id.clone());
    }
    
    Ok(())
}

/// Compute Merkle root from file entries
///
/// File entries must be sorted lexicographically by path.
/// If leaf count is odd, the last leaf is duplicated.
pub fn compute_merkle_root(file_entries: &[Value]) -> Result<String, ProvaraError> {
    if file_entries.is_empty() {
        return Ok(sha256_hash_hex(b""));
    }
    
    // Sort by path
    let mut sorted_entries: Vec<&Value> = file_entries.iter().collect();
    sorted_entries.sort_by(|a, b| {
        let path_a = a.get("path").and_then(|v| v.as_str()).unwrap_or("");
        let path_b = b.get("path").and_then(|v| v.as_str()).unwrap_or("");
        path_a.cmp(path_b)
    });
    
    // Compute leaf hashes
    let mut hashes: Vec<[u8; 32]> = Vec::new();
    for entry in sorted_entries {
        let canonical = canonicalize(entry)?;
        let hash = sha256_hash(&canonical);
        hashes.push(hash);
    }
    
    // Pad to even number by duplicating last leaf
    if hashes.len() % 2 == 1 {
        hashes.push(*hashes.last().unwrap());
    }
    
    // Build Merkle tree
    while hashes.len() > 1 {
        let mut next_level = Vec::new();
        
        for chunk in hashes.chunks(2) {
            let mut hasher = Sha256::new();
            hasher.update(&chunk[0]);
            hasher.update(&chunk[1]);
            let result = hasher.finalize();
            
            let mut hash = [0u8; 32];
            hash.copy_from_slice(&result);
            next_level.push(hash);
        }
        
        hashes = next_level;
        
        // Pad if odd
        if hashes.len() % 2 == 1 && hashes.len() > 1 {
            hashes.push(*hashes.last().unwrap());
        }
    }
    
    Ok(hex::encode(hashes[0]))
}

/// Compute state hash from reducer state
///
/// state_hash = SHA-256(canonical_json(state_without_metadata_block))
pub fn compute_state_hash(state: &Value) -> Result<String, ProvaraError> {
    let hash = canonical_hash_hex(state)?;
    Ok(hash)
}

/// Import a public key from Base64-encoded bytes
pub fn import_public_key_b64(key_b64: &str) -> Result<[u8; 32], ProvaraError> {
    use base64::Engine as _;
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(key_b64)
        .map_err(|e| ProvaraError::Encoding(format!("Base64 decode failed: {}", e)))?;
    
    if bytes.len() != 32 {
        return Err(ProvaraError::KeyDerivation(format!(
            "Invalid public key length: expected 32 bytes, got {}",
            bytes.len()
        )));
    }
    
    let mut key = [0u8; 32];
    key.copy_from_slice(&bytes);
    Ok(key)
}

// ---------------------------------------------------------------------------
// WASM bindings — browser-compatible functions exposed via wasm-bindgen
// ---------------------------------------------------------------------------

#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub struct WasmKeyPair {
    inner: KeyPair,
}

#[cfg(feature = "wasm")]
#[wasm_bindgen]
impl WasmKeyPair {
    #[wasm_bindgen(constructor)]
    pub fn new() -> Self {
        use rand_core::OsRng;
        WasmKeyPair {
            inner: KeyPair::generate(&mut OsRng),
        }
    }

    #[wasm_bindgen(getter)]
    pub fn key_id(&self) -> Result<String, JsValue> {
        self.inner.key_id().map_err(|e| JsValue::from_str(&e.to_string()))
    }

    #[wasm_bindgen(getter)]
    pub fn public_key_b64(&self) -> String {
        use base64::Engine as _;
        base64::engine::general_purpose::STANDARD.encode(self.inner.public_key())
    }

    #[wasm_bindgen(getter)]
    pub fn private_key_b64(&self) -> String {
        use base64::Engine as _;
        base64::engine::general_purpose::STANDARD.encode(self.inner.seed_bytes())
    }
}

/// Generate a new Ed25519 keypair.
/// Returns a plain JS object: { key_id: string, public_key_b64: string, private_key_b64: string }
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn generate_keypair_js() -> Result<JsValue, JsValue> {
    use rand_core::OsRng;
    use base64::Engine as _;

    let kp = KeyPair::generate(&mut OsRng);
    let key_id = kp.key_id().map_err(|e| JsValue::from_str(&e.to_string()))?;
    let public_key_b64 = base64::engine::general_purpose::STANDARD.encode(kp.public_key());
    let private_key_b64 = base64::engine::general_purpose::STANDARD.encode(kp.seed_bytes());

    let obj = js_sys::Object::new();
    js_sys::Reflect::set(&obj, &"key_id".into(), &key_id.into())?;
    js_sys::Reflect::set(&obj, &"public_key_b64".into(), &public_key_b64.into())?;
    js_sys::Reflect::set(&obj, &"private_key_b64".into(), &private_key_b64.into())?;

    Ok(obj.into())
}

/// Create and sign a Provara event.
///
/// - event_type: "OBSERVATION" | "ATTESTATION" | "RETRACTION" | …
/// - payload_json: JSON string for the event payload
/// - prev_event_hash: event_id of the previous event by this actor, or null
/// - private_key_b64: Base64-encoded 32-byte Ed25519 seed
/// - timestamp_utc: ISO 8601 UTC timestamp string (e.g. new Date().toISOString())
///
/// Returns the signed event as a JSON string.
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn create_event_js(
    event_type: &str,
    payload_json: &str,
    prev_event_hash: Option<String>,
    private_key_b64: &str,
    timestamp_utc: Option<String>,
) -> Result<JsValue, JsValue> {
    use base64::Engine as _;

    let key_bytes = base64::engine::general_purpose::STANDARD
        .decode(private_key_b64)
        .map_err(|e| JsValue::from_str(&format!("Invalid private key: {}", e)))?;

    if key_bytes.len() != 32 {
        return Err(JsValue::from_str(&format!(
            "Private key must be 32 bytes, got {}",
            key_bytes.len()
        )));
    }

    let mut seed = [0u8; 32];
    seed.copy_from_slice(&key_bytes);

    let keypair = KeyPair::from_bytes(&seed)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    let payload: Value = serde_json::from_str(payload_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid payload JSON: {}", e)))?;

    let event = create_event_full(event_type, &keypair, prev_event_hash, payload, timestamp_utc)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    let event_json = serde_json::to_string(&event)
        .map_err(|e| JsValue::from_str(&format!("Serialization failed: {}", e)))?;

    Ok(JsValue::from_str(&event_json))
}

/// Verify an event's Ed25519 signature.
/// - event_json: JSON string of the signed event
/// - public_key_b64: Base64-encoded 32-byte public key
///
/// Returns true if valid, throws on invalid JSON or key format.
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn verify_event_js(event_json: &str, public_key_b64: &str) -> Result<bool, JsValue> {
    let event: Event = serde_json::from_str(event_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid event JSON: {}", e)))?;

    let pub_key = import_public_key_b64(public_key_b64)
        .map_err(|e| JsValue::from_str(&e.to_string()))?;

    verify_event_signature(&event, &pub_key)
        .map_err(|e| JsValue::from_str(&e.to_string()))
}

/// Verify causal chain integrity for an array of events.
/// - events_json: JSON array string of events
///
/// Returns a JS object: { valid: boolean, errors: string[] }
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn verify_chain_js(events_json: &str) -> Result<JsValue, JsValue> {
    let events: Vec<Event> = serde_json::from_str(events_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid JSON: {}", e)))?;

    let mut valid = true;
    let errors_arr = js_sys::Array::new();

    if let Err(e) = verify_causal_chain(&events) {
        valid = false;
        errors_arr.push(&JsValue::from_str(&e.to_string()));
    }

    let result = js_sys::Object::new();
    js_sys::Reflect::set(&result, &"valid".into(), &JsValue::from_bool(valid))?;
    js_sys::Reflect::set(&result, &"errors".into(), &errors_arr.into())?;

    Ok(result.into())
}

/// Compute RFC 8785 canonical JSON of the input JSON string.
/// Returns the canonical UTF-8 string.
#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn canonical_json_js(input_json: &str) -> Result<String, JsValue> {
    let value: Value = serde_json::from_str(input_json)
        .map_err(|e| JsValue::from_str(&format!("Invalid JSON: {}", e)))?;

    canonical_to_string(&value)
        .map_err(|e| JsValue::from_str(&e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::thread_rng;
    use serde_json::json;

    #[test]
    fn test_key_id_derivation() {
        // Test vector from vectors.json
        let public_key_hex = "42e47a04929e14ec37c1a9bedf7107030c22804f39908456b96562a81bc2e5c7";
        let public_key_bytes = hex::decode(public_key_hex).unwrap();
        let mut key = [0u8; 32];
        key.copy_from_slice(&public_key_bytes);
        
        let key_id = derive_key_id(&key).unwrap();
        assert_eq!(key_id, "bp1_5c99599d178e7632");
    }

    #[test]
    fn test_event_creation() {
        let mut rng = thread_rng();
        let keypair = KeyPair::generate(&mut rng);
        
        let event = create_event(
            "OBSERVATION",
            &keypair,
            None,
            json!({"subject": "test", "value": "ok"}),
        ).unwrap();
        
        assert!(event.event_id.starts_with("evt_"));
        assert!(event.signature.is_some());
        assert_eq!(event.actor, keypair.key_id().unwrap());
    }

    #[test]
    fn test_signature_verification() {
        let mut rng = thread_rng();
        let keypair = KeyPair::generate(&mut rng);
        
        let event = create_event(
            "OBSERVATION",
            &keypair,
            None,
            json!({"data": "test"}),
        ).unwrap();
        
        assert!(verify_event_signature(&event, &keypair.public_key()).unwrap());
    }

    #[test]
    fn test_causal_chain() {
        let mut rng = thread_rng();
        let keypair = KeyPair::generate(&mut rng);
        
        // Create genesis event
        let event1 = create_event(
            "OBSERVATION",
            &keypair,
            None,
            json!({"seq": 1}),
        ).unwrap();
        
        // Create second event
        let event2 = create_event(
            "OBSERVATION",
            &keypair,
            Some(event1.event_id.clone()),
            json!({"seq": 2}),
        ).unwrap();
        
        // Verify chain
        let events = vec![event1.clone(), event2.clone()];
        assert!(verify_causal_chain(&events).is_ok());
    }

    #[test]
    fn test_broken_chain_detection() {
        let mut rng = thread_rng();
        let keypair = KeyPair::generate(&mut rng);
        
        let event1 = create_event(
            "OBSERVATION",
            &keypair,
            None,
            json!({"seq": 1}),
        ).unwrap();
        
        // Create event with wrong prev hash
        let event2 = create_event(
            "OBSERVATION",
            &keypair,
            Some("evt_wrong_hash".to_string()),
            json!({"seq": 2}),
        ).unwrap();
        
        let events = vec![event1, event2];
        assert!(verify_causal_chain(&events).is_err());
    }

    #[test]
    fn test_merkle_root() {
        let entries = vec![
            json!({
                "path": "a.txt",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "size": 0
            }),
            json!({
                "path": "b.txt",
                "sha256": "315f5bdb76d078c43b8ac00c33e22F06d20353842d059013e96196a84f33161",
                "size": 1
            }),
        ];
        
        let root = compute_merkle_root(&entries).unwrap();
        // Test vector from vectors.json
        assert_eq!(root, "fa577a0bb290df978337de3342ebc17fcd3ad261f9ece7ce41622c36ccc2ed03");
    }
}
