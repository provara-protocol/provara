"""
agent_loop.py — The Autonomous Alpha Engine

Orchestrates the full "Proof of Alpha" lifecycle:
Signal -> Log -> Validate -> Anchor -> Reputation.
"""

from __future__ import annotations
import time
import random
from pathlib import Path
from typing import Dict, Any

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
    
    print(f"--- Starting Alpha Loop for {actor_name} ---")
    
    for i in range(iterations):
        print(f"\n[Cycle {i+1}/{iterations}]")
        
        # 1. Generate Signal (Simulated Strategy)
        ticker = random.choice(["BTC", "ETH", "SOL", "NVDA"])
        signal = random.choice(["LONG", "SHORT"])
        print(f"1. Generating Signal: {signal} {ticker}")
        
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
        print("2. Requesting Oracle Validation...")
        # In reality, this would happen days later.
        # Our oracle.py prototype mocks the future lookup.
        results = validate_market_alpha(vault_path, keyfile, actor="Oracle_Node")
        
        if results:
            attestation = results[0]
            perf = attestation["payload"]["value"]["performance_pct"]
            status = attestation["payload"]["value"]["status"]
            print(f"   Oracle Result: {status} ({perf:+.2f}%)")
            
            # 3. Anchor if Successful (The "Win" Condition)
            if status == "SUCCESS":
                print("3. High Performance Detected. Anchoring to L2...")
                anchor = v.anchor_to_l2(kid, priv, network="base-sepolia")
                print(f"   Anchored: {anchor['payload']['value']['tx_hash'][:16]}...")
                
                # 4. Update Resume stats implicitly via event log
                print("4. Reputation Updated.")
            else:
                print("3. Performance below threshold. No anchor.")
        else:
            print("   No validation possible yet.")
            
    print(f"\n--- Loop Complete. Vault Head: {v.replay_state()['metadata']['last_event_id']} ---")
