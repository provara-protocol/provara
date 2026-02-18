/**
 * crypto.ts — Ed25519 and SHA-256 for Provara Protocol v1.0
 *
 * Uses Node.js built-in node:crypto. Zero external dependencies.
 * Compatible with Node.js 18+.
 */

import {
  createHash,
  createPrivateKey,
  createPublicKey,
  generateKeyPairSync,
  sign,
  verify,
} from "node:crypto";
import type { KeyObject } from "node:crypto";

// ---------------------------------------------------------------------------
// SHA-256
// ---------------------------------------------------------------------------

export function sha256(data: Buffer | Uint8Array | string): Buffer {
  return createHash("sha256").update(data).digest();
}

export function sha256Hex(data: Buffer | Uint8Array | string): string {
  return createHash("sha256").update(data).digest("hex");
}

// ---------------------------------------------------------------------------
// Ed25519 DER wrappers (RFC 8410)
// ---------------------------------------------------------------------------

// PKCS8 DER prefix for Ed25519 private key — 32-byte seed follows
const PKCS8_PREFIX = Buffer.from("302e020100300506032b657004220420", "hex");
// SPKI DER prefix for Ed25519 public key — 32-byte pubkey follows
const SPKI_PREFIX = Buffer.from("302a300506032b6570032100", "hex");

// ---------------------------------------------------------------------------
// Key ID derivation
// ---------------------------------------------------------------------------

/** Derive Provara key ID: "bp1_" + first 16 hex chars of SHA-256(raw_pub_bytes). */
export function keyIdFromPublicBytes(pubBytes: Buffer | Uint8Array): string {
  return `bp1_${sha256Hex(pubBytes).slice(0, 16)}`;
}

// ---------------------------------------------------------------------------
// Key import
// ---------------------------------------------------------------------------

export function privateKeyFromB64(b64: string): KeyObject {
  const raw = Buffer.from(b64, "base64");
  return createPrivateKey({
    key: Buffer.concat([PKCS8_PREFIX, raw]),
    format: "der",
    type: "pkcs8",
  });
}

export function publicKeyFromB64(b64: string): KeyObject {
  const raw = Buffer.from(b64, "base64");
  return createPublicKey({
    key: Buffer.concat([SPKI_PREFIX, raw]),
    format: "der",
    type: "spki",
  });
}

// ---------------------------------------------------------------------------
// Keypair generation
// ---------------------------------------------------------------------------

export interface Keypair {
  privateKeyB64: string;
  publicKeyB64: string;
  keyId: string;
}

export function generateKeypair(): Keypair {
  const { privateKey: privDer, publicKey: pubDer } = generateKeyPairSync(
    "ed25519",
    {
      privateKeyEncoding: { type: "pkcs8", format: "der" },
      publicKeyEncoding:  { type: "spki",  format: "der" },
    }
  ) as { privateKey: Buffer; publicKey: Buffer };

  const privateRaw = privDer.subarray(PKCS8_PREFIX.length); // 32-byte seed
  const publicRaw  = pubDer.subarray(SPKI_PREFIX.length);   // 32-byte pubkey

  return {
    privateKeyB64: privateRaw.toString("base64"),
    publicKeyB64:  publicRaw.toString("base64"),
    keyId:         keyIdFromPublicBytes(publicRaw),
  };
}

// ---------------------------------------------------------------------------
// Sign / Verify
// ---------------------------------------------------------------------------

/** Sign message bytes with an Ed25519 private key (base64-encoded raw seed). */
export function signBytes(
  message: Buffer | Uint8Array,
  privateKeyB64: string
): string {
  const key = privateKeyFromB64(privateKeyB64);
  const sig = sign(null, Buffer.from(message), key);
  return sig.toString("base64");
}

/** Verify an Ed25519 signature. Returns true if valid, false otherwise. */
export function verifyBytes(
  message: Buffer | Uint8Array,
  sigB64: string,
  publicKeyB64: string
): boolean {
  try {
    const key = publicKeyFromB64(publicKeyB64);
    const sig = Buffer.from(sigB64, "base64");
    return verify(null, Buffer.from(message), key, sig);
  } catch {
    return false;
  }
}
