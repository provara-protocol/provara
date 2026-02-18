/**
 * vault.ts — Provara vault read operations
 *
 * Provides tools for reading and verifying existing Provara vaults.
 * Uses the raw-tokenizer path for signature verification so that
 * Python-created float values (e.g., 1.0) are preserved correctly.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { parseJSON } from "./jcs.js";
import { verifyEventSignatureRaw, parseChainFields } from "./event.js";
import { verifyAllCausalChains } from "./chain.js";
import type { ChainEvent } from "./chain.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface KeyEntry {
  key_id: string;
  public_key_b64: string;
  status?: string;
  [key: string]: unknown;
}

export interface KeysRegistry {
  [keyId: string]: KeyEntry;
}

// ---------------------------------------------------------------------------
// Loaders
// ---------------------------------------------------------------------------

export function loadKeysRegistry(keysPath: string): KeysRegistry {
  const data = JSON.parse(readFileSync(keysPath, "utf-8")) as {
    keys?: KeyEntry[];
  };
  const registry: KeysRegistry = {};
  for (const entry of data.keys ?? []) {
    if (entry.key_id) registry[entry.key_id] = entry;
  }
  return registry;
}

/**
 * Load raw NDJSON event lines from a vault events file.
 * Returns the non-empty lines (preserving raw text for tokenizer-based verify).
 */
export function loadRawEvents(eventsPath: string): string[] {
  return readFileSync(eventsPath, "utf-8")
    .split("\n")
    .filter(line => line.trim().length > 0);
}

// ---------------------------------------------------------------------------
// Vault verification
// ---------------------------------------------------------------------------

export interface VaultVerifyResult {
  eventsCount: number;
  valid: number;
  invalid: number;
  chainsOk: boolean;
  errors: string[];
}

/**
 * Verify all event signatures and causal chains in a vault.
 * Uses the tokenizer path so Python float values are preserved for sig check.
 */
export function verifyVault(vaultPath: string): VaultVerifyResult {
  const keysPath   = join(vaultPath, "identity", "keys.json");
  const eventsPath = join(vaultPath, "events",   "events.ndjson");

  const registry  = loadKeysRegistry(keysPath);
  const rawLines  = loadRawEvents(eventsPath);

  let valid   = 0;
  let invalid = 0;
  const errors: string[] = [];
  const chainEvents: ChainEvent[] = [];

  for (const line of rawLines) {
    // Extract actor_key_id for public key lookup
    const node = parseJSON(line);
    if (node.tag !== "object") {
      invalid++;
      errors.push("Non-object event line");
      continue;
    }

    const findStr = (key: string): string | null => {
      const e = node.entries.find(([k]) => k === key);
      if (!e || e[1].tag !== "string") return null;
      return e[1].value;
    };

    const keyId   = findStr("actor_key_id");
    const eventId = findStr("event_id");
    const actor   = findStr("actor");

    if (!keyId || !actor) {
      invalid++;
      errors.push(`Event missing actor_key_id or actor: ${eventId ?? "?"}`);
      continue;
    }

    const keyEntry = registry[keyId];
    if (!keyEntry) {
      invalid++;
      errors.push(`Unknown key_id: ${keyId}`);
      continue;
    }
    if (keyEntry.status === "revoked") {
      invalid++;
      errors.push(`Key revoked: ${keyId}`);
      continue;
    }

    if (verifyEventSignatureRaw(line, keyEntry.public_key_b64)) {
      valid++;
    } else {
      invalid++;
      errors.push(`Invalid signature on event ${eventId ?? "?"}`);
    }

    // Collect chain fields for causal chain check
    const fields = parseChainFields(line);
    if (fields) chainEvents.push(fields);
  }

  // Verify causal chains for all actors
  const chainResults = verifyAllCausalChains(chainEvents);
  const chainsOk = [...chainResults.values()].every(v => v);
  for (const [actor, ok] of chainResults) {
    if (!ok) errors.push(`Broken causal chain for actor: ${actor}`);
  }

  return { eventsCount: rawLines.length, valid, invalid, chainsOk, errors };
}
