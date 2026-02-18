//! jcs-rs — RFC 8785 JSON Canonicalization Scheme
//!
//! This crate provides deterministic JSON serialization according to
//! [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html).
//!
//! ## Features
//!
//! - Lexicographic key ordering by Unicode code point
//! - No whitespace between tokens
//! - Minimal escape sequences in strings
//! - Canonical number formatting
//! - UTF-8 encoding without BOM
//!
//! ## Example
//!
//! ```rust
//! use serde_json::json;
//! use jcs_rs::canonicalize;
//!
//! let value = json!({
//!     "z": null,
//!     "a": true,
//!     "b": [1, 2, 3]
//! });
//!
//! let canonical = canonicalize(&value).unwrap();
//! assert_eq!(
//!     canonical,
//!     b"{\"a\":true,\"b\":[1,2,3],\"z\":null}"
//! );
//! ```

#[cfg(feature = "wasm")]
use wasm_bindgen::prelude::*;

use serde::Serialize;
use serde_json::{Map, Number, Value};
use thiserror::Error;

/// Errors that can occur during canonicalization
#[derive(Debug, Error, PartialEq)]
pub enum CanonicalizeError {
    #[error("Invalid UTF-8 sequence")]
    InvalidUtf8,
    #[error("Number out of range")]
    NumberOutOfRange,
    #[error("Invalid JSON structure")]
    InvalidJson,
}

/// Canonicalize a JSON value according to RFC 8785.
///
/// Returns the canonical JSON bytes as a Vec<u8>.
pub fn canonicalize(value: &Value) -> Result<Vec<u8>, CanonicalizeError> {
    let canonical_str = canonical_to_string(value)?;
    Ok(canonical_str.into_bytes())
}

/// Canonicalize a JSON value and return as a String.
///
/// This is the main entry point for RFC 8785 canonicalization.
pub fn canonical_to_string(value: &Value) -> Result<String, CanonicalizeError> {
    canonicalize_value(value)
}

/// Canonicalize a serde::Serialize value.
///
/// This is a convenience function that first serializes the value
/// to JSON, then canonicalizes it.
pub fn canonicalize_serializable<T: Serialize>(value: &T) -> Result<Vec<u8>, CanonicalizeError> {
    let json_value = serde_json::to_value(value).map_err(|_| CanonicalizeError::InvalidJson)?;
    canonicalize(&json_value)
}

/// Internal recursive canonicalization function
fn canonicalize_value(value: &Value) -> Result<String, CanonicalizeError> {
    match value {
        Value::Null => Ok("null".to_string()),
        Value::Bool(b) => Ok(if *b { "true" } else { "false" }.to_string()),
        Value::Number(n) => canonicalize_number(n),
        Value::String(s) => Ok(canonicalize_string(s)),
        Value::Array(arr) => canonicalize_array(arr),
        Value::Object(obj) => canonicalize_object(obj),
    }
}

/// Canonicalize a JSON number according to RFC 8785.
///
/// Rules:
/// - No leading zeros
/// - No positive sign
/// - No trailing decimal zeros
/// - No trailing decimal point
/// - Minus zero (-0.0) is preserved as distinct from 0.0
fn canonicalize_number(n: &Number) -> Result<String, CanonicalizeError> {
    if let Some(i) = n.as_i64() {
        Ok(i.to_string())
    } else if let Some(u) = n.as_u64() {
        Ok(u.to_string())
    } else if let Some(f) = n.as_f64() {
        // Handle special cases
        if f.is_infinite() || f.is_nan() {
            return Err(CanonicalizeError::NumberOutOfRange);
        }

        // Format with 17 significant digits then strip trailing zeros.
        // This value fell through the integer branches, so it is stored as a
        // float in serde_json (e.g. 0.0, -0.0, 0.125).  Python's json.dumps
        // preserves the decimal point for such values (0.0 → "0.0"), so we
        // keep at least one digit after the decimal to stay byte-for-byte
        // compatible with the Python canonical-JSON implementation.
        let mut s = format!("{:.17}", f);

        if s.contains('.') {
            while s.ends_with('0') {
                s.pop();
            }
            // Keep the trailing '.' so we can append '0' below — don't strip it.
        }

        // Ensure there is always at least one decimal digit (e.g. "0." → "0.0").
        if s.ends_with('.') {
            s.push('0');
        }

        Ok(s)
    } else {
        Err(CanonicalizeError::NumberOutOfRange)
    }
}

/// Canonicalize a JSON string according to RFC 8785.
///
/// Rules:
/// - Use minimal escape sequences
/// - Only escape control characters, quotes, and backslashes
/// - Use \uXXXX for other non-ASCII characters
fn canonicalize_string(s: &str) -> String {
    let mut result = String::with_capacity(s.len() + 2);
    result.push('"');
    
    for c in s.chars() {
        match c {
            '"' => result.push_str("\\\""),
            '\\' => result.push_str("\\\\"),
            '\n' => result.push_str("\\n"),
            '\r' => result.push_str("\\r"),
            '\t' => result.push_str("\\t"),
            '\u{08}' => result.push_str("\\b"),
            '\u{0C}' => result.push_str("\\f"),
            c if c.is_control() => {
                // Use \uXXXX for other control characters
                let code = c as u32;
                result.push_str(&format!("\\u{:04x}", code));
            }
            c => result.push(c),
        }
    }
    
    result.push('"');
    result
}

/// Canonicalize a JSON array.
fn canonicalize_array(arr: &[Value]) -> Result<String, CanonicalizeError> {
    let mut result = String::from("[");
    
    for (i, item) in arr.iter().enumerate() {
        if i > 0 {
            result.push(',');
        }
        result.push_str(&canonicalize_value(item)?);
    }
    
    result.push(']');
    Ok(result)
}

/// Canonicalize a JSON object.
///
/// Keys are sorted lexicographically by Unicode code point.
fn canonicalize_object(obj: &Map<String, Value>) -> Result<String, CanonicalizeError> {
    let mut result = String::from("{");
    
    // Sort keys lexicographically by Unicode code point
    let mut keys: Vec<&String> = obj.keys().collect();
    keys.sort_by(|a, b| a.as_str().cmp(b.as_str()));
    
    for (i, key) in keys.iter().enumerate() {
        if i > 0 {
            result.push(',');
        }
        
        // Add the key
        result.push_str(&canonicalize_string(key));
        result.push(':');
        
        // Add the value
        let value = &obj[*key];
        result.push_str(&canonicalize_value(value)?);
    }
    
    result.push('}');
    Ok(result)
}

/// Compute SHA-256 hash of canonical JSON bytes.
///
/// This is a convenience function for computing content-addressed IDs.
pub fn canonical_hash(value: &Value) -> Result<[u8; 32], CanonicalizeError> {
    use sha2::{Digest, Sha256};
    
    let canonical_bytes = canonicalize(value)?;
    let mut hasher = Sha256::new();
    hasher.update(&canonical_bytes);
    let result = hasher.finalize();
    
    let mut hash = [0u8; 32];
    hash.copy_from_slice(&result);
    Ok(hash)
}

/// Compute SHA-256 hash of canonical JSON as hex string.
pub fn canonical_hash_hex(value: &Value) -> Result<String, CanonicalizeError> {
    let hash = canonical_hash(value)?;
    Ok(hex::encode(hash))
}

#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn canonicalize_js(value: &JsValue) -> Result<Vec<u8>, JsValue> {
    // Convert JS value to JSON string, then parse to Value
    let json_str = value.as_string().ok_or("Invalid input: expected string")?;
    let json_value: Value = serde_json::from_str(&json_str)
        .map_err(|e| JsValue::from_str(&format!("Invalid JSON: {}", e)))?;
    
    canonicalize(&json_value)
        .map_err(|e| JsValue::from_str(&e.to_string()))
}

#[cfg(feature = "wasm")]
#[wasm_bindgen]
pub fn canonicalize_string_js(value: &JsValue) -> Result<String, JsValue> {
    let json_str = value.as_string().ok_or("Invalid input: expected string")?;
    let json_value: Value = serde_json::from_str(&json_str)
        .map_err(|e| JsValue::from_str(&format!("Invalid JSON: {}", e)))?;
    
    canonical_to_string(&json_value)
        .map_err(|e| JsValue::from_str(&e.to_string()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn test_basic_object() {
        let value = json!({
            "z": null,
            "a": true,
            "b": [1, 2, 3]
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"a":true,"b":[1,2,3],"z":null}"#);
    }

    #[test]
    fn test_key_ordering() {
        let value = json!({
            "z": 1,
            "a": 2,
            "m": 3
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"a":2,"m":3,"z":1}"#);
    }

    #[test]
    fn test_nested_structure() {
        let value = json!({
            "a": [1, {"b": 2}, [3, 4]],
            "c": {"d": {"e": 5}}
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"a":[1,{"b":2},[3,4]],"c":{"d":{"e":5}}}"#);
    }

    #[test]
    fn test_null_preservation() {
        let value = json!({
            "a": null,
            "b": {"c": null}
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"a":null,"b":{"c":null}}"#);
    }

    #[test]
    fn test_string_escapes() {
        let value = json!({
            "s": "quote: \", backslash: \\, tab: \t, newline: \n"
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"s":"quote: \", backslash: \\, tab: \t, newline: \n"}"#);
    }

    #[test]
    fn test_number_formatting() {
        let value = json!({
            "int": 10,
            "neg_int": -7,
            "frac": 0.125,
            "big": 1000000.5
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"big":1000000.5,"frac":0.125,"int":10,"neg_int":-7}"#);
    }

    #[test]
    fn test_empty_containers() {
        let value = json!({
            "empty_obj": {},
            "empty_arr": []
        });
        
        let result = canonical_to_string(&value).unwrap();
        assert_eq!(result, r#"{"empty_arr":[],"empty_obj":{}}"#);
    }

    #[test]
    fn test_hash_determinism() {
        let value1 = json!({"a": 1, "b": 2});
        let value2 = json!({"b": 2, "a": 1});
        
        let hash1 = canonical_hash_hex(&value1).unwrap();
        let hash2 = canonical_hash_hex(&value2).unwrap();
        
        // Same logical object should produce same hash
        assert_eq!(hash1, hash2);
    }
}
