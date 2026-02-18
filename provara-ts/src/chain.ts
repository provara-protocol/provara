/**
 * chain.ts — Per-actor causal chain validation
 *
 * Each actor maintains an independent linked list of events.
 * The first event for an actor has prev_event_hash === null.
 * Subsequent events must reference the event_id of the previous event.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChainEvent {
  event_id: string;
  actor: string;
  prev_event_hash: string | null;
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

/**
 * Verify the causal chain for every actor in the event log.
 *
 * Returns a Map<actor, boolean> where true means the chain is unbroken.
 * Events are assumed to be in append order (NDJSON line order).
 */
export function verifyAllCausalChains(
  events: ChainEvent[]
): Map<string, boolean> {
  // Group by actor (preserving order within each actor)
  const byActor = new Map<string, ChainEvent[]>();
  for (const event of events) {
    if (!byActor.has(event.actor)) byActor.set(event.actor, []);
    byActor.get(event.actor)!.push(event);
  }

  const results = new Map<string, boolean>();

  for (const [actor, actorEvents] of byActor) {
    let valid = true;
    for (let i = 0; i < actorEvents.length; i++) {
      const ev = actorEvents[i];
      if (i === 0) {
        if (ev.prev_event_hash !== null) { valid = false; break; }
      } else {
        if (ev.prev_event_hash !== actorEvents[i - 1].event_id) { valid = false; break; }
      }
    }
    results.set(actor, valid);
  }

  return results;
}
