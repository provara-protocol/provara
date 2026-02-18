import ctypes
import json
import platform
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Iterable, List

from provara.canonical_json import canonical_dumps
from provara.reducer_v0 import SovereignReducerV0
from provara.reducer_v1 import (
    VaultState,
    reduce_stream,
    save_checkpoint,
)
from provara.backpack_integrity import merkle_root_hex


def _obs(event_id: str, actor: str, prev: str | None, i: int) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "type": "OBSERVATION",
        "actor": actor,
        "prev_event_hash": prev,
        "timestamp_utc": f"2026-02-18T00:{i % 60:02d}:00Z",
        "payload": {
            "subject": f"sensor_{i % 7}",
            "predicate": "status",
            "value": {"seq": i, "ok": i % 3 != 0},
            "confidence": 0.9,
        },
    }


def _write_events(vault_path: Path, events: Iterable[Dict[str, Any]]) -> None:
    events_path = vault_path / "events" / "events.ndjson"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    with events_path.open("w", encoding="utf-8") as f:
        for event in events:
            f.write(canonical_dumps(event) + "\n")


def _build_events(n: int) -> List[Dict[str, Any]]:
    actors = ["actor_a", "actor_b", "actor_c"]
    prev_by_actor: Dict[str, str | None] = {a: None for a in actors}
    out: List[Dict[str, Any]] = []
    for i in range(n):
        actor = actors[i % len(actors)]
        event = _obs(f"evt_{i:06d}", actor, prev_by_actor[actor], i)
        prev_by_actor[actor] = event["event_id"]
        out.append(event)
    return out


def _expected_from_full(events: List[Dict[str, Any]]) -> VaultState:
    actor_chain_heads: Dict[str, str] = {}
    actors = set()
    type_counts: Dict[str, int] = {}

    for event in events:
        actor = str(event.get("actor") or "")
        event_id = str(event.get("event_id") or "")
        event_type = str(event.get("type") or "")

        if actor:
            actors.add(actor)
            if event_id:
                actor_chain_heads[actor] = event_id

        if event_type:
            type_counts[event_type] = type_counts.get(event_type, 0) + 1

    leaves = [canonical_dumps(e).encode("utf-8") for e in events]
    return VaultState(
        event_count=len(events),
        actor_chain_heads=actor_chain_heads,
        actors=actors,
        type_counts=type_counts,
        merkle_root=merkle_root_hex(leaves),
        last_event_id=str(events[-1].get("event_id")) if events else "",
        last_event_offset=0,
    )


def _iter_final_state(vault_path: Path, **kwargs: Any) -> VaultState:
    state = None
    for snapshot in reduce_stream(vault_path, **kwargs):
        state = snapshot
    assert state is not None
    return state


def _rss_bytes() -> int:
    if platform.system() == "Windows":
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        psapi.GetProcessMemoryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
            ctypes.c_ulong,
        ]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        handle = kernel32.GetCurrentProcess()
        ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
        if not ok:
            raise RuntimeError("GetProcessMemoryInfo failed")
        return int(counters.WorkingSetSize)

    import resource

    usage = resource.getrusage(resource.RUSAGE_SELF)
    if platform.system() == "Darwin":
        return int(usage.ru_maxrss)
    return int(usage.ru_maxrss) * 1024


class TestReducerV1(unittest.TestCase):
    def test_stream_100_events_matches_expected_and_v0_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = _build_events(100)
            _write_events(vault, events)

            final_state = _iter_final_state(vault, snapshot_interval=25)
            expected = _expected_from_full(events)

            self.assertEqual(final_state.event_count, expected.event_count)
            self.assertEqual(final_state.actor_chain_heads, expected.actor_chain_heads)
            self.assertEqual(final_state.actors, expected.actors)
            self.assertEqual(final_state.type_counts, expected.type_counts)
            self.assertEqual(final_state.merkle_root, expected.merkle_root)
            self.assertEqual(final_state.last_event_id, expected.last_event_id)

            v0 = SovereignReducerV0()
            v0.apply_events(events)
            self.assertEqual(final_state.event_count, v0.state["metadata"]["event_count"])
            self.assertEqual(final_state.last_event_id, v0.state["metadata"]["last_event_id"])

    def test_checkpoint_resume_matches_full_stream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = _build_events(250)
            _write_events(vault, events)

            interval = 50
            snapshots = list(reduce_stream(vault, snapshot_interval=interval))
            self.assertEqual(len(snapshots), 5)
            mid_snapshot = snapshots[2]

            cp_path = vault / "checkpoints" / "resume.chk"
            save_checkpoint(cp_path, mid_snapshot)

            resumed_final = _iter_final_state(vault, checkpoint=cp_path, snapshot_interval=interval)
            full_final = snapshots[-1]

            self.assertEqual(resumed_final.event_count, full_final.event_count)
            self.assertEqual(resumed_final.actor_chain_heads, full_final.actor_chain_heads)
            self.assertEqual(resumed_final.actors, full_final.actors)
            self.assertEqual(resumed_final.type_counts, full_final.type_counts)
            self.assertEqual(resumed_final.merkle_root, full_final.merkle_root)
            self.assertEqual(resumed_final.last_event_id, full_final.last_event_id)

    def test_stream_empty_vault_returns_valid_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _write_events(vault, [])

            snapshots = list(reduce_stream(vault, snapshot_interval=10))
            self.assertEqual(len(snapshots), 1)
            state = snapshots[0]

            self.assertEqual(state.event_count, 0)
            self.assertEqual(state.actor_chain_heads, {})
            self.assertEqual(state.actors, set())
            self.assertEqual(state.type_counts, {})
            self.assertEqual(state.last_event_id, "")
            self.assertEqual(len(state.merkle_root), 64)

    def test_memory_usage_10k_events_peak_rss_under_50mb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            events = _build_events(10_000)
            _write_events(vault, events)

            baseline = _rss_bytes()
            peak = baseline
            for _ in reduce_stream(vault, snapshot_interval=500):
                peak = max(peak, _rss_bytes())

            growth_mb = (peak - baseline) / (1024 * 1024)
            self.assertLess(growth_mb, 50.0)


if __name__ == "__main__":
    unittest.main()
