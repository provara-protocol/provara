#!/usr/bin/env python3
"""
import_datasets.py — Import downloaded public datasets into a Provara SQLite vault.

Handles: Treasury yields, CISA KEV, MITRE ATT&CK, USGS GeoJSON,
         World Bank GDP, GDELT events, and more.

Usage:
    python tools/import_datasets.py --output vault.sqlite
"""

import csv
import json
import os
import sqlite3
import sys
import time
import uuid
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Reuse schema from seed_vault
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
    source_format   TEXT    NOT NULL DEFAULT 'imported'
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


def _insert(conn, event_id, etype, ts, payload, tags=None, source="imported", actor=None):
    try:
        conn.execute(
            """INSERT OR IGNORE INTO events
               (event_id, type, timestamp, payload, tags, source_format, actor)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(event_id),
                etype,
                ts,
                json.dumps(payload, sort_keys=True, separators=(",", ":")) if isinstance(payload, dict) else payload,
                json.dumps(tags) if tags else None,
                source,
                actor,
            ),
        )
        return True
    except sqlite3.IntegrityError:
        return False


# ---------------------------------------------------------------------------
# Treasury Yield Curve (1990-2024)
# ---------------------------------------------------------------------------

def import_treasury(conn, path):
    """Import Treasury yield curve CSV — one event per trading day."""
    total = 0
    tenors = []

    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        tenors = [h for h in (reader.fieldnames or []) if h != "Date"]

        for row in reader:
            date_str = row.get("Date", "")
            if not date_str:
                continue

            # Parse date (MM/DD/YY format)
            parts = date_str.split("/")
            if len(parts) == 3:
                m, d, y = parts
                year = int(y)
                if year < 100:
                    year += 2000 if year < 50 else 1900
                ts = f"{year:04d}-{int(m):02d}-{int(d):02d}T16:00:00Z"
            else:
                ts = date_str

            yields = {}
            for tenor in tenors:
                val = row.get(tenor, "").strip()
                if val and val != "N/A":
                    try:
                        yields[tenor.strip()] = float(val)
                    except ValueError:
                        pass

            if not yields:
                continue

            payload = {"yields": yields, "date": date_str}

            # Classify the curve state
            y2 = yields.get("2 Yr", 0)
            y10 = yields.get("10 Yr", 0)
            spread = round(y10 - y2, 2) if y2 and y10 else None
            if spread is not None:
                payload["spread_2_10"] = spread

            etype = "yield.normal" if (spread and spread > 0) else "yield.inverted"

            _insert(conn, f"tsy-{date_str}", etype, ts, payload,
                    tags=["treasury", "yield-curve", "macro"], source="treasury")
            total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# CISA Known Exploited Vulnerabilities
# ---------------------------------------------------------------------------

def import_cisa_kev(conn, path):
    """Import CISA KEV — one event per exploited vulnerability."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    vulns = data.get("vulnerabilities", [])
    total = 0

    for v in vulns:
        cve_id = v.get("cveID", str(uuid.uuid4()))
        ts = v.get("dateAdded", "")
        if ts and len(ts) == 10:
            ts += "T00:00:00Z"

        payload = {
            "cve_id": cve_id,
            "vendor": v.get("vendorProject", ""),
            "product": v.get("product", ""),
            "name": v.get("vulnerabilityName", ""),
            "description": v.get("shortDescription", "")[:300],
            "action": v.get("requiredAction", "")[:200],
            "due_date": v.get("dueDate", ""),
            "known_ransomware": v.get("knownRansomwareCampaignUse", "Unknown"),
        }

        ransomware = "Yes" in str(v.get("knownRansomwareCampaignUse", ""))
        etype = "cve.ransomware" if ransomware else "cve.exploited"
        tags = ["cisa", "kev", v.get("vendorProject", "").lower()]

        _insert(conn, cve_id, etype, ts, payload, tags=tags, source="cisa_kev")
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# MITRE ATT&CK
# ---------------------------------------------------------------------------

def import_mitre_attack(conn, path):
    """Import MITRE ATT&CK techniques and groups."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    objects = data.get("objects", [])
    total = 0

    for obj in objects:
        obj_type = obj.get("type", "")
        if obj_type not in ("attack-pattern", "intrusion-set", "malware", "tool", "campaign"):
            continue

        obj_id = obj.get("id", str(uuid.uuid4()))
        name = obj.get("name", "")
        ts = obj.get("created", obj.get("modified", ""))

        # Extract ATT&CK ID
        ext_refs = obj.get("external_references", [])
        attack_id = ""
        for ref in ext_refs:
            if ref.get("source_name") == "mitre-attack":
                attack_id = ref.get("external_id", "")
                break

        description = obj.get("description", "")[:300]

        # Extract kill chain phases
        phases = [p.get("phase_name", "") for p in obj.get("kill_chain_phases", [])]

        payload = {
            "attack_id": attack_id,
            "name": name,
            "description": description,
            "object_type": obj_type,
            "platforms": obj.get("x_mitre_platforms", []),
            "kill_chain_phases": phases,
        }

        type_map = {
            "attack-pattern": "attack.technique",
            "intrusion-set": "attack.group",
            "malware": "attack.malware",
            "tool": "attack.tool",
            "campaign": "attack.campaign",
        }
        etype = type_map.get(obj_type, "attack.other")
        tags = ["mitre", "att&ck", obj_type]
        if phases:
            tags.extend(phases[:2])

        _insert(conn, obj_id, etype, ts, payload, tags=tags, source="mitre_attack")
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# World Bank GDP
# ---------------------------------------------------------------------------

def import_worldbank(conn, path):
    """Import World Bank GDP data — one event per country per year."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # World Bank API returns [metadata, records]
    records = data[1] if len(data) > 1 else []
    total = 0

    for rec in records:
        country = rec.get("country", {}).get("value", "Unknown")
        country_code = rec.get("countryiso3code") or rec.get("country", {}).get("id", "")
        year = rec.get("date", "")
        value = rec.get("value")

        if value is None:
            continue

        ts = f"{year}-06-30T00:00:00Z"
        event_id = f"wb-gdp-{country_code}-{year}"

        payload = {
            "country": country,
            "country_code": country_code,
            "indicator": "GDP (current US$)",
            "year": int(year) if year else 0,
            "value_usd": value,
            "value_trillion": round(value / 1e12, 3) if value else 0,
        }

        etype = "economic.gdp"
        tags = ["worldbank", "gdp", country_code.lower()]

        _insert(conn, event_id, etype, ts, payload, tags=tags, source="worldbank")
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# USGS Earthquake GeoJSON
# ---------------------------------------------------------------------------

def import_usgs_geojson(conn, path):
    """Import USGS earthquake GeoJSON feed."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])
    total = 0

    for feat in features:
        props = feat.get("properties", {})
        coords = feat.get("geometry", {}).get("coordinates", [0, 0, 0])

        event_id = feat.get("id", str(uuid.uuid4()))
        ts_ms = props.get("time", 0)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts_ms / 1000)) if ts_ms else ""

        mag = props.get("mag", 0) or 0
        payload = {
            "magnitude": mag,
            "mag_type": props.get("magType", ""),
            "place": props.get("place", ""),
            "depth_km": coords[2] if len(coords) > 2 else 0,
            "latitude": coords[1] if len(coords) > 1 else 0,
            "longitude": coords[0] if coords else 0,
            "status": props.get("status", ""),
            "tsunami": props.get("tsunami", 0),
            "felt": props.get("felt"),
            "alert": props.get("alert"),
        }

        if mag >= 6.0:
            etype = "earthquake.major"
        elif mag >= 4.0:
            etype = "earthquake.moderate"
        else:
            etype = "earthquake.minor"

        tags = ["usgs", "earthquake", props.get("net", "")]
        if props.get("tsunami"):
            tags.append("tsunami")
        if props.get("alert"):
            tags.append(f"alert-{props['alert']}")

        _insert(conn, event_id, etype, ts, payload, tags=tags, source="usgs")
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# GDELT Events
# ---------------------------------------------------------------------------

def import_gdelt(conn, path):
    """Import GDELT event CSV (from zip or plain CSV)."""
    total = 0

    if str(path).endswith(".zip"):
        with zipfile.ZipFile(path) as zf:
            csv_name = [n for n in zf.namelist() if n.endswith(".CSV") or n.endswith(".csv")]
            if not csv_name:
                return 0
            with zf.open(csv_name[0]) as cf:
                content = cf.read().decode("utf-8", errors="replace")
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

    # GDELT export CSV is tab-delimited with no header
    # Key columns: 0=GlobalEventID, 1=Day, 5=Actor1Code, 15=Actor2Code,
    # 26=GoldsteinScale, 30=NumMentions, 34=ActionGeo_CountryCode,
    # 53=SourceURL
    for line in content.strip().split("\n"):
        cols = line.split("\t")
        if len(cols) < 40:
            continue

        event_id = f"gdelt-{cols[0]}"
        day = cols[1]  # YYYYMMDD
        if len(day) == 8:
            ts = f"{day[:4]}-{day[4:6]}-{day[6:8]}T00:00:00Z"
        else:
            ts = day

        actor1 = cols[5] if len(cols) > 5 else ""
        actor2 = cols[15] if len(cols) > 15 else ""

        try:
            goldstein = float(cols[30]) if len(cols) > 30 and cols[30] else 0
        except ValueError:
            goldstein = 0

        try:
            num_mentions = int(cols[31]) if len(cols) > 31 and cols[31] else 0
        except ValueError:
            num_mentions = 0

        country = cols[37] if len(cols) > 37 else ""
        event_code = cols[26] if len(cols) > 26 else ""

        payload = {
            "actor1": actor1,
            "actor2": actor2,
            "event_code": event_code,
            "goldstein_scale": goldstein,
            "num_mentions": num_mentions,
            "country": country,
        }

        if goldstein > 5:
            etype = "geopolitical.cooperation"
        elif goldstein < -5:
            etype = "geopolitical.conflict"
        else:
            etype = "geopolitical.event"

        tags = ["gdelt", country.lower()] if country else ["gdelt"]

        _insert(conn, event_id, etype, ts, payload, tags=tags, source="gdelt")
        total += 1

    conn.commit()
    return total


# ---------------------------------------------------------------------------
# Main — import all available datasets
# ---------------------------------------------------------------------------

DATA_DIR = Path("/tmp/vault_data")

IMPORTERS = [
    ("Treasury Yields (1990-2024)", "treasury_yields.csv", import_treasury),
    ("CISA KEV", "cisa_kev.json", import_cisa_kev),
    ("MITRE ATT&CK", "mitre_attack.json", import_mitre_attack),
    ("World Bank GDP", "worldbank_gdp.json", import_worldbank),
    ("USGS Earthquakes", "usgs_all_day.geojson", import_usgs_geojson),
    ("GDELT Events", "gdelt_latest.csv.zip", import_gdelt),
]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Import all downloaded datasets into vault")
    parser.add_argument("--output", "-o", default="/tmp/demo_vault.sqlite")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    conn = init_db(args.output)

    print(f"Importing datasets into {args.output}\n")
    grand_total = 0

    for name, filename, importer in IMPORTERS:
        filepath = data_dir / filename
        if not filepath.exists():
            print(f"  SKIP  {name} — {filename} not found")
            continue

        t0 = time.time()
        try:
            count = importer(conn, filepath)
            elapsed = time.time() - t0
            print(f"  OK    {name}: {count:,} events ({elapsed:.1f}s)")
            grand_total += count
        except Exception as e:
            print(f"  FAIL  {name}: {e}")

    # Final stats
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    by_format = conn.execute(
        "SELECT source_format, COUNT(*) FROM events GROUP BY source_format ORDER BY COUNT(*) DESC"
    ).fetchall()

    print(f"\n{'='*50}")
    print(f"Imported: {grand_total:,} new events")
    print(f"Total in vault: {total:,} events")
    print(f"\nBy source:")
    for fmt, cnt in by_format:
        print(f"  {fmt}: {cnt:,}")

    size = os.path.getsize(args.output)
    print(f"\nVault size: {size/1024/1024:.1f} MB")

    conn.close()


if __name__ == "__main__":
    main()
