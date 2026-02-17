"""
test_schemas.py — Test JSON schemas against real Provara events

Validates that the schemas correctly accept valid events and reject invalid ones.
"""

import json
import sys
import unittest
from pathlib import Path

try:
    from jsonschema import validate, ValidationError
except ImportError:
    print("Error: jsonschema package not found", file=sys.stderr)
    print("Install it with: pip install jsonschema", file=sys.stderr)
    sys.exit(1)


class TestEventSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Load schema
        schema_path = Path(__file__).parent / "event_types.json"
        with open(schema_path, "r", encoding="utf-8") as f:
            cls.schema = json.load(f)
    
    def test_genesis_event(self):
        """Valid GENESIS event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "GENESIS",
            "namespace": "canonical",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 0,
            "prev_event_hash": None,
            "timestamp_utc": "2026-02-16T10:00:00Z",
            "payload": {
                "uid": "550e8400-e29b-41d4-a716-446655440000",
                "created_at_utc": "2026-02-16T10:00:00Z",
                "root_key_id": "bp1_0123456789abcdef",
                "actor": "genesis"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        # Should not raise
        validate(instance=event, schema=self.schema)
    
    def test_observation_event(self):
        """Valid OBSERVATION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 1,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:01:00Z",
            "payload": {
                "subject": "door_01",
                "predicate": "status",
                "value": "open",
                "confidence": 0.95
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_assertion_event(self):
        """Valid ASSERTION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "ASSERTION",
            "namespace": "local",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 2,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:02:00Z",
            "payload": {
                "subject": "weather",
                "predicate": "forecast",
                "value": "sunny",
                "confidence": 0.75,
                "reasoning": "Based on satellite data"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_attestation_event(self):
        """Valid ATTESTATION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "ATTESTATION",
            "namespace": "canonical",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 3,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:03:00Z",
            "payload": {
                "subject": "door_01",
                "predicate": "status",
                "value": "open",
                "target_event_id": "evt_bbccddee2233445566778899"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_key_revocation_event(self):
        """Valid KEY_REVOCATION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "KEY_REVOCATION",
            "namespace": "canonical",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 4,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:04:00Z",
            "payload": {
                "revoked_key_id": "bp1_fedcba9876543210",
                "reason": "key_compromise",
                "revoked_at_utc": "2026-02-16T10:04:00Z",
                "trust_boundary_event_id": "evt_ccddeeaa3344556677889900"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_key_promotion_event(self):
        """Valid KEY_PROMOTION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "KEY_PROMOTION",
            "namespace": "canonical",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 5,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:05:00Z",
            "payload": {
                "new_key_id": "bp1_123456789abcdef0",
                "new_public_key_b64": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
                "algorithm": "Ed25519",
                "roles": ["root", "attestation"],
                "promoted_by": "bp1_0123456789abcdef",
                "replaces_key_id": "bp1_fedcba9876543210",
                "promoted_at_utc": "2026-02-16T10:05:00Z"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_retraction_event(self):
        """Valid RETRACTION event should pass."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "RETRACTION",
            "namespace": "local",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 6,
            "prev_event_hash": "evt_aabbccdd1122334455667788",
            "timestamp_utc": "2026-02-16T10:06:00Z",
            "payload": {
                "retracted_event_id": "evt_ddeeffbb4455667788990011",
                "reason": "Sensor malfunction detected",
                "correction_event_id": "evt_eeffaabb5566778899001122",
                "retracted_at_utc": "2026-02-16T10:06:00Z"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        validate(instance=event, schema=self.schema)
    
    def test_invalid_event_id_format(self):
        """Event with malformed event_id should fail."""
        event = {
            "event_id": "bad_id",  # Should be evt_<24 hex>
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 1,
            "prev_event_hash": None,
            "timestamp_utc": "2026-02-16T10:00:00Z",
            "payload": {
                "subject": "door",
                "predicate": "status",
                "value": "open"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        with self.assertRaises(ValidationError):
            validate(instance=event, schema=self.schema)
    
    def test_invalid_key_id_format(self):
        """Event with malformed key_id should fail."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "bad_key_id",  # Should be bp1_<16 hex>
            "actor_key_id": "bad_key_id",
            "ts_logical": 1,
            "prev_event_hash": None,
            "timestamp_utc": "2026-02-16T10:00:00Z",
            "payload": {
                "subject": "door",
                "predicate": "status",
                "value": "open"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        with self.assertRaises(ValidationError):
            validate(instance=event, schema=self.schema)
    
    def test_missing_required_field(self):
        """Event missing required field should fail."""
        event = {
            "event_id": "evt_abc123def456789012345678",
            "type": "OBSERVATION",
            "namespace": "local",
            "actor": "bp1_0123456789abcdef",
            "actor_key_id": "bp1_0123456789abcdef",
            "ts_logical": 1,
            "prev_event_hash": None,
            "timestamp_utc": "2026-02-16T10:00:00Z",
            "payload": {
                "subject": "door",
                # Missing "predicate" (required)
                "value": "open"
            },
            "sig": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        }
        
        with self.assertRaises(ValidationError):
            validate(instance=event, schema=self.schema)


if __name__ == "__main__":
    unittest.main()

