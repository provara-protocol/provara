import json
import shutil
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path


def _stop_proc(proc: subprocess.Popen) -> None:
    """Terminate a subprocess and wait for it to fully exit (Windows-safe)."""
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def _stdio_request(proc, method, params=None, request_id=None):
    """Send a JSON-RPC request via stdio and return the response."""
    req = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        req["params"] = params
    if request_id is not None:
        req["id"] = request_id
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    
    # Read non-empty lines only
    while True:
        line = proc.stdout.readline()
        if not line:
            # Check if process died
            ret = proc.poll()
            if ret is not None:
                raise EOFError(f"MCP server process closed with exit code {ret}")
            continue
        stripped = line.strip()
        if stripped:
            try:
                return json.loads(stripped)
            except json.JSONDecodeError as exc:
                print(f"DEBUG: Failed to decode line: {repr(stripped)}", file=sys.stderr)
                raise exc


def _sse_request(port, session_id, method, params=None, request_id=None):
    """Send a JSON-RPC request via SSE transport and return the response."""
    req = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        req["params"] = params
    if request_id is not None:
        req["id"] = request_id

    endpoint = f"http://127.0.0.1:{port}/message?session_id={session_id}"
    post_req = urllib.request.Request(
        endpoint,
        data=json.dumps(req).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(post_req) as resp:
        assert resp.status == 202
    return endpoint


class TestMCPServerStdio(unittest.TestCase):
    """Test MCP server via stdio transport."""

    @classmethod
    def setUpClass(cls):
        cls.server_script = Path(__file__).parent / "server.py"
        cls.psmc_script = Path(__file__).parent.parent / "psmc" / "psmc.py"

    def setUp(self):
        self.vault_path = Path(__file__).parent / "test_vault_stdio"
        # Ensure fully removed
        for _ in range(3):
            if self.vault_path.exists():
                shutil.rmtree(self.vault_path, ignore_errors=True)
                time.sleep(0.1)
            else:
                break
        
        result = subprocess.run(
            [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "init"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            # Clean up and retry once more
            shutil.rmtree(self.vault_path, ignore_errors=True)
            time.sleep(0.2)
            result = subprocess.run(
                [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "init"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"DEBUG: psmc init failed permanently:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                raise RuntimeError(f"PSMC init failed: {result.stderr}")

    def tearDown(self):
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path)

    def test_stdio_ping(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        ping = {"jsonrpc": "2.0", "id": 1, "method": "ping"}
        proc.stdin.write(json.dumps(ping) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"], {"ok": True})

    def test_stdio_initialize(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        req = {"jsonrpc": "2.0", "id": 1, "method": "initialize"}
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["serverInfo"]["name"], "provara-mcp")
        self.assertIn("capabilities", resp["result"])

    def test_stdio_tools_list(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        req = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertIn("tools", resp["result"])
        tool_names = [t["name"] for t in resp["result"]["tools"]]
        self.assertIn("append_event", tool_names)
        self.assertIn("verify_chain", tool_names)
        self.assertIn("generate_digest", tool_names)
        self.assertIn("snapshot_state", tool_names)

    def test_stdio_append_event(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "append_event",
            "arguments": {
                "vault_path": str(self.vault_path),
                "event_type": "note",
                "data": {"key": "value", "number": 42}
            }
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("event_id", content)
        self.assertIn("hash", content)

    def test_stdio_snapshot_state(self):
        # First append an event
        subprocess.run(
            [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path),
             "append", "--type", "note", "--data", '{"test": true}'],
            check=True,
            capture_output=True
        )

        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "snapshot_state",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        
        self.assertIn("metadata", content)
        self.assertIn("state_hash", content["metadata"])
        self.assertIn("event_count", content["metadata"])

    def test_stdio_verify_chain(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "verify_chain",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("valid", content)
        self.assertTrue(content["valid"])

    def test_stdio_generate_digest(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "generate_digest",
            "arguments": {"vault_path": str(self.vault_path), "weeks": 1}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        content = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("digest", content)

    def test_stdio_full_roundtrip(self):
        """Full roundtrip: append_event → snapshot_state → verify_chain."""
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 1. Append event
        resp1 = _stdio_request(proc, "tools/call", {
            "name": "append_event",
            "arguments": {
                "vault_path": str(self.vault_path),
                "event_type": "note",
                "data": {"step": 1, "test": "full_roundtrip"}
            }
        }, request_id=1)
        self.assertIn("result", resp1)

        # 2. Snapshot state
        resp2 = _stdio_request(proc, "tools/call", {
            "name": "snapshot_state",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=2)
        self.assertIn("result", resp2)
        content2 = json.loads(resp2["result"]["content"][0]["text"])
        
        self.assertIn("metadata", content2)
        self.assertIn("state_hash", content2["metadata"])

        # 3. Verify chain
        resp3 = _stdio_request(proc, "tools/call", {
            "name": "verify_chain",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=3)
        self.assertIn("result", resp3)
        content3 = json.loads(resp3["result"]["content"][0]["text"])
        self.assertTrue(content3["valid"])

        _stop_proc(proc)

    def test_stdio_query_timeline(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "query_timeline",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("events", data)
        self.assertIsInstance(data["events"], list)

    def test_stdio_list_conflicts(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "list_conflicts",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        conflicts = json.loads(resp["result"]["content"][0]["text"])
        self.assertIsInstance(conflicts, dict)

    def test_stdio_export_markdown(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "export_markdown",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("markdown", data)

    def test_stdio_checkpoint_vault(self):
        # PSMC init creates the vault but create_checkpoint needs merkle_root.txt (optional now)
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        resp = _stdio_request(proc, "tools/call", {
            "name": "checkpoint_vault",
            "arguments": {"vault_path": str(self.vault_path)}
        }, request_id=1)
        _stop_proc(proc)

        self.assertEqual(resp["id"], 1)
        self.assertIn("result", resp)
        data = json.loads(resp["result"]["content"][0]["text"])
        self.assertIn("path", data)
        self.assertIn("event_count", data)

    def test_stdio_error_invalid_vault(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "snapshot_state",
                "arguments": {"vault_path": "/nonexistent/path"}
            }
        }
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertIn("error", resp)

    def test_stdio_error_missing_params(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "append_event",
                "arguments": {"vault_path": str(self.vault_path)}
                # Missing event_type and data
            }
        }
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertIn("error", resp)

    def test_stdio_error_unknown_tool(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {}
            }
        }
        proc.stdin.write(json.dumps(req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        _stop_proc(proc)

        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertIn("error", resp)
        self.assertEqual(resp["error"]["code"], -32601)


class TestMCPServerSSE(unittest.TestCase):
    """Test MCP server via SSE (HTTP) transport."""

    @classmethod
    def setUpClass(cls):
        cls.server_script = Path(__file__).parent / "server.py"
        cls.psmc_script = Path(__file__).parent.parent / "psmc" / "psmc.py"
        cls.port = 8768

    def setUp(self):
        self.vault_path = Path(__file__).parent / "test_vault_sse"
        # Ensure fully removed
        for _ in range(3):
            if self.vault_path.exists():
                shutil.rmtree(self.vault_path, ignore_errors=True)
                time.sleep(0.1)
            else:
                break

        result = subprocess.run(
            [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "init"],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            # Clean up and retry once more
            shutil.rmtree(self.vault_path, ignore_errors=True)
            time.sleep(0.2)
            result = subprocess.run(
                [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path), "init"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                print(f"DEBUG: psmc init failed permanently (SSE):\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
                raise RuntimeError(f"PSMC init failed (SSE): {result.stderr}")

    def tearDown(self):
        if self.vault_path.exists():
            shutil.rmtree(self.vault_path)

    def _setup_sse_session(self, port):
        """Set up SSE connection and return session endpoint."""
        sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{port}/sse", timeout=5)
        line1 = sse_conn.readline().decode("utf-8")
        line2 = sse_conn.readline().decode("utf-8")
        sse_conn.readline()  # blank line

        self.assertTrue(line1.startswith("event: endpoint"))
        endpoint_path = line2.replace("data: ", "").strip()
        return sse_conn, endpoint_path

    def _send_sse_request(self, port, endpoint, method, params=None, request_id=1):
        """Send JSON-RPC request via SSE and return response."""
        req = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            req["params"] = params

        post_req = urllib.request.Request(
            f"http://127.0.0.1:{port}{endpoint}",
            data=json.dumps(req).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(post_req, timeout=5) as resp:
            self.assertEqual(resp.status, 202)

        # Read response from SSE stream (already connected)
        # Note: This requires the SSE connection to still be open
        return None  # Response is read by caller from SSE stream

    def test_sse_ping(self):
        port = 8767
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{port}/sse", timeout=5)

            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line1.startswith("event: endpoint"))
            endpoint_path = line2.replace("data: ", "").strip()
            session_id = endpoint_path.split("=")[1]

            ping = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{endpoint_path}",
                data=json.dumps(ping).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as post_resp:
                self.assertEqual(post_resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 3)
            self.assertEqual(resp_data["result"], {"ok": True})

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_append_event(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=5)
            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            endpoint_path = line2.replace("data: ", "").strip()

            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "append_event",
                    "arguments": {
                        "vault_path": str(self.vault_path),
                        "event_type": "note",
                        "data": {"transport": "sse"}
                    }
                }
            }
            post_req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 1)
            self.assertIn("result", resp_data)
            content = json.loads(resp_data["result"]["content"][0]["text"])
            self.assertIn("event_id", content)

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_snapshot_state(self):
        subprocess.run(
            [sys.executable, str(self.psmc_script), "--vault", str(self.vault_path),
             "append", "--type", "note", "--data", '{"test": true}'],
            check=True,
            capture_output=True
        )

        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=5)
            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            endpoint_path = line2.replace("data: ", "").strip()

            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "snapshot_state",
                    "arguments": {"vault_path": str(self.vault_path)}
                }
            }
            post_req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 1)
            content = json.loads(resp_data["result"]["content"][0]["text"])
            
            self.assertIn("metadata", content)
            self.assertIn("state_hash", content["metadata"])

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_verify_chain(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=5)
            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            endpoint_path = line2.replace("data: ", "").strip()

            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "verify_chain",
                    "arguments": {"vault_path": str(self.vault_path)}
                }
            }
            post_req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 1)
            content = json.loads(resp_data["result"]["content"][0]["text"])
            self.assertIn("valid", content)

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_generate_digest(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=5)
            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            endpoint_path = line2.replace("data: ", "").strip()

            req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "generate_digest",
                    "arguments": {"vault_path": str(self.vault_path), "weeks": 1}
                }
            }
            post_req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 1)
            content = json.loads(resp_data["result"]["content"][0]["text"])
            self.assertIn("digest", content)

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_full_roundtrip(self):
        """Full roundtrip via SSE: append_event → snapshot_state → verify_chain."""
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{self.port}/sse", timeout=5)
            line1 = sse_conn.readline().decode("utf-8")
            line2 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()

            endpoint_path = line2.replace("data: ", "").strip()

            # 1. Append event
            req1 = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "append_event",
                    "arguments": {
                        "vault_path": str(self.vault_path),
                        "event_type": "note",
                        "data": {"step": 1, "test": "sse_roundtrip"}
                    }
                }
            }
            post_req1 = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req1).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req1, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line4 = sse_conn.readline().decode("utf-8")
            line5 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()
            resp1 = json.loads(line5.replace("data: ", "").strip())
            self.assertIn("result", resp1)

            # 2. Snapshot state
            req2 = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "snapshot_state",
                    "arguments": {"vault_path": str(self.vault_path)}
                }
            }
            post_req2 = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req2).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req2, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line6 = sse_conn.readline().decode("utf-8")
            line7 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()
            resp2 = json.loads(line7.replace("data: ", "").strip())
            self.assertIn("result", resp2)
            content2 = json.loads(resp2["result"]["content"][0]["text"])
            
            self.assertIn("metadata", content2)
            self.assertIn("state_hash", content2["metadata"])

            # 3. Verify chain
            req3 = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "verify_chain",
                    "arguments": {"vault_path": str(self.vault_path)}
                }
            }
            post_req3 = urllib.request.Request(
                f"http://127.0.0.1:{self.port}{endpoint_path}",
                data=json.dumps(req3).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(post_req3, timeout=5) as resp:
                self.assertEqual(resp.status, 202)

            line8 = sse_conn.readline().decode("utf-8")
            line9 = sse_conn.readline().decode("utf-8")
            sse_conn.readline()
            resp3 = json.loads(line9.replace("data: ", "").strip())
            self.assertIn("result", resp3)
            content3 = json.loads(resp3["result"]["content"][0]["text"])
            self.assertTrue(content3["valid"])

            sse_conn.close()
        finally:
            _stop_proc(proc)

    def test_sse_health_endpoint(self):
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(self.port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)

        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health", timeout=5) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertEqual(data["server"], "provara-mcp")
        finally:
            _stop_proc(proc)


if __name__ == "__main__":
    unittest.main()
