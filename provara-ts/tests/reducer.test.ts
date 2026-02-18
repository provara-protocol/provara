/**
 * reducer.test.ts — SovereignReducerV0 deterministic state machine
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { SovereignReducerV0 } from "../src/reducer.js";

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

test("SovereignReducerV0: initial event_count is 0", () => {
  const r = new SovereignReducerV0();
  const s = r.exportState() as { metadata: { event_count: number } };
  assert.equal(s.metadata.event_count, 0);
});

test("SovereignReducerV0: exportState contains canonical/local/contested/archived/metadata", () => {
  const s = new SovereignReducerV0().exportState();
  assert.ok("canonical" in s);
  assert.ok("local"     in s);
  assert.ok("contested" in s);
  assert.ok("archived"  in s);
  assert.ok("metadata"  in s);
});

// ---------------------------------------------------------------------------
// OBSERVATION
// ---------------------------------------------------------------------------

test("SovereignReducerV0: OBSERVATION creates a local entry", () => {
  const r = new SovereignReducerV0();
  r.applyEvent({
    type:     "OBSERVATION",
    event_id: "evt_1",
    actor:    "bot",
    payload:  { subject: "door", predicate: "state", value: "open" },
  });
  const s = r.exportState() as { local: Record<string, unknown> };
  assert.ok("door:state" in s.local);
});

test("SovereignReducerV0: event_count increments per applyEvent call", () => {
  const r = new SovereignReducerV0();
  r.applyEvent({ type: "OBSERVATION", event_id: "e1", actor: "a", payload: { subject: "x", predicate: "y", value: 1 } });
  r.applyEvent({ type: "OBSERVATION", event_id: "e2", actor: "a", payload: { subject: "x", predicate: "z", value: 2 } });
  const s = r.exportState() as { metadata: { event_count: number } };
  assert.equal(s.metadata.event_count, 2);
});

// ---------------------------------------------------------------------------
// ATTESTATION
// ---------------------------------------------------------------------------

test("SovereignReducerV0: ATTESTATION promotes to canonical and removes from local", () => {
  const r = new SovereignReducerV0();
  r.applyEvent({ type: "OBSERVATION", event_id: "e1", actor: "bot",
    payload: { subject: "x", predicate: "y", value: 1 } });
  r.applyEvent({ type: "ATTESTATION", event_id: "e2", actor: "admin",
    payload: { subject: "x", predicate: "y", value: 1, actor_key_id: "ak" } });
  const s = r.exportState() as {
    canonical: Record<string, unknown>;
    local:     Record<string, unknown>;
  };
  assert.ok("x:y" in s.canonical);
  assert.ok(!("x:y" in s.local));
});

// ---------------------------------------------------------------------------
// RETRACTION
// ---------------------------------------------------------------------------

test("SovereignReducerV0: RETRACTION removes canonical and moves it to archived", () => {
  const r = new SovereignReducerV0();
  r.applyEvent({ type: "ATTESTATION", event_id: "e1", actor: "admin",
    payload: { subject: "x", predicate: "y", value: 1, actor_key_id: "ak" } });
  r.applyEvent({ type: "RETRACTION", event_id: "e2", actor: "admin",
    payload: { subject: "x", predicate: "y" } });
  const s = r.exportState() as {
    canonical: Record<string, unknown>;
    archived:  Record<string, unknown[]>;
  };
  assert.ok(!("x:y" in s.canonical));
  assert.ok("x:y" in s.archived);
  assert.equal((s.archived["x:y"] as unknown[]).length, 1);
});

// ---------------------------------------------------------------------------
// Contested
// ---------------------------------------------------------------------------

test("SovereignReducerV0: conflicting high-confidence observations become contested", () => {
  const r = new SovereignReducerV0();
  r.applyEvent({ type: "OBSERVATION", event_id: "e1", actor: "a",
    payload: { subject: "x", predicate: "y", value: "yes", confidence: 0.9 } });
  r.applyEvent({ type: "OBSERVATION", event_id: "e2", actor: "b",
    payload: { subject: "x", predicate: "y", value: "no",  confidence: 0.9 } });
  const s = r.exportState() as { contested: Record<string, unknown> };
  assert.ok("x:y" in s.contested);
});

// ---------------------------------------------------------------------------
// Edge cases
// ---------------------------------------------------------------------------

test("SovereignReducerV0: unknown event type does not throw", () => {
  const r = new SovereignReducerV0();
  assert.doesNotThrow(() => {
    r.applyEvent({ type: "COMPLETELY_UNKNOWN_TYPE", event_id: "e1", actor: "bot", payload: {} });
  });
});

test("SovereignReducerV0: state hash changes after applying an event", () => {
  const r = new SovereignReducerV0();
  const h0 = r.getStateHash();
  r.applyEvent({ type: "OBSERVATION", event_id: "e1", actor: "bot",
    payload: { subject: "x", predicate: "y", value: 1 } });
  assert.notEqual(r.getStateHash(), h0);
});

// ---------------------------------------------------------------------------
// Test vector: reducer_determinism_01
// ---------------------------------------------------------------------------

test("SovereignReducerV0: reducer_determinism_01 state hash matches vector", () => {
  const r = new SovereignReducerV0();
  r.applyEvents([
    {
      type:     "OBSERVATION",
      event_id: "evt_1",
      actor:    "bot",
      payload:  { subject: "door", predicate: "state", value: "open" },
    },
    {
      type:     "ATTESTATION",
      event_id: "evt_2",
      actor:    "admin",
      payload:  { subject: "door", predicate: "state", value: "open", actor_key_id: "admin_key" },
    },
  ]);
  assert.equal(
    r.getStateHash(),
    "3e62dfa0a4472310c00adcb5c054cfa8a580986555c50c8fa0b3e392374fd09a"
  );
});
