import json
import tempfile
import unittest
from pathlib import Path

from provara.bootstrap_v0 import bootstrap_backpack
from provara.migrate import migrate_vault


class TestMigrate(unittest.TestCase):
    def test_migrate_to_same_version_is_noop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = bootstrap_backpack(vault, actor="migrator", quiet=True)
            self.assertTrue(result.success)

            report = migrate_vault(vault, target_version="1.0")
            self.assertEqual(report.source_version, "1.0")
            self.assertEqual(report.target_version, "1.0")
            self.assertEqual(report.events_migrated, 0)

    def test_migrate_to_v1_1_records_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = bootstrap_backpack(vault, actor="migrator", quiet=True)
            self.assertTrue(result.success)

            report = migrate_vault(vault, target_version="1.1")
            self.assertEqual(report.source_version, "1.0")
            self.assertEqual(report.target_version, "1.1")
            self.assertTrue(report.migration_event_id.startswith("evt_"))

            events_path = vault / "events" / "events.ndjson"
            lines = [ln for ln in events_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
            last_event = json.loads(lines[-1])
            self.assertEqual(last_event.get("type"), "com.provara.migration")
            self.assertEqual(last_event.get("payload", {}).get("from_version"), "1.0")
            self.assertEqual(last_event.get("payload", {}).get("to_version"), "1.1")

    def test_dry_run_makes_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = bootstrap_backpack(vault, actor="migrator", quiet=True)
            self.assertTrue(result.success)

            events_path = vault / "events" / "events.ndjson"
            genesis_path = vault / "identity" / "genesis.json"
            before_events = events_path.read_bytes()
            before_genesis = genesis_path.read_bytes()

            report = migrate_vault(vault, target_version="1.1", dry_run=True)
            self.assertEqual(report.target_version, "1.1")
            self.assertEqual(events_path.read_bytes(), before_events)
            self.assertEqual(genesis_path.read_bytes(), before_genesis)

    def test_migrate_already_current_skips_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = bootstrap_backpack(vault, actor="migrator", quiet=True)
            self.assertTrue(result.success)

            genesis_path = vault / "identity" / "genesis.json"
            genesis = json.loads(genesis_path.read_text(encoding="utf-8"))
            genesis["spec_version"] = "1.1"
            genesis_path.write_text(json.dumps(genesis, indent=2), encoding="utf-8")

            report = migrate_vault(vault, target_version="1.1")
            self.assertEqual(report.source_version, "1.1")
            self.assertEqual(report.target_version, "1.1")
            self.assertEqual(report.events_migrated, 0)

    def test_bad_target_version_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            result = bootstrap_backpack(vault, actor="migrator", quiet=True)
            self.assertTrue(result.success)

            with self.assertRaises(ValueError):
                migrate_vault(vault, target_version="9.9")


if __name__ == "__main__":
    unittest.main()
