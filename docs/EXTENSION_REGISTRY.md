# Provara Extension Registry Process (v1)

Purpose: define how new custom event types and candidate core event types are proposed without fragmenting interoperability.

## Scope

- Applies to event type naming and semantic registration.
- Does not change frozen `PROTOCOL_PROFILE.txt` for v1.0.
- Core types remain reserved: `GENESIS`, `OBSERVATION`, `ASSERTION`, `ATTESTATION`, `RETRACTION`, `KEY_REVOCATION`, `KEY_PROMOTION`, `REDUCER_EPOCH`.

## Naming Rules

1. Custom types MUST use reverse-domain form, e.g.:
   - `com.example.sensor_frame`
   - `org.provara.research_probe`
2. Custom types MUST NOT collide with reserved core names.
3. Once published, a type name’s meaning MUST NOT be silently changed.

## Registration Workflow

1. Open a GitHub issue titled:
   - `RFC: event type <reverse-domain-name>`
2. Include required fields:
   - type name
   - owner/maintainer
   - payload schema (JSON Schema snippet)
   - reducer impact (`none` by default)
   - security considerations
   - migration/compatibility notes
3. Maintainers label as:
   - `extension:proposed`
   - `extension:accepted`
   - `extension:rejected`
4. Accepted extensions are added to this file under **Accepted Extensions**.

## Core Promotion Workflow

To promote an extension into a future core profile:

1. At least two independent implementations exist.
2. Test vectors and conformance checks are available.
3. Security review completed.
4. Promotion occurs only in a new profile/version (never by mutating v1.0).

## Accepted Extensions

None yet.

## Rejected Extensions

None yet.
