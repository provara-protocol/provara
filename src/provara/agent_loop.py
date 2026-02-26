"""
agent_loop.py — The Autonomous Alpha Engine

Orchestrates the full "Proof of Alpha" lifecycle:
Signal -> Log -> Validate -> Anchor -> Reputation.
"""

from __future__ import annotations
import time
import random
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

from . import Vault, validate_market_alpha, generate_resume

def run_alpha_loop(
    vault_path: Path,
    keyfile: Path,
    actor_name: str = "Alpha_Bot_01",
    iterations: int = 1
) -> None:
    """
    Execute the autonomous alpha loop.
    """
    import json
    keys_data = json.loads(keyfile.read_text())
    kid = list(keys_data.keys())[0]
    priv = keys_data[kid]
    
    v = Vault(vault_path)
    
    logger.info(f"--- Starting Alpha Loop for {actor_name} ---")
    
    for i in range(iterations):
        logger.info(f"\\n[Cycle {i+1}/{iterations}]")
        
        # 1. Generate Signal (Simulated Strategy)
        ticker = random.choice(["BTC", "ETH", "SOL", "NVDA"])
        signal = random.choice(["LONG", "SHORT"])
        logger.info(f"1. Generating Signal: {signal} {ticker}")
        
        v.append_event(
            "OBSERVATION",
            {
                "subject": f"market:{ticker}",
                "predicate": "signal",
                "value": {
                    "ticker": ticker, 
                    "signal": signal,
                    "conviction": 0.9,
                    "horizon": "24h"
                },
                "extension": "provara.market.market_alpha"
            },
            kid, priv, actor=actor_name
        )
        
        # 2. Oracle Validation (Simulated Time Jump)
        logger.info("2. Requesting Oracle Validation...")
        # In reality, this would happen days later.
        # Our oracle.py prototype mocks the future lookup.
        results = validate_market_alpha(vault_path, keyfile, actor="Oracle_Node")
        
        if results:
            attestation = results[0]
            perf = attestation["payload"]["value"]["performance_pct"]
            status = attestation["payload"]["value"]["status"]
            logger.info(f"   Oracle Result: {status} ({perf:+.2f}%)")
            
            # 3. Anchor if Successful (The "Win" Condition)
            if status == "SUCCESS":
                logger.info("3. High Performance Detected. Anchoring to L2...")
                anchor = v.anchor_to_l2(kid, priv, network="base-sepolia")
                logger.info(f"   Anchored: {anchor['payload']['value']['tx_hash'][:16]}...")
                
                # 4. Update Resume stats implicitly via event log
                logger.info("4. Reputation Updated.")
            else:
                logger.info("3. Performance below threshold. No anchor.")
        else:
            logger.info("   No validation possible yet.")
            
    logger.info(f"\\n--- Loop Complete. Vault Head: {v.replay_state()['metadata']['last_event_id']} ---")
