import asyncio

import httpx
import pytest

from app.providers import DexScreenerMarketDataProvider, HTTPTransport, SolanaRPCProvider


async def test_rate_limit_circuit():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(429, headers={"retry-after": "30"}))
    ) as client:
        t = HTTPTransport(client, asyncio.Semaphore(1), 0)
        with pytest.raises(httpx.HTTPStatusError):
            await t.request("https://example.test")
        with pytest.raises(RuntimeError, match="CIRCUIT"):
            await t.request("https://example.test")
        assert t.requests == 1
        assert t.rate_limits == 1


async def test_cache_and_readonly():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"result": "ok"}))
    ) as client:
        t = HTTPTransport(client, asyncio.Semaphore(1), 0)
        rpc = SolanaRPCProvider(t)
        assert await rpc.call("getHealth") == {"result": "ok"}
        await rpc.call("getHealth")
        assert t.requests == 1 and t.cache_hits == 1
        with pytest.raises(ValueError):
            await rpc.call("sendTransaction")


async def test_dex_missing_data_never_becomes_live_tradable():
    payload = [
        {
            "chainId": "solana",
            "baseToken": {"address": "mint", "symbol": "TEST"},
            "pairAddress": "pool",
            "priceUsd": "1.2",
            "liquidity": {"usd": 50000},
            "volume": {"m5": 1000},
        }
    ]
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload))
    ) as client:
        provider = DexScreenerMarketDataProvider(HTTPTransport(client, asyncio.Semaphore(1), 0))
        snapshots = await provider.fetch(["mint"])
        assert snapshots[0].data_quality_status == "UNAVAILABLE"
        assert not snapshots[0].token_safety_known
