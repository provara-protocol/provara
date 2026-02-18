use std::fs;
use std::path::Path;

use jcs_rs::{canonicalize, canonicalize_str};
use serde_json::Value;

#[test]
fn provara_conformance_vectors() {
    let root = Path::new(env!("CARGO_MANIFEST_DIR")).join("../../test_vectors/canonical_conformance.json");
    let raw = fs::read_to_string(root).expect("read conformance vectors");
    let suite: Value = serde_json::from_str(&raw).expect("parse conformance vectors");
    let vectors = suite["vectors"].as_array().expect("vectors array");
    assert_eq!(vectors.len(), 12, "expected 12 conformance vectors");

    for vector in vectors {
        let id = vector["id"].as_str().unwrap_or("unknown");
        let input = &vector["input"];
        let expected_hex = vector["expected_hex"].as_str().expect("expected_hex");

        let bytes = canonicalize(input).unwrap_or_else(|_| panic!("canonicalize failed: {id}"));
        let actual_hex = hex_encode(&bytes);
        assert_eq!(
            actual_hex, expected_hex,
            "vector failed: {id}"
        );
    }
}

#[test]
fn rfc_examples_and_edges() {
    // RFC-style sorted object
    let out = canonicalize_str(r#"{"b":2,"a":1}"#).unwrap();
    assert_eq!(out, br#"{"a":1,"b":2}"#);

    // Unicode normalization: preserve distinct codepoints
    let out = canonicalize_str(r#"{"nfc":"\u00e9","nfd":"e\u0301"}"#).unwrap();
    assert_eq!(String::from_utf8(out).unwrap(), r#"{"nfc":"é","nfd":"é"}"#);

    // Number normalization behavior expected by current suite
    let out = canonicalize_str(r#"{"n":1.2300,"m":1E+30}"#).unwrap();
    let s = std::str::from_utf8(&out).unwrap();
    assert!(s.contains("1.23"));
    assert!(s.contains("1e30") || s.contains("1e+30") || s.contains("1000000000000000000000000000000"));

    // UTF-16 sort behavior check
    let out = canonicalize_str(r#"{"\ud83d\ude00":1,"\ufffd":2}"#).unwrap();
    assert_eq!(String::from_utf8(out).unwrap(), r#"{"😀":1,"�":2}"#);

    // Deep nesting
    let mut nested = String::new();
    for _ in 0..64 {
        nested.push('[');
    }
    nested.push('0');
    for _ in 0..64 {
        nested.push(']');
    }
    let out = canonicalize_str(&nested).unwrap();
    assert_eq!(out, nested.into_bytes());

    // Empty containers
    let out = canonicalize_str(r#"{"empty_obj":{},"empty_arr":[]}"#).unwrap();
    assert_eq!(out, br#"{"empty_arr":[],"empty_obj":{}}"#);
}

#[test]
fn object_key_sorting_by_utf16_units() {
    // U+1F600 => surrogate pair D83D DE00, should sort before U+FFFD (FFFD)
    let out = canonicalize_str(r#"{"\ufffd":2,"\ud83d\ude00":1,"a":0}"#).unwrap();
    let s = String::from_utf8(out).unwrap();
    assert_eq!(s, r#"{"a":0,"😀":1,"�":2}"#);
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        out.push(HEX[(b >> 4) as usize] as char);
        out.push(HEX[(b & 0x0f) as usize] as char);
    }
    out
}
