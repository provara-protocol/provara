"""
playground_api.py — Provara Interactive Playground API

Minimal Flask server for browser-based vault demo.
Exposes vault creation, event appending, and chain verification.

Run:
  pip install flask flask-cors
  python playground_api.py

Then open http://localhost:5000 in browser.
"""

import json
import tempfile
import shutil
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

from src.provara.bootstrap_v0 import bootstrap_backpack
from src.provara.backpack_signing import sign_event, verify_event_signature
from src.provara.canonical_json import canonical_hash, canonical_dumps
from src.provara.sync_v0 import verify_causal_chain
from src.provara.reducer_v0 import SovereignReducerV0

app = Flask(__name__)
CORS(app)

# In-memory vault storage (demo only; not persistent)
vaults = {}


@app.route("/api/vault/create", methods=["POST"])
def create_vault():
    """Create a new demo vault."""
    try:
        data = request.json or {}
        name = data.get("name", "Demo Vault")
        
        # Bootstrap a vault in temp directory
        tmp = tempfile.mkdtemp()
        vault_path = Path(tmp) / "vault"
        vault_path.mkdir(parents=True)
        
        result = bootstrap_backpack(
            name=name,
            description="Demo vault created in browser playground",
            quorum_size=1,
            target=vault_path,
        )
        
        # Store vault info in memory
        vault_id = result.vault_id[:8]
        vaults[vault_id] = {
            "path": str(vault_path),
            "actor_id": result.actor_id,
            "keypair_public": result.keypair.public_key.hex(),
            "keypair_key_id": result.keypair.key_id,
            "events": [],
        }
        
        # Load genesis event
        events_file = vault_path / "events" / "events.ndjson"
        with open(events_file) as f:
            genesis = json.loads(f.readline())
        
        vaults[vault_id]["events"].append(genesis)
        
        return jsonify({
            "success": True,
            "vault_id": vault_id,
            "actor_id": result.actor_id,
            "genesis_hash": canonical_hash(genesis),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/vault/<vault_id>/append-event", methods=["POST"])
def append_event(vault_id):
    """Append an observation event to vault."""
    try:
        if vault_id not in vaults:
            return jsonify({"success": False, "error": "Vault not found"}), 404
        
        vault = vaults[vault_id]
        data = request.json or {}
        
        # Build event
        event = {
            "type": "OBSERVATION",
            "namespace": data.get("namespace", "local"),
            "actor": vault["actor_id"],
            "actor_key_id": vault["keypair_key_id"],
            "subject": data.get("subject", "demo_subject"),
            "predicate": data.get("predicate", "observation"),
            "value": data.get("value", "test"),
            "confidence": data.get("confidence", 0.9),
            "timestamp": data.get("timestamp", "2026-02-17T17:00:00Z"),
            "prev_hash": canonical_hash(vault["events"][-1]),
        }
        
        # Reconstruct keypair to sign (demo only; normally would be stored)
        from src.provara.backpack_signing import BackpackKeypair
        keypair = BackpackKeypair.from_hex(vault["keypair_public"])
        
        # Sign the event
        event_signed = sign_event(event, keypair)
        
        vault["events"].append(event_signed)
        
        return jsonify({
            "success": True,
            "event_id": event_signed.get("event_id"),
            "event_hash": canonical_hash(event_signed),
            "event_count": len(vault["events"]),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/vault/<vault_id>/verify-chain", methods=["GET"])
def verify_chain(vault_id):
    """Verify the causal chain of the vault."""
    try:
        if vault_id not in vaults:
            return jsonify({"success": False, "error": "Vault not found"}), 404
        
        vault = vaults[vault_id]
        
        # Verify the chain
        verify_causal_chain(vault["events"], vault["actor_id"])
        
        return jsonify({
            "success": True,
            "verified": True,
            "event_count": len(vault["events"]),
            "chain_hash": canonical_hash(vault["events"]),
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "verified": False,
            "error": str(e),
        }), 400


@app.route("/api/vault/<vault_id>/events", methods=["GET"])
def get_events(vault_id):
    """Get all events in the vault."""
    try:
        if vault_id not in vaults:
            return jsonify({"success": False, "error": "Vault not found"}), 404
        
        vault = vaults[vault_id]
        
        # Return events with hashes
        events_with_hashes = []
        for i, event in enumerate(vault["events"]):
            events_with_hashes.append({
                "index": i,
                "type": event.get("type"),
                "actor": event.get("actor"),
                "subject": event.get("subject"),
                "value": event.get("value"),
                "hash": canonical_hash(event),
                "prev_hash": event.get("prev_hash"),
            })
        
        return jsonify({
            "success": True,
            "events": events_with_hashes,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/", methods=["GET"])
def serve_playground():
    """Serve the playground HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Provara Interactive Playground</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #0a0e27;
            color: #e0e6ed;
            padding: 20px;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { color: #00d4ff; margin-bottom: 10px; font-size: 28px; }
        .subtitle { color: #888; margin-bottom: 30px; }
        .card {
            background: #0f1432;
            border: 1px solid #1a2449;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .button {
            background: #1d4e63;
            color: #00d4ff;
            border: 1px solid #00d4ff;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }
        .button:hover {
            background: #1d4e63cc;
        }
        input[type="text"], textarea {
            background: #0a0e27;
            border: 1px solid #1a2449;
            color: #e0e6ed;
            padding: 8px 12px;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
        }
        .event {
            background: #0a0e27;
            border-left: 3px solid #1f6b4f;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 4px;
            font-size: 12px;
        }
        .hash {
            font-family: monospace;
            color: #00d4ff;
            word-break: break-all;
        }
        .success { color: #1f6b4f; }
        .error { color: #ff6b6b; }
        .two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .label { color: #888; font-size: 12px; margin-top: 10px; margin-bottom: 5px; }
        .status { padding: 10px; border-radius: 4px; margin-bottom: 10px; display: none; }
        .status.show { display: block; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Provara Interactive Playground</h1>
        <p class="subtitle">Create a vault, append events, verify the cryptographic chain.</p>
        
        <div class="two-column">
            <div>
                <div class="card">
                    <h2>1. Create Vault</h2>
                    <input type="text" id="vaultName" placeholder="Vault name..." value="My Vault">
                    <button class="button" onclick="createVault()">Create</button>
                    <div id="createStatus" class="status"></div>
                </div>
                
                <div class="card">
                    <h2>2. Add Event</h2>
                    <div class="label">Subject (what you're observing)</div>
                    <input type="text" id="subject" placeholder="e.g., door_01" value="sensor_x">
                    <div class="label">Observation (what you observed)</div>
                    <input type="text" id="value" placeholder="e.g., open" value="42.5">
                    <div class="label">Confidence (0.0 to 1.0)</div>
                    <input type="text" id="confidence" value="0.95">
                    <button class="button" onclick="appendEvent()">Add Event</button>
                    <div id="appendStatus" class="status"></div>
                </div>
                
                <div class="card">
                    <h2>3. Verify Chain</h2>
                    <button class="button" onclick="verifyChain()">Verify</button>
                    <div id="verifyStatus" class="status"></div>
                </div>
            </div>
            
            <div>
                <div class="card">
                    <h2>Chain Visualization</h2>
                    <div id="chainViz" style="font-family: monospace; font-size: 11px; line-height: 1.4;">
                        (Create a vault to begin)
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let vaultId = null;
        
        async function createVault() {
            const name = document.getElementById('vaultName').value;
            try {
                const res = await fetch('/api/vault/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name })
                });
                const data = await res.json();
                if (data.success) {
                    vaultId = data.vault_id;
                    showStatus('createStatus', `Vault created: ${data.actor_id.substring(0, 12)}...`, true);
                    updateVisualization();
                } else {
                    showStatus('createStatus', 'Error: ' + data.error, false);
                }
            } catch (e) {
                showStatus('createStatus', 'Error: ' + e.message, false);
            }
        }
        
        async function appendEvent() {
            if (!vaultId) {
                showStatus('appendStatus', 'Create a vault first', false);
                return;
            }
            try {
                const res = await fetch(`/api/vault/${vaultId}/append-event`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        subject: document.getElementById('subject').value,
                        value: document.getElementById('value').value,
                        confidence: parseFloat(document.getElementById('confidence').value),
                    })
                });
                const data = await res.json();
                if (data.success) {
                    showStatus('appendStatus', `Event added (#${data.event_count - 1})`, true);
                    updateVisualization();
                } else {
                    showStatus('appendStatus', 'Error: ' + data.error, false);
                }
            } catch (e) {
                showStatus('appendStatus', 'Error: ' + e.message, false);
            }
        }
        
        async function verifyChain() {
            if (!vaultId) {
                showStatus('verifyStatus', 'Create a vault first', false);
                return;
            }
            try {
                const res = await fetch(`/api/vault/${vaultId}/verify-chain`);
                const data = await res.json();
                if (data.success) {
                    showStatus('verifyStatus', `✓ Chain verified (${data.event_count} events)`, true);
                } else {
                    showStatus('verifyStatus', '✗ Chain verification failed: ' + data.error, false);
                }
            } catch (e) {
                showStatus('verifyStatus', 'Error: ' + e.message, false);
            }
        }
        
        async function updateVisualization() {
            if (!vaultId) return;
            try {
                const res = await fetch(`/api/vault/${vaultId}/events`);
                const data = await res.json();
                if (data.success) {
                    const viz = document.getElementById('chainViz');
                    let html = '<div style="color: #888;">Chain:</div>';
                    data.events.forEach((e, i) => {
                        const hashShort = e.hash.substring(0, 16) + '...';
                        const prevShort = e.prev_hash.substring(0, 16) + '...';
                        html += `
                            <div class="event">
                                <div>[${i}] ${e.type} <span class="hash">${hashShort}</span></div>
                                <div style="color: #666; font-size: 11px;">← ${prevShort}</div>
                            </div>
                        `;
                    });
                    viz.innerHTML = html;
                }
            } catch (e) {
                console.error(e);
            }
        }
        
        function showStatus(elemId, msg, success) {
            const elem = document.getElementById(elemId);
            elem.textContent = msg;
            elem.className = 'status show ' + (success ? 'success' : 'error');
        }
    </script>
</body>
</html>
    """


if __name__ == "__main__":
    print("Starting Provara Playground API on http://localhost:5000")
    print("Open browser and navigate to http://localhost:5000")
    app.run(debug=True, port=5000)
