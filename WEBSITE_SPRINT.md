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
| **provara.ai** | Technical depth | AI researchers, enterprises | Whitepapers, EU AI Act compliance, architecture deep-dives |
| **provara.com** | Consumer-facing | Individuals, families | "Preserve your memories for 50 years" narrative |

**Brand rule:** All sites use "Provara" (not "Hunt Information Systems"). Legal entity only appears in footer copyright.

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

## provara.ai (Priority #2)

### Required Pages

1. **Homepage** (`/`)
   - "Cryptographic Truth Without Consensus"
   - Technical audience positioning
   - Links to spec, whitepapers, conformance tests

2. **Protocol Spec** (`/spec/`)
   - Embedded `BACKPACK_PROTOCOL_v1.0.html`
   - Version selector (v1.0 only for now)
   - PDF download option

3. **Whitepapers** (`/papers/`)
   - "EU AI Act Article 12 Compliance with Provara"
   - "AI Agent Memory Requirements"
   - "50-Year Readability: Design for Digital Longevity"

4. **Conformance** (`/conformance/`)
   - Test vector download
   - Implementation checklist
   - "Provara Conformant" certification info

5. **Governance** (`/governance/`)
   - Extension registry process
   - IANA considerations
   - RFC submission process

### Tone

- Academic but accessible
- Cite the spec, not the implementation
- Position as infrastructure, not product

---

## provara.com (Priority #3)

### Required Pages

1. **Homepage** (`/`)
   - "Your Memories, Forever"
   - Emotional narrative (family photos, cognitive continuity)
   - "No cloud dependency" positioning
   - Consumer pricing ($5-10/month for hosted vaults)

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
| **Gemini CLI** | provara.ai | Spec integration, whitepapers, conformance |
| **Codex** | provara.com | Consumer copy, pricing, signup flow |
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
├── ai/            # provara.ai
│   ├── index.html
│   ├── spec/
│   ├── papers/
│   └── conformance/
├── com/           # provara.com
│   ├── index.html
│   ├── how-it-works/
│   ├── use-cases/
│   ├── pricing/
│   └── signup/
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
   - `provara-dev` → `sites/dev/`
   - `provara-ai` → `sites/ai/`
   - `provara-com` → `sites/com/`
4. Custom domains:
   - provara.dev → `provara-dev.pages.dev`
   - provara.ai → `provara-ai.pages.dev`
   - provara.com → `provara-com.pages.dev`

### Build Settings

- **Build command:** None (static site)
- **Output directory:** Site-specific folder
- **Environment variables:** None needed

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
3. **[AI]** Embed BACKPACK_PROTOCOL_v1.0.html into spec page
4. **[AI]** Draft "EU AI Act Compliance" whitepaper outline
5. **[COM]** Write consumer homepage copy ("Your Memories, Forever")
6. **[COM]** Create pricing page with 3-tier structure
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
