"""
Provara Protocol SDK
====================

A sovereign, tamper-evident memory substrate for AI agents and digital institutions.

Usage:
    from provara import SovereignReducer, bootstrap_backpack, sign_event

    reducer = SovereignReducer()
    reducer.apply_events(events)
    print(reducer.export_state())
"""

from pathlib import Path
from typing import Any, Dict, Optional

from .canonical_json import canonical_dumps, canonical_hash, canonical_bytes
from .backpack_signing import (
    BackpackKeypair,
    sign_event,
    verify_event_signature,
    load_private_key_b64,
    load_public_key_b64,
    key_id_from_public_bytes,
)
from .backpack_integrity import merkle_root_hex
from .reducer_v0 import SovereignReducerV0 as SovereignReducer
from .bootstrap_v0 import bootstrap_backpack
from .sync_v0 import sync_backpacks, load_events
from .checkpoint_v0 import create_checkpoint, load_latest_checkpoint
from .perception_v0 import emit_perception_event, PerceptionTier
from .market import record_market_alpha, record_hedge_fund_sim
from .oracle import validate_market_alpha
from .resume import generate_resume
from .wallet import export_to_solana, import_from_solana


class Vault:
    """High-level facade for working with a Provara vault path."""

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()

    @classmethod
    def create(
        cls,
        path: str | Path,
        uid: Optional[str] = None,
        actor: str = "sovereign_genesis",
        include_quorum: bool = False,
        quiet: bool = False,
    ) -> "Vault":
        result = bootstrap_backpack(
            Path(path),
            uid=uid,
            actor=actor,
            include_quorum=include_quorum,
            quiet=quiet,
        )
        if not result.success:
            raise ValueError(f"Bootstrap failed: {result.errors}")
        return cls(path)

    def replay_state(self) -> Dict[str, Any]:
        from .sync_v0 import iter_events
        events = iter_events(self.path / "events" / "events.ndjson")
        reducer = SovereignReducer()
        reducer.apply_events(events)
        return reducer.export_state()

    def sync_from(self, remote_path: str | Path) -> Any:
        return sync_backpacks(self.path, Path(remote_path).resolve())

    def append_event(
        self,
        event_type: str,
        payload: Dict[str, Any],
        key_id: str,
        private_key_b64: str,
        actor: str = "provara_sdk",
    ) -> Dict[str, Any]:
        """Append a signed event to the vault."""
        import json
        from datetime import datetime, timezone
        from .sync_v0 import write_events, iter_events

        # 1. Load keys
        priv = load_private_key_b64(private_key_b64)

        # 2. Find prev_hash (Streaming Search)
        events_file = self.path / "events" / "events.ndjson"
        prev_hash = None
        for e in iter_events(events_file):
            if e.get("actor_key_id") == key_id:
                prev_hash = e.get("event_id")

        # 3. Build event
        event = {
            "type": event_type.upper(),
            "actor": actor,
            "prev_event_hash": prev_hash,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "payload": payload,
        }

        # 4. Content ID
        eid_hash = canonical_hash(event)
        event["event_id"] = f"evt_{eid_hash[:24]}"

        # 5. Sign
        signed = sign_event(event, priv, key_id)

        # 6. Append
        with open(events_file, "a", encoding="utf-8") as f:
            f.write(canonical_dumps(signed) + "\n")

        return signed

    def checkpoint(self, key_id: str, private_key_b64: str) -> Path:
        """Create a signed state snapshot."""
        state = self.replay_state()
        priv = load_private_key_b64(private_key_b64)
        cp = create_checkpoint(self.path, state, priv, key_id)
        from .checkpoint_v0 import save_checkpoint
        return save_checkpoint(self.path, cp)

    def anchor_to_l2(
        self,
        key_id: str,
        private_key_b64: str,
        network: str = "base-mainnet",
    ) -> Dict[str, Any]:
        """
        Simulate anchoring the current Merkle root to an L2.
        Records an ANCHOR_ATTESTATION in the vault.
        """
        # 1. Get current Merkle root
        merkle_root_path = self.path / "merkle_root.txt"
        if not merkle_root_path.exists():
            raise FileNotFoundError("merkle_root.txt not found. Run manifest first.")
        merkle_root = merkle_root_path.read_text(encoding="utf-8").strip()

        # 2. MOCK L2 TRANSACTION
        # In production, this would use web3.py to call a contract
        import hashlib
        tx_hash = f"0x{hashlib.sha256(merkle_root.encode()).hexdigest()}"

        payload = {
            "subject": "vault:state_root",
            "predicate": "anchored",
            "value": {
                "merkle_root": merkle_root,
                "network": network,
                "tx_hash": tx_hash,
                "contract_address": "0xProvaraAnchorV1MockAddress",
            },
            "confidence": 1.0,
            "extension": "provara.crypto.l2_anchor_v1"
        }

        # 3. Record as ATTESTATION
        return self.append_event("ATTESTATION", payload, key_id, private_key_b64, actor="anchor_service")

    def create_agent(
        self,
        agent_name: str,
        parent_key_id: str,
        parent_private_key_b64: str,
    ) -> Dict[str, Any]:
        """
        Spin up a new sovereign sub-agent.
        1. Generates new keypair.
        2. Bootstraps a new vault for the agent.
        3. Records an AGENT_CREATION event in the parent vault (this vault).
        Returns the new agent's credentials.
        """
        import uuid
        from datetime import datetime, timezone
        
        # 1. New Identity
        new_kp = BackpackKeypair.generate()
        agent_uid = f"agent-{uuid.uuid4()}"
        agent_dir = self.path.parent / agent_name
        
        # 2. Bootstrap Child Vault
        res = bootstrap_backpack(
            agent_dir,
            uid=agent_uid,
            actor=agent_name,
            quiet=True
        )
        if not res.success:
            raise ValueError(f"Failed to bootstrap agent vault: {res.errors}")
            
        # 3. Record in Parent Vault
        payload = {
            "subject": f"agent:{agent_name}",
            "predicate": "created",
            "value": {
                "agent_uid": agent_uid,
                "agent_root_key_id": res.root_key_id, # Use bootstrap result key ID
                "vault_path": str(agent_dir),
                "created_at_utc": datetime.now(timezone.utc).isoformat(),
            },
            "extension": "provara.agent.lifecycle_v1"
        }
        
        # Sign with PARENT authority
        event = self.append_event(
            "OBSERVATION", 
            payload, 
            parent_key_id, 
            parent_private_key_b64, 
            actor="agent_factory"
        )
        
        return {
            "agent_name": agent_name,
            "agent_uid": agent_uid,
            "vault_path": str(agent_dir),
            "root_key_id": res.root_key_id,
            "root_private_key": res.root_private_key_b64,
            "creation_event_id": event["event_id"]
        }

    def log_task(
        self,
        key_id: str,
        private_key_b64: str,
        task_id: str,
        status: str,
        output_hash: str,
        details: Optional[Dict[str, Any]] = None,
        actor: str = "agent_worker",
    ) -> Dict[str, Any]:
        """
        Record a TASK_COMPLETION event (The "Billable Hour" of the Agent Economy).
        """
        value = {
            "task_id": task_id,
            "status": status.upper(),
            "output_hash": output_hash,
        }
        if details:
            value.update(details)
            
        payload = {
            "subject": f"task:{task_id}",
            "predicate": "completed",
            "value": value,
            "confidence": 1.0,
            "extension": "provara.agent.task_v1"
        }
        
        return self.append_event("OBSERVATION", payload, key_id, private_key_b64, actor=actor)

    def check_safety(self, action_type: str) -> Dict[str, Any]:
        """
        Evaluate a proposed action against the vault's safety policy.
        Returns a result dict with 'status' (APPROVED, BLOCKED, REQUIRES_MFA).
        """
        import json
        policy_path = self.path / "policies" / "safety_policy.json"
        if not policy_path.exists():
            return {"status": "APPROVED", "reason": "No safety policy found (L0 default)"}
            
        policy = json.loads(policy_path.read_text())
        
        # Action to Tier Mapping (Extensible)
        tier_map = {
            "READ": "L0",
            "REPLAY": "L0",
            "APPEND_OBSERVATION": "L1",
            "APPEND_ASSERTION": "L1",
            "CHECKPOINT": "L1",
            "SYNC_OUT": "L1",
            "REKEY": "L2",
            "UPDATE_POLICY": "L2",
            "SYNC_IN": "L2",
            "DELETE_VAULT": "L3",
            "EXPORT_PRIVATE_KEYS": "L3"
        }
        
        target_tier = tier_map.get(action_type.upper(), "L1") # Default to L1 for unknown
        tier_config = policy.get("action_classes", {}).get(target_tier)
        
        if not tier_config:
            return {"status": "BLOCKED", "reason": f"Tier {target_tier} not defined in policy"}
            
        approval = tier_config.get("approval")
        
        if approval == "remote_signature_or_mfa":
            return {"status": "REQUIRES_MFA", "tier": target_tier, "reason": tier_config.get("description")}
        elif target_tier == "L3":
            return {"status": "BLOCKED", "tier": "L3", "reason": "L3 actions are human-only"}
        else:
            return {
                "status": "APPROVED", 
                "tier": target_tier, 
                "approval": approval,
                "description": tier_config.get("description")
            }


# Backward-compatible alias while public API transitions.
SovereignReducerV0 = SovereignReducer

__version__ = "1.0.0"
__all__ = [
    "Vault",
    "SovereignReducer",
    "SovereignReducerV0",
    "bootstrap_backpack",
    "sync_backpacks",
    "canonical_dumps",
    "canonical_hash",
    "canonical_bytes",
    "BackpackKeypair",
    "sign_event",
    "verify_event_signature",
    "load_private_key_b64",
    "load_public_key_b64",
    "key_id_from_public_bytes",
    "merkle_root_hex",
    "load_events",
    "create_checkpoint",
    "load_latest_checkpoint",
    "emit_perception_event",
    "PerceptionTier",
    "record_market_alpha",
    "record_hedge_fund_sim",
    "validate_market_alpha",
    "generate_resume",
    "check_safety",
    "export_to_solana",
    "import_from_solana",
]
