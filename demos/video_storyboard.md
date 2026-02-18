# Provara MCP Server — 90-Second Demo Video Storyboard

**Title:** "Trustworthy AI Memory with Provara"  
**Duration:** 90 seconds  
**Format:** Screen recording + terminal + text overlays  
**Target:** Developers building AI agents

---

## Scene 1 (0-15s): Problem Statement

**Visual:** Black screen, white text appears line by line.

**Text Overlay:**
```
AI agents forget.

Or worse — they lie about remembering.
```

**Narration:**
> "AI agents have a fundamental problem: their memory is mutable. Vector databases can be edited. RAG systems can be altered. There's no way to verify what an agent actually remembered."

**Visual:** Fade to terminal showing a vector DB being silently modified.

**Text Overlay:**
```
Mutable memory = Untrustworthy agents
```

**Transition:** Quick zoom into terminal, screen shatters effect.

---

## Scene 2 (15-40s): The Demo

**Visual:** Screen recording of Claude Desktop with Provara MCP server running.

**Narration:**
> "Provara gives AI agents verifiable memory through cryptographic event logs."

**Visual:** Terminal showing vault initialization.

**Text Overlay:**
```bash
provara init agent_vault --actor "claude"
# Ed25519 keys generated
# SHA-256 hash chain initialized
```

**Narration:**
> "Every observation is signed with Ed25519..."

**Visual:** Claude appending an event via MCP tool call.

**Text Overlay:**
```json
{
  "tool": "append_event",
  "data": {"finding": "Research result"}
}
# Event signed, hashed, chained
```

**Narration:**
> "...chained with SHA-256..."

**Visual:** Animation showing hash chain linking events.

**Text Overlay:**
```
evt_001 → evt_002 → evt_003
  ↓        ↓        ↓
hash     hash     hash
```

**Narration:**
> "...and stored in an append-only vault."

**Visual:** Claude querying its memory.

**Text Overlay:**
```
Claude: "Let me check my research notes..."
query_timeline → 3 events found
```

---

## Scene 3 (40-60s): Verification

**Visual:** Terminal running verify command.

**Narration:**
> "Unlike mutable databases, Provara memory can be independently verified."

**Text Overlay:**
```bash
provara verify agent_vault
# ✓ Chain integrity: OK
# ✓ All signatures valid
# ✓ No tampering detected
```

**Visual:** Split screen — Claude on left, verification output on right.

**Narration:**
> "Anyone can run this verification. No need to trust the agent — the cryptography proves the audit trail is intact."

**Text Overlay:**
```
Trust, but verify.
Actually, just verify.
```

---

## Scene 4 (60-80s): The Difference

**Visual:** Side-by-side comparison.

**Left side (Unverified Memory):**
```
Vector DB:
- Can be edited silently
- No audit trail
- Trust the provider
```

**Right side (Provara):**
```
Provara Vault:
- Tamper-evident
- Full audit trail
- Verify yourself
```

**Narration:**
> "With unverified memory, you trust the provider. With Provara, you verify yourself."

**Visual:** Animation showing someone trying to edit a Provara vault — red "TAMPER DETECTED" warning appears.

**Text Overlay:**
```
Tamper attempt detected
Hash chain broken
Signature invalid
```

**Narration:**
> "Any alteration breaks the cryptographic chain. The evidence is undeniable."

---

## Scene 5 (80-90s): Call to Action

**Visual:** Provara logo on clean background.

**Narration:**
> "Build trustworthy AI agents with verifiable memory."

**Text Overlay:**
```
pip install provara-protocol

provara.dev/docs
```

**Visual:** QR code appears (links to docs).

**Text Overlay:**
```
Provara Protocol v1.0
Apache 2.0 · Open Source
```

**Narration:**
> "Provara. Truth is not merged. Evidence is merged. Truth is recomputed."

**Fade to black.**

---

## Production Notes

### Camera Angles

- **Terminal closeups:** 1080p, monospace font (Fira Code or Cascadia Code), high contrast
- **Screen recordings:** 1440p, smooth mouse movements, highlight clicks
- **Text overlays:** White text, dark semi-transparent background, 3-second minimum read time

### Audio

- **Narration:** Clear, professional, moderate pace (150 words/minute)
- **Background music:** Minimal, non-distracting, tech/corporate style
- **Sound effects:** Subtle keyboard clicks for terminal scenes, soft "ding" for verification success

### Key Visual Moments

1. **0:12** — Vector DB modification (shows the problem)
2. **0:25** — Hash chain animation (shows the solution)
3. **0:45** — Verification output (shows the proof)
4. **1:05** — Tamper detection (shows the difference)
5. **1:25** — QR code + URL (shows the action)

### Color Palette

- **Primary:** #0066cc (trust blue)
- **Accent:** #00cc99 (success green)
- **Error:** #cc3333 (danger red)
- **Background:** #0d1117 (GitHub dark)
- **Text:** #ffffff (white)

### Accessibility

- **Captions:** Burned-in subtitles throughout
- **Color contrast:** WCAG AA compliant
- **Pacing:** 3-second minimum for text overlays
- **Audio description:** Optional track describing visual elements

---

## Script Timing Reference

| Time | Scene | Words | Visual |
|------|-------|-------|--------|
| 0-15s | Problem | 35 | Black screen, text |
| 15-40s | Demo | 60 | Screen recording |
| 40-60s | Verification | 45 | Terminal output |
| 60-80s | Comparison | 50 | Split screen |
| 80-90s | CTA | 25 | Logo + QR code |

**Total:** ~215 words at 150 wpm = 86 seconds + 4 seconds buffer

---

## Assets Needed

- [ ] Provara logo (SVG, PNG)
- [ ] QR code generator (link to provara.dev/docs)
- [ ] Terminal theme (export settings)
- [ ] Background music (royalty-free)
- [ ] Font license (Fira Code OFL)

---

**"The interface is the product. Make it count."**
