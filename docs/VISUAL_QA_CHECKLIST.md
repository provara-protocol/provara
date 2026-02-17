# Visual QA Checklist

Use this checklist before shipping any public-facing Provara page.

## 1. Durability

- [ ] Page remains readable with CSS partially disabled.
- [ ] Typographic strata are clear: prose (serif), UI (sans), protocol data (mono).
- [ ] Line lengths stay within readability bounds (`72ch` prose, `96ch` technical).

## 2. Normative Clarity

- [ ] Normative vs explanatory sections are visibly distinct.
- [ ] RFC keyword callouts (`MUST`, `SHOULD`, `MAY`) are consistently styled.
- [ ] Source-of-truth references are explicit and reachable.

## 3. Evidence-First UX

- [ ] At least one protocol block appears in machine-readable format.
- [ ] Verification state communicates exact pass/fail semantics.
- [ ] No decorative-only interactive elements are present.

## 4. Accessibility

- [ ] Contrast meets WCAG AA for text and controls.
- [ ] Keyboard focus states are visible.
- [ ] Color is not the sole communication channel for status.

## 5. Brand Safety

- [ ] Avoids crypto cliches (neon hacker visuals, chain/coin iconography).
- [ ] Avoids generic enterprise SaaS sameness.
- [ ] Maintains "civic technical" tone: calm, exact, inspectable.

## 6. Mobile/Desktop

- [ ] Layout is usable at <= 768px without horizontal scrolling.
- [ ] Sticky/side navigation gracefully collapses on small screens.
- [ ] Code/protocol blocks remain readable and scroll safely.
