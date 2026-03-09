"""
Provara Managed Vault Service (SaaS Backend)
Version: 0.1.0 (MVP)
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid as _uuid_mod
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Provara Protocol Imports
from provara.bootstrap_v0 import bootstrap_backpack
from provara.backpack_signing import sign_event, BackpackKeypair
from provara.canonical_json import canonical_hash
from provara.sync_v0 import verify_causal_chain

# --- Configuration ---
VAULT_STORAGE_ROOT = Path(os.getenv("PROVARA_VAULT_ROOT", "/app/data/vaults"))
VAULT_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

# API key auth — set PROVARA_API_KEY in env; if unset, auth is disabled (dev only)
_API_KEY = os.getenv("PROVARA_API_KEY", "")

# CORS — comma-separated origins in PROVARA_ALLOWED_ORIGINS, or "*" for dev
_raw_origins = os.getenv("PROVARA_ALLOWED_ORIGINS", "")
_ALLOWED_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()] or ["*"]

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("provara-saas")

app = FastAPI(
    title="Provara Managed Vault API",
    version="0.1.0",
    description="Persistent, verifiable memory infrastructure."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Models ---
class CreateVaultRequest(BaseModel):
    name: str = Field(..., example="My Work Vault")
    description: Optional[str] = Field(None, example="Tracks daily deep work blocks")

class AppendEventRequest(BaseModel):
    type: str = Field("OBSERVATION", example="MILESTONE")
    subject: str
    predicate: str = "observation"
    value: Any
    confidence: float = 1.0
    namespace: str = "managed"

# --- Internal Helpers ---
def _require_api_key(x_api_key: str = Header(default="")) -> None:
    """FastAPI dependency — enforce API key when PROVARA_API_KEY is configured."""
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def _validate_vault_id(vault_id: str) -> str:
    """Reject non-UUID vault IDs to prevent path traversal."""
    if not _UUID_RE.match(vault_id):
        raise HTTPException(status_code=400, detail="Invalid vault_id format")
    return vault_id


def _get_vault_path(vault_id: str) -> Path:
    _validate_vault_id(vault_id)
    path = VAULT_STORAGE_ROOT / vault_id
    # Confirm resolved path stays inside VAULT_STORAGE_ROOT
    if not path.resolve().is_relative_to(VAULT_STORAGE_ROOT.resolve()):
        raise HTTPException(status_code=400, detail="Invalid vault_id format")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Vault not found")
    return path

def _load_latest_event(vault_path: Path) -> Dict[str, Any]:
    events_file = vault_path / "events" / "events.ndjson"
    with open(events_file, "rb") as f:
        # Seek to end and find last line
        f.seek(0, os.SEEK_END)
        end = f.tell()
        pointer = end - 2
        while pointer > 0:
            f.seek(pointer)
            if f.read(1) == b"\n":
                break
            pointer -= 1
        return json.loads(f.readline().decode("utf-8"))

# --- Routes ---
@app.get("/")
async def root():
    return {
        "name": "Provara Managed Vault API",
        "status": "active",
        "version": "0.1.0",
        "message": "Sovereign memory infrastructure is online. Visit /docs for API reference."
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/vaults/create", status_code=status.HTTP_201_CREATED)
async def create_vault(req: CreateVaultRequest, _: None = Depends(_require_api_key)):
    try:
        vault_id = str(_uuid_mod.uuid4())
        vault_path = VAULT_STORAGE_ROOT / vault_id
        vault_path.mkdir()

        result = bootstrap_backpack(
            name=req.name,
            description=req.description or "Managed Provara Vault",
            quorum_size=1,
            target=vault_path,
        )

        return {
            "success": True,
            "vault_id": vault_id,
            "actor_id": result.actor_id,
            "genesis_hash": result.genesis_hash,
        }
    except Exception as e:
        logger.error(f"Failed to create vault: {e}")
        raise HTTPException(status_code=500, detail="Vault creation failed")

@app.post("/api/v1/vaults/{vault_id}/events")
async def append_event(vault_id: str, req: AppendEventRequest, _: None = Depends(_require_api_key)):
    vault_path = _get_vault_path(vault_id)
    
    try:
        # 1. Load latest event for chaining
        prev_event = _load_latest_event(vault_path)
        prev_hash = canonical_hash(prev_event)

        # 2. Load keys (Production should use a KMS/Vault)
        keys_file = vault_path / "identity" / "private_keys.json"
        with open(keys_file) as f:
            keys = json.load(f)
            # Find the primary actor key
            actor_id = list(keys.keys())[0]
            private_key_hex = keys[actor_id]["private_key"]
            key_id = keys[actor_id]["key_id"]

        keypair = BackpackKeypair.from_hex(private_key_hex)

        # 3. Construct Event
        import datetime
        event = {
            "type": req.type,
            "namespace": req.namespace,
            "actor": actor_id,
            "actor_key_id": key_id,
            "subject": req.subject,
            "predicate": req.predicate,
            "value": req.value,
            "confidence": req.confidence,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "prev_hash": prev_hash,
        }

        # 4. Sign and Append
        signed_event = sign_event(event, keypair)
        events_file = vault_path / "events" / "events.ndjson"
        with open(events_file, "a") as f:
            f.write(json.dumps(signed_event) + "\n")

        return {
            "success": True,
            "event_id": signed_event.get("event_id"),
            "event_hash": canonical_hash(signed_event)
        }
    except Exception as e:
        logger.error(f"Failed to append event: {e}")
        raise HTTPException(status_code=500, detail="Event append failed")

@app.get("/api/v1/vaults/{vault_id}/verify")
async def verify_vault(vault_id: str, _: None = Depends(_require_api_key)):
    vault_path = _get_vault_path(vault_id)
    events_file = vault_path / "events" / "events.ndjson"
    
    events = []
    with open(events_file) as f:
        for line in f:
            events.append(json.loads(line))

    try:
        # Load actor id from manifest
        with open(vault_path / "manifest.json") as f:
            manifest = json.load(f)
            primary_actor = manifest["actors"][0]["actor_id"]

        verify_causal_chain(events, primary_actor)
        return {
            "success": True,
            "status": "valid",
            "event_count": len(events),
            "state_hash": canonical_hash(events)
        }
    except Exception as e:
        logger.error(f"Verify failed for vault {vault_id}: {e}")
        return {
            "success": False,
            "status": "compromised",
            "error": "Chain verification failed"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
