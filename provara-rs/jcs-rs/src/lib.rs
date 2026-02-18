//! RFC 8785 JSON Canonicalization Scheme (JCS) for Rust.

use core::fmt;

use serde_json::{Map, Number, Value};

/// Canonicalization error.
#[derive(Debug)]
pub enum Error {
    /// Input JSON could not be parsed.
    InvalidJson(serde_json::Error),
    /// Non-finite number encountered.
    NonFiniteNumber,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Error::InvalidJson(e) => write!(f, "invalid json: {e}"),
            Error::NonFiniteNumber => write!(f, "non-finite number"),
        }
    }
}

impl std::error::Error for Error {}

impl From<serde_json::Error> for Error {
    fn from(value: serde_json::Error) -> Self {
        Error::InvalidJson(value)
    }
}

/// Serialize a JSON value to RFC 8785 canonical form.
pub fn canonicalize(value: &Value) -> Result<Vec<u8>, Error> {
    Ok(canonical_to_string(value)?.into_bytes())
}

/// Serialize a JSON string to RFC 8785 canonical form.
pub fn canonicalize_str(json: &str) -> Result<Vec<u8>, Error> {
    let value: Value = serde_json::from_str(json)?;
    canonicalize(&value)
}

/// Verify that a JSON byte string is in canonical form.
pub fn is_canonical(bytes: &[u8]) -> bool {
    let s = match core::str::from_utf8(bytes) {
        Ok(v) => v,
        Err(_) => return false,
    };
    let canonical = match canonicalize_str(s) {
        Ok(v) => v,
        Err(_) => return false,
    };
    canonical == bytes
}

/// Canonicalize to UTF-8 string (helper retained for workspace users).
pub fn canonical_to_string(value: &Value) -> Result<String, Error> {
    serialize_value(value)
}

fn serialize_value(value: &Value) -> Result<String, Error> {
    match value {
        Value::Null => Ok("null".to_string()),
        Value::Bool(b) => Ok(if *b { "true" } else { "false" }.to_string()),
        Value::Number(n) => serialize_number(n),
        Value::String(s) => serde_json::to_string(s).map_err(Error::InvalidJson),
        Value::Array(arr) => {
            let mut out = String::from("[");
            for (idx, item) in arr.iter().enumerate() {
                if idx > 0 {
                    out.push(',');
                }
                out.push_str(&serialize_value(item)?);
            }
            out.push(']');
            Ok(out)
        }
        Value::Object(map) => serialize_object(map),
    }
}

fn utf16_cmp(a: &str, b: &str) -> core::cmp::Ordering {
    let mut ia = a.encode_utf16();
    let mut ib = b.encode_utf16();

    loop {
        match (ia.next(), ib.next()) {
            (Some(ua), Some(ub)) => {
                let ord = ua.cmp(&ub);
                if ord != core::cmp::Ordering::Equal {
                    return ord;
                }
            }
            (None, Some(_)) => return core::cmp::Ordering::Less,
            (Some(_), None) => return core::cmp::Ordering::Greater,
            (None, None) => return core::cmp::Ordering::Equal,
        }
    }
}

fn serialize_object(map: &Map<String, Value>) -> Result<String, Error> {
    let mut keys: Vec<&str> = map.keys().map(String::as_str).collect();
    keys.sort_by(|a, b| utf16_cmp(a, b));

    let mut out = String::from("{");
    for (idx, key) in keys.iter().enumerate() {
        if idx > 0 {
            out.push(',');
        }
        out.push_str(&serde_json::to_string(key).map_err(Error::InvalidJson)?);
        out.push(':');
        out.push_str(&serialize_value(&map[*key])?);
    }
    out.push('}');
    Ok(out)
}

fn serialize_number(n: &Number) -> Result<String, Error> {
    if let Some(f) = n.as_f64() {
        if !f.is_finite() {
            return Err(Error::NonFiniteNumber);
        }
    }

    // serde_json uses ryu for float rendering. Apply small normalization for
    // RFC style exponent formatting.
    let mut s = n.to_string();
    if s.contains('E') {
        s = s.replace('E', "e");
    }
    if s.contains("e+") {
        s = s.replace("e+", "e");
    }
    Ok(s)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn canonicalize_basic() {
        let value = json!({"b": 2, "a": 1});
        let got = canonicalize(&value).unwrap();
        assert_eq!(got, b"{\"a\":1,\"b\":2}".to_vec());
    }

    #[test]
    fn canonicalize_from_str() {
        let got = canonicalize_str("{\"b\":2,\"a\":1}").unwrap();
        assert_eq!(got, b"{\"a\":1,\"b\":2}".to_vec());
    }

    #[test]
    fn canonical_check() {
        assert!(is_canonical(b"{\"a\":1,\"b\":2}"));
        assert!(!is_canonical(b"{\"b\":2,\"a\":1}"));
    }
}
