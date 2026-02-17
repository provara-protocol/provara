"""
test_perception_v0.py — Perception Tiering System Tests
"""

import unittest
from pathlib import Path
import sys

from provara.perception_v0 import PerceptionTier, create_perception_payload, emit_perception_event

class TestPerception(unittest.TestCase):
    def test_create_payload(self):
        payload = create_perception_payload(
            PerceptionTier.T0_RAW, 
            "camera_01", 
            "image_data", 
            cas_ref="sha256:123"
        )
        self.assertEqual(payload["tier"], "T0")
        self.assertEqual(payload["subject"], "camera_01")
        self.assertEqual(payload["cas_ref"], "sha256:123")

    def test_emit_event_t0(self):
        event = emit_perception_event(
            actor="sensor_01",
            tier=PerceptionTier.T0_RAW,
            subject="frame",
            value={"url": "cas/123.jpg"}
        )
        self.assertEqual(event["type"], "OBSERVATION")
        self.assertEqual(event["payload"]["tier"], "T0")

    def test_emit_event_t3(self):
        event = emit_perception_event(
            actor="reasoner_01",
            tier=PerceptionTier.T3_SUMMARY,
            subject="day_summary",
            value="Productive day, door was opened 5 times."
        )
        self.assertEqual(event["type"], "ASSERTION")
        self.assertEqual(event["payload"]["tier"], "T3")

if __name__ == "__main__":
    unittest.main()
