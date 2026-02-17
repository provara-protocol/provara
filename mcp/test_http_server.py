"""
test_http_server.py — Basic HTTP transport tests
"""

import json
import time
import requests
import subprocess
import sys
from pathlib import Path

def test_http_server():
    """Test HTTP/SSE transport."""
    server_path = Path(__file__).parent / "provara_server_http.py"
    
    # Start server
    proc = subprocess.Popen(
        [sys.executable, str(server_path), "--port", "8081"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Give server time to start
    time.sleep(2)
    
    try:
        base_url = "http://127.0.0.1:8081"
        
        # Test 1: Health check
        resp = requests.get(f"{base_url}/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
        
        # Test 2: MCP initialize
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
        
        resp = requests.post(f"{base_url}/mcp", json=init_req)
        assert resp.status_code == 200
        data = resp.json()
        assert data["result"]["protocolVersion"] == "2024-11-05"
        print("✓ MCP initialize passed")
        
        # Test 3: List tools
        list_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        resp = requests.post(f"{base_url}/mcp", json=list_req)
        assert resp.status_code == 200
        data = resp.json()
        tools = data["result"]["tools"]
        assert len(tools) > 0
        print(f"✓ Tools list passed ({len(tools)} tools)")
        
        # Test 4: Batch request
        batch = [init_req, list_req]
        resp = requests.post(f"{base_url}/batch", json=batch)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        print("✓ Batch request passed")
        
        print("\n✅ All HTTP server tests passed")
        
    except requests.RequestException as e:
        print(f"❌ HTTP request failed: {e}")
        print("Make sure Flask and flask-cors are installed:")
        print("  pip install flask flask-cors")
        sys.exit(1)
    
    finally:
        proc.terminate()
        proc.wait(timeout=5)

if __name__ == "__main__":
    test_http_server()
