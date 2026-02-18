use std::collections::{BTreeMap, BTreeSet};
use serde::{Deserialize, Serialize};
use serde_json::{Value, Map, json};
use jcs_rs::{canonical_hash_hex, canonical_to_string};

const REDUCER_NAME: &str = "SovereignReducerV0";
const REDUCER_VERSION: &str = "0.2.0";
const DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD: f64 = 0.50;
const DEFAULT_OBSERVATION_CONFIDENCE: f64 = 0.50;
const DEFAULT_ASSERTION_CONFIDENCE: f64 = 0.35;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Evidence {
    pub event_id: String,
    pub actor: String,
    pub namespace: String,
    pub timestamp_utc: Option<String>,
    pub value: Value,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReducerMetadata {
    pub name: String,
    pub version: String,
    pub conflict_confidence_threshold: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StateMetadata {
    pub last_event_id: Option<String>,
    pub event_count: u64,
    pub state_hash: Option<String>,
    pub current_epoch: Option<Value>,
    pub reducer: ReducerMetadata,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReducerState {
    pub canonical: BTreeMap<String, Value>,
    pub local: BTreeMap<String, Value>,
    pub contested: BTreeMap<String, Value>,
    pub archived: BTreeMap<String, Vec<Value>>,
    pub metadata: StateMetadata,
}

pub struct SovereignReducerV0 {
    pub state: ReducerState,
    evidence: BTreeMap<String, Vec<Evidence>>,
    ignored_types: BTreeSet<String>,
}

impl SovereignReducerV0 {
    pub fn new(conflict_confidence_threshold: Option<f64>) -> Self {
        let threshold = conflict_confidence_threshold.unwrap_or(DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD);
        
        let mut reducer = SovereignReducerV0 {
            state: ReducerState {
                canonical: BTreeMap::new(),
                local: BTreeMap::new(),
                contested: BTreeMap::new(),
                archived: BTreeMap::new(),
                metadata: StateMetadata {
                    last_event_id: None,
                    event_count: 0,
                    state_hash: None,
                    current_epoch: None,
                    reducer: ReducerMetadata {
                        name: REDUCER_NAME.to_string(),
                        version: REDUCER_VERSION.to_string(),
                        conflict_confidence_threshold: threshold,
                    },
                },
            },
            evidence: BTreeMap::new(),
            ignored_types: BTreeSet::new(),
        };
        
        reducer.update_state_hash();
        reducer
    }

    pub fn apply_events(&mut self, events: &[Value]) {
        for event in events {
            self.apply_event_internal(event);
        }
        self.update_state_hash();
    }

    pub fn apply_event(&mut self, event: &Value) {
        self.apply_event_internal(event);
        self.update_state_hash();
    }

    fn apply_event_internal(&mut self, event: &Value) {
        let obj = match event.as_object() {
            Some(o) => o,
            None => return,
        };

        let e_type = obj.get("type").and_then(|v| v.as_str()).unwrap_or("");
        let event_id = obj.get("event_id")
            .or_else(|| obj.get("id"))
            .and_then(|v| v.as_str())
            .unwrap_or("unknown_event")
            .to_string();
        let actor = obj.get("actor").and_then(|v| v.as_str()).unwrap_or("unknown").to_string();
        let namespace = self.normalize_namespace(obj.get("namespace"));
        let payload = obj.get("payload").and_then(|v| v.as_object());

        match e_type {
            "OBSERVATION" => {
                if let Some(p) = payload {
                    self.handle_observation(&event_id, &actor, &namespace, p, false);
                }
            },
            "ASSERTION" => {
                if let Some(p) = payload {
                    self.handle_observation(&event_id, &actor, &namespace, p, true);
                }
            },
            "ATTESTATION" => {
                if let Some(p) = payload {
                    self.handle_attestation(&event_id, &actor, p);
                }
            },
            "RETRACTION" => {
                if let Some(p) = payload {
                    self.handle_retraction(&event_id, &actor, p);
                }
            },
            "REDUCER_EPOCH" => {
                if let Some(p) = payload {
                    self.handle_reducer_epoch(&event_id, p);
                }
            },
            _ => {
                if !e_type.is_empty() {
                    self.ignored_types.insert(e_type.to_string());
                }
            }
        }

        self.state.metadata.last_event_id = Some(event_id);
        self.state.metadata.event_count += 1;
    }

    fn normalize_namespace(&self, raw: Option<&Value>) -> String {
        let ns = raw.and_then(|v| v.as_str()).unwrap_or("local").to_lowercase();
        if ["canonical", "local", "contested", "archived"].contains(&ns.as_str()) {
            ns
        } else {
            "local".to_string()
        }
    }

    fn handle_observation(
        &mut self,
        event_id: &str,
        actor: &str,
        namespace: &str,
        payload: &Map<String, Value>,
        is_assertion: bool,
    ) {
        let subject = match payload.get("subject").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => return,
        };
        let predicate = match payload.get("predicate").and_then(|v| v.as_str()) {
            Some(p) => p,
            None => return,
        };

        let key = format!("{}:{}", subject, predicate);
        let value = payload.get("value").cloned().unwrap_or(Value::Null);
        let default_conf = if is_assertion { DEFAULT_ASSERTION_CONFIDENCE } else { DEFAULT_OBSERVATION_CONFIDENCE };
        let confidence = payload.get("confidence").and_then(|v| v.as_f64()).unwrap_or(default_conf);
        let ts = payload.get("timestamp").or_else(|| payload.get("timestamp_utc")).and_then(|v| v.as_str());

        let ev = Evidence {
            event_id: event_id.to_string(),
            actor: actor.to_string(),
            namespace: namespace.to_string(),
            timestamp_utc: ts.map(|s| s.to_string()),
            value: value.clone(),
            confidence,
        };

        self.evidence.entry(key.clone()).or_insert_with(Vec::new).push(ev);

        // Conflict detection
        let canonical_entry = self.state.canonical.get(&key);
        let local_entry = self.state.local.get(&key);

        if let Some(ce) = canonical_entry {
            if ce.get("value") != Some(&value) && confidence >= self.state.metadata.reducer.conflict_confidence_threshold {
                self.mark_contested(&key, "conflicts_with_canonical");
                return;
            }
        }

        if let Some(le) = local_entry {
            if le.get("value") != Some(&value) {
                let prev_conf = le.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
                if prev_conf.max(confidence) >= self.state.metadata.reducer.conflict_confidence_threshold {
                    self.mark_contested(&key, "conflicts_with_local");
                    return;
                }
            } else {
                let existing_conf = le.get("confidence").and_then(|v| v.as_f64()).unwrap_or(0.0);
                if confidence <= existing_conf {
                    return;
                }
            }
        }

        self.state.local.insert(key, json!({
            "value": value,
            "confidence": confidence,
            "provenance": event_id,
            "actor": actor,
            "timestamp": ts,
            "evidence_count": self.evidence.get(subject).map(|e| e.len()).unwrap_or(0) // Fix: use key, not subject
        }));
        
        // Correct the evidence count indexing
        let key_again = format!("{}:{}", subject, predicate);
        if let Some(le) = self.state.local.get_mut(&key_again) {
            if let Some(obj) = le.as_object_mut() {
                obj.insert("evidence_count".to_string(), json!(self.evidence.get(&key_again).map(|e| e.len()).unwrap_or(0)));
            }
        }
    }

    fn handle_attestation(&mut self, event_id: &str, actor: &str, payload: &Map<String, Value>) {
        let subject = match payload.get("subject").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => return,
        };
        let predicate = match payload.get("predicate").and_then(|v| v.as_str()) {
            Some(p) => p,
            None => return,
        };

        let key = format!("{}:{}", subject, predicate);
        let value = payload.get("value").cloned().unwrap_or(Value::Null);
        let target_event_id = payload.get("target_event_id").and_then(|v| v.as_str());

        if let Some(existing) = self.state.canonical.get(&key) {
            let mut archived = existing.clone();
            if let Some(obj) = archived.as_object_mut() {
                obj.insert("superseded_by".to_string(), json!(event_id));
            }
            self.state.archived.entry(key.clone()).or_insert_with(Vec::new).push(archived);
        }

        self.state.canonical.insert(key.clone(), json!({
            "value": value,
            "attested_by": payload.get("actor_key_id").and_then(|v| v.as_str()).unwrap_or(actor),
            "provenance": target_event_id.unwrap_or(event_id),
            "attestation_event_id": event_id,
        }));

        self.state.local.remove(&key);
        self.state.contested.remove(&key);
    }

    fn handle_retraction(&mut self, event_id: &str, _actor: &str, payload: &Map<String, Value>) {
        let subject = match payload.get("subject").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => return,
        };
        let predicate = match payload.get("predicate").and_then(|v| v.as_str()) {
            Some(p) => p,
            None => return,
        };

        let key = format!("{}:{}", subject, predicate);

        if let Some(existing) = self.state.canonical.get(&key) {
            let mut archived = existing.clone();
            if let Some(obj) = archived.as_object_mut() {
                obj.insert("superseded_by".to_string(), json!(event_id));
                obj.insert("retracted".to_string(), json!(true));
            }
            self.state.archived.entry(key.clone()).or_insert_with(Vec::new).push(archived);
            self.state.canonical.remove(&key);
        }

        self.state.local.remove(&key);
        self.state.contested.remove(&key);
    }

    fn handle_reducer_epoch(&mut self, event_id: &str, payload: &Map<String, Value>) {
        self.state.metadata.current_epoch = Some(json!({
            "epoch_id": payload.get("epoch_id"),
            "reducer_hash": payload.get("reducer_hash"),
            "effective_from_event_id": payload.get("effective_from_event_id").and_then(|v| v.as_str()).unwrap_or(event_id),
            "ontology_versions": payload.get("ontology_versions"),
        }));
    }

    fn mark_contested(&mut self, key: &str, reason: &str) {
        let all_evidence = self.evidence.get(key).cloned().unwrap_or_default();
        
        let mut by_value: BTreeMap<String, Vec<Value>> = BTreeMap::new();
        for ev in &all_evidence {
            let val_key = canonical_to_string(&ev.value).unwrap_or_default();
            by_value.entry(val_key).or_insert_with(Vec::new).push(json!({
                "event_id": ev.event_id,
                "actor": ev.actor,
                "namespace": ev.namespace,
                "timestamp_utc": ev.timestamp_utc,
                "value": ev.value,
                "confidence": ev.confidence,
            }));
        }

        self.state.contested.insert(key.to_string(), json!({
            "status": "AWAITING_RESOLUTION",
            "reason": reason,
            "canonical_value": self.state.canonical.get(key).and_then(|v| v.get("value")),
            "evidence_by_value": by_value,
            "total_evidence_count": all_evidence.len(),
        }));

        self.state.local.remove(key);
    }

    fn update_state_hash(&mut self) {
        let hashable = json!({
            "canonical": self.state.canonical,
            "local": self.state.local,
            "contested": self.state.contested,
            "archived": self.state.archived,
            "metadata_partial": {
                "last_event_id": self.state.metadata.last_event_id,
                "event_count": self.state.metadata.event_count,
                "current_epoch": self.state.metadata.current_epoch,
                "reducer": self.state.metadata.reducer,
            },
        });
        
        self.state.metadata.state_hash = Some(canonical_hash_hex(&hashable).unwrap_or_default());
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty_state_hash() {
        let reducer = SovereignReducerV0::new(None);
        assert!(reducer.state.metadata.state_hash.is_some());
        let hash1 = reducer.state.metadata.state_hash.clone().unwrap();
        
        let reducer2 = SovereignReducerV0::new(None);
        let hash2 = reducer2.state.metadata.state_hash.unwrap();
        
        assert_eq!(hash1, hash2);
    }

    #[test]
    fn test_observation_to_local() {
        let mut reducer = SovereignReducerV0::new(None);
        let event = json!({
            "type": "OBSERVATION",
            "event_id": "evt_1",
            "actor": "alice",
            "payload": {
                "subject": "door",
                "predicate": "status",
                "value": "open",
                "confidence": 0.9
            }
        });
        
        reducer.apply_event(&event);
        assert_eq!(reducer.state.local.get("door:status").unwrap()["value"], "open");
        assert_eq!(reducer.state.metadata.event_count, 1);
    }
}
