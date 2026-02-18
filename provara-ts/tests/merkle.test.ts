/**
 * merkle.test.ts — Binary Merkle tree over SHA-256
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { merkleRootHex, merkleRootOfObjects } from "../src/merkle.js";
import { sha256Hex } from "../src/crypto.js";

// ---------------------------------------------------------------------------
// merkleRootHex — raw byte leaves
// ---------------------------------------------------------------------------

test("merkleRootHex: empty tree returns sha256(empty bytes)", () => {
  // Matches Python: hashlib.sha256(b"").hexdigest()
  assert.equal(
    merkleRootHex([]),
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  );
});

test("merkleRootHex: single leaf returns sha256(leaf)", () => {
  // level = [sha256(leaf)], loop doesn't run, returns level[0].hex
  const leaf = Buffer.from("hello");
  assert.equal(merkleRootHex([leaf]), sha256Hex(leaf));
});

test("merkleRootHex: two leaves produce balanced root", () => {
  const a = Buffer.from("leaf-a");
  const b = Buffer.from("leaf-b");
  const r1 = merkleRootHex([a, b]);
  const r2 = merkleRootHex([a, b]);
  assert.equal(r1, r2);
  assert.match(r1, /^[0-9a-f]{64}$/);
});

test("merkleRootHex: three leaves duplicates the last (odd-count padding)", () => {
  const [a, b, c] = [Buffer.from("a"), Buffer.from("b"), Buffer.from("c")];
  const three = merkleRootHex([a, b, c]);
  const two   = merkleRootHex([a, b]);
  assert.notEqual(three, two);
  assert.match(three, /^[0-9a-f]{64}$/);
});

test("merkleRootHex: different leaf sets produce different roots", () => {
  const r1 = merkleRootHex([Buffer.from("x")]);
  const r2 = merkleRootHex([Buffer.from("y")]);
  assert.notEqual(r1, r2);
});

test("merkleRootHex: output is always 64 lowercase hex chars", () => {
  for (const leaves of [[], [Buffer.from("a")], [Buffer.from("a"), Buffer.from("b")]]) {
    assert.match(merkleRootHex(leaves), /^[0-9a-f]{64}$/);
  }
});

// ---------------------------------------------------------------------------
// merkleRootOfObjects — JSON-serializable objects
// ---------------------------------------------------------------------------

test("merkleRootOfObjects: deterministic for same object list", () => {
  const objs = [
    { path: "a.txt", sha256: "abc", size: 0 },
    { path: "b.txt", sha256: "def", size: 1 },
  ];
  assert.equal(merkleRootOfObjects(objs), merkleRootOfObjects(objs));
});

test("merkleRootOfObjects: different objects produce different roots", () => {
  assert.notEqual(merkleRootOfObjects([{ x: 1 }]), merkleRootOfObjects([{ x: 2 }]));
});

test("merkleRootOfObjects: key insertion order does not change root (canonical JSON sorts keys)", () => {
  const r1 = merkleRootOfObjects([{ z: 1, a: 2 }]);
  const r2 = merkleRootOfObjects([{ a: 2, z: 1 }]);
  assert.equal(r1, r2);
});
