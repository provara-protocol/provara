/**
 * provara-crypto.ts — Browser-native Provara Protocol implementation
 *
 * Uses WebCrypto API (window.crypto.subtle) for Ed25519 + SHA-256.
 * No external dependencies. Compatible with Chrome 113+, Firefox 105+, Safari 15.4+.
 *
 * Signing contract (matches provara-rs):
 *   signature = Ed25519(SHA-256(canonical_json(signing_payload)), private_key)
 *
 * NOTE: When WASM builds become available on this machine (unblock rust-lld in
 * Application Control), replace this module with a wasm-bindgen wrapper that
 * calls the same functions compiled from provara-rs/provara-core with --features wasm.
 * The TypeScript interface is identical.
 */

// ---------------------------------------------------------------------------
// RFC 8785 JSON Canonicalization Scheme (JCS) — pure TypeScript, no deps
// ---------------------------------------------------------------------------
//
// Ported from provara-ts/src/jcs.ts. Browser-compatible subset: no float
// tokenizer needed since we're creating events in JS (all numbers go through
// valueToNode), not verifying Python-created events.

function cmpByCodePoint(a: string, b: string): number {
  const ca = [...a].map((c) => c.codePointAt(0)!);
  const cb = [...b].map((c) => c.codePointAt(0)!);
  for (let i = 0; i < Math.min(ca.length, cb.length); i++) {
    if (ca[i] !== cb[i]) return ca[i] - cb[i];
  }
  return ca.length - cb.length;
}

function escapeString(s: string): string {
  let result = '"';
  for (const ch of s) {
    const cp = ch.codePointAt(0)!;
    if (cp === 0x22) result += '\\"';
    else if (cp === 0x5c) result += '\\\\';
    else if (cp === 0x08) result += '\\b';
    else if (cp === 0x0c) result += '\\f';
    else if (cp === 0x0a) result += '\\n';
    else if (cp === 0x0d) result += '\\r';
    else if (cp === 0x09) result += '\\t';
    else if (cp < 0x20) {
      result += '\\u' + cp.toString(16).padStart(4, '0');
    } else {
      result += ch;
    }
  }
  return result + '"';
}

// Serialize a JS value into RFC 8785 canonical form
function serializeValue(v: unknown): string {
  if (v === null) return 'null';
  if (v === true) return 'true';
  if (v === false) return 'false';
  if (typeof v === 'number') {
    if (!isFinite(v)) throw new Error(`Non-finite number: ${v}`);
    return String(v);
  }
  if (typeof v === 'string') return escapeString(v);
  if (Array.isArray(v)) {
    return '[' + v.map(serializeValue).join(',') + ']';
  }
  if (typeof v === 'object') {
    const obj = v as Record<string, unknown>;
    const keys = Object.keys(obj).sort(cmpByCodePoint);
    return '{' + keys.map((k) => escapeString(k) + ':' + serializeValue(obj[k])).join(',') + '}';
  }
  throw new Error(`Unsupported value type: ${typeof v}`);
}

export function canonicalJson(value: unknown): string {
  return serializeValue(value);
}

export function canonicalBytes(value: unknown): Uint8Array<ArrayBuffer> {
  // TextEncoder.encode() returns Uint8Array<ArrayBufferLike> in TS 5.7 — cast to concrete type
  return new TextEncoder().encode(canonicalJson(value)) as unknown as Uint8Array<ArrayBuffer>;
}

// ---------------------------------------------------------------------------
// Byte helpers
// ---------------------------------------------------------------------------

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function bytesToBase64(bytes: Uint8Array): string {
  let binary = '';
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}

function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  return new Uint8Array(Array.from(atob(b64)).map((c) => c.charCodeAt(0)));
}

// JWK uses base64url; Provara uses standard base64
function base64urlToBase64(b64url: string): string {
  const pad = (4 - (b64url.length % 4)) % 4;
  return b64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat(pad);
}

// ---------------------------------------------------------------------------
// Provara types
// ---------------------------------------------------------------------------

export interface ProvaraKeypair {
  key_id: string;
  public_key_b64: string;
  private_key_b64: string; // base64 of raw 32-byte seed
}

export interface ProvaraEvent {
  type: string;
  event_id: string;
  actor: string; // key_id of signer
  prev_event_hash?: string;
  timestamp_utc?: string;
  payload: unknown;
  signature?: string; // base64 Ed25519 signature
}

export interface ChainVerifyResult {
  valid: boolean;
  errors: string[];
}

// ---------------------------------------------------------------------------
// SHA-256 (via WebCrypto)
// ---------------------------------------------------------------------------

async function sha256(data: Uint8Array<ArrayBuffer>): Promise<Uint8Array<ArrayBuffer>> {
  const buf = await crypto.subtle.digest('SHA-256', data);
  return new Uint8Array(buf);
}

// ---------------------------------------------------------------------------
// Key derivation
// ---------------------------------------------------------------------------

async function deriveKeyId(publicKeyBytes: Uint8Array<ArrayBuffer>): Promise<string> {
  const hash = await sha256(publicKeyBytes);
  return 'bp1_' + bytesToHex(hash).slice(0, 16);
}

// ---------------------------------------------------------------------------
// Keypair generation
// ---------------------------------------------------------------------------

export async function generateKeypair(): Promise<ProvaraKeypair> {
  const keyPair = await crypto.subtle.generateKey(
    { name: 'Ed25519' },
    true, // extractable — needed to export seed for storage
    ['sign', 'verify'],
  );

  // Export public key as raw 32 bytes
  const pubRaw = new Uint8Array(
    await crypto.subtle.exportKey('raw', keyPair.publicKey),
  );

  // Export private key via JWK to get the raw 32-byte seed (the 'd' field)
  const privJwk = await crypto.subtle.exportKey('jwk', keyPair.privateKey);
  const seedBytes = base64ToBytes(base64urlToBase64(privJwk.d!));

  const key_id = await deriveKeyId(pubRaw);
  const public_key_b64 = bytesToBase64(pubRaw);
  const private_key_b64 = bytesToBase64(seedBytes);

  return { key_id, public_key_b64, private_key_b64 };
}

// ---------------------------------------------------------------------------
// Import keys for signing/verification
// ---------------------------------------------------------------------------

async function importPrivateKey(privateKeyB64: string): Promise<CryptoKey> {
  // Reconstruct public key from the seed so we can build the JWK
  // WebCrypto requires the JWK 'x' field (public key) even for import
  const seed = base64ToBytes(privateKeyB64);

  // Derive the public key: import seed as private key, then export public
  // We do this by first generating an importable JWK with a placeholder x,
  // then let the browser derive x by importing the pkcs8 form.
  //
  // Standard approach: build PKCS8 DER for Ed25519
  //   Prefix (16 bytes): 302e020100300506032b657004220420
  //   Seed   (32 bytes): the raw private key seed
  const pkcs8prefix = new Uint8Array([
    0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70,
    0x04, 0x22, 0x04, 0x20,
  ]);
  const pkcs8 = new Uint8Array(pkcs8prefix.length + seed.length);
  pkcs8.set(pkcs8prefix);
  pkcs8.set(seed, pkcs8prefix.length);

  return crypto.subtle.importKey(
    'pkcs8',
    pkcs8,
    { name: 'Ed25519' },
    false,
    ['sign'],
  );
}

async function importPublicKey(publicKeyB64: string): Promise<CryptoKey> {
  const pubBytes = base64ToBytes(publicKeyB64);
  return crypto.subtle.importKey(
    'raw',
    pubBytes,
    { name: 'Ed25519' },
    false,
    ['verify'],
  );
}

// ---------------------------------------------------------------------------
// Event ID derivation
// ---------------------------------------------------------------------------

async function deriveEventId(event: Omit<ProvaraEvent, 'event_id' | 'signature'>): Promise<string> {
  // Compute over: type, actor, prev_event_hash?, timestamp_utc?, payload
  const base: Record<string, unknown> = {
    type: event.type,
    actor: event.actor,
  };
  if (event.prev_event_hash !== undefined) base.prev_event_hash = event.prev_event_hash;
  if (event.timestamp_utc !== undefined) base.timestamp_utc = event.timestamp_utc;
  base.payload = event.payload;

  const hash = await sha256(canonicalBytes(base));
  return 'evt_' + bytesToHex(hash).slice(0, 24);
}

// ---------------------------------------------------------------------------
// Event creation and signing
// ---------------------------------------------------------------------------

export async function createEvent(
  eventType: string,
  payload: unknown,
  privateKeyB64: string,
  keyId: string,
  prevEventHash?: string,
): Promise<ProvaraEvent> {
  const timestamp_utc = new Date().toISOString();

  const base: Omit<ProvaraEvent, 'event_id' | 'signature'> = {
    type: eventType,
    actor: keyId,
    payload,
    timestamp_utc,
  };
  if (prevEventHash !== undefined) base.prev_event_hash = prevEventHash;

  const event_id = await deriveEventId(base);

  // Signing payload: everything except signature, but INCLUDING event_id
  const signingPayload: Record<string, unknown> = {
    type: eventType,
    event_id,
    actor: keyId,
  };
  if (prevEventHash !== undefined) signingPayload.prev_event_hash = prevEventHash;
  signingPayload.timestamp_utc = timestamp_utc;
  signingPayload.payload = payload;

  // Sign SHA-256(canonical(signingPayload)) with Ed25519
  const canonBytes = canonicalBytes(signingPayload);
  const hashBytes = await sha256(canonBytes);
  const privKey = await importPrivateKey(privateKeyB64);
  const sigBuf = await crypto.subtle.sign('Ed25519', privKey, hashBytes);
  const signature = bytesToBase64(new Uint8Array(sigBuf));

  return { ...base, event_id, signature };
}

// ---------------------------------------------------------------------------
// Signature verification
// ---------------------------------------------------------------------------

export async function verifyEvent(
  event: ProvaraEvent,
  publicKeyB64: string,
): Promise<boolean> {
  if (!event.signature) return false;

  const signingPayload: Record<string, unknown> = {
    type: event.type,
    event_id: event.event_id,
    actor: event.actor,
  };
  if (event.prev_event_hash !== undefined) signingPayload.prev_event_hash = event.prev_event_hash;
  if (event.timestamp_utc !== undefined) signingPayload.timestamp_utc = event.timestamp_utc;
  signingPayload.payload = event.payload;

  const canonBytes = canonicalBytes(signingPayload);
  const hashBytes = await sha256(canonBytes);

  let sigBytes: Uint8Array<ArrayBuffer>;
  try {
    sigBytes = base64ToBytes(event.signature);
  } catch {
    return false;
  }

  const pubKey = await importPublicKey(publicKeyB64);
  return crypto.subtle.verify('Ed25519', pubKey, sigBytes, hashBytes);
}

// ---------------------------------------------------------------------------
// Chain verification
// ---------------------------------------------------------------------------

export async function verifyChain(
  events: ProvaraEvent[],
  publicKeyB64: string,
): Promise<ChainVerifyResult> {
  const errors: string[] = [];

  // 1. Causal chain integrity: per-actor prev_event_hash linkage
  const actorLastEvent = new Map<string, string>();
  for (const event of events) {
    const actor = event.actor;
    const prev = event.prev_event_hash;

    if (prev === undefined || prev === null) {
      if (actorLastEvent.has(actor)) {
        errors.push(`Actor ${actor} has multiple genesis events`);
      }
    } else {
      const expected = actorLastEvent.get(actor);
      if (expected === undefined) {
        errors.push(`Actor ${actor} references non-existent previous event`);
      } else if (prev !== expected) {
        errors.push(
          `Broken chain for actor ${actor}: expected ${expected}, got ${prev}`,
        );
      }
    }
    actorLastEvent.set(actor, event.event_id);
  }

  // 2. Signature verification for each event
  for (const event of events) {
    const ok = await verifyEvent(event, publicKeyB64);
    if (!ok) {
      errors.push(`Invalid signature on event ${event.event_id}`);
    }
  }

  return { valid: errors.length === 0, errors };
}
