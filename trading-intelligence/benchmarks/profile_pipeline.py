"""Profiles the actual synchronous writer, not asyncio's waiting thread."""
import cProfile
import io
import pstats
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import Store, metadata
from app.domain import D, MarketSnapshot, now
from app.engine import TradingEngine

root = Path(__file__).resolve().parents[1]
store = Store("sqlite:///" + str(root / "benchmarks/runs" / f"profile-{uuid4().hex}.db"))
metadata.create_all(store.engine)
engine = TradingEngine(store)
base = now()
profiler = cProfile.Profile()
profiler.enable()
for i in range(1000):
    engine.process(MarketSnapshot(event_id=str(i), event_time=base+timedelta(microseconds=i), provider="DEMO", token_mint="BENCH", symbol="BENCH", pool_address="BENCH", price=D(1)+D(i%100)/10000, liquidity=D(100000), volume=D(10000+i), buys=80, sells=20, token_safety_known=True, suspicious=False, execution_model="SYNTHETIC_CONSERVATIVE"))
profiler.disable()
output = io.StringIO()
pstats.Stats(profiler, stream=output).sort_stats("cumulative").print_stats(45)
destination = root / "docs" / (sys.argv[1] if len(sys.argv)>1 else "v11-profile-before.txt")
destination.write_text(output.getvalue(), encoding="utf-8")
print(output.getvalue())
store.engine.dispose()
