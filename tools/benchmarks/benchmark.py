#!/usr/bin/env python3
"""Reproducible performance benchmarks for Provara reducers and core operations."""

from __future__ import annotations

import ctypes
import json
import os
import platform
import random
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from provara.bootstrap_v0 import bootstrap_backpack
from provara.canonical_json import canonical_dumps
from provara.reducer_v0 import SovereignReducerV0
from provara.reducer_v1 import reduce_stream, save_checkpoint
from provara.sync_v0 import load_events, verify_all_causal_chains

SEED = 1337
EVENT_SIZES = (100, 1_000, 10_000, 100_000)
JSON_SIZES = (1_000, 10_000, 100_000)
RESULTS_PATH = Path("tools/benchmarks/results.json")


@dataclass
class BenchmarkRow:
    benchmark: str
    size: int
    total_seconds: float
    throughput: float
    peak_memory_mb: float | None = None
    speedup: float | None = None


class RSSSampler:
    """Cross-platform RSS sampler using stdlib/system calls."""

    def __init__(self) -> None:
        self.peak = self.current()

    def sample(self) -> int:
        rss = self.current()
        if rss > self.peak:
            self.peak = rss
        return rss

    @staticmethod
    def current() -> int:
        system = platform.system()
        if system == "Linux":
            try:
                with open("/proc/self/statm", "r", encoding="utf-8") as f:
                    parts = f.read().split()
                rss_pages = int(parts[1])
                return rss_pages * os.sysconf("SC_PAGE_SIZE")
            except (OSError, ValueError, IndexError):
                return 0

        if system == "Windows":
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
            psapi = ctypes.windll.psapi
            psapi.GetProcessMemoryInfo.argtypes = [
                ctypes.c_void_p,
                ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                ctypes.c_ulong,
            ]
            psapi.GetProcessMemoryInfo.restype = ctypes.c_int
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            ok = psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb)
            if not ok:
                return 0
            return int(counters.WorkingSetSize)

        # macOS fallback: ru_maxrss is peak, still useful as a conservative value
        try:
            import resource

            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        except Exception:
            return 0


def _events_path(vault_path: Path) -> Path:
    return vault_path / "events" / "events.ndjson"


def _make_event(idx: int, actor: str, prev: str | None, rng: random.Random) -> Dict[str, Any]:
    event_type = "OBSERVATION" if idx % 5 else "ASSERTION"
    score = round(rng.random(), 6)
    return {
        "event_id": f"evt_{idx:08d}",
        "type": event_type,
        "actor": actor,
        "prev_event_hash": prev,
        "timestamp_utc": f"2026-02-18T00:{idx % 60:02d}:{(idx // 60) % 60:02d}Z",
        "payload": {
            "subject": f"subject_{idx % 97}",
            "predicate": "score",
            "value": {"seq": idx, "score": score, "flag": idx % 2 == 0},
            "confidence": 0.5 + (score / 2.0),
        },
    }


def _append_events(vault_path: Path, n: int, seed: int = SEED) -> None:
    rng = random.Random(seed)
    actors = [f"actor_{i}" for i in range(8)]
    prev: Dict[str, str | None] = {a: None for a in actors}

    events_file = _events_path(vault_path)
    events_file.parent.mkdir(parents=True, exist_ok=True)

    with events_file.open("a", encoding="utf-8") as f:
        for i in range(n):
            actor = actors[i % len(actors)]
            event = _make_event(i, actor, prev[actor], rng)
            prev[actor] = event["event_id"]
            f.write(canonical_dumps(event) + "\n")


def _create_synthetic_vault(path: Path, n: int, seed: int = SEED) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _append_events(path, n, seed=seed)


def _run_to_final(vault_path: Path, checkpoint: Path | None = None) -> None:
    for _ in reduce_stream(vault_path, checkpoint=checkpoint, snapshot_interval=10_000):
        pass


def bench_vault_creation(ns: Iterable[int]) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []
    for n in ns:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            start = time.perf_counter()
            result = bootstrap_backpack(vault, uid=f"bench-{n}", actor="bench", quiet=True)
            if not result.success:
                raise RuntimeError(f"bootstrap_backpack failed for N={n}: {result.errors}")
            _append_events(vault, n, seed=SEED)
            total = time.perf_counter() - start
            rows.append(
                BenchmarkRow(
                    benchmark="vault_creation",
                    size=n,
                    total_seconds=total,
                    throughput=(n / total) if total > 0 else 0.0,
                )
            )
    return rows


def bench_chain_verification(ns: Iterable[int]) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []
    for n in ns:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            _create_synthetic_vault(vault, n, seed=SEED)

            start = time.perf_counter()
            events = load_events(_events_path(vault))
            results = verify_all_causal_chains(events)
            total = time.perf_counter() - start
            if not all(results.values()):
                raise RuntimeError(f"Causal chain verification failed for N={n}")

            rows.append(
                BenchmarkRow(
                    benchmark="chain_verification",
                    size=n,
                    total_seconds=total,
                    throughput=(n / total) if total > 0 else 0.0,
                )
            )
    return rows


def bench_streaming_reduce(ns: Iterable[int]) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []

    for n in ns:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            _create_synthetic_vault(vault, n, seed=SEED)

            # streaming
            stream_mem = RSSSampler()
            start = time.perf_counter()
            for _ in reduce_stream(vault, snapshot_interval=2000):
                stream_mem.sample()
            stream_total = time.perf_counter() - start
            rows.append(
                BenchmarkRow(
                    benchmark="streaming_reduce_v1",
                    size=n,
                    total_seconds=stream_total,
                    throughput=(n / stream_total) if stream_total > 0 else 0.0,
                    peak_memory_mb=stream_mem.peak / (1024 * 1024),
                )
            )

            # full-load
            full_mem = RSSSampler()
            start = time.perf_counter()
            events = load_events(_events_path(vault))
            full_mem.sample()
            reducer = SovereignReducerV0()
            reducer.apply_events(events)
            full_mem.sample()
            full_total = time.perf_counter() - start
            rows.append(
                BenchmarkRow(
                    benchmark="full_reduce_v0",
                    size=n,
                    total_seconds=full_total,
                    throughput=(n / full_total) if full_total > 0 else 0.0,
                    peak_memory_mb=full_mem.peak / (1024 * 1024),
                )
            )

    return rows


def bench_checkpoint_resume(ns: Iterable[int]) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []

    for n in ns:
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            _create_synthetic_vault(vault, n, seed=SEED)

            interval = max(1, n // 2)
            snapshots = list(reduce_stream(vault, snapshot_interval=interval))
            if not snapshots:
                continue
            cp_path = vault / "checkpoints" / "half.chk"
            save_checkpoint(cp_path, snapshots[0])

            start = time.perf_counter()
            _run_to_final(vault)
            full_total = time.perf_counter() - start

            start = time.perf_counter()
            _run_to_final(vault, checkpoint=cp_path)
            resume_total = time.perf_counter() - start

            rows.append(
                BenchmarkRow(
                    benchmark="checkpoint_resume",
                    size=n,
                    total_seconds=resume_total,
                    throughput=(n / resume_total) if resume_total > 0 else 0.0,
                    speedup=(full_total / resume_total) if resume_total > 0 else None,
                )
            )

    return rows


def bench_canonical_json(ns: Iterable[int]) -> List[BenchmarkRow]:
    rows: List[BenchmarkRow] = []
    rng = random.Random(SEED)

    for n in ns:
        payloads = [
            {
                "k": i,
                "f": round(rng.random(), 8),
                "nested": {"a": i % 10, "b": bool(i % 2)},
                "tags": ["alpha", "beta", i % 7],
            }
            for i in range(n)
        ]

        start = time.perf_counter()
        for payload in payloads:
            canonical_dumps(payload)
        total = time.perf_counter() - start
        rows.append(
            BenchmarkRow(
                benchmark="canonical_json",
                size=n,
                total_seconds=total,
                throughput=(n / total) if total > 0 else 0.0,
            )
        )

    return rows


def _table(rows: List[BenchmarkRow]) -> str:
    header = (
        f"{'Benchmark':<22} {'N':>8} {'Total(s)':>12} {'Throughput/s':>14} "
        f"{'Peak MB':>10} {'Speedup':>10}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        lines.append(
            f"{row.benchmark:<22} {row.size:>8} {row.total_seconds:>12.4f} "
            f"{row.throughput:>14.2f} "
            f"{(f'{row.peak_memory_mb:.2f}' if row.peak_memory_mb is not None else '-'):>10} "
            f"{(f'{row.speedup:.2f}x' if row.speedup is not None else '-'):>10}"
        )
    return "\n".join(lines)


def run_all() -> Dict[str, Any]:
    all_rows: List[BenchmarkRow] = []
    all_rows.extend(bench_vault_creation(EVENT_SIZES))
    all_rows.extend(bench_chain_verification(EVENT_SIZES))
    all_rows.extend(bench_streaming_reduce(EVENT_SIZES))
    all_rows.extend(bench_checkpoint_resume(EVENT_SIZES))
    all_rows.extend(bench_canonical_json(JSON_SIZES))

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python_version": platform.python_version(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": os.cpu_count(),
        },
        "seed": SEED,
        "rows": [asdict(r) for r in all_rows],
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(_table(all_rows))
    print(f"\nResults written: {RESULTS_PATH}")
    return report


def main() -> None:
    run_all()


if __name__ == "__main__":
    main()
