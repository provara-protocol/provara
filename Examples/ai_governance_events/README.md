# AI Governance Event Examples

Example NDJSON events demonstrating how AI governance data maps to Provara's event type system.

These examples use the standard Provara event schema — no protocol modifications required. All events follow the canonical field ordering and existing type system (`OBSERVATION`, `ATTESTATION`).

## Files

| File | Event Type | Scenario |
|------|-----------|----------|
| `model_eval_event.json` | `OBSERVATION` | Model benchmark evaluation (MMLU, HumanEval) |
| `prompt_execution_event.json` | `OBSERVATION` | Inference request logging with token counts and latency |
| `policy_decision_event.json` | `ATTESTATION` | Governance policy PERMIT/DENY decisions with rationale |
| `ai_cost_record_event.json` | `OBSERVATION` | AI routing decisions with cost, model selection, and fallback |
| `redteam_test_event.json` | `OBSERVATION` | Adversarial testing results with severity and attack vectors |

## Schema Notes

- All events use standard Provara fields: `actor`, `actor_key_id`, `event_id`, `namespace`, `payload`, `prev_event_hash`, `timestamp_utc`, `ts_logical`, `type`
- Fields are sorted lexicographically (canonical JSON convention)
- Each file contains two events demonstrating causal chaining via `prev_event_hash`
- `OBSERVATION` events go to `local` namespace; `ATTESTATION` events go to `canonical`
- Event IDs use the `evt_` prefix with 24-character hex content addresses
- Key IDs use the `bp1_` prefix per Provara v1.0 spec

## Usage

These are **reference examples**, not executable test fixtures. They demonstrate how governance-layer systems should structure events for ingestion into a Provara vault. Real events would be signed with Ed25519 keys and carry valid content-addressed `event_id` values.

For the protocol specification, see [`PROTOCOL_PROFILE.txt`](../../PROTOCOL_PROFILE.txt).
