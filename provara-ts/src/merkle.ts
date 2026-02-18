/**
 * merkle.ts — Binary Merkle tree over SHA-256
 *
 * Matches Python backpack_integrity.merkle_root_hex():
 *   - Leaf hash = SHA-256(leaf_bytes)
 *   - Parent = SHA-256(left_hash || right_hash)
 *   - Odd leaf count: last leaf is duplicated (standard padding)
 *   - Empty tree: SHA-256(empty bytes)
 */

import { sha256, sha256Hex } from "./crypto.js";
import { canonicalBytes } from "./jcs.js";

/**
 * Compute the Merkle root of a set of raw leaf byte arrays.
 * Returns lowercase hex SHA-256.
 */
export function merkleRootHex(leaves: Buffer[]): string {
  if (leaves.length === 0) {
    return sha256Hex(Buffer.alloc(0));
  }

  let level: Buffer[] = leaves.map(leaf => sha256(leaf));

  while (level.length > 1) {
    const next: Buffer[] = [];
    for (let i = 0; i < level.length; i += 2) {
      const left  = level[i];
      const right = i + 1 < level.length ? level[i + 1] : level[i]; // duplicate last if odd
      next.push(sha256(Buffer.concat([left, right])));
    }
    level = next;
  }

  return level[0].toString("hex");
}

/**
 * Compute the Merkle root over a list of JSON-serializable objects.
 * Each object is canonicalized to UTF-8 bytes before hashing.
 */
export function merkleRootOfObjects(objects: unknown[]): string {
  const leaves = objects.map(obj => Buffer.from(canonicalBytes(obj)));
  return merkleRootHex(leaves);
}
