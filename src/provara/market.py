"""
market.py — Provara Market Intelligence Extensions

Provides high-level helpers for recording high-alpha market signals,
liquidity depth, and AI-Hedge-Fund simulation results.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from pathlib import Path

from .backpack_signing import sign_event, load_private_key_b64
from .canonical_json import canonical_hash, canonical_dumps
from .sync_v0 import load_events

def record_market_alpha(
    vault_path: Path,
    keyfile: Path,
    ticker: str,
    signal: str,
    conviction: float,
    time_horizon: str,
    rationale: Optional[str] = None,
    actor: str = "market_analyst",
) -> Dict[str, Any]:
    """
    Record a high-conviction market signal.
    """
    data = {
        "ticker": ticker,
        "signal": signal.upper(),
        "conviction": conviction,
        "time_horizon": time_horizon,
    }
    if rationale:
        data["rationale"] = rationale

    return _append_market_event(
        vault_path, keyfile, "MARKET_ALPHA", ticker, "signal", data, actor
    )

def record_hedge_fund_sim(
    vault_path: Path,
    keyfile: Path,
    simulation_id: str,
    strategy_id: str,
    returns_pct: float,
    ticker: Optional[str] = None,
    actor: str = "simulation_engine",
) -> Dict[str, Any]:
    """
    Record an AI-Hedge-Fund simulation result.
    """
    data = {
        "simulation_id": simulation_id,
        "strategy_id": strategy_id,
        "returns_pct": returns_pct,
    }
    if ticker:
        data["ticker"] = ticker

    return _append_market_event(
        vault_path, keyfile, "HEDGE_FUND_SIM", strategy_id, "performance", data, actor
    )

def _append_market_event(
    vault_path: Path,
    keyfile: Path,
    event_type: str,
    subject: str,
    predicate: str,
    value: Dict[str, Any],
    actor: str,
) -> Dict[str, Any]:
    # 1. Load keys — handle both {"keys":[...]} and flat {kid: b64} formats
    import json
    raw = json.loads(keyfile.read_text())
    if "keys" in raw and isinstance(raw["keys"], list):
        entry = raw["keys"][0]
        kid = str(entry["key_id"])
        priv = load_private_key_b64(str(entry["private_key_b64"]))
    else:
        kid = next(k for k in raw if k != "WARNING")
        priv = load_private_key_b64(raw[kid])

    # 2. Find prev_hash
    events_file = vault_path / "events" / "events.ndjson"
    all_events = load_events(events_file)
    actor_events = [e for e in all_events if e.get("actor_key_id") == kid]
    prev_hash = actor_events[-1].get("event_id") if actor_events else None

    # 3. Build event
    event = {
        "type": "OBSERVATION",
        "actor": actor,
        "prev_event_hash": prev_hash,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "payload": {
            "subject": f"market:{subject}",
            "predicate": predicate,
            "value": value,
            "confidence": 1.0,
            "extension": f"provara.market.{event_type.lower()}"
        }
    }

    # 4. Content ID
    eid_hash = canonical_hash(event)
    event["event_id"] = f"evt_{eid_hash[:24]}"

    # 5. Sign
    signed = sign_event(event, priv, kid)

    # 6. Append
    with open(events_file, "a", encoding="utf-8") as f:
        f.write(canonical_dumps(signed) + "\n")

    return signed
