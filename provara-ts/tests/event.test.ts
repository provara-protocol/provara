/**
 * event.test.ts — Event creation, signing, and verification
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { signEvent, verifyEventSignature, verifyEventSignatureRaw, deriveEventId } from "../src/event.js";
import { generateKeypair } from "../src/crypto.js";
import { canonicalize } from "../src/jcs.js";

// ---------------------------------------------------------------------------
// Event ID derivation
// ---------------------------------------------------------------------------

test("deriveEventId: matches test vector event_id_derivation_01", () => {
  // From test_vectors/vectors.json
  const input = {
    type: "OBSERVATION",
    actor: "bp1_actor_id",
    prev_event_hash: "evt_previous_id",
    payload: { subject: "test", predicate: "status", value: "ok" },
  };
  const result = deriveEventId(input);
  assert.equal(result, "evt_f641d47f9c7b4846a11c9db8");
});

test("deriveEventId: starts with evt_ prefix", () => {
  const id = deriveEventId({ type: "TEST", actor: "a", prev_event_hash: null });
  assert.ok(id.startsWith("evt_"));
  assert.equal(id.length, 4 + 24); // "evt_" + 24 hex chars
});

test("deriveEventId: is deterministic", () => {
  const event = { type: "X", actor: "y", prev_event_hash: null, payload: { v: 1 } };
  assert.equal(deriveEventId(event), deriveEventId(event));
});

// ---------------------------------------------------------------------------
// Sign + Verify (TypeScript-created events)
// ---------------------------------------------------------------------------

test("signEvent: adds event_id, actor_key_id, sig fields", () => {
  const kp = generateKeypair();
  const event = {
    type: "OBSERVATION",
    actor: "test_actor",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: { subject: "x", predicate: "y", value: "z" },
  };
  const signed = signEvent(event, kp.privateKeyB64, kp.keyId);

  assert.ok(signed.event_id.startsWith("evt_"));
  assert.equal(signed.actor_key_id, kp.keyId);
  assert.ok(typeof signed.sig === "string" && signed.sig.length > 0);
});

test("verifyEventSignature: round-trip verification", () => {
  const kp = generateKeypair();
  const event = {
    type: "OBSERVATION",
    actor: "alice",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: { subject: "door", predicate: "state", value: "open" },
  };
  const signed = signEvent(event, kp.privateKeyB64, kp.keyId);
  assert.ok(verifyEventSignature(signed, kp.publicKeyB64));
});

test("verifyEventSignature: rejects tampered payload", () => {
  const kp = generateKeypair();
  const event = {
    type: "OBSERVATION",
    actor: "alice",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: { value: "original" },
  };
  const signed = signEvent(event, kp.privateKeyB64, kp.keyId);
  const tampered = { ...signed, payload: { value: "hacked" } };
  assert.ok(!verifyEventSignature(tampered, kp.publicKeyB64));
});

test("verifyEventSignature: rejects wrong public key", () => {
  const kp1 = generateKeypair();
  const kp2 = generateKeypair();
  const event = {
    type: "TEST",
    actor: "a",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: {},
  };
  const signed = signEvent(event, kp1.privateKeyB64, kp1.keyId);
  assert.ok(!verifyEventSignature(signed, kp2.publicKeyB64));
});

// ---------------------------------------------------------------------------
// verifyEventSignatureRaw — for Python-created events
// ---------------------------------------------------------------------------

test("verifyEventSignatureRaw: verifies TypeScript-signed event serialized as JSON", () => {
  const kp = generateKeypair();
  const event = {
    type: "OBSERVATION",
    actor: "bot",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: { subject: "s", predicate: "p", value: "v" },
  };
  const signed = signEvent(event, kp.privateKeyB64, kp.keyId);
  // Serialize to raw JSON line (as it would appear in events.ndjson)
  const rawLine = canonicalize(signed);
  assert.ok(verifyEventSignatureRaw(rawLine, kp.publicKeyB64));
});

test("verifyEventSignatureRaw: rejects tampered raw JSON", () => {
  const kp = generateKeypair();
  const event = {
    type: "OBSERVATION",
    actor: "bot",
    prev_event_hash: null,
    timestamp_utc: "2026-01-01T00:00:00+00:00",
    payload: { value: "real" },
  };
  const signed = signEvent(event, kp.privateKeyB64, kp.keyId);
  // Tamper the raw JSON
  const rawLine = canonicalize(signed).replace('"real"', '"fake"');
  assert.ok(!verifyEventSignatureRaw(rawLine, kp.publicKeyB64));
});
