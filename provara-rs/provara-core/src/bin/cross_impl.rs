use base64::Engine as _;
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::fs;
use std::path::Path;

fn canonical_bytes(v: &Value) -> Result<Vec<u8>, String> {
    jcs_rs::canonicalize(v).map_err(|e| format!("canonicalization failed: {e}"))
}

fn sha256_hex(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}

fn key_id_from_public(public_key: &[u8; 32]) -> String {
    let digest = Sha256::digest(public_key);
    format!("bp1_{}", hex::encode(&digest[..8]))
}

fn verify_vault(vault: &Path) -> Result<(), String> {
    let events_path = vault.join("events").join("events.ndjson");
    let keys_path = vault.join("identity").join("keys.json");

    let keys_raw = fs::read_to_string(&keys_path)
        .map_err(|e| format!("failed to read {}: {e}", keys_path.display()))?;
    let keys_json: Value = serde_json::from_str(&keys_raw)
        .map_err(|e| format!("invalid keys.json: {e}"))?;

    let mut key_map: BTreeMap<String, [u8; 32]> = BTreeMap::new();
    if let Some(entries) = keys_json.get("keys").and_then(|v| v.as_array()) {
        for entry in entries {
            let kid = entry.get("key_id").and_then(|v| v.as_str());
            let pub_b64 = entry.get("public_key_b64").and_then(|v| v.as_str());
            if let (Some(k), Some(p)) = (kid, pub_b64) {
                let decoded = base64::engine::general_purpose::STANDARD
                    .decode(p)
                    .map_err(|e| format!("invalid base64 pubkey for {k}: {e}"))?;
                if decoded.len() != 32 {
                    return Err(format!("public key {k} must be 32 bytes"));
                }
                let mut pk = [0u8; 32];
                pk.copy_from_slice(&decoded);
                key_map.insert(k.to_string(), pk);
            }
        }
    }

    let content = fs::read_to_string(&events_path)
        .map_err(|e| format!("failed to read {}: {e}", events_path.display()))?;

    let mut last_by_actor: BTreeMap<String, String> = BTreeMap::new();
    for (idx, line) in content.lines().enumerate() {
        let raw = line.trim();
        if raw.is_empty() {
            continue;
        }
        let event: Value = serde_json::from_str(raw)
            .map_err(|e| format!("invalid event JSON at line {}: {e}", idx + 1))?;

        let actor = event
            .get("actor")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("event line {} missing actor", idx + 1))?
            .to_string();
        let event_id = event
            .get("event_id")
            .and_then(|v| v.as_str())
            .ok_or_else(|| format!("event line {} missing event_id", idx + 1))?
            .to_string();

        let prev = event.get("prev_event_hash");
        match last_by_actor.get(&actor) {
            None => {
                if !prev.is_none() && !prev.is_some_and(|v| v.is_null()) {
                    return Err(format!("broken chain for actor {actor}: first event must have null prev_event_hash"));
                }
            }
            Some(expected_prev) => {
                let actual_prev = prev.and_then(|v| v.as_str()).unwrap_or("");
                if actual_prev != expected_prev {
                    return Err(format!(
                        "broken chain for actor {actor}: expected prev {}, got {}",
                        expected_prev, actual_prev
                    ));
                }
            }
        }

        if let (Some(sig_b64), Some(kid)) = (
            event.get("sig").and_then(|v| v.as_str()),
            event.get("actor_key_id").and_then(|v| v.as_str()),
        ) {
            let pubkey = key_map
                .get(kid)
                .ok_or_else(|| format!("event {event_id} references unknown key_id {kid}"))?;
            let verifying_key = VerifyingKey::from_bytes(pubkey)
                .map_err(|e| format!("invalid key for {kid}: {e}"))?;

            let mut signing_obj = event.clone();
            if let Some(map) = signing_obj.as_object_mut() {
                map.remove("sig");
            }
            let canonical = canonical_bytes(&signing_obj)?;
            let hash = Sha256::digest(&canonical);

            let sig_bytes = base64::engine::general_purpose::STANDARD
                .decode(sig_b64)
                .map_err(|e| format!("invalid signature b64 on event {event_id}: {e}"))?;
            let signature = Signature::from_slice(&sig_bytes)
                .map_err(|e| format!("invalid signature on event {event_id}: {e}"))?;

            verifying_key
                .verify(&hash, &signature)
                .map_err(|e| format!("signature verification failed on {event_id}: {e}"))?;
        }

        last_by_actor.insert(actor, event_id);
    }

    Ok(())
}

fn create_vault(vault: &Path) -> Result<(), String> {
    fs::create_dir_all(vault.join("events")).map_err(|e| e.to_string())?;
    fs::create_dir_all(vault.join("identity")).map_err(|e| e.to_string())?;

    let seed = [7u8; 32];
    let signing_key = SigningKey::from_bytes(&seed);
    let verifying_key = signing_key.verifying_key();
    let public = verifying_key.to_bytes();
    let key_id = key_id_from_public(&public);

    let keys_json = json!({
        "keys": [{
            "key_id": key_id,
            "algorithm": "Ed25519",
            "public_key_b64": base64::engine::general_purpose::STANDARD.encode(public),
            "status": "active"
        }]
    });
    fs::write(vault.join("identity").join("keys.json"), serde_json::to_string_pretty(&keys_json).unwrap())
        .map_err(|e| e.to_string())?;

    let mut event = json!({
        "type": "OBSERVATION",
        "actor": "rust_actor",
        "prev_event_hash": null,
        "timestamp_utc": "2026-01-01T00:00:00+00:00",
        "payload": {
            "subject": "interop",
            "predicate": "status",
            "value": "rust-created"
        }
    });

    let event_id_hash = sha256_hex(&canonical_bytes(&event)?);
    event["event_id"] = Value::String(format!("evt_{}", &event_id_hash[..24]));
    event["actor_key_id"] = Value::String(key_id);

    let signature_b64 = sign_event_json_internal(
        base64::engine::general_purpose::STANDARD.encode(seed),
        serde_json::to_string(&event).map_err(|e| e.to_string())?,
    )?;
    event["sig"] = Value::String(signature_b64);

    let line = String::from_utf8(canonical_bytes(&event)?).map_err(|e| e.to_string())? + "\n";
    fs::write(vault.join("events").join("events.ndjson"), line).map_err(|e| e.to_string())?;

    Ok(())
}

fn sign_event_json_internal(private_key_b64: String, event_json: String) -> Result<String, String> {
    let priv_bytes = base64::engine::general_purpose::STANDARD
        .decode(private_key_b64)
        .map_err(|e| format!("invalid private key b64: {e}"))?;
    if priv_bytes.len() != 32 {
        return Err("private key must decode to 32 bytes".to_string());
    }
    let mut seed = [0u8; 32];
    seed.copy_from_slice(&priv_bytes);
    let signing_key = SigningKey::from_bytes(&seed);

    let event: Value = serde_json::from_str(&event_json)
        .map_err(|e| format!("invalid event json: {e}"))?;
    let canonical = canonical_bytes(&event)?;
    let hash = Sha256::digest(&canonical);
    let sig = signing_key.sign(&hash);
    Ok(base64::engine::general_purpose::STANDARD.encode(sig.to_bytes()))
}

fn usage() {
    eprintln!("Usage:");
    eprintln!("  cross_impl canonical-sha256 --input-json <json>");
    eprintln!("  cross_impl verify-vault --vault <path>");
    eprintln!("  cross_impl create-vault --vault <path>");
    eprintln!("  cross_impl sign-event-json --private-key-b64 <b64> --event-json <json>");
}

fn arg_value(args: &[String], name: &str) -> Option<String> {
    args.windows(2)
        .find_map(|w| if w[0] == name { Some(w[1].clone()) } else { None })
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 2 {
        usage();
        std::process::exit(2);
    }

    let cmd = args[1].as_str();
    let result = match cmd {
        "canonical-sha256" => {
            let input = arg_value(&args, "--input-json").ok_or_else(|| "--input-json is required".to_string());
            input.and_then(|j| {
                let v: Value = serde_json::from_str(&j).map_err(|e| format!("invalid json: {e}"))?;
                let c = canonical_bytes(&v)?;
                println!("{}", sha256_hex(&c));
                Ok(())
            })
        }
        "verify-vault" => {
            let vault = arg_value(&args, "--vault").ok_or_else(|| "--vault is required".to_string());
            vault.and_then(|p| verify_vault(Path::new(&p)))
        }
        "create-vault" => {
            let vault = arg_value(&args, "--vault").ok_or_else(|| "--vault is required".to_string());
            vault.and_then(|p| create_vault(Path::new(&p)))
        }
        "sign-event-json" => {
            let private_key = arg_value(&args, "--private-key-b64")
                .ok_or_else(|| "--private-key-b64 is required".to_string());
            let event_json = arg_value(&args, "--event-json")
                .ok_or_else(|| "--event-json is required".to_string());
            private_key.and_then(|pk| event_json.and_then(|ev| {
                let sig = sign_event_json_internal(pk, ev)?;
                println!("{}", sig);
                Ok(())
            }))
        }
        _ => Err(format!("unknown command: {cmd}")),
    };

    if let Err(e) = result {
        eprintln!("ERROR: {e}");
        std::process::exit(1);
    }
}
