# Intelligence Terminal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a single-file financial intelligence dashboard (`master-vault/observatory.html`) that reads vault.sqlite via SQL.js WASM and surfaces actionable market signals through five visual zones.

**Architecture:** Single self-contained HTML file with inline CSS and JS. SQL.js (WASM) reads the SQLite vault directly in the browser — no server needed. Chart.js handles all visualizations. User double-clicks the file to open it alongside vault.sqlite.

**Tech Stack:** SQL.js 1.10+ (SQLite WASM), Chart.js 4.x, chartjs-adapter-date-fns, date-fns, Kestrel design system (CSS custom properties from `sites/provara.dev/assets/site.css`)

**Vault Schema Reference:**
```sql
-- Table: events (20,886 rows, 9 sources, 1990-2026)
-- Key columns: seq, event_id, type, timestamp, payload (JSON), source_format, tags
-- Sources: treasury(8,756), worldbank(4,846), synthetic(1,958), mitre_attack(1,861),
--          gdelt(1,639), cisa_kev(1,529), usgs(262), psmc(33), backpack(2)
-- Payload access: json_extract(payload, '$.field_name')
-- Treasury tenors: "1 Mo","2 Mo","3 Mo","4 Mo","6 Mo","1 Yr","2 Yr","3 Yr","5 Yr","7 Yr","10 Yr","20 Yr","30 Yr"
```

---

### Task 1: HTML Skeleton + Kestrel CSS Foundation

**Files:**
- Create: `master-vault/observatory.html`

**Step 1: Create the base HTML file with Kestrel design tokens and five empty zone containers**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Provara Intelligence Terminal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    /* ================================================================
       KESTREL DESIGN TOKENS
       From: sites/provara.dev/assets/site.css
       ================================================================ */
    :root {
      --k-bg: #060a10;
      --k-bg-card: #0a0e18;
      --k-bg-card-alt: #080c14;
      --k-bg-hover: #0d1220;
      --k-bg-elevated: #0e1424;
      --k-border: #111822;
      --k-border-light: #151c28;
      --k-border-hover: #1a2330;
      --k-border-accent: #1a2636;
      --k-text: #c8d4e0;
      --k-text-bright: #e0e8f0;
      --k-text-muted: #8899aa;
      --k-text-dark: #5a7088;
      --k-accent: #00e5a0;
      --k-accent-dim: #00c488;
      --k-accent-blue: #00b8ff;
      --k-accent-purple: #8866ff;
      --k-red: #ff4466;
      --k-orange: #ff8800;
      --k-yellow: #e6b84a;
      --k-sans: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      --k-mono: 'JetBrains Mono', 'SF Mono', 'Cascadia Code', monospace;
      --k-max-width: 1140px;
      --k-gutter: 20px;
    }

    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    html { scroll-behavior: smooth; }
    body {
      font-family: var(--k-sans);
      font-size: 16px;
      line-height: 1.6;
      color: var(--k-text);
      background: var(--k-bg);
      -webkit-font-smoothing: antialiased;
      min-height: 100vh;
    }

    .container {
      max-width: var(--k-max-width);
      margin: 0 auto;
      padding: 0 var(--k-gutter);
    }

    .card {
      background: var(--k-bg-card);
      border: 1px solid var(--k-border);
      border-radius: 8px;
      padding: 24px;
    }

    .card-title {
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--k-text-muted);
      margin-bottom: 16px;
    }

    /* ---- Zone 1: Status Bar ---- */
    #zone-status { /* filled in Task 3 */ }

    /* ---- Zone 2: Macro + Risk ---- */
    #zone-macro-risk { /* filled in Task 4 */ }

    /* ---- Zone 3: Yield Curve ---- */
    #zone-yield { /* filled in Task 5 */ }

    /* ---- Zone 4: Sector Intel ---- */
    #zone-sectors { /* filled in Task 6 */ }

    /* ---- Zone 5: SQL Console ---- */
    #zone-console { /* filled in Task 7 */ }

    /* ---- Loading state ---- */
    #loading {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      gap: 16px;
    }
    #loading .spinner {
      width: 40px;
      height: 40px;
      border: 3px solid var(--k-border);
      border-top-color: var(--k-accent);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    #loading .label {
      font-family: var(--k-mono);
      font-size: 0.875rem;
      color: var(--k-text-muted);
    }

    #app { display: none; }
  </style>
</head>
<body>
  <!-- Loading state (visible until SQL.js loads vault) -->
  <div id="loading">
    <div class="spinner"></div>
    <div class="label">Loading vault...</div>
  </div>

  <!-- Main app (hidden until ready) -->
  <div id="app">
    <div class="container">
      <!-- Zone 1: Status Bar -->
      <header id="zone-status"></header>

      <!-- Zone 2: Macro Regime + Risk Signals -->
      <section id="zone-macro-risk"></section>

      <!-- Zone 3: Yield Curve Monitor -->
      <section id="zone-yield"></section>

      <!-- Zone 4: Sector Intelligence -->
      <section id="zone-sectors"></section>

      <!-- Zone 5: SQL Console -->
      <section id="zone-console"></section>
    </div>
  </div>

  <script>
    // App bootstrap — filled in Task 2
  </script>
</body>
</html>
```

**Step 2: Verify the file opens in a browser and shows the loading spinner**

Run: Open `master-vault/observatory.html` in a browser (or use `python3 -m http.server` from `master-vault/`).
Expected: Dark navy background, spinning green ring, "Loading vault..." text in JetBrains Mono.

**Step 3: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): scaffold HTML skeleton with Kestrel design tokens"
```

---

### Task 2: SQL.js Integration + Vault Loading

**Files:**
- Modify: `master-vault/observatory.html` (script section)

**Step 1: Add SQL.js CDN script tags and vault loading logic**

Add before the closing `</body>` tag, replacing the empty script block:

```html
<!-- Dependencies (CDN) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>

<script>
  // ================================================================
  // PROVARA INTELLIGENCE TERMINAL
  // ================================================================

  let DB = null;

  // Utility: run SQL, return array of objects
  function query(sql, params = []) {
    const stmt = DB.prepare(sql);
    if (params.length) stmt.bind(params);
    const rows = [];
    while (stmt.step()) {
      rows.push(stmt.getAsObject());
    }
    stmt.free();
    return rows;
  }

  // Utility: run SQL, return single value
  function scalar(sql, params = []) {
    const rows = query(sql, params);
    if (!rows.length) return null;
    return Object.values(rows[0])[0];
  }

  async function loadVault() {
    const loadingLabel = document.querySelector('#loading .label');

    try {
      loadingLabel.textContent = 'Initializing SQL engine...';
      const SQL = await initSqlJs({
        locateFile: file => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${file}`
      });

      loadingLabel.textContent = 'Loading vault.sqlite...';
      const response = await fetch('vault.sqlite');
      if (!response.ok) throw new Error(`Failed to load vault.sqlite: ${response.status}`);
      const buf = await response.arrayBuffer();

      DB = new SQL.Database(new Uint8Array(buf));
      const eventCount = scalar('SELECT COUNT(*) FROM events');
      console.log(`Vault loaded: ${eventCount} events`);

      // Hide loading, show app
      document.getElementById('loading').style.display = 'none';
      document.getElementById('app').style.display = 'block';

      // Boot all zones
      renderStatusBar();
      renderMacroRisk();
      renderYieldCurve();
      renderSectors();
      renderConsole();

    } catch (err) {
      loadingLabel.textContent = `Error: ${err.message}`;
      loadingLabel.style.color = '#ff4466';
      console.error(err);
    }
  }

  // Zone render stubs (filled in subsequent tasks)
  function renderStatusBar() { console.log('Zone 1: Status Bar'); }
  function renderMacroRisk() { console.log('Zone 2: Macro + Risk'); }
  function renderYieldCurve() { console.log('Zone 3: Yield Curve'); }
  function renderSectors() { console.log('Zone 4: Sectors'); }
  function renderConsole() { console.log('Zone 5: Console'); }

  // Boot
  loadVault();
</script>
```

**Step 2: Verify vault loads by serving locally**

Run:
```bash
cd ~/provara/master-vault && python3 -m http.server 8080
# Open http://localhost:8080/observatory.html in browser
# Check browser console for "Vault loaded: 20886 events"
```

Expected: Loading spinner → app div appears (empty zones), console shows event count.

**Step 3: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): integrate SQL.js WASM and vault loading"
```

---

### Task 3: Zone 1 — Status Bar

**Files:**
- Modify: `master-vault/observatory.html` (CSS + renderStatusBar function)

**Step 1: Add Status Bar CSS**

Add to the `<style>` block:

```css
/* ---- Zone 1: Status Bar ---- */
#zone-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 0;
  border-bottom: 1px solid var(--k-border);
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 12px;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.status-brand {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--k-text-bright);
  letter-spacing: -0.02em;
}

.status-brand span {
  color: var(--k-accent);
}

.status-stats {
  display: flex;
  gap: 20px;
}

.stat {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  color: var(--k-text-muted);
}

.stat strong {
  color: var(--k-text);
  font-weight: 500;
}

.status-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.risk-badge {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.risk-low { background: rgba(0,229,160,0.15); color: var(--k-accent); border: 1px solid rgba(0,229,160,0.3); }
.risk-medium { background: rgba(255,136,0,0.15); color: var(--k-orange); border: 1px solid rgba(255,136,0,0.3); }
.risk-high { background: rgba(255,68,102,0.15); color: var(--k-red); border: 1px solid rgba(255,68,102,0.3); }
```

**Step 2: Implement renderStatusBar**

Replace the stub:

```javascript
function renderStatusBar() {
  const totalEvents = scalar('SELECT COUNT(*) FROM events');
  const sourceCount = scalar('SELECT COUNT(DISTINCT source_format) FROM events');
  const minTs = scalar('SELECT MIN(timestamp) FROM events');
  const maxTs = scalar('SELECT MAX(timestamp) FROM events');
  const minYear = minTs ? minTs.substring(0, 4) : '—';
  const maxYear = maxTs ? maxTs.substring(0, 4) : '—';

  document.getElementById('zone-status').innerHTML = `
    <div class="status-left">
      <div class="status-brand">Provara <span>Observatory</span></div>
      <div class="status-stats">
        <div class="stat"><strong>${totalEvents.toLocaleString()}</strong> events</div>
        <div class="stat"><strong>${sourceCount}</strong> sources</div>
        <div class="stat"><strong>${minYear}–${maxYear}</strong> span</div>
      </div>
    </div>
    <div class="status-right">
      <div class="stat">Updated ${maxTs ? maxTs.substring(0, 10) : '—'}</div>
      <div id="combined-risk-badge" class="risk-badge risk-low">RISK: —</div>
    </div>
  `;
}
```

**Step 3: Verify status bar renders with real data**

Run: Refresh `http://localhost:8080/observatory.html`
Expected: Top bar shows "Provara Observatory", "20,886 events", "9 sources", "1990–2026 span".

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): implement Zone 1 status bar with vault stats"
```

---

### Task 4: Zone 2 — Macro Regime + Risk Signals

**Files:**
- Modify: `master-vault/observatory.html` (CSS + renderMacroRisk function)

**Step 1: Add Zone 2 CSS**

```css
/* ---- Zone 2: Macro Regime + Risk Signals ---- */
.macro-risk-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .macro-risk-grid { grid-template-columns: 1fr; }
}

.regime-value {
  font-family: var(--k-mono);
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
  margin: 12px 0 8px;
}

.regime-label {
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 4px 10px;
  border-radius: 4px;
  display: inline-block;
  margin-bottom: 12px;
}

.regime-expansion { background: rgba(0,229,160,0.15); color: var(--k-accent); }
.regime-caution { background: rgba(255,136,0,0.15); color: var(--k-orange); }
.regime-recession { background: rgba(255,68,102,0.15); color: var(--k-red); }

.regime-detail {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  color: var(--k-text-muted);
  margin-top: 4px;
}

.risk-signals {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.signal-card {
  background: var(--k-bg-card-alt);
  border: 1px solid var(--k-border-light);
  border-radius: 6px;
  padding: 16px;
}

.signal-name {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--k-text-muted);
  margin-bottom: 8px;
}

.signal-status {
  font-family: var(--k-mono);
  font-size: 0.8rem;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
}

.signal-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.signal-green .signal-dot { background: var(--k-accent); box-shadow: 0 0 6px rgba(0,229,160,0.5); }
.signal-yellow .signal-dot { background: var(--k-orange); box-shadow: 0 0 6px rgba(255,136,0,0.5); }
.signal-red .signal-dot { background: var(--k-red); box-shadow: 0 0 6px rgba(255,68,102,0.5); }
.signal-green .signal-label { color: var(--k-accent); }
.signal-yellow .signal-label { color: var(--k-orange); }
.signal-red .signal-label { color: var(--k-red); }

.combined-score {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--k-border-light);
  font-family: var(--k-mono);
  font-size: 0.8rem;
  color: var(--k-text-muted);
  text-align: center;
}

.combined-score strong {
  font-size: 1.25rem;
}
```

**Step 2: Implement renderMacroRisk**

Replace the stub:

```javascript
function renderMacroRisk() {
  // --- Macro Regime (2/10 yield spread) ---
  const latestYield = query(`
    SELECT json_extract(payload, '$.spread_2_10') as spread,
           json_extract(payload, '$.yields."2 Yr"') as y2,
           json_extract(payload, '$.yields."10 Yr"') as y10,
           timestamp
    FROM events
    WHERE source_format='treasury'
      AND json_extract(payload, '$.spread_2_10') IS NOT NULL
    ORDER BY timestamp DESC LIMIT 1
  `)[0];

  const spread = latestYield ? latestYield.spread : 0;
  const spreadColor = spread < 0 ? 'var(--k-red)' : spread < 0.5 ? 'var(--k-orange)' : 'var(--k-accent)';
  const regimeClass = spread < 0 ? 'regime-recession' : spread < 0.5 ? 'regime-caution' : 'regime-expansion';
  const regimeLabel = spread < 0 ? 'INVERTED' : spread < 0.5 ? 'CAUTION' : 'EXPANSION';

  // Count inversion days
  const inversionCount = scalar(`
    SELECT COUNT(*) FROM events
    WHERE type='yield.inverted' AND json_extract(payload, '$.spread_2_10') < 0
  `);

  // --- Risk Signals ---
  // 1. Yield Curve Signal
  const yieldSignal = spread < 0 ? { cls: 'signal-red', label: 'INVERTED' }
    : spread < 0.5 ? { cls: 'signal-yellow', label: 'FLATTENING' }
    : { cls: 'signal-green', label: 'NORMAL' };

  // 2. Cyber Threat (CISA KEV acceleration)
  const kevRecent = scalar(`
    SELECT COUNT(*) FROM events
    WHERE source_format='cisa_kev'
      AND timestamp >= date('2024-01-01')
  `) || 0;
  const kevTotal = scalar(`SELECT COUNT(*) FROM events WHERE source_format='cisa_kev'`) || 1;
  const kevRate = kevRecent / kevTotal;
  const cyberSignal = kevRate > 0.3 ? { cls: 'signal-red', label: 'CRITICAL' }
    : kevRate > 0.15 ? { cls: 'signal-yellow', label: 'ELEVATED' }
    : { cls: 'signal-green', label: 'BASELINE' };

  // 3. Geopolitical (GDELT Goldstein scale)
  const avgGoldstein = scalar(`
    SELECT AVG(json_extract(payload, '$.goldstein_scale'))
    FROM events WHERE source_format='gdelt'
  `) || 0;
  const geoSignal = avgGoldstein < -3 ? { cls: 'signal-red', label: 'HIGH' }
    : avgGoldstein < 0 ? { cls: 'signal-yellow', label: 'ELEVATED' }
    : { cls: 'signal-green', label: 'STABLE' };

  // 4. Seismic (USGS major events)
  const majorQuakes = scalar(`
    SELECT COUNT(*) FROM events
    WHERE source_format='usgs'
      AND json_extract(payload, '$.magnitude') >= 6.0
  `) || 0;
  const seismicSignal = majorQuakes > 0 ? { cls: 'signal-red', label: 'MAJOR' }
    : { cls: 'signal-green', label: 'BASELINE' };

  // Combined risk score (0-10)
  const riskScores = {
    yield: spread < 0 ? 4 : spread < 0.5 ? 2 : 0,
    cyber: kevRate > 0.3 ? 3 : kevRate > 0.15 ? 1.5 : 0,
    geo: avgGoldstein < -3 ? 2 : avgGoldstein < 0 ? 1 : 0,
    seismic: majorQuakes > 0 ? 1 : 0,
  };
  const combinedRisk = Math.min(10, Object.values(riskScores).reduce((a, b) => a + b, 0));
  const riskColor = combinedRisk >= 6 ? 'var(--k-red)' : combinedRisk >= 3 ? 'var(--k-orange)' : 'var(--k-accent)';

  // Update status bar badge
  const badgeEl = document.getElementById('combined-risk-badge');
  const badgeClass = combinedRisk >= 6 ? 'risk-high' : combinedRisk >= 3 ? 'risk-medium' : 'risk-low';
  badgeEl.className = `risk-badge ${badgeClass}`;
  badgeEl.textContent = `RISK: ${combinedRisk.toFixed(1)}`;

  document.getElementById('zone-macro-risk').innerHTML = `
    <div class="macro-risk-grid">
      <div class="card">
        <div class="card-title">Macro Regime — 2/10 Yield Spread</div>
        <div class="regime-value" style="color:${spreadColor}">${spread >= 0 ? '+' : ''}${spread.toFixed(2)}%</div>
        <div class="regime-label ${regimeClass}">${regimeLabel}</div>
        <div class="regime-detail">2Yr: ${latestYield ? latestYield.y2 : '—'}% · 10Yr: ${latestYield ? latestYield.y10 : '—'}%</div>
        <div class="regime-detail">${inversionCount.toLocaleString()} inversion days recorded (1990–2024)</div>
        <div class="regime-detail">As of ${latestYield ? latestYield.timestamp.substring(0, 10) : '—'}</div>
      </div>
      <div class="card">
        <div class="card-title">Risk Signal Dashboard</div>
        <div class="risk-signals">
          <div class="signal-card">
            <div class="signal-name">Yield Curve</div>
            <div class="signal-status ${yieldSignal.cls}">
              <span class="signal-dot"></span>
              <span class="signal-label">${yieldSignal.label}</span>
            </div>
          </div>
          <div class="signal-card">
            <div class="signal-name">Cyber Threat</div>
            <div class="signal-status ${cyberSignal.cls}">
              <span class="signal-dot"></span>
              <span class="signal-label">${cyberSignal.label}</span>
            </div>
          </div>
          <div class="signal-card">
            <div class="signal-name">Geopolitical</div>
            <div class="signal-status ${geoSignal.cls}">
              <span class="signal-dot"></span>
              <span class="signal-label">${geoSignal.label}</span>
            </div>
          </div>
          <div class="signal-card">
            <div class="signal-name">Seismic</div>
            <div class="signal-status ${seismicSignal.cls}">
              <span class="signal-dot"></span>
              <span class="signal-label">${seismicSignal.label}</span>
            </div>
          </div>
        </div>
        <div class="combined-score">
          Combined Risk: <strong style="color:${riskColor}">${combinedRisk.toFixed(1)}</strong>/10
        </div>
      </div>
    </div>
  `;
}
```

**Step 3: Verify regime indicator and risk signals render**

Run: Refresh browser
Expected: Two-column layout — left card shows spread "+0.33%" with "EXPANSION" badge, right card shows four signal lights with color-coded statuses, combined risk score.

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): implement Zone 2 macro regime + risk signals"
```

---

### Task 5: Zone 3 — Yield Curve Monitor (Charts)

**Files:**
- Modify: `master-vault/observatory.html` (CSS + renderYieldCurve function)

**Step 1: Add Zone 3 CSS**

```css
/* ---- Zone 3: Yield Curve Monitor ---- */
.yield-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}

@media (max-width: 768px) {
  .yield-grid { grid-template-columns: 1fr; }
}

.chart-wrap {
  position: relative;
  height: 280px;
}

.chart-wrap canvas {
  width: 100% !important;
  height: 100% !important;
}
```

**Step 2: Implement renderYieldCurve**

Replace the stub:

```javascript
function renderYieldCurve() {
  document.getElementById('zone-yield').innerHTML = `
    <div class="yield-grid">
      <div class="card">
        <div class="card-title">Current Yield Curve</div>
        <div class="chart-wrap"><canvas id="chart-curve"></canvas></div>
      </div>
      <div class="card">
        <div class="card-title">2/10 Spread History (1990–2024)</div>
        <div class="chart-wrap"><canvas id="chart-spread"></canvas></div>
      </div>
    </div>
  `;

  // --- Chart A: Current yield curve vs 6 months prior ---
  const tenorOrder = ['1 Mo','2 Mo','3 Mo','4 Mo','6 Mo','1 Yr','2 Yr','3 Yr','5 Yr','7 Yr','10 Yr','20 Yr','30 Yr'];

  const latest = query(`
    SELECT payload, timestamp FROM events
    WHERE source_format='treasury'
    ORDER BY timestamp DESC LIMIT 1
  `)[0];

  const sixMonthsAgo = query(`
    SELECT payload, timestamp FROM events
    WHERE source_format='treasury'
      AND timestamp <= date(?, '-6 months')
    ORDER BY timestamp DESC LIMIT 1
  `, [latest ? latest.timestamp : '2024-12-31'])[0];

  function extractYields(row) {
    if (!row) return tenorOrder.map(() => null);
    const p = JSON.parse(row.payload);
    const yields = p.yields || {};
    return tenorOrder.map(t => yields[t] ?? null);
  }

  const latestYields = extractYields(latest);
  const priorYields = extractYields(sixMonthsAgo);

  new Chart(document.getElementById('chart-curve'), {
    type: 'line',
    data: {
      labels: tenorOrder,
      datasets: [
        {
          label: latest ? latest.timestamp.substring(0, 10) : 'Latest',
          data: latestYields,
          borderColor: '#00e5a0',
          backgroundColor: 'rgba(0,229,160,0.1)',
          borderWidth: 2,
          pointRadius: 3,
          pointBackgroundColor: '#00e5a0',
          fill: false,
          tension: 0.3,
        },
        {
          label: sixMonthsAgo ? sixMonthsAgo.timestamp.substring(0, 10) : '6mo prior',
          data: priorYields,
          borderColor: '#8899aa',
          borderDash: [6, 3],
          borderWidth: 1.5,
          pointRadius: 2,
          pointBackgroundColor: '#8899aa',
          fill: false,
          tension: 0.3,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8899aa', font: { family: "'JetBrains Mono'", size: 10 } } },
        tooltip: {
          backgroundColor: '#0a0e18',
          borderColor: '#1a2636',
          borderWidth: 1,
          titleFont: { family: "'JetBrains Mono'" },
          bodyFont: { family: "'JetBrains Mono'" },
        },
      },
      scales: {
        x: {
          ticks: { color: '#5a7088', font: { family: "'JetBrains Mono'", size: 9 } },
          grid: { color: 'rgba(17,24,34,0.5)' },
        },
        y: {
          ticks: { color: '#5a7088', font: { family: "'JetBrains Mono'", size: 10 }, callback: v => v + '%' },
          grid: { color: 'rgba(17,24,34,0.5)' },
        },
      },
    },
  });

  // --- Chart B: 2/10 Spread History ---
  // Sample every 20th trading day for performance
  const spreadData = query(`
    SELECT timestamp, json_extract(payload, '$.spread_2_10') as spread
    FROM events
    WHERE source_format='treasury'
      AND json_extract(payload, '$.spread_2_10') IS NOT NULL
    ORDER BY timestamp ASC
  `);

  // Downsample for chart performance (every 10th point)
  const sampled = spreadData.filter((_, i) => i % 10 === 0 || i === spreadData.length - 1);

  new Chart(document.getElementById('chart-spread'), {
    type: 'line',
    data: {
      labels: sampled.map(r => r.timestamp.substring(0, 10)),
      datasets: [{
        label: '2/10 Spread (%)',
        data: sampled.map(r => r.spread),
        borderColor: sampled.map(r => r.spread < 0 ? '#ff4466' : '#00e5a0'),
        segment: {
          borderColor: ctx => {
            const val = ctx.p1.parsed.y;
            return val < 0 ? '#ff4466' : '#00e5a0';
          },
        },
        backgroundColor: 'transparent',
        borderWidth: 1.5,
        pointRadius: 0,
        fill: {
          target: { value: 0 },
          above: 'rgba(0,229,160,0.05)',
          below: 'rgba(255,68,102,0.15)',
        },
        tension: 0.1,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0a0e18',
          borderColor: '#1a2636',
          borderWidth: 1,
          titleFont: { family: "'JetBrains Mono'" },
          bodyFont: { family: "'JetBrains Mono'" },
          callbacks: { label: ctx => `Spread: ${ctx.parsed.y.toFixed(2)}%` },
        },
      },
      scales: {
        x: {
          type: 'time',
          time: { unit: 'year', displayFormats: { year: 'yyyy' } },
          ticks: { color: '#5a7088', font: { family: "'JetBrains Mono'", size: 9 }, maxTicksLimit: 12 },
          grid: { color: 'rgba(17,24,34,0.5)' },
        },
        y: {
          ticks: { color: '#5a7088', font: { family: "'JetBrains Mono'", size: 10 }, callback: v => v + '%' },
          grid: { color: 'rgba(17,24,34,0.5)' },
        },
      },
      // Zero line annotation
      annotation: undefined,
    },
  });
}
```

**Step 3: Verify both charts render with real yield data**

Run: Refresh browser
Expected: Left chart shows current yield curve (green solid) vs 6-month prior (gray dashed). Right chart shows 1990–2024 spread history with red fill below zero line for inversions.

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): implement Zone 3 yield curve monitor with Chart.js"
```

---

### Task 6: Zone 4 — Sector Intelligence Cards

**Files:**
- Modify: `master-vault/observatory.html` (CSS + renderSectors function)

**Step 1: Add Zone 4 CSS**

```css
/* ---- Zone 4: Sector Intelligence ---- */
.sector-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

@media (max-width: 900px) {
  .sector-grid { grid-template-columns: 1fr; }
}

.metric-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-family: var(--k-mono);
  font-size: 0.75rem;
  border-bottom: 1px solid var(--k-border-light);
}

.metric-row:last-child { border-bottom: none; }

.metric-label { color: var(--k-text-muted); }
.metric-value { color: var(--k-text-bright); font-weight: 500; }

.implication {
  margin-top: 16px;
  padding: 10px 12px;
  background: var(--k-bg-card-alt);
  border-left: 3px solid var(--k-accent-purple);
  border-radius: 0 4px 4px 0;
  font-size: 0.75rem;
  color: var(--k-text-muted);
  font-style: italic;
}

.mini-chart {
  height: 140px;
  margin: 12px 0;
}

.mini-chart canvas {
  width: 100% !important;
  height: 100% !important;
}
```

**Step 2: Implement renderSectors**

Replace the stub:

```javascript
function renderSectors() {
  // --- Card A: Cyber Threat Acceleration ---
  const kevByMonth = query(`
    SELECT substr(timestamp, 1, 7) as month, COUNT(*) as cnt
    FROM events WHERE source_format='cisa_kev'
    GROUP BY month ORDER BY month DESC LIMIT 24
  `).reverse();

  const totalKev = scalar('SELECT COUNT(*) FROM events WHERE source_format=\'cisa_kev\'');
  const ransomwareCount = scalar('SELECT COUNT(*) FROM events WHERE type=\'cve.ransomware\'') || 0;
  const ransomwarePct = totalKev > 0 ? ((ransomwareCount / totalKev) * 100).toFixed(1) : '0';

  const topVendors = query(`
    SELECT json_extract(payload, '$.vendor') as vendor, COUNT(*) as cnt
    FROM events WHERE source_format='cisa_kev'
    GROUP BY vendor ORDER BY cnt DESC LIMIT 3
  `);

  // --- Card B: Geopolitical Risk ---
  const gdeltByMonth = query(`
    SELECT substr(timestamp, 1, 7) as month,
           AVG(json_extract(payload, '$.goldstein_scale')) as avg_g,
           COUNT(*) as cnt
    FROM events WHERE source_format='gdelt'
    GROUP BY month ORDER BY month DESC LIMIT 12
  `).reverse();

  const coopCount = scalar('SELECT COUNT(*) FROM events WHERE type=\'geopolitical.cooperation\'') || 0;
  const conflictCount = scalar('SELECT COUNT(*) FROM events WHERE type=\'geopolitical.conflict\'') || 0;
  const coopRatio = conflictCount > 0 ? (coopCount / conflictCount).toFixed(2) : '—';

  const topDyads = query(`
    SELECT json_extract(payload, '$.actor1') as a1,
           json_extract(payload, '$.actor2') as a2,
           COUNT(*) as cnt
    FROM events WHERE source_format='gdelt'
      AND json_extract(payload, '$.actor1') != ''
      AND json_extract(payload, '$.actor2') != ''
    GROUP BY a1, a2 ORDER BY cnt DESC LIMIT 3
  `);

  // --- Card C: Global GDP Trends ---
  const latestGdp = query(`
    SELECT json_extract(payload, '$.country') as country,
           json_extract(payload, '$.country_code') as code,
           json_extract(payload, '$.value_trillion') as gdp_t,
           json_extract(payload, '$.year') as year
    FROM events
    WHERE source_format='worldbank'
      AND json_extract(payload, '$.country_code') IN ('USA','CHN','JPN','DEU','IND','GBR','FRA','BRA','ITA','CAN')
    ORDER BY year DESC
  `);

  // Get latest year per country
  const gdpByCountry = {};
  for (const row of latestGdp) {
    if (!gdpByCountry[row.code]) gdpByCountry[row.code] = row;
  }
  const top10 = Object.values(gdpByCountry).sort((a, b) => b.gdp_t - a.gdp_t);

  document.getElementById('zone-sectors').innerHTML = `
    <div class="sector-grid">
      <div class="card">
        <div class="card-title">Cyber Threat Acceleration</div>
        <div class="mini-chart"><canvas id="chart-kev"></canvas></div>
        <div class="metric-row">
          <span class="metric-label">Total KEVs</span>
          <span class="metric-value">${totalKev.toLocaleString()}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Ransomware</span>
          <span class="metric-value" style="color:var(--k-red)">${ransomwarePct}%</span>
        </div>
        ${topVendors.map(v => `
          <div class="metric-row">
            <span class="metric-label">${v.vendor}</span>
            <span class="metric-value">${v.cnt}</span>
          </div>
        `).join('')}
        <div class="implication">Rising CVE velocity → bullish cyber defense sector</div>
      </div>

      <div class="card">
        <div class="card-title">Geopolitical Risk Index</div>
        <div class="mini-chart"><canvas id="chart-gdelt"></canvas></div>
        <div class="metric-row">
          <span class="metric-label">Coop/Conflict Ratio</span>
          <span class="metric-value">${coopRatio}</span>
        </div>
        ${topDyads.map(d => `
          <div class="metric-row">
            <span class="metric-label">${d.a1 || '?'} ↔ ${d.a2 || '?'}</span>
            <span class="metric-value">${d.cnt}</span>
          </div>
        `).join('')}
        <div class="implication">Elevated conflict → defense & commodities exposure</div>
      </div>

      <div class="card">
        <div class="card-title">Global GDP (Top 10)</div>
        <div class="mini-chart"><canvas id="chart-gdp"></canvas></div>
        ${top10.slice(0, 5).map(c => `
          <div class="metric-row">
            <span class="metric-label">${c.code}</span>
            <span class="metric-value">$${c.gdp_t}T <span style="color:var(--k-text-muted)">(${c.year})</span></span>
          </div>
        `).join('')}
        <div class="implication">Growth divergence → regional allocation signals</div>
      </div>
    </div>
  `;

  // --- Mini charts ---

  // KEV monthly bar chart
  new Chart(document.getElementById('chart-kev'), {
    type: 'bar',
    data: {
      labels: kevByMonth.map(r => r.month),
      datasets: [{
        data: kevByMonth.map(r => r.cnt),
        backgroundColor: kevByMonth.map(r => r.cnt > 80 ? '#ff4466' : r.cnt > 50 ? '#ff8800' : '#00e5a0'),
        borderRadius: 2,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#5a7088', font: { size: 8 }, maxRotation: 45 }, grid: { display: false } },
        y: { ticks: { color: '#5a7088', font: { size: 9 } }, grid: { color: 'rgba(17,24,34,0.5)' } },
      },
    },
  });

  // GDELT Goldstein line chart
  new Chart(document.getElementById('chart-gdelt'), {
    type: 'line',
    data: {
      labels: gdeltByMonth.map(r => r.month),
      datasets: [{
        data: gdeltByMonth.map(r => r.avg_g),
        borderColor: '#8866ff',
        backgroundColor: 'rgba(136,102,255,0.1)',
        borderWidth: 2,
        pointRadius: 3,
        pointBackgroundColor: '#8866ff',
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#5a7088', font: { size: 8 } }, grid: { display: false } },
        y: { ticks: { color: '#5a7088', font: { size: 9 } }, grid: { color: 'rgba(17,24,34,0.5)' } },
      },
    },
  });

  // GDP horizontal bar chart
  new Chart(document.getElementById('chart-gdp'), {
    type: 'bar',
    data: {
      labels: top10.map(c => c.code),
      datasets: [{
        data: top10.map(c => c.gdp_t),
        backgroundColor: top10.map((_, i) => i === 0 ? '#00e5a0' : i === 1 ? '#00b8ff' : '#8866ff'),
        borderRadius: 2,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#5a7088', font: { size: 9 }, callback: v => '$' + v + 'T' }, grid: { color: 'rgba(17,24,34,0.5)' } },
        y: { ticks: { color: '#8899aa', font: { family: "'JetBrains Mono'", size: 10 } }, grid: { display: false } },
      },
    },
  });
}
```

**Step 3: Verify all three sector cards render with charts and metrics**

Run: Refresh browser
Expected: Three-column layout — Cyber card with monthly KEV bar chart, Geopolitical card with Goldstein line chart, GDP card with horizontal bar chart. Each has metrics rows and purple implication callouts.

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): implement Zone 4 sector intelligence cards"
```

---

### Task 7: Zone 5 — SQL Console

**Files:**
- Modify: `master-vault/observatory.html` (CSS + renderConsole function)

**Step 1: Add Zone 5 CSS**

```css
/* ---- Zone 5: SQL Console ---- */
.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}

.console-header:hover .card-title {
  color: var(--k-text);
}

.console-toggle {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  color: var(--k-text-muted);
  transition: transform 0.2s;
}

.console-body {
  display: none;
  margin-top: 16px;
}

.console-body.open {
  display: block;
}

.console-toggle.open {
  transform: rotate(180deg);
}

.sql-input {
  width: 100%;
  min-height: 80px;
  background: var(--k-bg);
  border: 1px solid var(--k-border);
  border-radius: 4px;
  color: var(--k-accent);
  font-family: var(--k-mono);
  font-size: 0.8rem;
  padding: 12px;
  resize: vertical;
  outline: none;
}

.sql-input:focus {
  border-color: var(--k-accent);
  box-shadow: 0 0 0 2px rgba(0,229,160,0.15);
}

.console-toolbar {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  align-items: center;
}

.btn-run {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  font-weight: 600;
  padding: 6px 16px;
  background: rgba(0,229,160,0.15);
  color: var(--k-accent);
  border: 1px solid rgba(0,229,160,0.3);
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}

.btn-run:hover {
  background: rgba(0,229,160,0.25);
}

.preset-select {
  font-family: var(--k-mono);
  font-size: 0.75rem;
  padding: 6px 10px;
  background: var(--k-bg);
  color: var(--k-text-muted);
  border: 1px solid var(--k-border);
  border-radius: 4px;
  outline: none;
}

.console-results {
  margin-top: 12px;
  max-height: 300px;
  overflow: auto;
  font-family: var(--k-mono);
  font-size: 0.75rem;
}

.console-results table {
  width: 100%;
  border-collapse: collapse;
}

.console-results th {
  text-align: left;
  padding: 6px 10px;
  background: var(--k-bg-elevated);
  color: var(--k-accent);
  font-weight: 600;
  border-bottom: 1px solid var(--k-border);
  position: sticky;
  top: 0;
}

.console-results td {
  padding: 4px 10px;
  border-bottom: 1px solid var(--k-border-light);
  color: var(--k-text);
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.console-results tr:hover td {
  background: var(--k-bg-hover);
}

.console-error {
  color: var(--k-red);
  font-family: var(--k-mono);
  font-size: 0.8rem;
  padding: 8px;
  margin-top: 8px;
}

.console-info {
  color: var(--k-text-muted);
  font-family: var(--k-mono);
  font-size: 0.75rem;
  margin-top: 4px;
}
```

**Step 2: Implement renderConsole**

Replace the stub:

```javascript
const PRESET_QUERIES = {
  '': 'SELECT * FROM events ORDER BY seq DESC LIMIT 20',
  'Yield curve inversions': `SELECT timestamp, json_extract(payload, '$.spread_2_10') as spread,
    json_extract(payload, '$.yields."2 Yr"') as y2,
    json_extract(payload, '$.yields."10 Yr"') as y10
FROM events WHERE type='yield.inverted'
ORDER BY timestamp DESC LIMIT 50`,
  'Monthly CVE acceleration': `SELECT substr(timestamp, 1, 7) as month,
    COUNT(*) as cves_added,
    SUM(CASE WHEN type='cve.ransomware' THEN 1 ELSE 0 END) as ransomware
FROM events WHERE source_format='cisa_kev'
GROUP BY month ORDER BY month DESC LIMIT 24`,
  'GDELT conflict spikes': `SELECT substr(timestamp, 1, 7) as month,
    AVG(json_extract(payload, '$.goldstein_scale')) as avg_goldstein,
    COUNT(*) as events,
    SUM(CASE WHEN type='geopolitical.conflict' THEN 1 ELSE 0 END) as conflicts
FROM events WHERE source_format='gdelt'
GROUP BY month ORDER BY month DESC`,
  'Cross-source event density': `SELECT source_format,
    COUNT(*) as total,
    MIN(timestamp) as earliest,
    MAX(timestamp) as latest
FROM events GROUP BY source_format
ORDER BY total DESC`,
  'Top targeted vendors (KEV)': `SELECT json_extract(payload, '$.vendor') as vendor,
    COUNT(*) as vulns,
    SUM(CASE WHEN type='cve.ransomware' THEN 1 ELSE 0 END) as ransomware
FROM events WHERE source_format='cisa_kev'
GROUP BY vendor ORDER BY vulns DESC LIMIT 20`,
  'Major earthquakes': `SELECT timestamp,
    json_extract(payload, '$.magnitude') as mag,
    json_extract(payload, '$.place') as place,
    json_extract(payload, '$.depth_km') as depth_km
FROM events WHERE source_format='usgs'
  AND json_extract(payload, '$.magnitude') >= 4.5
ORDER BY json_extract(payload, '$.magnitude') DESC`,
  'GDP leaders by year': `SELECT json_extract(payload, '$.year') as year,
    json_extract(payload, '$.country_code') as code,
    json_extract(payload, '$.value_trillion') as gdp_trillion
FROM events WHERE source_format='worldbank'
  AND json_extract(payload, '$.country_code') IN ('USA','CHN','JPN','DEU','IND')
ORDER BY year DESC, gdp_trillion DESC LIMIT 50`,
};

function renderConsole() {
  const presetOptions = Object.keys(PRESET_QUERIES)
    .map(k => `<option value="${k}">${k || '— Preset Queries —'}</option>`)
    .join('');

  document.getElementById('zone-console').innerHTML = `
    <div class="card">
      <div class="console-header" onclick="toggleConsole()">
        <div class="card-title" style="margin-bottom:0">SQL Console</div>
        <div class="console-toggle" id="console-chevron">▼</div>
      </div>
      <div class="console-body" id="console-body">
        <textarea class="sql-input" id="sql-input"
          placeholder="SELECT * FROM events LIMIT 10"
          spellcheck="false">SELECT source_format, COUNT(*) as total, MIN(timestamp) as earliest, MAX(timestamp) as latest FROM events GROUP BY source_format ORDER BY total DESC</textarea>
        <div class="console-toolbar">
          <button class="btn-run" onclick="runQuery()">Run (Ctrl+Enter)</button>
          <select class="preset-select" id="preset-select" onchange="loadPreset(this.value)">
            ${presetOptions}
          </select>
        </div>
        <div id="console-output"></div>
      </div>
    </div>
  `;

  // Keyboard shortcut
  document.getElementById('sql-input').addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      runQuery();
    }
  });
}

function toggleConsole() {
  const body = document.getElementById('console-body');
  const chevron = document.getElementById('console-chevron');
  body.classList.toggle('open');
  chevron.classList.toggle('open');
}

function loadPreset(name) {
  const sql = PRESET_QUERIES[name];
  if (sql) {
    document.getElementById('sql-input').value = sql;
    runQuery();
  }
}

function runQuery() {
  const sql = document.getElementById('sql-input').value.trim();
  const output = document.getElementById('console-output');
  if (!sql) return;

  const t0 = performance.now();
  try {
    const rows = query(sql);
    const elapsed = (performance.now() - t0).toFixed(1);

    if (!rows.length) {
      output.innerHTML = `<div class="console-info">No results (${elapsed}ms)</div>`;
      return;
    }

    const cols = Object.keys(rows[0]);
    const headerHtml = cols.map(c => `<th>${c}</th>`).join('');
    const bodyHtml = rows.slice(0, 200).map(row =>
      '<tr>' + cols.map(c => {
        let val = row[c];
        if (val === null) val = '<span style="color:var(--k-text-dark)">NULL</span>';
        else if (typeof val === 'string' && val.length > 80) val = val.substring(0, 80) + '…';
        return `<td>${val}</td>`;
      }).join('') + '</tr>'
    ).join('');

    output.innerHTML = `
      <div class="console-info">${rows.length} row${rows.length !== 1 ? 's' : ''} · ${elapsed}ms</div>
      <div class="console-results">
        <table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table>
      </div>
    `;
  } catch (err) {
    output.innerHTML = `<div class="console-error">${err.message}</div>`;
  }
}
```

**Step 3: Verify console opens, runs preset queries, and displays results**

Run: Refresh browser, click "SQL Console" header to expand, click "Run", try preset queries from dropdown.
Expected: Collapsible console with monospace textarea, preset dropdown populates and auto-runs, results shown as dark-themed table with sticky headers. Ctrl+Enter shortcut works.

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): implement Zone 5 SQL console with preset queries"
```

---

### Task 8: Polish — Responsive Layout, Footer, Final Wiring

**Files:**
- Modify: `master-vault/observatory.html` (final CSS polish + responsive)

**Step 1: Add responsive polish and footer**

Add to CSS:

```css
/* ---- Responsive ---- */
@media (max-width: 600px) {
  .status-left { flex-direction: column; gap: 8px; }
  .status-stats { flex-wrap: wrap; }
  .risk-signals { grid-template-columns: 1fr; }
}

/* ---- Footer ---- */
.footer {
  text-align: center;
  padding: 32px 0;
  font-family: var(--k-mono);
  font-size: 0.7rem;
  color: var(--k-text-dark);
  border-top: 1px solid var(--k-border);
  margin-top: 32px;
}
```

Add footer HTML after the `#zone-console` section:

```html
<footer class="footer">
  Provara Intelligence Terminal · Data from vault.sqlite · Rendered locally, no server
</footer>
```

**Step 2: Ensure the console starts expanded by default**

Add to end of `renderConsole()`:

```javascript
// Auto-open console
toggleConsole();
```

Actually, start it collapsed (better for overview first). Remove this line if added.

**Step 3: Verify full page renders correctly on desktop and narrow viewport**

Run: Open in browser at full width and at 375px width (mobile simulation).
Expected: All five zones render, cards reflow to single-column on mobile, no horizontal overflow.

**Step 4: Commit**

```bash
git add master-vault/observatory.html
git commit -m "feat(observatory): add responsive polish and footer"
```

---

### Task 9: Integration Test — Full Verification

**Files:**
- None (verification only)

**Step 1: Serve and verify all five zones render with real data**

```bash
cd ~/provara/master-vault && python3 -m http.server 8080
```

Open `http://localhost:8080/observatory.html` and verify:

1. **Zone 1 (Status Bar):** Shows "20,886 events", "9 sources", "1990–2026", risk badge
2. **Zone 2 (Macro + Risk):** 2/10 spread value, regime badge, four signal lights with colors
3. **Zone 3 (Yield Curve):** Two charts — current curve vs 6mo prior, historical spread with red inversions
4. **Zone 4 (Sectors):** Three cards with mini charts and metrics
5. **Zone 5 (Console):** Collapsible, runs queries, results table works

**Step 2: Test all preset SQL queries**

Click each preset in the dropdown. All should execute without errors and return meaningful results.

**Step 3: Test offline behavior**

Disconnect from internet after first load (CDN scripts cached). Reload page — verify it still works from browser cache. If not, note in docs that first load requires internet for CDN.

**Step 4: Check load time**

Open DevTools → Network tab. Total load time should be under 3 seconds (success criterion #1 from design doc).

**Step 5: Final commit**

```bash
git add master-vault/observatory.html docs/plans/
git commit -m "feat(observatory): complete Intelligence Terminal — 5 zones, live vault data"
```

---

## Execution Notes

- **All code goes into a single file:** `master-vault/observatory.html`. No separate JS or CSS files.
- **CDN dependencies** load on first open; the vault.sqlite (10 MB) is the main payload.
- **The file sits alongside vault.sqlite** — user double-clicks to open (with local server) or uses `python3 -m http.server` for fetch API access.
- **Chart.js segment coloring** for the spread chart requires Chart.js 4.x which supports the `segment` option natively.
- **SQL.js parameterized queries** use `stmt.bind([params])` syntax.
- **Downsampling**: The 8,756 treasury events are sampled every 10th point for the spread chart (~876 points), keeping charts responsive.
