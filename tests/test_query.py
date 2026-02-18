import json
import tempfile
import time
import unittest
from pathlib import Path

from provara.canonical_json import canonical_dumps
from provara.query import VaultIndex


def _event(i: int, actor: str, event_type: str, ts: str, tag: str) -> dict:
    return {
        "event_id": f"evt_{i:06d}",
        "type": event_type,
        "actor": actor,
        "actor_key_id": f"kid_{actor}",
        "timestamp_utc": ts,
        "prev_event_hash": None if i == 0 else f"evt_{i-1:06d}",
        "sig": f"sig_{i}",
        "payload": {
            "subject": f"s{i % 5}",
            "predicate": "tag",
            "value": i,
            "tag": tag,
        },
    }


def _write_events(vault: Path, events: list[dict]) -> None:
    events_path = vault / "events" / "events.ndjson"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(canonical_dumps(e) + "\n")


class TestQueryIndex(unittest.TestCase):
    def test_build_and_query_by_actor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = [
                _event(0, "a1", "OBSERVATION", "2026-01-01T00:00:00Z", "alpha"),
                _event(1, "a2", "ASSERTION", "2026-01-02T00:00:00Z", "beta"),
                _event(2, "a1", "OBSERVATION", "2026-01-03T00:00:00Z", "alpha"),
            ]
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()
                rows = idx.query_by_actor("a1")

            self.assertEqual(len(rows), 2)
            self.assertTrue(all(r["actor"] == "a1" for r in rows))

    def test_query_by_time_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = [
                _event(0, "a1", "OBSERVATION", "2026-01-01T00:00:00Z", "alpha"),
                _event(1, "a1", "OBSERVATION", "2026-06-01T00:00:00Z", "beta"),
                _event(2, "a1", "OBSERVATION", "2027-01-01T00:00:00Z", "alpha"),
            ]
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()
                rows = idx.query_by_time_range("2026-01-01T00:00:00Z", "2026-12-31T23:59:59Z")
            self.assertEqual(len(rows), 2)

    def test_query_by_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = [
                _event(0, "a1", "OBSERVATION", "2026-01-01T00:00:00Z", "alpha"),
                _event(1, "a2", "OBSERVATION", "2026-01-02T00:00:00Z", "beta"),
            ]
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()
                rows = idx.query_by_content("tag", "alpha")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["actor"], "a1")

    def test_incremental_update_reflects_new_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = [
                _event(0, "a1", "OBSERVATION", "2026-01-01T00:00:00Z", "alpha"),
                _event(1, "a2", "OBSERVATION", "2026-01-02T00:00:00Z", "beta"),
            ]
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()
                self.assertEqual(len(idx.query_by_actor("a1")), 1)

                with (vault / "events" / "events.ndjson").open("a", encoding="utf-8") as f:
                    f.write(canonical_dumps(_event(2, "a1", "ASSERTION", "2026-01-03T00:00:00Z", "alpha")) + "\n")

                idx.update()
                self.assertEqual(len(idx.query_by_actor("a1")), 2)

    def test_delete_index_then_rebuild_same_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = [_event(i, "a1", "OBSERVATION", f"2026-01-{i+1:02d}T00:00:00Z", "alpha") for i in range(5)]
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()
                first = idx.query_by_actor("a1")

            db_path = vault / ".index" / "events.db"
            db_path.unlink()

            with VaultIndex(vault) as idx2:
                idx2.build()
                second = idx2.query_by_actor("a1")
            self.assertEqual(first, second)

    def test_empty_vault_returns_empty_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _write_events(vault, [])

            with VaultIndex(vault) as idx:
                idx.build()

                self.assertEqual(idx.query_by_actor("none"), [])
                self.assertEqual(idx.query_by_type("OBSERVATION"), [])
                self.assertEqual(idx.query_by_time_range("2026-01-01", "2026-12-31"), [])

    def test_perf_10k_query_by_actor_under_10ms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = []
            for i in range(10_000):
                actor = f"actor_{i % 1000}"
                events.append(_event(i, actor, "OBSERVATION", "2026-01-01T00:00:00Z", "alpha"))
            _write_events(vault, events)

            with VaultIndex(vault) as idx:
                idx.build()

                start = time.perf_counter()
                rows = idx.query_by_actor("actor_777")
                elapsed = (time.perf_counter() - start) * 1000.0

                self.assertGreater(len(rows), 0)
                self.assertLess(elapsed, 10.0)


if __name__ == "__main__":
    unittest.main()
