"""
storage_sqlite.py — Provara Protocol SQLite Vault Storage Engine

Single-file SQLite backend for append-only, cryptographically chained
event storage with Ed25519 signatures and SHA-256 chain hashing.

Design principles:
  - Single .sqlite file = single vault (portable, shippable artifact)
  - Ed25519 signatures per event (RFC 8032)
  - SHA-256 chain hash (each event hashes over the previous)
  - RFC 8785 canonical JSON serialization (via provara.canonical_json)
  - WAL mode for concurrent reads + crash safety
  - 50-year readability: schema is self-documenting, no ORMs

Dependencies:
  - cryptography >= 41.0
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from .backpack_signing import BackpackKeypair
from .canonical_json import canonical_bytes, sha256_hex
from .errors import BrokenCausalChainError, HashMismatchError, InvalidSignatureError


# ---------------------------------------------------------------------------
# Schema — self-documenting, no migrations needed for v1
# ---------------------------------------------------------------------------

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vault_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    seq         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT    NOT NULL UNIQUE,
    event_type  TEXT    NOT NULL,
    timestamp   TEXT    NOT NULL,
    payload     TEXT    NOT NULL,          -- canonical JSON
    prev_hash   TEXT    NOT NULL,          -- SHA-256 hex of previous event (or "GENESIS")
    event_hash  TEXT    NOT NULL UNIQUE,   -- SHA-256 hex of this event's canonical form
    signature   TEXT    NOT NULL,          -- Ed25519 signature (hex) over event_hash
    signer_pub      TEXT    NOT NULL,          -- Ed25519 public key (hex)
    schema_version  TEXT,                      -- sovereign schema version (NULL for backpack)
    payload_type    TEXT                        -- sovereign payload type (NULL for backpack)
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_payload_type ON events(payload_type);
"""


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Event:
    seq: int
    event_id: str
    event_type: str
    timestamp: str
    payload: dict
    prev_hash: str
    event_hash: str
    signature: str
    signer_pub: str
    schema_version: Optional[str] = None
    payload_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Vault — the core engine
# ---------------------------------------------------------------------------

class Vault:
    """A single SQLite-backed Provara vault."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.conn = sqlite3.connect(
            str(self.path),
            isolation_level=None,  # autocommit off — we manage txns explicitly
        )
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize schema and pragmas for durability + performance."""
        c = self.conn
        # --- Performance + safety pragmas ---
        c.execute("PRAGMA journal_mode=WAL;")         # concurrent reads, crash-safe
        c.execute("PRAGMA synchronous=NORMAL;")        # safe with WAL
        c.execute("PRAGMA foreign_keys=ON;")
        c.execute("PRAGMA busy_timeout=5000;")          # 5s retry on lock

        # --- Schema ---
        c.executescript(SCHEMA_SQL)

        # --- Metadata ---
        c.execute(
            "INSERT OR IGNORE INTO vault_meta (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        c.execute(
            "INSERT OR IGNORE INTO vault_meta (key, value) VALUES (?, ?)",
            ("created_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )
        c.commit()

    # -----------------------------------------------------------------------
    # Write path
    # -----------------------------------------------------------------------

    def append(
        self,
        event_type: str,
        payload: dict,
        private_key: Ed25519PrivateKey,
        schema_version: Optional[str] = None,
        payload_type: Optional[str] = None,
    ) -> Event:
        """Append a new event to the chain. Returns the stored Event."""

        # 1. Get previous hash
        row = self.conn.execute(
            "SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev_hash = row["event_hash"] if row else "GENESIS"

        # 2. Build event envelope
        event_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        envelope = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "payload": payload,
            "prev_hash": prev_hash,
        }

        # 3. Hash canonical form
        canonical = canonical_bytes(envelope)
        event_hash = sha256_hex(canonical)

        # 4. Sign the hash
        sig = private_key.sign(bytes.fromhex(event_hash))
        sig_hex = sig.hex()

        # 5. Extract public key
        pub_key = private_key.public_key()
        pub_hex = pub_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        # 6. Store
        self.conn.execute(
            """INSERT INTO events
               (event_id, event_type, timestamp, payload,
                prev_hash, event_hash, signature, signer_pub,
                schema_version, payload_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id, event_type, timestamp,
                canonical.decode("utf-8"),
                prev_hash, event_hash, sig_hex, pub_hex,
                schema_version, payload_type,
            ),
        )
        self.conn.commit()

        seq = self.conn.execute(
            "SELECT seq FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()["seq"]

        return Event(
            seq=seq,
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
            prev_hash=prev_hash,
            event_hash=event_hash,
            signature=sig_hex,
            signer_pub=pub_hex,
            schema_version=schema_version,
            payload_type=payload_type,
        )

    # -----------------------------------------------------------------------
    # Read path
    # -----------------------------------------------------------------------

    def get(self, event_id: str) -> Optional[Event]:
        """Retrieve a single event by ID."""
        row = self.conn.execute(
            "SELECT * FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return self._row_to_event(row) if row else None

    def chain(self, limit: int = 100, offset: int = 0) -> list[Event]:
        """Return events in chain order."""
        rows = self.conn.execute(
            "SELECT * FROM events ORDER BY seq ASC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]

    def query(self, event_type: str, limit: int = 100) -> list[Event]:
        """Query events by type."""
        rows = self.conn.execute(
            "SELECT * FROM events WHERE event_type = ? ORDER BY seq ASC LIMIT ?",
            (event_type, limit),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # -----------------------------------------------------------------------
    # Verification
    # -----------------------------------------------------------------------

    def verify_chain(self, strict: bool = False) -> tuple[bool, str]:
        """
        Walk the full chain and verify:
          1. Each event_hash matches its canonical content
          2. Each prev_hash matches the prior event's event_hash
          3. Each signature is valid for its event_hash + public key

        Returns (is_valid, message).

        When strict=True, raises HashMismatchError, BrokenCausalChainError,
        or InvalidSignatureError instead of returning (False, msg).
        """
        events = self.chain(limit=-1)  # all events

        for i, event in enumerate(events):
            # 1. Chain linkage (checked first — structural before content)
            if i == 0:
                if event.prev_hash != "GENESIS":
                    msg = f"First event prev_hash is not GENESIS (seq={event.seq})"
                    if strict:
                        raise BrokenCausalChainError(context=msg)
                    return False, msg
            else:
                if event.prev_hash != events[i - 1].event_hash:
                    msg = (
                        f"Chain break at seq={event.seq}: "
                        f"prev_hash does not match seq={events[i-1].seq}"
                    )
                    if strict:
                        raise BrokenCausalChainError(context=msg)
                    return False, msg

            # 2. Hash integrity
            envelope = {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "payload": event.payload,
                "prev_hash": event.prev_hash,
            }
            canonical = canonical_bytes(envelope)
            computed_hash = sha256_hex(canonical)

            if computed_hash != event.event_hash:
                msg = f"Hash mismatch at seq={event.seq} ({event.event_id})"
                if strict:
                    raise HashMismatchError(context=msg)
                return False, msg

            # 3. Signature verification
            try:
                pub_key = Ed25519PublicKey.from_public_bytes(
                    bytes.fromhex(event.signer_pub)
                )
                pub_key.verify(
                    bytes.fromhex(event.signature),
                    bytes.fromhex(event.event_hash),
                )
            except Exception as e:
                msg = f"Signature invalid at seq={event.seq}: {e}"
                if strict:
                    raise InvalidSignatureError(context=msg) from e
                return False, msg

        return True, f"Chain valid — {len(events)} events verified."

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> Event:
        return Event(
            seq=row["seq"],
            event_id=row["event_id"],
            event_type=row["event_type"],
            timestamp=row["timestamp"],
            payload=json.loads(row["payload"]).get("payload", {}),
            prev_hash=row["prev_hash"],
            event_hash=row["event_hash"],
            signature=row["signature"],
            signer_pub=row["signer_pub"],
            schema_version=row["schema_version"],
            payload_type=row["payload_type"],
        )

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# Alias for callers that prefer the explicit backend name.
SQLiteVault = Vault


# ---------------------------------------------------------------------------
# Key management helpers
# ---------------------------------------------------------------------------

def generate_keypair() -> tuple[Ed25519PrivateKey, str]:
    """Generate a new Ed25519 keypair via BackpackKeypair.

    Returns (private_key, public_key_hex) for backward compatibility
    with callers that work with raw hex public keys.
    """
    kp = BackpackKeypair.generate()
    pub_hex = kp.public_key.public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    return kp.private_key, pub_hex


def export_private_key(sk: Ed25519PrivateKey) -> bytes:
    """Export private key as PEM bytes."""
    return sk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
