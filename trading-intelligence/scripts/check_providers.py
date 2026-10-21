"""Read-only external check; does not change runtime settings."""
import asyncio
import json
import sys
from pathlib import Path
import httpx
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.providers import DexScreenerMarketDataProvider, HTTPTransport, SolanaRPCProvider


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        t = HTTPTransport(client, asyncio.Semaphore(2))
        result = {}
        for name, call in [("dexscreener", DexScreenerMarketDataProvider(t).fetch(["So11111111111111111111111111111111111111112"])), ("solana_rpc", SolanaRPCProvider(t).call("getHealth"))]:
            try:
                data = await call
                result[name] = {"status": "OK", "snapshots": len(data), "trading_enabled": False} if isinstance(data, list) else {"status": "OK", "response": data}
            except Exception as exc:
                result[name] = {"status": "UNAVAILABLE", "error": type(exc).__name__}
        output = Path(__file__).resolve().parents[1] / "docs" / "provider-check.json"
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2))


asyncio.run(main())
