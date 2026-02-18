"""
test_export.py — Tests for SCITT Phase 2 Export Tool

Tests:
  - Create vault with SCITT events → export → verify export bundle
  - Export empty vault (no SCITT events) → produces empty index
  - Export bundle is self-contained and verifiable
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
import sys

# Add src to path
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from provara.bootstrap_v0 import bootstrap_backpack
from provara.scitt import record_scitt_statement, record_scitt_receipt, SIGNED_STATEMENT_TYPE, RECEIPT_TYPE
from provara.export import export_vault_scitt_compat
from provara.canonical_json import canonical_hash


class TestExportScittCompat(unittest.TestCase):
    
    def setUp(self):
        """Create a test vault with SCITT events."""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.vault_path = self.tmp_dir / "test_vault"
        self.keys_path = self.tmp_dir / "test_keys.json"
        self.output_path = self.tmp_dir / "export_output"
        
        # Bootstrap vault
        result = bootstrap_backpack(
            self.vault_path,
            uid="export-test-vault",
            actor="export_test_actor",
            include_quorum=False,
            quiet=True
        )
        
        # Save keys
        keys_data = {
            "keys": [{
                "key_id": result.root_key_id,
                "private_key_b64": result.root_private_key_b64,
                "algorithm": "Ed25519"
            }]
        }
        with open(self.keys_path, "w") as f:
            json.dump(keys_data, f)
        
        # Add SCITT statement
        self.statement_hash = canonical_hash(b"test statement content")
        self.statement_result = record_scitt_statement(
            self.vault_path,
            self.keys_path,
            statement_hash=self.statement_hash,
            content_type="application/json",
            subject="test:example",
            issuer="did:example:test123",
            actor="scitt_export_tester"
        )
        
        # Add SCITT receipt
        self.receipt_result = record_scitt_receipt(
            self.vault_path,
            self.keys_path,
            statement_event_id=self.statement_result["event_id"],
            transparency_service="https://test-ts.example.com",
            inclusion_proof={"leaf_index": 0, "root": "test_root"},
            actor="scitt_export_tester"
        )
    
    def tearDown(self):
        """Clean up temp directory."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_export_vault_with_scitt_events(self):
        """Export vault with SCITT events produces valid bundle."""
        result = export_vault_scitt_compat(self.vault_path, self.output_path)
        
        # Check result
        self.assertTrue(result["success"])
        self.assertEqual(result["exported_count"], 1)
        self.assertEqual(result["verification_status"], "PASS")
        
        # Check output files exist
        self.assertTrue((self.output_path / "index.json").exists())
        self.assertTrue((self.output_path / "keys.json").exists())
        self.assertTrue((self.output_path / "verification_report.json").exists())
        self.assertTrue((self.output_path / "statements").exists())
        
        # Check statement file exists
        statement_id = self.statement_result["event_id"]
        statement_file = self.output_path / "statements" / f"{statement_id}.json"
        self.assertTrue(statement_file.exists())
        
        # Check statement content
        with open(statement_file, "r") as f:
            stmt_data = json.load(f)
        
        self.assertEqual(stmt_data["statement"]["event_id"], statement_id)
        self.assertEqual(stmt_data["statement"]["subject"], "test:example")
        self.assertEqual(stmt_data["statement"]["issuer"], "did:example:test123")
        self.assertIn("chain_proof", stmt_data)
        self.assertIn("merkle_proof", stmt_data)
        self.assertIn("signature", stmt_data)
        
        # Check receipt is included
        self.assertIn("receipt", stmt_data)
        self.assertEqual(
            stmt_data["receipt"]["transparency_service"],
            "https://test-ts.example.com"
        )
        
        # Check index
        with open(self.output_path / "index.json", "r") as f:
            index_data = json.load(f)
        
        self.assertEqual(index_data["statement_count"], 1)
        self.assertEqual(len(index_data["statements"]), 1)
        self.assertEqual(index_data["statements"][0]["event_id"], statement_id)
        self.assertTrue(index_data["statements"][0]["has_receipt"])
    
    def test_export_empty_vault(self):
        """Export vault with no SCITT events produces empty index."""
        # Create fresh vault without SCITT events
        empty_vault = self.tmp_dir / "empty_vault"
        empty_output = self.tmp_dir / "empty_output"
        
        result = bootstrap_backpack(
            empty_vault,
            uid="empty-test-vault",
            actor="empty_test_actor",
            include_quorum=False,
            quiet=True
        )
        
        keys_data = {
            "keys": [{
                "key_id": result.root_key_id,
                "private_key_b64": result.root_private_key_b64,
                "algorithm": "Ed25519"
            }]
        }
        with open(self.tmp_dir / "empty_keys.json", "w") as f:
            json.dump(keys_data, f)
        
        # Export
        export_result = export_vault_scitt_compat(empty_vault, empty_output)
        
        # Check result
        self.assertTrue(export_result["success"])
        self.assertEqual(export_result["exported_count"], 0)
        
        # Check index is empty
        with open(empty_output / "index.json", "r") as f:
            index_data = json.load(f)
        
        self.assertEqual(index_data["statement_count"], 0)
        self.assertEqual(len(index_data["statements"]), 0)
    
    def test_export_bundle_is_verifiable(self):
        """Export bundle contains all necessary data for independent verification."""
        export_vault_scitt_compat(self.vault_path, self.output_path)
        
        # Load verification report
        with open(self.output_path / "verification_report.json", "r") as f:
            report = json.load(f)
        
        # Check all verification checks passed
        self.assertEqual(report["overall_status"], "PASS")
        
        check_names = [c["check"] for c in report["checks"]]
        self.assertIn("index_json_valid", check_names)
        self.assertIn("keys_json_exists", check_names)
        self.assertIn("statement_files_exist", check_names)
        self.assertIn("chain_integrity", check_names)
        
        # Verify chain proof structure
        statement_id = self.statement_result["event_id"]
        with open(self.output_path / "statements" / f"{statement_id}.json", "r") as f:
            stmt_data = json.load(f)
        
        chain_proof = stmt_data["chain_proof"]
        self.assertNotIn("error", chain_proof)
        self.assertIn("chain_segment", chain_proof)
        self.assertGreater(chain_proof["chain_length"], 0)
        
        # Verify chain linkage
        chain_segment = chain_proof["chain_segment"]
        for i in range(1, len(chain_segment)):
            prev_event = chain_segment[i - 1]
            curr_event = chain_segment[i]
            self.assertEqual(
                curr_event["prev_event_hash"],
                prev_event["event_id"],
                f"Chain broken between {prev_event['event_id']} and {curr_event['event_id']}"
            )
    
    def test_export_bundle_contains_keys(self):
        """Export bundle includes public keys for signature verification."""
        export_vault_scitt_compat(self.vault_path, self.output_path)
        
        with open(self.output_path / "keys.json", "r") as f:
            keys_data = json.load(f)
        
        self.assertIn("keys", keys_data)
        self.assertGreater(len(keys_data["keys"]), 0)
        
        # Check key structure
        key = keys_data["keys"][0]
        self.assertIn("key_id", key)
        self.assertIn("public_key_b64", key)
        self.assertEqual(key["algorithm"], "Ed25519")


class TestExportEdgeCases(unittest.TestCase):
    
    def setUp(self):
        """Create a test vault."""
        self.tmp_dir = Path(tempfile.mkdtemp())
        self.vault_path = self.tmp_dir / "test_vault"
        self.keys_path = self.tmp_dir / "test_keys.json"
        self.output_path = self.tmp_dir / "export_output"
        
        result = bootstrap_backpack(
            self.vault_path,
            uid="edge-case-vault",
            actor="edge_case_actor",
            include_quorum=False,
            quiet=True
        )
        
        keys_data = {
            "keys": [{
                "key_id": result.root_key_id,
                "private_key_b64": result.root_private_key_b64,
                "algorithm": "Ed25519"
            }]
        }
        with open(self.keys_path, "w") as f:
            json.dump(keys_data, f)
    
    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
    
    def test_export_statement_without_receipt(self):
        """Export handles statements without paired receipts."""
        # Add only statement, no receipt
        statement_hash = canonical_hash(b"orphan statement")
        record_scitt_statement(
            self.vault_path,
            self.keys_path,
            statement_hash=statement_hash,
            content_type="application/json",
            subject="test:orphan",
            issuer="did:example:orphan",
            actor="orphan_tester"
        )
        
        # Export
        result = export_vault_scitt_compat(self.vault_path, self.output_path)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["exported_count"], 1)
        
        # Check statement has no receipt
        statement_id = result.get("statement_id", "")
        # Find the statement file
        import glob
        statement_files = list((self.output_path / "statements").glob("*.json"))
        self.assertEqual(len(statement_files), 1)
        
        with open(statement_files[0], "r") as f:
            stmt_data = json.load(f)
        
        self.assertNotIn("receipt", stmt_data)
        self.assertFalse(
            any(s["has_receipt"] for s in json.load(open(self.output_path / "index.json"))["statements"])
        )
    
    def test_export_multiple_statements(self):
        """Export handles multiple statements correctly."""
        # Add multiple statements
        statement_ids = []
        for i in range(3):
            stmt_hash = canonical_hash(f"statement {i}".encode())
            stmt = record_scitt_statement(
                self.vault_path,
                self.keys_path,
                statement_hash=stmt_hash,
                content_type="application/json",
                subject=f"test:statement:{i}",
                issuer=f"did:example:issuer{i}",
                actor=f"actor{i}"
            )
            statement_ids.append(stmt["event_id"])
        
        # Export
        result = export_vault_scitt_compat(self.vault_path, self.output_path)
        
        self.assertTrue(result["success"])
        self.assertEqual(result["exported_count"], 3)
        
        # Check index
        with open(self.output_path / "index.json", "r") as f:
            index_data = json.load(f)
        
        self.assertEqual(index_data["statement_count"], 3)
        exported_ids = [s["event_id"] for s in index_data["statements"]]
        for stmt_id in statement_ids:
            self.assertIn(stmt_id, exported_ids)
        
        # Check all statement files exist
        for stmt_id in statement_ids:
            stmt_file = self.output_path / "statements" / f"{stmt_id}.json"
            self.assertTrue(stmt_file.exists())


if __name__ == "__main__":
    unittest.main()
