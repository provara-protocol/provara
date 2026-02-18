"""
test_timestamp.py — Unit tests for RFC 3161 timestamping
"""

import base64
import json
import unittest
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from provara.timestamp import record_timestamp_anchor, get_rfc3161_timestamp
from provara.backpack_signing import BackpackKeypair
from provara.sync_v0 import load_events

class TestTimestamp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vault_path = self.tmp / "test_vault"
        self.vault_path.mkdir()
        (self.vault_path / "events").mkdir()
        
        # Create a dummy events file
        self.events_file = self.vault_path / "events" / "events.ndjson"
        self.events_file.touch()
        
        # Create a keyfile
        self.kp = BackpackKeypair.generate()
        self.keyfile = self.tmp / "keys.json"
        self.keyfile.write_text(json.dumps({self.kp.key_id: self.kp.private_key_b64()}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    @patch("urllib.request.urlopen")
    def test_timestamp_anchor_flow(self, mock_urlopen):
        # Mock TSA response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b"MOCK_TSA_RESPONSE_BYTES"
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response
        
        # Run anchoring
        signed_event = record_timestamp_anchor(
            self.vault_path,
            self.keyfile,
            tsa_url="http://mock-tsa.org",
            actor="test_tsa_actor"
        )
        
        # Verify event structure
        self.assertEqual(signed_event["type"], "com.provara.timestamp_anchor")
        self.assertEqual(signed_event["actor"], "test_tsa_actor")
        self.assertEqual(signed_event["payload"]["tsa_url"], "http://mock-tsa.org")
        
        tsr_decoded = base64.b64decode(signed_event["payload"]["rfc3161_tsr_b64"])
        self.assertEqual(tsr_decoded, b"MOCK_TSA_RESPONSE_BYTES")
        
        # Verify it was written to the log
        events = load_events(self.events_file)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_id"], signed_event["event_id"])

if __name__ == "__main__":
    unittest.main()
