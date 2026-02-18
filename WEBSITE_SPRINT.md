# Provara Website Sprint — AI Agent Bootstrap

**Copy/paste this at the start of every website work session.**

---

## Mission

Build three coordinated websites that establish Provara as the **default memory layer for AI systems**.

**Timeline:** 7 days to launch-ready
**Goal:** Every site live on Cloudflare Pages before Show HN

---

## Three-Domain Architecture

| Domain | Purpose | Audience | Content |
|--------|---------|----------|---------|
| **provara.dev** | Primary site | Developers, adopters | Docs, quickstart, API reference, GitHub links |
| **provara.app** | Product/Consumer | Individuals, AI agents | Hosted vaults, pricing, "Preserve your memories" |
| **huntinformationsystems.com** | Corporate/Legal | Enterprises, regulators | Company info, compliance, EU AI Act, contact |

**Brand rule:** 
- provara.dev/app → "Provara" brand (public-facing)
- huntinformationsystems.com → "Hunt Information Systems LLC" (legal entity)
- Legal entity only appears in footer copyright on Provara sites

---

## provara.dev (Priority #1)

### Required Pages

1. **Homepage** (`/`)
   - Hero: "Sovereign Memory for AI Agents"
   - 30-second value prop
   - Code snippet: `pip install provara-protocol`
   - Links to GitHub, docs, PyPI
   - Social proof: "225 tests passing · Apache 2.0 · 50-year readability"

2. **Quickstart** (`/docs/quickstart`)
   - 5-minute vault creation
   - Windows/Mac/Linux tabs
   - Verification step
   - "What you just created" explainer

3. **Documentation** (`/docs/`)
   - Installation
   - Core concepts (vaults, events, reducers)
   - CLI reference
   - API reference (auto-generated from docstrings)
   - MCP server integration guide

4. **Examples** (`/examples/`)
   - Basic vault operations
   - AI agent memory logging
   - Multi-device sync
   - Key rotation

5. **About** (`/about`)
   - Why Provara exists
   - Design philosophy ("Truth is recomputed")
   - Team (anonymous, "Provara Maintainers")

### Technical Requirements

- **Static site** (no backend)
- **Cloudflare Pages** deployment
- **Mobile responsive**
- **Dark mode** (auto-detect)
- **No JavaScript** for core content (progressive enhancement OK)
- **Lighthouse score >95**

### Content Sources

- `README.md` → Homepage hero
- `BOOTSTRAP.md` → Quickstart
- `docs/BACKPACK_PROTOCOL_v1.0.html` → Spec reference
- `docs/` → Documentation pages
- Auto-generate API docs from `src/provara/` docstrings

---

## provara.app (Priority #2)

### Required Pages

1. **Homepage** (`/`)
   - "Your Memories, Forever"
   - Emotional narrative (family photos, cognitive continuity)
   - "No cloud dependency" positioning
   - Hosted vault pricing ($5-10/month)

2. **How It Works** (`/how-it-works/`)
   - Non-technical explainer
   - Visual: vault as digital safe deposit box
   - "Works offline" emphasis

3. **Use Cases** (`/use-cases/`)
   - Family memory preservation
   - Digital inheritance
   - AI agent continuity
   - Whistleblower evidence logs

4. **Pricing** (`/pricing/`)
   - Free: Self-hosted (open source)
   - $5/month: Hosted vault (1GB)
   - $20/month: Family vault (10GB, multi-sig)
   - Enterprise: Custom

5. **Sign Up** (`/signup/`)
   - Email capture for beta (if not ready for full launch)
   - Or direct to hosted vault creation

### Tone

- Warm, human, accessible
- No cryptography jargon
- Focus on outcomes, not technology

---

## huntinformationsystems.com (Priority #3)

### Required Pages

1. **Homepage** (`/`)
   - "Hunt Information Systems LLC"
   - "Builders of Provara Protocol"
   - Corporate positioning
   - Contact information

2. **Provara** (`/provara/`)
   - Link to provara.dev (primary product)
   - Brief overview
   - Investment/ownership disclosure

3. **Compliance** (`/compliance/`)
   - EU AI Act Article 12 positioning
   - Whitepapers
   - Regulatory contact

4. **About** (`/about/`)
   - Company mission
   - Anonymous founder note ("Built for 50-year longevity")
   - OPSEC-compliant story

5. **Contact** (`/contact/`)
   - Business inquiries
   - Regulatory contact
   - Press inquiries

### Tone

- Professional, corporate
- Legitimate business presence
- Separate from Provara brand (but owns it)

---

## Design System

### Colors

```css
:root {
  --primary: #0066cc;      /* Trust blue */
  --accent: #00cc99;       /* Growth green */
  --dark: #0d1117;         /* GitHub dark */
  --light: #ffffff;
  --muted: #666666;
}
```

### Typography

```css
--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
--font-mono: "SF Mono", "Cascadia Code", monospace;
```

### Components

- **Header:** Logo (left), Nav (center), GitHub/PyPI badges (right)
- **Footer:** Copyright, links to all three sites, Apache 2.0 license
- **Code blocks:** GitHub-style syntax highlighting
- **Buttons:** Primary (filled), Secondary (outline)

### Logo

- Text-based: "Provara" in bold sans-serif
- Optional: Simple geometric mark (cube, vault door, chain link)
- No stock photos

---

## Agent Coordination

### Suggested Task Split

| Agent | Domain | Responsibilities |
|-------|--------|------------------|
| **Claude Opus** | provara.dev | Homepage, quickstart, docs structure |
| **Gemini CLI** | provara.app | Consumer copy, pricing, use cases |
| **Codex** | huntinformationsystems.com | Corporate site, compliance pages |
| **Qwen** | All three | Design system, shared components, deployment |

### Coordination Protocol

1. **Claim pages** in comments before editing
2. **Shared components** go in `/sites/_shared/`
3. **Daily sync** — commit by end of session
4. **Don't block** — if waiting on content, build around it

### File Structure

```
sites/
├── dev/           # provara.dev
│   ├── index.html
│   ├── docs/
│   ├── examples/
│   └── about/
├── app/           # provara.app
│   ├── index.html
│   ├── how-it-works/
│   ├── use-cases/
│   ├── pricing/
│   └── signup/
├── his/           # huntinformationsystems.com
│   ├── index.html
│   ├── provara/
│   ├── compliance/
│   ├── about/
│   └── contact/
└── _shared/       # Shared CSS, JS, components
    ├── css/
    ├── js/
    └── components/
```

---

## Deployment

### Cloudflare Pages Setup

1. Go to https://pages.cloudflare.com/
2. Connect GitHub repo `provara-protocol/provara`
3. Create 3 projects:
   - `provara-dev` → `sites/dev/` → Custom domain: **provara.dev**
   - `provara-app` → `sites/app/` → Custom domain: **provara.app**
   - `hunt-his` → `sites/his/` → Custom domain: **huntinformationsystems.com**
4. DNS configuration:
   - provara.dev → CNAME to `provara-dev.pages.dev`
   - provara.app → CNAME to `provara-app.pages.dev`
   - huntinformationsystems.com → CNAME to `hunt-his.pages.dev`

### Build Settings

- **Build command:** None (static site)
- **Output directory:** Site-specific folder
- **Environment variables:** None needed

### SSL/HTTPS

- Automatic via Cloudflare (included free)
- Force HTTPS redirect enabled

---

## Content Guidelines

### OPSEC (Non-Negotiable)

- ❌ No real names
- ❌ No personal emails (use `contact@huntinformationsystems.com` or `hello@provara.dev`)
- ❌ No locations, timezones, physical addresses
- ✅ Use "Provara", "the Provara team", "the maintainers"
- ✅ Copyright: "© 2026 Hunt Information Systems LLC"

### Voice

| Site | Voice |
|------|-------|
| provara.dev | Technical, direct, developer-friendly |
| provara.ai | Academic, precise, citation-heavy |
| provara.com | Warm, human, outcome-focused |

### Avoid

- "Revolutionary", "disruptive", "game-changing"
- Hype without substance
- Competitor name-dropping

### Emphasize

- "50-year readability"
- "Tamper-evident"
- "Offline-first"
- "Apache 2.0"
- "225 tests passing"

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Lighthouse score** | >95 | Chrome DevTools |
| **Page load** | <2s | WebPageTest |
| **Mobile responsive** | 100% | Manual testing |
| **Accessibility** | AA compliant | WAVE tool |
| **SEO** | All pages indexed | Google Search Console |

---

## Immediate Next Actions

**All agents, pick one:**

1. **[DEV]** Create provara.dev homepage with hero, code snippet, badges
2. **[DEV]** Build quickstart page from BOOTSTRAP.md content
3. **[APP]** Write consumer homepage copy ("Your Memories, Forever")
4. **[APP]** Create pricing page with 3-tier structure
5. **[HIS]** Draft corporate homepage (Hunt Information Systems LLC)
6. **[HIS]** Write compliance/EU AI Act page outline
7. **[ALL]** Build shared design system (`sites/_shared/css/`)

**Commit by end of session. Update this file with progress.**

---

## Session Template

```markdown
### [Agent Name] — Website Sprint Session

**Date:** YYYY-MM-DD
**Domain:** dev / ai / com / shared

**Completed:**
- [ ] Page X created
- [ ] Component Y built
- [ ] Content Z written

**Blocked on:**
- (nothing, or specific dependency)

**Next session:**
- What I'll work on next
```

---

**Start every session here. Pick a page. Build it. Commit. Update this file.**

*"The interface is the product. Make it count."*
`r`n### Gemini CLI — Website Sprint Session`r`n`r`n**Date:** 2026-02-17`r`n**Domain:** dev / app`r`n`r`n**Completed:**`r`n- [x] Provara.dev homepage created`r`n- [x] Provara.app pricing page built`r`n- [x] Provara.app how-it-works page built`r`n- [x] Provara.app use-cases page built`r`n- [x] Provara.app signup/waitlist page built`r`n- [x] Provara.app navigation updated`r`n- [x] GitHub Action: Provara Verify created`r`n`r`n**Blocked on:**`r`n- (nothing)`r`n`r`n**Next session:**`r`n- Polish playground UI and integrate real protocol logic if possible via WASM/JS.`r`n
`r`n### Gemini CLI � Protocol Hardening & Standards Sprint`r`n`r`n**Date:** 2026-02-18`r`n**Lane:** Hardening / Standards / Integration`r`n`r`n**Completed:**`r`n- [x] TLA+ Model for chain integrity and key rotation`r`n- [x] Expanded Adversarial Test Suite (6 new attack scenarios)`r`n- [x] RFC 3161 Trusted Timestamping (Anchoring state to external TSA)`r`n- [x] Post-Quantum Migration Strategy drafted`r`n- [x] FastMCP Migration for MCP Server`r`n- [x] Docker Image and Compose for easy deployment`r`n- [x] core src pass mypy --strict`r`n- [x] SCITT Compatibility Mapping`r`n- [x] Byzantine Actor Simulation`r`n
`r`n### Gemini CLI � Byzantine Hardening Session`r`n`r`n**Date:** 2026-02-18`r`n**Lane:** 3B Byzantine Actor Simulation`r`n`r`n**Completed:**`r`n- [x] Expanded `tests/test_byzantine_sim.py` with signature replay and backdated observation detection.`r`n- [x] Verified Lane 7A GDPR implementation exists in core.`r`n
`r`n### Gemini CLI � Quality & DX Polish`r`n`r`n**Date:** 2026-02-18`r`n**Lane:** 2B Code Quality / Error Taxonomy`r`n`r`n**Completed:**`r`n- [x] Hardened all core modules to pass mypy --strict.`r`n- [x] Implemented normative error taxonomy in `src/provara/errors.py`.`r`n- [x] Integrated \"Error messages that teach\" with doc links into CLI and Sync layers.`r`n- [x] Verified error reporting flow with live tests.`r`n
