/**
 * event.ts — Provara event creation and signature verification
 *
 * Signing protocol (matches Python backpack_signing.sign_event):
 *   1. Build event dict (type, actor, prev_event_hash, timestamp_utc, payload).
 *   2. Derive event_id = "evt_" + sha256(canonical(event))[:24].
 *   3. Add actor_key_id and event_id to the dict.
 *   4. Sign canonical_bytes(dict_without_sig) with Ed25519.
 *   5. Attach base64-encoded sig.
 */

import { canonicalize, canonicalBytes, parseJSON, serializeNode } from "./jcs.js";
import type { JNode } from "./jcs.js";
import { sha256Hex, signBytes, verifyBytes } from "./crypto.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface Event {
  type: string;
  actor: string;
  prev_event_hash: string | null;
  timestamp_utc: string;
  payload: Record<string, unknown>;
  [key: string]: unknown;
}

export interface SignedEvent extends Event {
  event_id: string;
  actor_key_id: string;
  sig: string;
}

// ---------------------------------------------------------------------------
// Event ID derivation
// ---------------------------------------------------------------------------

/**
 * Derive a content-addressed event ID.
 * Input: event dict WITHOUT event_id, actor_key_id, or sig.
 * Output: "evt_" + first 24 hex chars of SHA-256(canonical_bytes(event)).
 */
export function deriveEventId(event: Record<string, unknown>): string {
  return `evt_${sha256Hex(canonicalBytes(event)).slice(0, 24)}`;
}

// ---------------------------------------------------------------------------
// Signing
// ---------------------------------------------------------------------------

/**
 * Sign an event. Mirrors Python's sign_event():
 *   - Adds actor_key_id and event_id.
 *   - Signs canonical bytes of the event (without sig).
 */
export function signEvent(
  event: Event,
  privateKeyB64: string,
  keyId: string
): SignedEvent {
  // event_id derived from the base event (no actor_key_id, no event_id, no sig)
  const eventId = deriveEventId(event as Record<string, unknown>);

  // Build the dict to sign: base event + actor_key_id + event_id (no sig yet)
  const toSign: Record<string, unknown> = {
    ...event,
    actor_key_id: keyId,
    event_id: eventId,
  };

  const sig = signBytes(canonicalBytes(toSign), privateKeyB64);
  return { ...toSign, sig } as SignedEvent;
}

// ---------------------------------------------------------------------------
// Verification — TypeScript-created events
// ---------------------------------------------------------------------------

/**
 * Verify the Ed25519 signature of a SignedEvent created by TypeScript.
 * Reconstructs signed bytes using plain JS canonicalization (integer-safe).
 */
export function verifyEventSignature(
  event: SignedEvent,
  publicKeyB64: string
): boolean {
  const { sig, ...withoutSig } = event;
  if (!sig) return false;
  return verifyBytes(canonicalBytes(withoutSig), sig, publicKeyB64);
}

// ---------------------------------------------------------------------------
// Verification — Python-created events (raw NDJSON line)
// ---------------------------------------------------------------------------

/**
 * Verify the signature on a raw NDJSON event line from a Python-created vault.
 *
 * Uses the custom tokenizer so that floats like 1.0 in the Python-produced
 * JSON are preserved as "1.0" (not "1") when the canonical bytes are
 * reconstructed — essential for signature verification to succeed.
 */
export function verifyEventSignatureRaw(
  rawLine: string,
  publicKeyB64: string
): boolean {
  const node = parseJSON(rawLine.trim());
  if (node.tag !== "object") return false;

  const sigEntry = node.entries.find(([k]) => k === "sig");
  if (!sigEntry || sigEntry[1].tag !== "string") return false;
  const sigB64 = sigEntry[1].value;

  // Reconstruct the event without the sig field, preserving float tags
  const withoutSig: JNode = {
    tag: "object",
    entries: node.entries.filter(([k]) => k !== "sig"),
  };
  const messageBytes = new TextEncoder().encode(serializeNode(withoutSig));
  return verifyBytes(messageBytes, sigB64, publicKeyB64);
}

// ---------------------------------------------------------------------------
// Helper: extract a string field from a raw NDJSON event
// ---------------------------------------------------------------------------

export function getEventField(rawLine: string, field: string): string | null {
  const node = parseJSON(rawLine.trim());
  if (node.tag !== "object") return null;
  const entry = node.entries.find(([k]) => k === field);
  if (!entry || entry[1].tag !== "string") return null;
  return entry[1].value;
}

// ---------------------------------------------------------------------------
// Causal chain helpers
// ---------------------------------------------------------------------------

/**
 * Parse a raw NDJSON line and return { event_id, actor, prev_event_hash }.
 * Returns null if the line is not a valid event object.
 */
export function parseChainFields(rawLine: string): {
  event_id: string;
  actor: string;
  prev_event_hash: string | null;
} | null {
  const node = parseJSON(rawLine.trim());
  if (node.tag !== "object") return null;

  const get = (key: string): string | null => {
    const e = node.entries.find(([k]) => k === key);
    if (!e) return null;
    if (e[1].tag === "string") return e[1].value;
    if (e[1].tag === "null") return null;
    return null;
  };

  const event_id = get("event_id");
  const actor    = get("actor");
  if (!event_id || !actor) return null;
  return { event_id, actor, prev_event_hash: get("prev_event_hash") };
}

// ---------------------------------------------------------------------------
// Timestamp helper
// ---------------------------------------------------------------------------

export function utcNow(): string {
  return new Date().toISOString().replace("Z", "+00:00");
}

// Re-export canonical for convenience in vault operations
export { canonicalize, canonicalBytes };
