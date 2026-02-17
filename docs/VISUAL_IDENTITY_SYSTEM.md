# Provara Visual Identity System v1

Status: Draft for implementation
Audience: Design, frontend, docs, brand
Principle: 50-year readability over trend aesthetics

## 1. Core Design Doctrine

1. Evidence-first: UI must expose provenance, not conceal it.
2. Durable tone: institutional calm, not startup hype.
3. Semantic layers: human narrative, machine truth, and controls are visually distinct.
4. Reproducible style: tokens and components are deterministic and reusable.

## 2. Design Tokens

## 2.1 Color Tokens

Use light mode as primary. Dark mode is optional and secondary.

```css
:root {
  --pv-bg: #f5f2ea;            /* archival paper */
  --pv-surface: #fffdf8;       /* document surface */
  --pv-ink: #1f2329;           /* primary text */
  --pv-ink-muted: #4a535c;     /* secondary text */
  --pv-rule: #d2c9bb;          /* separators and borders */
  --pv-accent: #1d4e63;        /* links, active controls */
  --pv-success: #1f6b4f;       /* valid/verified */
  --pv-warning: #8a5b21;       /* caution */
  --pv-danger: #8a2f2f;        /* invalid/tampered */
  --pv-focus: #9a7d3a;         /* keyboard focus ring */
}
```

Rules:
- Accent is functional, not decorative.
- Never use neon gradients, glow, or cyberpunk effects.
- Status colors are only for verification state, not brand expression.

## 2.2 Typography Tokens

Three-family system:
- Serif (narrative): long-form doctrine and explanatory prose.
- Sans (interface): nav, labels, controls.
- Mono (protocol): hashes, IDs, schemas, logs, code.

```css
:root {
  --pv-font-serif: "Source Serif 4", "Iowan Old Style", serif;
  --pv-font-sans: "IBM Plex Sans", "Segoe UI", sans-serif;
  --pv-font-mono: "IBM Plex Mono", "Consolas", monospace;
}
```

Type scale:
- `--pv-text-xs: 0.75rem`
- `--pv-text-sm: 0.875rem`
- `--pv-text-md: 1rem`
- `--pv-text-lg: 1.125rem`
- `--pv-text-xl: 1.375rem`
- `--pv-text-2xl: 1.875rem`

## 2.3 Spacing Tokens

```css
:root {
  --pv-space-1: 4px;
  --pv-space-2: 8px;
  --pv-space-3: 12px;
  --pv-space-4: 16px;
  --pv-space-6: 24px;
  --pv-space-8: 32px;
  --pv-space-12: 48px;
  --pv-space-16: 64px;
}
```

Layout rhythm:
- Section blocks: `48-64px` top spacing.
- Dense technical blocks: `12-16px` vertical spacing.
- Max reading width: `72ch` prose, `96ch` technical tables.

## 3. Information Hierarchy

Every page must indicate:
1. Normative vs explanatory content.
2. Requirement strength (`MUST`, `SHOULD`, `MAY`).
3. Traceability path (source event, reducer output, verification check).

Badges:
- `NORMATIVE`
- `EXPLANATORY`
- `REFERENCE`
- `EXAMPLE`

## 4. Component Primitives

1. `ProtocolBlock`
- Monospace container for hashes, event payloads, chain pointers.
- Includes copy action and integrity status icon.

2. `NormativeCallout`
- Left border + label (`MUST`, `SHOULD`, `MAY`).
- Used only where behavior is binding.

3. `VerificationPanel`
- Input + deterministic output + failure reasons.
- Always displays exact failing field or check.

4. `StateDiffTable`
- Shows belief transitions (`local -> contested -> canonical -> archived`).
- Always includes timestamp and event_id columns.

5. `AuditTimeline`
- Vertical sequence of events with signatures and prev hash links.
- Must support keyboard navigation and text-only mode.

## 5. Motion Policy

Allowed:
- short opacity/translate reveals (`120-180ms`) for section transitions.
- explicit feedback transitions for verification pass/fail.

Disallowed:
- decorative parallax, continuous ambient animations, scroll theater.
- animation that competes with reading.

## 6. Mark Semantics (Non-Logo Guidance)

Desired semantics:
- attestation, continuity, layered history, civic reliability.

Avoid:
- chain/coin cliches, shield-lock tropes, hacker neon, mascot language.

Shape guidance:
- should work as one-color stamp and small favicon.
- should imply imprint, registry, or structured layering.

## 7. Page Templates

## 7.1 Home (`/`)

Purpose: explain why Provara exists and show verifiability immediately.

Sections:
1. Mission statement (short, sober).
2. "Verify in 30 seconds" interactive validator.
3. Three invariants: signed, chained, replayable.
4. Links to spec, conformance kit, and reference implementation.

## 7.2 Spec (`/spec/v1.0`)

Purpose: citable normative source.

Sections:
1. TOC with section anchors.
2. Normative clauses with badges and RFC keywords.
3. Inline examples in `ProtocolBlock`.
4. Cross-links to schema and error taxonomy.

## 7.3 Validator (`/validator`)

Purpose: practical trust conversion.

Sections:
1. Input (event/vault fragment).
2. Check suite (schema, signature, chain, reducer determinism).
3. Machine output with exact failures.
4. Export report (markdown/json).

## 7.4 Docs (`/docs`)

Purpose: implementation onboarding.

Sections:
1. Install + minimal CLI path.
2. API and CLI references.
3. Test matrix and conformance instructions.
4. Migration and extension registry links.

## 8. Accessibility and Longevity Rules

1. Minimum contrast target: WCAG AA for all text and controls.
2. Keyboard-first support for all validation workflows.
3. All interactive outputs must have copyable plain text.
4. Avoid novelty JS dependencies for core reading experience.
5. No information encoded by color alone.

## 9. Build Acceptance Criteria

A page is accepted only if:
1. It still reads clearly with styles partially disabled.
2. Normative content is visually distinguishable from explanation.
3. At least one trust path can be verified end-to-end on-page.
4. No decorative interaction exists without comprehension benefit.

