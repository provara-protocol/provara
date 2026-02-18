/**
 * chain.test.ts — Per-actor causal chain validation
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { verifyAllCausalChains } from "../src/chain.js";

test("verifyAllCausalChains: empty event list returns empty map", () => {
  assert.equal(verifyAllCausalChains([]).size, 0);
});

test("verifyAllCausalChains: single event with null prev is valid", () => {
  const result = verifyAllCausalChains([
    { event_id: "evt_1", actor: "alice", prev_event_hash: null },
  ]);
  assert.equal(result.get("alice"), true);
});

test("verifyAllCausalChains: two-event chain with correct prev is valid", () => {
  const result = verifyAllCausalChains([
    { event_id: "evt_1", actor: "alice", prev_event_hash: null },
    { event_id: "evt_2", actor: "alice", prev_event_hash: "evt_1" },
  ]);
  assert.equal(result.get("alice"), true);
});

test("verifyAllCausalChains: first event with non-null prev is invalid", () => {
  const result = verifyAllCausalChains([
    { event_id: "evt_1", actor: "alice", prev_event_hash: "evt_0" },
  ]);
  assert.equal(result.get("alice"), false);
});

test("verifyAllCausalChains: broken chain (wrong prev) is invalid", () => {
  const result = verifyAllCausalChains([
    { event_id: "evt_1", actor: "alice", prev_event_hash: null },
    { event_id: "evt_2", actor: "alice", prev_event_hash: "evt_WRONG" },
  ]);
  assert.equal(result.get("alice"), false);
});

test("verifyAllCausalChains: multiple actors validated independently", () => {
  const result = verifyAllCausalChains([
    { event_id: "a1", actor: "alice", prev_event_hash: null },
    { event_id: "b1", actor: "bob",   prev_event_hash: null },
    { event_id: "a2", actor: "alice", prev_event_hash: "a1" },
    { event_id: "b2", actor: "bob",   prev_event_hash: "b1" },
  ]);
  assert.equal(result.get("alice"), true);
  assert.equal(result.get("bob"),   true);
});

test("verifyAllCausalChains: one actor broken does not affect other actors", () => {
  const result = verifyAllCausalChains([
    { event_id: "a1", actor: "alice", prev_event_hash: null },
    { event_id: "b1", actor: "bob",   prev_event_hash: null },
    { event_id: "a2", actor: "alice", prev_event_hash: "WRONG" },
    { event_id: "b2", actor: "bob",   prev_event_hash: "b1" },
  ]);
  assert.equal(result.get("alice"), false);
  assert.equal(result.get("bob"),   true);
});

test("verifyAllCausalChains: long valid chain (10 events) passes", () => {
  const events = Array.from({ length: 10 }, (_, i) => ({
    event_id:        `evt_${i}`,
    actor:           "alice",
    prev_event_hash: i === 0 ? null : `evt_${i - 1}`,
  }));
  assert.equal(verifyAllCausalChains(events).get("alice"), true);
});

test("verifyAllCausalChains: break in the middle of a long chain is detected", () => {
  const events = [
    { event_id: "e0", actor: "alice", prev_event_hash: null },
    { event_id: "e1", actor: "alice", prev_event_hash: "e0" },
    { event_id: "e2", actor: "alice", prev_event_hash: "BREAK" }, // bad link
    { event_id: "e3", actor: "alice", prev_event_hash: "e2" },
  ];
  assert.equal(verifyAllCausalChains(events).get("alice"), false);
});
