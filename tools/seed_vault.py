#!/usr/bin/env python3
"""
seed_vault.py — Generate realistic data for Provara SQLite vault visualization.

Two modes:
  1. Synthetic: Generate 12-24 months of agent memory events (PSMC format)
  2. Import:    Load public datasets (GitHub, USGS, NVD) into vault format

Usage:
    # Generate 1 year of synthetic agent memory events
    python tools/seed_vault.py synthetic --months 12 --output demo_vault.sqlite

    # Generate 2 years, heavy activity
    python tools/seed_vault.py synthetic --months 24 --intensity high --output demo_vault.sqlite

    # Import a downloaded GitHub Archive hour
    python tools/seed_vault.py import-github data/2024-01-01-15.json.gz --output demo_vault.sqlite

    # Import USGS earthquake CSV
    python tools/seed_vault.py import-usgs data/2.5_month.csv --output demo_vault.sqlite
"""

import argparse
import csv
import gzip
import hashlib
import json
import random
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path for provara imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ---------------------------------------------------------------------------
# Schema (same as migrate_ndjson.py)
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vault_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq             INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT    NOT NULL UNIQUE,
    type            TEXT    NOT NULL,
    timestamp       TEXT    NOT NULL,
    payload         TEXT    NOT NULL,
    actor           TEXT,
    actor_key_id    TEXT,
    namespace       TEXT,
    ts_logical      INTEGER,
    prev_event_hash TEXT,
    sig             TEXT,
    raw_canonical   TEXT,
    hash            TEXT,
    prev_hash       TEXT,
    tags            TEXT,
    source_format   TEXT    NOT NULL DEFAULT 'synthetic'
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_actor ON events(actor);
CREATE INDEX IF NOT EXISTS idx_events_tags ON events(tags);
CREATE INDEX IF NOT EXISTS idx_events_format ON events(source_format);
"""


def init_db(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Synthetic data generation
# ---------------------------------------------------------------------------

AGENTS = [
    ("claude-code", "The Architect", 0.35),   # Most active
    ("gemini", "The Scout", 0.25),
    ("codex", "The Operator", 0.20),
    ("openclaw", "The Tinkerer", 0.10),
    ("qwen", "The Auditor", 0.10),
]

EVENT_TYPES = {
    "decision": {
        "weight": 0.15,
        "tags_pool": ["architecture", "infrastructure", "security", "ux", "api", "database", "deployment"],
        "payloads": [
            {"title": "Adopt SQLite for vault storage", "choice": "SQLite WAL mode", "reason": "Single-file portability + SQL query support"},
            {"title": "Use Ed25519 for all signing", "choice": "Ed25519 via cryptography lib", "reason": "RFC 8032 compliance, deterministic"},
            {"title": "Implement rate limiting", "choice": "Token bucket at gateway", "reason": "Protects downstream services"},
            {"title": "Switch to async event processing", "choice": "asyncio with bounded queue", "reason": "Better throughput under load"},
            {"title": "Add RBAC to vault operations", "choice": "Tier-based (L0-L3)", "reason": "Granular access control"},
            {"title": "Migrate CI to GitHub Actions", "choice": "Reusable workflows", "reason": "Better caching, matrix builds"},
            {"title": "Adopt RFC 8785 canonical JSON", "choice": "Custom minimal implementation", "reason": "No external deps, spec compliance"},
            {"title": "Use content-addressed event IDs", "choice": "SHA-256 prefix (24 hex chars)", "reason": "Dedup-safe, deterministic"},
        ],
    },
    "milestone": {
        "weight": 0.12,
        "tags_pool": ["release", "infrastructure", "testing", "deployment", "documentation", "performance"],
        "payloads": [
            {"description": "First 100 tests passing", "metric": "100 tests, 0 failures"},
            {"description": "Vault v1.0 released to PyPI", "metric": "v1.0.0 published"},
            {"description": "Provara.dev site deployed", "metric": "Cloudflare Pages live"},
            {"description": "Agent memory system operational", "metric": "5 agents connected"},
            {"description": "Compliance test suite complete", "metric": "17 spec tests green"},
            {"description": "Sub-second vault verification", "metric": "0.3s for 10K events"},
            {"description": "Multi-device sync working", "metric": "3 devices merged cleanly"},
            {"description": "Docker read-only vault mount", "metric": "Security hardened"},
        ],
    },
    "note": {
        "weight": 0.30,
        "tags_pool": ["debugging", "research", "observation", "learning", "pattern", "idea", "todo"],
        "payloads": [
            {"content": "SQLite WAL mode gives concurrent reads without blocking writes"},
            {"content": "Ed25519 signatures are 64 bytes, fitting nicely in base64 (88 chars)"},
            {"content": "RFC 8785 requires sorted keys AND no whitespace — both matter for hash stability"},
            {"content": "Python json.dumps with sort_keys=True matches RFC 8785 for ASCII-safe content"},
            {"content": "Append-only is a logical invariant, not a physical one — enforced by crypto, not format"},
            {"content": "NDJSON is great for streaming but terrible for random access — SQLite wins here"},
            {"content": "Content-addressed IDs make dedup trivial during sync — same content = same ID"},
            {"content": "The reducer pattern means same events always produce same state — deterministic replay"},
            {"content": "Vault sealing needs to be reversible in dev but permanent in production"},
            {"content": "Git hooks can enforce vault integrity checks before commits"},
            {"content": "X25519 key exchange + ChaCha20-Poly1305 for agent-to-agent encrypted messages"},
            {"content": "Merkle trees over events give O(log n) proof that an event exists in the chain"},
        ],
    },
    "belief": {
        "weight": 0.08,
        "tags_pool": ["hypothesis", "assessment", "prediction", "observation"],
        "payloads": [
            {"subject": "vault_performance", "belief": "SQLite can handle 1M+ events without degradation", "confidence": 0.85},
            {"subject": "market_trend", "belief": "AI agent memory will become a product category by 2027", "confidence": 0.70},
            {"subject": "security_posture", "belief": "Ed25519 + SHA-256 chain is sufficient for 10-year integrity", "confidence": 0.95},
            {"subject": "adoption", "belief": "Protocol needs a compelling demo before devs will try it", "confidence": 0.80},
            {"subject": "interop", "belief": "Multi-agent teams need shared state, not shared memory", "confidence": 0.75},
        ],
    },
    "correction": {
        "weight": 0.05,
        "tags_pool": ["bugfix", "misunderstanding", "update"],
        "payloads": [
            {"original": "NDJSON is faster than SQLite for small vaults", "corrected": "SQLite is faster even for small vaults due to indexing"},
            {"original": "Vault sync requires both parties online", "corrected": "Delta bundles allow offline sync"},
            {"original": "Ed25519 keys are 64 bytes", "corrected": "Ed25519 public keys are 32 bytes, signatures are 64 bytes"},
        ],
    },
    "identity": {
        "weight": 0.02,
        "tags_pool": ["system", "configuration"],
        "payloads": [
            {"entity": "Hunt Information Systems LLC", "role": "owner", "agents": ["claude-code", "gemini", "codex", "openclaw", "qwen"]},
        ],
    },
    "observation": {
        "weight": 0.18,
        "tags_pool": ["codebase", "performance", "security", "deployment", "testing", "monitoring"],
        "payloads": [
            {"subject": "test_suite", "predicate": "status", "value": "582 passed, 8 skipped"},
            {"subject": "vault_size", "predicate": "measured", "value": "184 KB for 35 events"},
            {"subject": "sync_latency", "predicate": "measured", "value": "12ms for 100-event merge"},
            {"subject": "memory_usage", "predicate": "measured", "value": "8.2 MB peak during verification"},
            {"subject": "api_response_time", "predicate": "measured", "value": "p99 = 45ms"},
            {"subject": "error_rate", "predicate": "measured", "value": "0.02% over 24h"},
            {"subject": "deployment", "predicate": "completed", "value": "v1.0.1 to PyPI"},
            {"subject": "security_scan", "predicate": "clean", "value": "0 critical, 0 high, 2 medium"},
        ],
    },
    "research": {
        "weight": 0.10,
        "tags_pool": ["paper", "competitor", "standard", "protocol", "tool"],
        "payloads": [
            {"topic": "SCITT supply chain transparency", "finding": "IETF draft aligns well with Provara attestation model"},
            {"topic": "Sigstore keyless signing", "finding": "Can anchor vault state without managing long-lived keys"},
            {"topic": "RFC 3161 timestamping", "finding": "Free TSA services available for non-commercial use"},
            {"topic": "Post-quantum cryptography", "finding": "CRYSTALS-Dilithium as hybrid alongside Ed25519"},
            {"topic": "SQLite as application file format", "finding": "Used by Firefox, Chrome, iOS — proven at scale"},
            {"topic": "Merkle tree verification", "finding": "Can prove single event membership in O(log n)"},
        ],
    },
}

# Activity patterns (hour weights — when do agents work?)
HOUR_WEIGHTS = {
    # US Eastern working hours (heavy), some late night
    0: 0.3, 1: 0.2, 2: 0.15, 3: 0.1, 4: 0.05, 5: 0.05,
    6: 0.1, 7: 0.3, 8: 0.6, 9: 0.9, 10: 1.0, 11: 0.95,
    12: 0.7, 13: 0.85, 14: 1.0, 15: 0.95, 16: 0.8, 17: 0.6,
    18: 0.4, 19: 0.5, 20: 0.6, 21: 0.7, 22: 0.5, 23: 0.4,
}

# Day-of-week weights (weekdays heavy, weekends lighter)
DAY_WEIGHTS = {0: 1.0, 1: 1.0, 2: 0.9, 3: 1.0, 4: 0.8, 5: 0.3, 6: 0.2}

INTENSITY_MAP = {"low": 3, "medium": 8, "high": 15}


def generate_synthetic(conn, months=12, intensity="medium", start_date=None):
    """Generate synthetic vault events over a time period."""
    events_per_day = INTENSITY_MAP.get(intensity, 8)

    if start_date is None:
        start_date = datetime.now(timezone.utc) - timedelta(days=months * 30)

    end_date = start_date + timedelta(days=months * 30)
    current = start_date

    prev_hash = "0" * 64
    seq = 0
    total = 0

    # Build weighted type selector
    type_names = list(EVENT_TYPES.keys())
    type_weights = [EVENT_TYPES[t]["weight"] for t in type_names]

    while current < end_date:
        # How many events today?
        dow = current.weekday()
        day_factor = DAY_WEIGHTS.get(dow, 0.5)
        n_events = max(1, int(events_per_day * day_factor * random.uniform(0.5, 1.5)))

        for _ in range(n_events):
            # Pick time of day (weighted)
            hour = random.choices(range(24), weights=[HOUR_WEIGHTS[h] for h in range(24)])[0]
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            ts = current.replace(hour=hour, minute=minute, second=second, microsecond=random.randint(0, 999999))

            # Pick event type (weighted)
            event_type = random.choices(type_names, weights=type_weights)[0]
            type_info = EVENT_TYPES[event_type]

            # Pick agent (weighted)
            agent_name, _, _ = random.choices(AGENTS, weights=[a[2] for a in AGENTS])[0]

            # Pick payload
            payload = random.choice(type_info["payloads"]).copy()

            # Pick tags
            n_tags = random.randint(1, 3)
            tags = random.sample(type_info["tags_pool"], min(n_tags, len(type_info["tags_pool"])))

            # Build event
            event_id = str(uuid.uuid4())
            event_hash = hashlib.sha256(
                json.dumps({"id": event_id, "payload": payload, "ts": ts.isoformat()}, sort_keys=True).encode()
            ).hexdigest()

            conn.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, type, timestamp, payload, actor, tags,
                    hash, prev_hash, ts_logical, source_format)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    event_type,
                    ts.isoformat(),
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    agent_name,
                    json.dumps(tags),
                    event_hash,
                    prev_hash,
                    seq,
                    "synthetic",
                ),
            )

            prev_hash = event_hash
            seq += 1
            total += 1

        current += timedelta(days=1)

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# GitHub Archive importer
# ---------------------------------------------------------------------------

def import_github(conn, path):
    """Import a GitHub Archive NDJSON (or .gz) file."""
    path = Path(path)
    total = 0

    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_id = str(ev.get("id", uuid.uuid4()))
            event_type = ev.get("type", "unknown")
            ts = ev.get("created_at", "")
            actor = ev.get("actor", {}).get("login", "unknown")
            repo = ev.get("repo", {}).get("name", "")

            payload = {
                "repo": repo,
                "action": ev.get("payload", {}).get("action", ""),
            }
            # Add type-specific fields
            gh_payload = ev.get("payload", {})
            if event_type == "PushEvent":
                payload["commits"] = gh_payload.get("size", 0)
                payload["ref"] = gh_payload.get("ref", "")
            elif event_type in ("PullRequestEvent", "IssuesEvent"):
                pr_or_issue = gh_payload.get("pull_request") or gh_payload.get("issue") or {}
                payload["title"] = pr_or_issue.get("title", "")[:100]
                payload["state"] = pr_or_issue.get("state", "")

            tags = [event_type, repo.split("/")[0] if "/" in repo else repo]

            conn.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, type, timestamp, payload, actor, tags, source_format)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    event_type,
                    ts,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    actor,
                    json.dumps(tags),
                    "github",
                ),
            )
            total += 1

            if total % 10000 == 0:
                conn.commit()
                print(f"  ... {total:,} events imported", flush=True)

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# USGS Earthquake importer
# ---------------------------------------------------------------------------

def import_usgs(conn, path):
    """Import a USGS earthquake CSV file."""
    path = Path(path)
    total = 0

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            event_id = row.get("id", str(uuid.uuid4()))
            ts = row.get("time", "")

            payload = {
                "magnitude": float(row.get("mag", 0) or 0),
                "mag_type": row.get("magType", ""),
                "depth_km": float(row.get("depth", 0) or 0),
                "latitude": float(row.get("latitude", 0) or 0),
                "longitude": float(row.get("longitude", 0) or 0),
                "place": row.get("place", ""),
                "status": row.get("status", ""),
            }

            mag = payload["magnitude"]
            if mag >= 6.0:
                event_type = "earthquake.major"
            elif mag >= 4.0:
                event_type = "earthquake.moderate"
            else:
                event_type = "earthquake.minor"

            tags = [event_type, row.get("net", ""), row.get("magType", "")]

            conn.execute(
                """INSERT OR IGNORE INTO events
                   (event_id, type, timestamp, payload, tags, source_format)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    event_type,
                    ts,
                    json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    json.dumps([t for t in tags if t]),
                    "usgs",
                ),
            )
            total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# NVD CVE importer
# ---------------------------------------------------------------------------

def import_nvd(conn, path):
    """Import a NIST NVD CVE JSON feed (.json or .json.gz)."""
    path = Path(path)

    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
    else:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

    items = data.get("CVE_Items") or data.get("vulnerabilities", [])
    total = 0

    for item in items:
        cve = item.get("cve", item)
        meta = cve.get("CVE_data_meta") or cve.get("id", "")
        cve_id = meta.get("ID", meta) if isinstance(meta, dict) else str(meta)

        # Timestamp
        ts = item.get("publishedDate") or item.get("published", "")

        # Description
        desc_data = cve.get("description", {})
        if isinstance(desc_data, dict):
            descs = desc_data.get("description_data", [])
            description = descs[0].get("value", "") if descs else ""
        else:
            descriptions = item.get("descriptions", [])
            description = descriptions[0].get("value", "") if descriptions else ""

        # CVSS score
        impact = item.get("impact", {})
        cvss_v3 = impact.get("baseMetricV3", {}).get("cvssV3", {})
        score = cvss_v3.get("baseScore", 0)
        severity = cvss_v3.get("baseSeverity", "UNKNOWN")

        if not score:
            metrics = item.get("metrics", {})
            v31 = metrics.get("cvssMetricV31", [{}])
            if v31:
                cvss_data = v31[0].get("cvssData", {})
                score = cvss_data.get("baseScore", 0)
                severity = cvss_data.get("baseSeverity", "UNKNOWN")

        payload = {
            "cve_id": cve_id,
            "description": description[:500],
            "cvss_score": score,
            "severity": severity,
        }

        event_type = f"cve.{severity.lower()}" if severity != "UNKNOWN" else "cve.unscored"
        tags = ["cve", severity.lower()]

        conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, type, timestamp, payload, tags, source_format)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                cve_id,
                event_type,
                ts,
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                json.dumps(tags),
                "nvd",
            ),
        )
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed a Provara SQLite vault with data")
    sub = parser.add_subparsers(dest="command")

    # Synthetic
    syn = sub.add_parser("synthetic", help="Generate synthetic agent memory events")
    syn.add_argument("--months", type=int, default=12, help="Months of data (default: 12)")
    syn.add_argument("--intensity", choices=["low", "medium", "high"], default="medium")
    syn.add_argument("--output", "-o", default="demo_vault.sqlite")

    # GitHub
    gh = sub.add_parser("import-github", help="Import GitHub Archive NDJSON")
    gh.add_argument("file", help="Path to .json or .json.gz file")
    gh.add_argument("--output", "-o", default="demo_vault.sqlite")

    # USGS
    usgs = sub.add_parser("import-usgs", help="Import USGS earthquake CSV")
    usgs.add_argument("file", help="Path to CSV file")
    usgs.add_argument("--output", "-o", default="demo_vault.sqlite")

    # NVD
    nvd = sub.add_parser("import-nvd", help="Import NIST NVD CVE feed")
    nvd.add_argument("file", help="Path to .json or .json.gz file")
    nvd.add_argument("--output", "-o", default="demo_vault.sqlite")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    conn = init_db(args.output)
    t0 = time.time()

    if args.command == "synthetic":
        print(f"Generating {args.months} months of synthetic data ({args.intensity} intensity)...")
        count = generate_synthetic(conn, months=args.months, intensity=args.intensity)
    elif args.command == "import-github":
        print(f"Importing GitHub Archive: {args.file}")
        count = import_github(conn, args.file)
    elif args.command == "import-usgs":
        print(f"Importing USGS earthquake data: {args.file}")
        count = import_usgs(conn, args.file)
    elif args.command == "import-nvd":
        print(f"Importing NVD CVE feed: {args.file}")
        count = import_nvd(conn, args.file)
    else:
        parser.print_help()
        return

    elapsed = time.time() - t0
    size = Path(args.output).stat().st_size

    print(f"\nDone: {count:,} events → {args.output} ({size/1024:.1f} KB) in {elapsed:.1f}s")

    # Print summary
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    by_format = conn.execute(
        "SELECT source_format, COUNT(*) FROM events GROUP BY source_format"
    ).fetchall()

    print(f"Total events in vault: {total:,}")
    for fmt, cnt in by_format:
        print(f"  {fmt}: {cnt:,}")

    conn.close()


if __name__ == "__main__":
    main()
