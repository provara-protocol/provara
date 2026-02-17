import json
import subprocess
import sys
import time
import unittest
import urllib.request
from pathlib import Path

class TestMCPServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server_script = Path(__file__).parent / "server.py"
        cls.vault_path = Path(__file__).parent / "test_vault"
        if cls.vault_path.exists():
            import shutil
            shutil.rmtree(cls.vault_path)
        
        # Init vault via psmc
        psmc_script = Path(__file__).parent.parent / "psmc" / "psmc.py"
        subprocess.run([sys.executable, str(psmc_script), "--vault", str(cls.vault_path), "init"], check=True)

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
        proc.terminate()
        
        resp = json.loads(line)
        self.assertEqual(resp["id"], 1)
        self.assertEqual(resp["result"], {"ok": True})

    def test_sse_ping(self):
        port = 8767
        proc = subprocess.Popen(
            [sys.executable, str(self.server_script), "--transport", "http", "--port", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(1)
        
        try:
            # 1. Connect to SSE
            sse_conn = urllib.request.urlopen(f"http://127.0.0.1:{port}/sse")
            
            # 2. Read endpoint event
            line1 = sse_conn.readline().decode("utf-8") # event: endpoint
            line2 = sse_conn.readline().decode("utf-8") # data: /message?session_id=...
            line3 = sse_conn.readline().decode("utf-8") # \n
            
            self.assertTrue(line1.startswith("event: endpoint"))
            endpoint_path = line2.replace("data: ", "").strip()
            session_id = endpoint_path.split("=")[1]
            
            # 3. Post a message
            ping = {"jsonrpc": "2.0", "id": 3, "method": "ping"}
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{endpoint_path}",
                data=json.dumps(ping).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as post_resp:
                self.assertEqual(post_resp.status, 202)
            
            # 4. Read response from SSE
            line4 = sse_conn.readline().decode("utf-8") # event: message
            line5 = sse_conn.readline().decode("utf-8") # data: {...}
            line6 = sse_conn.readline().decode("utf-8") # \n
            
            self.assertTrue(line4.startswith("event: message"))
            resp_data = json.loads(line5.replace("data: ", "").strip())
            self.assertEqual(resp_data["id"], 3)
            self.assertEqual(resp_data["result"], {"ok": True})
            
            sse_conn.close()
        finally:
            proc.terminate()

if __name__ == "__main__":
    import sys
    unittest.main()
