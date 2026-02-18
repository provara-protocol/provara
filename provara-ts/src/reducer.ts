/**
 * reducer.ts — Provara deterministic state reducer (TypeScript port)
 *
 * Matches Python reducer_v0.SovereignReducerV0 exactly, including:
 *   - Four-namespace model: canonical, local, contested, archived
 *   - State hash computed over content excluding metadata.state_hash
 *   - Float constant 0.5 for DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD
 *
 * This port is designed to produce byte-identical state hashes to the
 * Python implementation given the same event sequence.
 */

import { canonicalize, canonicalBytes } from "./jcs.js";
import { sha256Hex } from "./crypto.js";

// ---------------------------------------------------------------------------
// Constants — must match Python reducer_v0.py exactly
// ---------------------------------------------------------------------------

const REDUCER_NAME    = "SovereignReducerV0";
const REDUCER_VERSION = "0.2.0";
const DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD = 0.50;
const DEFAULT_OBSERVATION_CONFIDENCE = 0.50;
const DEFAULT_ASSERTION_CONFIDENCE   = 0.35;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function beliefKey(subject: string, predicate: string): string {
  return `${subject}:${predicate}`;
}

function normalizeNamespace(raw: unknown): string {
  const ns = String(raw ?? "local").trim().toLowerCase();
  const valid = new Set(["canonical", "local", "contested", "archived"]);
  return valid.has(ns) ? ns : "local";
}

function safeFloat(val: unknown, dflt: number): number {
  if (val === null || val === undefined) return dflt;
  const f = Number(val);
  return isFinite(f) ? f : dflt;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Evidence {
  event_id: string;
  actor: string;
  namespace: string;
  timestamp_utc: string | null;
  value: unknown;
  confidence: number;
}

interface LocalEntry {
  value: unknown;
  confidence: number;
  provenance: string;
  actor: string;
  timestamp: string | null;
  evidence_count: number;
}

interface CanonicalEntry {
  value: unknown;
  attested_by: string;
  provenance: string;
  attestation_event_id: string;
}

// ---------------------------------------------------------------------------
// Reducer
// ---------------------------------------------------------------------------

export class SovereignReducerV0 {
  private conflictThreshold: number;
  private canonical: Record<string, CanonicalEntry> = {};
  private local:     Record<string, LocalEntry> = {};
  private contested: Record<string, unknown> = {};
  private archived:  Record<string, unknown[]> = {};
  private metadata = {
    last_event_id: null as string | null,
    event_count: 0,
    state_hash: null as string | null,
    current_epoch: null as unknown,
    reducer: {
      name:    REDUCER_NAME,
      version: REDUCER_VERSION,
      conflict_confidence_threshold: DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD,
    },
  };
  private evidence: Record<string, Evidence[]> = {};

  constructor(conflictThreshold = DEFAULT_CONFLICT_CONFIDENCE_THRESHOLD) {
    this.conflictThreshold = conflictThreshold;
    this.metadata.reducer.conflict_confidence_threshold = conflictThreshold;
    this.metadata.state_hash = this.computeStateHash();
  }

  applyEvents(events: Record<string, unknown>[]): void {
    for (const ev of events) this.applyEventInternal(ev);
    this.metadata.state_hash = this.computeStateHash();
  }

  applyEvent(event: Record<string, unknown>): void {
    this.applyEventInternal(event);
    this.metadata.state_hash = this.computeStateHash();
  }

  private applyEventInternal(event: Record<string, unknown>): void {
    if (typeof event !== "object" || event === null) return;

    const eType     = event["type"] as string | undefined;
    const eventId   = String(event["event_id"] ?? event["id"] ?? "unknown_event");
    const actor     = String(event["actor"] ?? "unknown");
    const namespace = normalizeNamespace(event["namespace"]);
    const payload   = (event["payload"] as Record<string, unknown>) ?? {};

    if (eType === "OBSERVATION") {
      this.handleObservation(eventId, actor, namespace, payload, false);
    } else if (eType === "ASSERTION") {
      this.handleObservation(eventId, actor, namespace, payload, true);
    } else if (eType === "ATTESTATION") {
      this.handleAttestation(eventId, actor, payload);
    } else if (eType === "RETRACTION") {
      this.handleRetraction(eventId, payload);
    } else if (eType === "REDUCER_EPOCH") {
      this.handleReducerEpoch(eventId, payload);
    }
    // Unknown types: count in metadata but don't crash

    this.metadata.last_event_id = eventId;
    this.metadata.event_count  += 1;
  }

  private handleObservation(
    eventId: string,
    actor: string,
    namespace: string,
    payload: Record<string, unknown>,
    isAssertion: boolean,
  ): void {
    const subject   = payload["subject"] as string | undefined;
    const predicate = payload["predicate"] as string | undefined;
    if (!subject || !predicate) return;

    const key        = beliefKey(String(subject), String(predicate));
    const value      = payload["value"];
    const defaultConf = isAssertion ? DEFAULT_ASSERTION_CONFIDENCE : DEFAULT_OBSERVATION_CONFIDENCE;
    const confidence  = safeFloat(payload["confidence"], defaultConf);
    const ts = (payload["timestamp"] ?? payload["timestamp_utc"]) ?? null;

    const ev: Evidence = {
      event_id: eventId,
      actor,
      namespace,
      timestamp_utc: ts !== null ? String(ts) : null,
      value,
      confidence,
    };
    if (!this.evidence[key]) this.evidence[key] = [];
    this.evidence[key].push(ev);

    const canonEntry = this.canonical[key];
    const localEntry = this.local[key];

    // Case 1: conflicts with canonical
    if (canonEntry && canonEntry.value !== value && confidence >= this.conflictThreshold) {
      this.markContested(key, "conflicts_with_canonical");
      return;
    }
    // Case 2: conflicts with local
    if (localEntry && localEntry.value !== value) {
      const prevConf = safeFloat(localEntry.confidence, 0.0);
      if (Math.max(prevConf, confidence) >= this.conflictThreshold) {
        this.markContested(key, "conflicts_with_local");
        return;
      }
    }
    // Case 3: agreeing — keep if existing confidence is >= new confidence
    if (localEntry && localEntry.value === value) {
      if (confidence <= safeFloat(localEntry.confidence, 0.0)) return;
    }
    // Case 4: new or stronger-confidence local entry
    this.local[key] = {
      value,
      confidence,
      provenance: eventId,
      actor,
      timestamp: ts !== null ? String(ts) : null,
      evidence_count: this.evidence[key].length,
    };
  }

  private handleAttestation(
    eventId: string,
    actor: string,
    payload: Record<string, unknown>,
  ): void {
    const subject   = payload["subject"] as string | undefined;
    const predicate = payload["predicate"] as string | undefined;
    if (!subject || !predicate) return;

    const key            = beliefKey(String(subject), String(predicate));
    const value          = payload["value"];
    const targetEventId  = (payload["target_event_id"] as string | undefined) ?? null;
    const actorKeyId     = payload["actor_key_id"] as string | undefined;

    // Archive existing canonical if present
    const existing = this.canonical[key];
    if (existing !== undefined) {
      if (!this.archived[key]) this.archived[key] = [];
      this.archived[key].push({ ...existing, superseded_by: eventId });
    }

    this.canonical[key] = {
      value,
      attested_by: actorKeyId ?? actor,
      provenance: targetEventId ?? eventId,
      attestation_event_id: eventId,
    };
    delete this.local[key];
    delete this.contested[key];
  }

  private handleRetraction(
    eventId: string,
    payload: Record<string, unknown>,
  ): void {
    const subject   = payload["subject"] as string | undefined;
    const predicate = payload["predicate"] as string | undefined;
    if (!subject || !predicate) return;

    const key = beliefKey(String(subject), String(predicate));
    const existing = this.canonical[key];
    if (existing !== undefined) {
      if (!this.archived[key]) this.archived[key] = [];
      this.archived[key].push({ ...existing, superseded_by: eventId, retracted: true });
      delete this.canonical[key];
    }
    delete this.local[key];
    delete this.contested[key];
  }

  private handleReducerEpoch(
    eventId: string,
    payload: Record<string, unknown>,
  ): void {
    this.metadata.current_epoch = {
      epoch_id:                  payload["epoch_id"] ?? null,
      reducer_hash:              payload["reducer_hash"] ?? null,
      effective_from_event_id:   payload["effective_from_event_id"] ?? eventId,
      ontology_versions:         payload["ontology_versions"] ?? null,
    };
  }

  private markContested(key: string, reason: string): void {
    const allEvidence = this.evidence[key] ?? [];
    const byValue: Record<string, unknown[]> = {};
    for (const ev of allEvidence) {
      const valKey = canonicalize(ev.value);
      if (!byValue[valKey]) byValue[valKey] = [];
      byValue[valKey].push({
        event_id:      ev.event_id,
        actor:         ev.actor,
        namespace:     ev.namespace,
        timestamp_utc: ev.timestamp_utc,
        value:         ev.value,
        confidence:    ev.confidence,
      });
    }
    // Sort by key (canonical strings already comparable) — matches Python sorted()
    const evidenceByValue: Record<string, unknown[]> = {};
    for (const k of Object.keys(byValue).sort()) {
      evidenceByValue[k] = byValue[k];
    }
    this.contested[key] = {
      status: "AWAITING_RESOLUTION",
      reason,
      canonical_value: this.canonical[key]?.value ?? null,
      evidence_by_value: evidenceByValue,
      total_evidence_count: allEvidence.length,
    };
    delete this.local[key];
  }

  // ---------------------------------------------------------------------------
  // State hash
  // ---------------------------------------------------------------------------

  private computeStateHash(): string {
    const hashable = {
      canonical:  this.canonical,
      local:      this.local,
      contested:  this.contested,
      archived:   this.archived,
      metadata_partial: {
        last_event_id:  this.metadata.last_event_id,
        event_count:    this.metadata.event_count,
        current_epoch:  this.metadata.current_epoch,
        reducer:        this.metadata.reducer,
      },
    };
    return sha256Hex(canonicalBytes(hashable));
  }

  getStateHash(): string {
    return this.metadata.state_hash ?? this.computeStateHash();
  }

  exportState(): Record<string, unknown> {
    return {
      canonical: this.canonical,
      local:     this.local,
      contested: this.contested,
      archived:  this.archived,
      metadata:  this.metadata,
    };
  }
}
