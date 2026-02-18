/**
 * jcs.test.ts — RFC 8785 Canonical JSON conformance tests
 *
 * Tests all 12 vectors from test_vectors/canonical_conformance.json.
 * The number_formatting_minus_zero test uses canonicalizeRaw() to read
 * the raw JSON text so that -0.0 is preserved as negative zero.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { canonicalize, canonicalizeRaw } from "../src/jcs.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
// dist/tests → dist → provara-ts → provara (repo root)
const REPO_ROOT = resolve(__dirname, "..", "..", "..");
const CONFORMANCE_FILE = resolve(REPO_ROOT, "test_vectors", "canonical_conformance.json");

function hexToBytes(hex: string): Buffer {
  return Buffer.from(hex, "hex");
}

function assertHex(result: string, expectedHex: string, label: string): void {
  const resultHex = Buffer.from(result, "utf-8").toString("hex");
  if (resultHex !== expectedHex) {
    throw new Error(
      `[${label}]\n` +
      `  Expected: ${hexToBytes(expectedHex).toString("utf-8")}\n` +
      `  Got:      ${result}\n` +
      `  ExpHex:   ${expectedHex}\n` +
      `  GotHex:   ${resultHex}`
    );
  }
}

// Load conformance vectors via JSON.parse (safe for all tests except minus_zero)
const conformance = JSON.parse(readFileSync(CONFORMANCE_FILE, "utf-8")) as {
  vectors: Array<{ id: string; description: string; input: unknown; expected_hex: string }>;
};

// ---------------------------------------------------------------------------
// Standard conformance tests (using JSON.parse — no float precision issues)
// ---------------------------------------------------------------------------

const SKIP_FOR_RAW = new Set(["number_formatting_minus_zero"]);

for (const vec of conformance.vectors) {
  if (SKIP_FOR_RAW.has(vec.id)) continue;

  test(`conformance: ${vec.id} — ${vec.description}`, () => {
    const result = canonicalize(vec.input);
    assertHex(result, vec.expected_hex, vec.id);
  });
}

// ---------------------------------------------------------------------------
// number_formatting_minus_zero — must use raw tokenizer
// ---------------------------------------------------------------------------
//
// JSON.parse converts both -0.0 and 0.0 to JS +0.
// The custom tokenizer uses parseFloat() which correctly returns -0 for "-0.0".
// We hardcode the raw JSON string that matches what the conformance file contains.

test("conformance: number_formatting_minus_zero — Minus zero preserved by current Python canonicalizer", () => {
  // This is the exact input as it appears in the conformance JSON file.
  // We must NOT use JSON.parse because that collapses -0.0 → +0.
  const rawInput = '{"minus_zero": -0.0, "zero": 0.0}';
  const result = canonicalizeRaw(rawInput);

  // Expected: {"minus_zero":-0.0,"zero":0.0}
  const expectedHex = "7b226d696e75735f7a65726f223a2d302e302c227a65726f223a302e307d";
  assertHex(result, expectedHex, "number_formatting_minus_zero");
});

// ---------------------------------------------------------------------------
// Unit tests for specific canonicalization behaviors
// ---------------------------------------------------------------------------

test("unit: empty string canonicalizes correctly", () => {
  assert.equal(canonicalize(""), '""');
});

test("unit: null value", () => {
  assert.equal(canonicalize(null), "null");
});

test("unit: boolean values", () => {
  assert.equal(canonicalize(true),  "true");
  assert.equal(canonicalize(false), "false");
});

test("unit: integer 0 (not float)", () => {
  // JS integer 0 → canonical "0" (no decimal point)
  assert.equal(canonicalize(0), "0");
});

test("unit: float 0.5 → '0.5'", () => {
  assert.equal(canonicalize(0.5), "0.5");
});

test("unit: integer-valued float 1.0 via raw tokenizer → '1.0'", () => {
  // When read from raw JSON, 1.0 gets float tag and serializes as "1.0"
  const result = canonicalizeRaw("1.0");
  assert.equal(result, "1.0");
});

test("unit: negative zero via raw tokenizer → '-0.0'", () => {
  assert.equal(canonicalizeRaw("-0.0"), "-0.0");
});

test("unit: positive zero as float via raw tokenizer → '0.0'", () => {
  assert.equal(canonicalizeRaw("0.0"), "0.0");
});

test("unit: control character escaping", () => {
  // \u0001 should be escaped as \\u0001
  const result = canonicalize("\u0001");
  assert.equal(result, '"\\u0001"');
});

test("unit: key sort is by Unicode code point not locale", () => {
  // £ (U+00A3=163) sorts after z (U+007A=122), € (U+20AC=8364) after £
  const result = canonicalize({ "\u20ac": 3, "\u00a3": 1, z: 4, a: 2 });
  assert.equal(result, '{"a":2,"z":4,"\u00a3":1,"\u20ac":3}');
});
