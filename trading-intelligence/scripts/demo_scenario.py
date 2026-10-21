"""Real Demo provider, isolated ledger, paced fills; never touches user's session."""
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.database import Store, metadata
from app.domain import D
from app.engine import TradingEngine
from app.providers import DemoMarketDataProvider


async def main():
    root = Path(__file__).resolve().parents[1]
    store = Store("sqlite:///" + str(root / "benchmarks" / "runs" / f"scenario-{uuid4().hex}.db"))
    metadata.create_all(store.engine)
    engine = TradingEngine(store)
    demo = DemoMarketDataProvider()
    engine.control("start")
    for _ in range(8):
        for s in await demo.fetch([]):
            engine.process(s)
        await asyncio.sleep(1.05)
    opened = len(engine.state["positions"])
    assert opened > 0, "No demo fills"
    engine.control("stop")
    engine.control("close-all")
    await asyncio.sleep(1.05)
    for s in await demo.fetch([]):
        engine.process(s)
    assert not engine.state["positions"]
    assert D(engine.state["cash"]) - D("70") == D(engine.state["realized"])
    restored = TradingEngine(store)
    assert restored.state["cash"] == engine.state["cash"]
    result = {"scenario": "SYNTHETIC_DEMO_NOT_MARKET_PERFORMANCE", "opened_positions": opened, "closed_positions": engine.state["closed"], "cash": engine.state["cash"], "realized": engine.state["realized"], "fees": engine.state["fees"], "decision_count": engine.state["decision_count"], "recovery_verified": True}
    (root / "docs" / "demo-scenario.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    store.engine.dispose()


asyncio.run(main())
