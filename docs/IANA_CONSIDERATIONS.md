# IANA-Style Considerations (Stub)

Status: Informational draft for future standards-track work (e.g., IETF SCITT alignment).

## 1. Media Type Candidate

Proposed media type (informational):

- Type: `application`
- Subtype: `provara+json`
- Encoding: UTF-8 JSON (canonicalization per RFC 8785 profile constraints)

Intended use:

- Event records
- Delta bundles
- Conformance payloads

## 2. URN Namespace Candidate

Potential namespace for event and profile identification:

- `urn:provara:<component>:<version>:<id>`

Examples:

- `urn:provara:profile:1.0:profile-a`
- `urn:provara:event:1.0:evt_abcdef0123456789abcdef01`

## 3. Registry Concepts

Future registries may include:

1. Core event type registry
2. Extension event type registry
3. Error code registry (`PROVARA_E###`)
4. Profile identifier registry

## 4. Security and Interop Notes

- Registries must preserve immutability guarantees for published identifiers.
- Backward-compatible additions only; no semantic redefinition of existing entries.
- Any future standards registration must preserve profile precedence:
  - `PROTOCOL_PROFILE.txt` remains authoritative for v1.0.
