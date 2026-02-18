//! Canonical JSON conformance suite validation
//!
//! This module validates RFC 8785 implementation against the
//! Provara canonical conformance suite in test_vectors/canonical_conformance.json

use crate::canonical_to_string;
use serde::Deserialize;
use serde_json::Value;

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct ConformanceVector {
    id: String,
    description: String,
    input: Value,
    expected_hex: String,
}

#[allow(dead_code)]
#[derive(Debug, Deserialize)]
struct ConformanceSuite {
    version: String,
    description: String,
    vectors: Vec<ConformanceVector>,
}

/// Run all conformance tests and return results
pub fn run_conformance_suite(conformance_json: &str) -> Result<Vec<(String, bool, String)>, String> {
    let suite: ConformanceSuite = serde_json::from_str(conformance_json)
        .map_err(|e| format!("Failed to parse conformance suite: {}", e))?;
    
    let mut results = Vec::new();
    
    for vector in suite.vectors {
        let passed = test_canonical_vector(&vector);
        let ok = passed.is_ok();
        let msg = passed.err().unwrap_or_default();
        results.push((vector.id, ok, msg));
    }
    
    Ok(results)
}

fn test_canonical_vector(vector: &ConformanceVector) -> Result<(), String> {
    let canonical = canonical_to_string(&vector.input)
        .map_err(|e| format!("Canonicalization failed: {}", e))?;
    
    let canonical_hex = hex::encode(canonical.as_bytes());
    
    if canonical_hex == vector.expected_hex {
        Ok(())
    } else {
        Err(format!(
            "Conformance mismatch for {}:\n  Description: {}\n  Expected: {}\n  Got:      {}",
            vector.id, vector.description, vector.expected_hex, canonical_hex
        ))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_run_conformance_suite() {
        // Load conformance suite from file
        let conformance_json = include_str!("../../../test_vectors/canonical_conformance.json");
        
        let results = run_conformance_suite(conformance_json).unwrap();
        
        println!("\nCanonical Conformance Suite Results:");
        for (id, passed, message) in &results {
            if *passed {
                println!("  ✓ {}", id);
            } else {
                println!("  ✗ {}: {}", id, message);
            }
        }
        
        // Count passed/failed
        let passed = results.iter().filter(|(_, p, _)| *p).count();
        let total = results.len();
        
        println!("\nPassed: {}/{}", passed, total);
        
        assert_eq!(passed, total, "All conformance tests must pass");
    }
}
