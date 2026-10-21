"""Run from repository root: .venv/Scripts/python benchmarks/run.py"""
import argparse
import asyncio
import json
import platform
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import Store, metadata
from app.domain import D, MarketSnapshot, now
from app.engine import TradingEngine


async def benchmark(events: int):
    folder = Path(__file__).resolve().parent / "runs"
    folder.mkdir(exist_ok=True)
    store = Store("sqlite:///" + str(folder / f"bench-{uuid4().hex}.db"))
    metadata.create_all(store.engine)
    engine = TradingEngine(store)
    process = psutil.Process()
    process.cpu_percent()
    await asyncio.sleep(2)
    idle_cpu = process.cpu_percent()
    initial_rss = process.memory_info().rss
    queue: asyncio.Queue = asyncio.Queue(maxsize=256)
    delays, lags = [], []
    produced = consumed = 0
    started = time.perf_counter()
    base = now()
    done = False

    async def producer():
        nonlocal produced
        for i in range(events):
            intended = started + i / 1000
            await asyncio.sleep(max(0, intended - time.perf_counter()))
            s = MarketSnapshot(event_id=str(i), event_time=base + timedelta(microseconds=i), provider="DEMO", token_mint="BENCH", symbol="BENCH", pool_address="BENCH", price=D(1)+D(i % 100)/10000, liquidity=D(100000), volume=D(10000+i), buys=80, sells=20, token_safety_known=True, suspicious=False, execution_model="SYNTHETIC_CONSERVATIVE")
            await queue.put((s, intended))
            produced += 1

    async def consumer():
        nonlocal consumed
        while consumed < events:
            s, intended = await queue.get()
            await asyncio.to_thread(engine.process, s)
            delays.append((time.perf_counter() - intended)*1000)
            consumed += 1
            queue.task_done()

    async def heartbeat():
        while not done:
            before = time.perf_counter()
            await asyncio.sleep(.01)
            lags.append(max(0, (time.perf_counter()-before-.01)*1000))

    pulse = asyncio.create_task(heartbeat())
    await asyncio.gather(producer(), consumer())
    done = True
    await pulse
    elapsed = time.perf_counter()-started

    def percentiles(values):
        ordered = sorted(values)
        return {f"p{p}": ordered[min(len(ordered)-1, int(len(ordered)*p/100))] for p in (50,95,99)}

    result = {"hardware": platform.platform(), "processor": platform.processor(), "logical_cpus": psutil.cpu_count(), "python": platform.python_version(), "storage": "SQLite WAL FULL; one durable transaction per event", "events_produced": produced, "events_consumed": consumed, "dropped": produced-consumed, "target_rate": 1000, "achieved_events_per_second": consumed/elapsed, "elapsed_seconds": elapsed, "processing_ms": percentiles(list(engine.latencies)), "end_to_end_including_backpressure_ms": percentiles(delays), "event_loop_lag_ms": percentiles(lags), "idle_cpu_one_core_percent": idle_cpu, "initial_rss_mb": initial_rss/1024**2, "final_rss_mb": process.memory_info().rss/1024**2, "memory_growth_mb": (process.memory_info().rss-initial_rss)/1024**2}
    (folder / "latest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    store.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", type=int, default=1000)
    args = parser.parse_args()
    if not 1 <= args.events <= 100000:
        parser.error("events must be 1..100000")
    asyncio.run(benchmark(args.events))
