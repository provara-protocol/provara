"""
test_integration.py — Integration tests for MCP server tools
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

def send_request(proc, request):
    """Send a JSON-RPC request and read response."""
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    response_line = proc.stdout.readline()
    return json.loads(response_line)

def test_full_workflow():
    """Test complete vault lifecycle: bootstrap → state → delta → sync."""
    server_path = Path(__file__).parent / "provara_server.py"
    
    proc = subprocess.Popen(
        [sys.executable, str(server_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            vault1 = Path(tmpdir) / "vault1"
            vault2 = Path(tmpdir) / "vault2"
            delta_file = Path(tmpdir) / "delta.ndjson"
            
            # Initialize
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"}
                }
            }
            response = send_request(proc, init_req)
            assert "result" in response
            print("✓ Initialize")
            
            # Test 1: Bootstrap vault1
            bootstrap_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "bootstrap_vault",
                    "arguments": {
                        "path": str(vault1),
                        "actor": "device_alpha",
                        "quorum": False
                    }
                }
            }
            response = send_request(proc, bootstrap_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            print(f"✓ Bootstrap vault1: {result['root_key_id']}")
            
            # Test 2: Export state from vault1
            export_state_req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "export_state",
                    "arguments": {
                        "path": str(vault1)
                    }
                }
            }
            response = send_request(proc, export_state_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            assert result["event_count"] == 2  # genesis + seed observation
            print(f"✓ Export state: {result['event_count']} events, state_hash={result['state_hash'][:16]}...")
            
            # Test 3: Verify chain
            verify_req = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "verify_chain",
                    "arguments": {
                        "path": str(vault1)
                    }
                }
            }
            response = send_request(proc, verify_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            print(f"✓ Verify chain: {result['actors_checked']} actors")
            
            # Test 4: Export delta
            export_delta_req = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "export_delta",
                    "arguments": {
                        "path": str(vault1),
                        "output_file": str(delta_file)
                    }
                }
            }
            response = send_request(proc, export_delta_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            assert delta_file.exists()
            print(f"✓ Export delta: {result['event_count']} events, {result['size_bytes']} bytes")
            
            # Test 5: Bootstrap vault2
            bootstrap2_req = {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "bootstrap_vault",
                    "arguments": {
                        "path": str(vault2),
                        "actor": "device_beta",
                        "quorum": False
                    }
                }
            }
            response = send_request(proc, bootstrap2_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            print(f"✓ Bootstrap vault2: {result['root_key_id']}")
            
            # Test 6: Import delta into vault2
            import_delta_req = {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "import_delta",
                    "arguments": {
                        "path": str(vault2),
                        "delta_file": str(delta_file)
                    }
                }
            }
            response = send_request(proc, import_delta_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            print(f"✓ Import delta: {result['imported_count']} imported, {result['rejected_count']} rejected")
            
            # Test 7: Sync vaults
            sync_req = {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "sync_vaults",
                    "arguments": {
                        "local": str(vault1),
                        "remote": str(vault2)
                    }
                }
            }
            response = send_request(proc, sync_req)
            result = json.loads(response["result"]["content"][0]["text"])
            assert result["success"]
            print(f"✓ Sync vaults: {result['events_merged']} merged, final state_hash={result['new_state_hash'][:16]}...")
            
            print("\n✅ All integration tests passed")
            
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    test_full_workflow()
