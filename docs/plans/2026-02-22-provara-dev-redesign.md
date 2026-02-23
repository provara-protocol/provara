# provara.dev Redesign — Full Kestrel Visual Parity

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild provara.dev landing page to match kestrelmarkets.com visual quality — same design system, layout patterns, and polish level, with Provara Protocol content.

**Architecture:** Static HTML/CSS/JS site. Three files: `index.html` (all 9 sections), `assets/site.css` (full design system + section styles), `assets/app.js` (animations, mobile drawer, code tabs). No build step, no framework. Deployed to Cloudflare Pages as-is.

**Tech Stack:** HTML5, CSS3 (custom properties, grid, backdrop-filter), Vanilla JS (IntersectionObserver, details/summary), Google Fonts (Space Grotesk, JetBrains Mono)

---

## Reference Material

**Design doc:** `docs/plans/2026-02-22-provara-dev-redesign.md` (this file)

**Kestrel source (the visual target):**
- HTML structure: `/home/syncshadow7/.cache/superpowers/browser/2026-02-22/session-1771780217851/003-navigate.html`
- Live site: `https://kestrelmarkets.com` (for visual comparison)

**Current provara.dev files (to be rewritten):**
- `sites/provara.dev/index.html` (52 lines — rewrite)
- `sites/provara.dev/assets/site.css` (84 lines — rewrite)
- `sites/provara.dev/assets/app.js` (new file)

**Inner pages that must remain reachable** (do NOT modify):
- `/spec/v1.0/` — Spec page
- `/docs/` — Docs hub
- `/blog/` — Blog
- `/playground/` — Playground redirect

---

## Task 1: Write the CSS Design System

**Files:**
- Rewrite: `sites/provara.dev/assets/site.css`

**Step 1: Write the complete CSS file**

The CSS must include these sections in order. Use the Kestrel CSS as the direct template — same class names where the structure matches, renamed for Provara-specific sections.

```css
/* Root tokens — match Kestrel exactly */
:root {
  --k-bg: #060a10;
  --k-bg-card: #0a0e18;
  --k-bg-card-alt: #080c14;
  --k-bg-hover: #0d1220;
  --k-bg-elevated: #0e1424;
  --k-border: #111822;
  --k-border-light: #151c28;
  --k-border-hover: #1a2330;
  --k-text: #c8d4e0;
  --k-text-bright: #e0e8f0;
  --k-text-muted: #8899aa;
  --k-text-dark: #5a7088;
  --k-text-darker: #4a5f73;
  --k-accent: #00e5a0;
  --k-accent-blue: #00b8ff;
  --k-accent-purple: #8866ff;
  --k-red: #ff4466;
  --k-orange: #ff8800;
  --k-sans: 'Space Grotesk', -apple-system, BlinkMacSystemFont, sans-serif;
  --k-mono: 'JetBrains Mono', 'SF Mono', monospace;
  --k-max-width: 1140px;
  --k-gutter: 20px;
  --k-nav-height: 56px;
}
```

Required CSS sections (match Kestrel patterns exactly):
1. Reset + base body styles
2. Skip link
3. Atmospheric background (`.bg-field` — fixed radial gradients)
4. Container layout
5. Navigation (`.nav`, sticky, backdrop-filter blur, frosted glass)
6. Mobile drawer (`.nav-drawer`, slide-in panel + backdrop)
7. Buttons (`.btn`, `.btn-primary`, `.btn-ghost`)
8. Hero section (`.hero`, two-column grid, badge with pulse animation)
9. Hero terminal visual (`.hv-*` classes — window chrome, body, status lines, scanline animation)
10. Trust bar (`.trust-bar` — horizontal strip with icons)
11. Section utilities (`.section-tag`, `.section-title`, `.section-sub`)
12. Method/phase cards (`.method-grid`, `.method-card` — 3-col with color-coded top borders)
13. Protocol feature cards (`.platform-grid`, `.platform-card` — 2x2 with icons)
14. Metrics row (`.metrics`, `.metric` — 4-col stats)
15. API/code section (`.api-section`, `.api-tabs`, `.api-code-block` — tabbed code display)
16. FAQ section (`.faq-section`, `.faq-item` using `<details>` — with +/- toggle)
17. Footer (`.footer`, multi-column grid)
18. Keyframe animations (`pulse`, `fadeUp`, `scanline`)
19. Fade-up utility classes (`.fade-up`, `.visible`, `.delay-1` through `.delay-5`)
20. Reduced motion media query
21. Responsive breakpoints (768px tablet, 1024px desktop)

**Step 2: Verify CSS file is valid**

Run: `python3 -c "open('sites/provara.dev/assets/site.css').read(); print('CSS file readable, length:', len(open('sites/provara.dev/assets/site.css').read()), 'chars')"`

Expected: File exists, ~800-1100 lines

**Step 3: Commit**

```bash
git add sites/provara.dev/assets/site.css
git commit -m "feat(sites): rewrite provara.dev CSS with Kestrel design system"
```

---

## Task 2: Write the HTML Landing Page

**Files:**
- Rewrite: `sites/provara.dev/index.html`

**Step 1: Write the complete HTML file**

The HTML must include all 9 sections from the design doc. Reference the Kestrel HTML at `/home/syncshadow7/.cache/superpowers/browser/2026-02-22/session-1771780217851/003-navigate.html` for the exact structural patterns.

**Head section must include:**
- Charset, viewport, title: "Provara Protocol — Self-Sovereign Cryptographic Event Logs"
- Meta description, OG tags, Twitter card, canonical URL (`https://provara.dev/`)
- JSON-LD structured data (Organization + WebSite)
- Google Fonts preconnect + stylesheet (Space Grotesk weights 400,500,600,700 + JetBrains Mono weights 400,500,700)
- Link to `assets/site.css`
- RSS link to `/rss.xml`
- Theme color `#060a10`

**Body sections in order:**

1. **Atmospheric background div** (`.bg-field`)

2. **Navigation** — match Kestrel structure:
   - `.nav` > `.container.nav-inner` > logo + nav-links + hamburger
   - Logo: shield SVG + "Provara" text
   - Links: `<a href="/spec/v1.0/">Spec v1.0</a>`, `<a href="/docs/">Docs</a>`, `<a href="/blog/">Blog</a>`, `<a href="https://github.com/provara-protocol/provara">GitHub</a>`
   - CTA: `<a href="/playground/" class="nav-cta nav-cta-desktop">Try Playground</a>`
   - Mobile drawer with same links

3. **Hero** — two-column grid:
   - Left: badge ("Self-sovereign cryptographic event logs" with pulsing dot), H1 ("Tamper-Evident Event Logs for a 50-Year Horizon"), subtitle, CTAs
   - Right: Terminal visual titled `provara://vault` with VERIFIED badge. Body shows:
     ```
     {"type":"event","action":"user.login",
      "actor":"alice","ts":"2026-02-22T14:30:00Z",
      "sig":"ed25519:a3f8c9...d721",
      "prev":"sha256:7b2cf1...e490",
      "hash":"sha256:9c4a21...f832"}
     ```
   - Status lines: checkmark + "Ed25519 signature valid", checkmark + "Hash chain integrity confirmed"

4. **Trust bar** — 4 items with SVG icons:
   - Ed25519 Signed (shield icon)
   - SHA-256 Hash-Chained (chain/grid icon)
   - Append-Only NDJSON (checkmark-circle icon)
   - Self-Sovereign Keys (crosshair icon)

5. **How It Works** — 3 method cards:
   - Phase 01 / Sign (green border)
   - Phase 02 / Chain (blue border)
   - Phase 03 / Verify (purple border)
   Content from design doc sections.

6. **Protocol Features** — 2x2 platform grid:
   - Vault Init (lock icon, green)
   - Event Append (plus-circle icon, blue)
   - Verification (shield-check icon, purple)
   - Deterministic Replay (refresh icon, orange)
   Each with title + description from design doc.

7. **Stats row** — 4 metrics:
   - v1.0 / Spec Version
   - 2 / Languages
   - Apache 2.0 / License
   - STABLE / Status (green color)

8. **Developer Experience** — tabbed code:
   - 3 tab buttons: Python (active), CLI, npm
   - 3 code blocks (only active visible), syntax-highlighted with span classes (`.cc` comment, `.ck` keyword, `.cs` string)
   - Code content from design doc.

9. **FAQ** — 6 `<details>` elements:
   - Q: What is Provara Protocol?
     A: Provara is an open-source protocol for tamper-evident event logs. Every event is Ed25519 signed and SHA-256 hash-chained into an append-only NDJSON file. The result is a verifiable, replayable record that works offline and stays readable for decades.
   - Q: How does the hash chain work?
     A: Each event's SHA-256 hash incorporates the previous event's hash. This creates a chain where modifying any single event breaks the hash of every event that follows. Verification is a single pass through the log — no external service required.
   - Q: What happens if someone modifies an event?
     A: The hash chain breaks at the point of modification. Every subsequent event's hash will fail verification. This is detectable by anyone with the public key and the event log. Tampering is not prevented — it is made provably detectable.
   - Q: Do I need to run a server?
     A: No. Provara vaults are local files. The protocol is designed for self-sovereign operation — you hold the keys, you hold the logs. No hosted dependency, no API, no account. Verification is a pure computation.
   - Q: What key types are supported?
     A: Ed25519 is the sole supported signing algorithm. This is a deliberate constraint — Ed25519 is fast, deterministic, and widely supported across languages and platforms. Key rotation is supported through the checkpoint mechanism.
   - Q: Is Provara Protocol open source?
     A: Yes. Apache 2.0 licensed. The specification, reference implementation (Python), and all tooling are on GitHub at github.com/provara-protocol/provara.

10. **Footer** — 4-column grid:
    - Brand: Provara logo + description
    - Protocol: Spec v1.0, Docs, Playground, Blog
    - Community: GitHub, Discord
    - Bottom: "© 2026 Provara Protocol" + "Apache 2.0 · provara.dev"

11. **Script tag**: `<script src="assets/app.js" defer></script>`

**Step 2: Validate HTML structure**

Run: `python3 -c "h=open('sites/provara.dev/index.html').read(); print('HTML length:', len(h), 'chars'); print('Has nav:', '<nav' in h or 'class=\"nav\"' in h); print('Has hero:', 'class=\"hero\"' in h); print('Has footer:', '<footer' in h); print('Has 9 sections:', h.count('section-tag'))"`

Expected: HTML exists, has nav, hero, footer, and 5+ section-tags.

**Step 3: Commit**

```bash
git add sites/provara.dev/index.html
git commit -m "feat(sites): rewrite provara.dev HTML with full section layout"
```

---

## Task 3: Write the JavaScript

**Files:**
- Create: `sites/provara.dev/assets/app.js`

**Step 1: Write the complete JS file**

Match Kestrel's app.js functionality. The JS must include:

```javascript
(function () {
  'use strict';

  // 1. Mobile drawer toggle
  //    - menuBtn click → open drawer + backdrop
  //    - closeBtn/backdrop click → close
  //    - Escape key → close
  //    - Link click inside drawer → close
  //    - document.body overflow toggle

  // 2. Smooth scroll with nav offset
  //    - All a[href^="#"] links
  //    - Calculate nav height offset
  //    - window.scrollTo with smooth behavior

  // 3. Fade-up scroll animations
  //    - IntersectionObserver on all .fade-up elements
  //    - Add .visible class when intersecting
  //    - threshold: 0.1, rootMargin: '0px 0px -40px 0px'
  //    - Unobserve after triggering

  // 4. API code tabs
  //    - Click handler on .api-tab buttons
  //    - Toggle .active on tabs and corresponding .api-code-block
  //    - data-tab attribute matches code block ID

})();
```

**Step 2: Verify JS file**

Run: `node -c sites/provara.dev/assets/app.js && echo "Syntax OK"`

Expected: "Syntax OK"

**Step 3: Commit**

```bash
git add sites/provara.dev/assets/app.js
git commit -m "feat(sites): add provara.dev JavaScript for animations and interactivity"
```

---

## Task 4: Visual Verification in Browser

**Step 1: Open the local site in the browser**

Open `file:///home/syncshadow7/provara/sites/provara.dev/index.html` in the browser.

**Step 2: Compare against Kestrel**

Check each section visually:
- [ ] Navigation: frosted glass, logo, links, CTA button
- [ ] Hero: two-column layout, terminal visual on right
- [ ] Trust bar: horizontal strip with icons
- [ ] How It Works: 3 phase cards with colored borders
- [ ] Protocol Features: 2x2 grid with icons
- [ ] Stats row: 4 metrics
- [ ] Developer Experience: tabbed code examples (tabs switch correctly)
- [ ] FAQ: expandable details with +/- indicators
- [ ] Footer: multi-column layout
- [ ] Animations: fade-up on scroll works
- [ ] Mobile: hamburger menu and drawer work at narrow viewport

**Step 3: Fix any visual issues found**

Address spacing, alignment, color, or interaction bugs.

**Step 4: Commit fixes**

```bash
git add sites/provara.dev/
git commit -m "fix(sites): polish provara.dev visual alignment and responsiveness"
```

---

## Task 5: Final Commit and Cleanup

**Step 1: Run final checks**

- Verify all inner page links still work (`/spec/v1.0/`, `/docs/`, `/blog/`, `/playground/`)
- Verify no broken references in HTML (CSS path, JS path, font URLs)
- Check that the CSS file doesn't reference fonts from a local `/fonts/` directory (use Google Fonts CDN)

**Step 2: Squash or tidy commits if needed**

Ensure commit history is clean.

**Step 3: Final commit message**

```bash
git add -A sites/provara.dev/
git commit -m "feat(sites): redesign provara.dev landing page with Kestrel visual parity

- Adopt Kestrel design system: colors, typography, layout patterns
- Add 9 sections: nav, hero, trust bar, how-it-works, features, stats, dev experience, FAQ, footer
- Add terminal visualization showing Provara vault event
- Add fade-up scroll animations, mobile drawer, tabbed code examples
- Preserve inner page links (spec, docs, blog, playground)"
```
