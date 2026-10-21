import asyncio
import math
import time
from typing import Protocol
from uuid import uuid4

import httpx

from .domain import D, MarketSnapshot, now


class MarketDataProvider(Protocol):
    async def fetch(self, mints: list[str]) -> list[MarketSnapshot]: ...


class DemoMarketDataProvider:
    def __init__(self) -> None:
        self.tick = 0
        self.run = str(uuid4())

    async def fetch(self, mints: list[str]) -> list[MarketSnapshot]:
        self.tick += 1
        result = []
        for i, symbol in enumerate(["EMBER", "TIDAL", "MOSS"]):
            phase = (self.tick + i * 9) % 80
            # Reproducible rise, reversal and flat intervals; not real tokens.
            price = D(
                str(round((1 + i) * (1 + 0.008 * min(phase, 35) - 0.012 * max(0, phase - 35)), 6))
            )
            result.append(
                MarketSnapshot(
                    event_id=f"demo:{self.run}:{self.tick}:{i}",
                    event_time=now(),
                    provider="DEMO",
                    token_mint=f"DEMO-{symbol}",
                    symbol=symbol,
                    pool_address=f"DEMO-POOL-{i}",
                    price=price,
                    liquidity=D("100000"),
                    volume=D(10000 + phase * 250),
                    buys=80 if phase < 35 else 20,
                    sells=20 if phase < 35 else 80,
                    token_safety_known=True,
                    suspicious=False,
                    execution_model="SYNTHETIC_CONSERVATIVE",
                )
            )
        return result


class HTTPTransport:
    def __init__(
        self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore, interval: float = 1.0
    ):
        self.client, self.semaphore, self.interval = client, semaphore, interval
        self.lock = asyncio.Lock()
        self.last = 0.0
        self.open_until = 0.0
        self.failures = 0
        self.requests = self.errors = self.rate_limits = self.cache_hits = 0
        self.cache: dict[str, tuple[float, object]] = {}

    async def request(self, url: str, body: dict | None = None) -> object:
        key = url + str(body)
        cached = self.cache.get(key)
        if cached and cached[0] > time.monotonic():
            self.cache_hits += 1
            return cached[1]
        async with self.lock:
            if time.monotonic() < self.open_until:
                raise RuntimeError("PROVIDER_CIRCUIT_OPEN")
            await asyncio.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            try:
                async with self.semaphore:
                    self.last = time.monotonic()
                    self.requests += 1
                    response = await (
                        self.client.post(url, json=body) if body else self.client.get(url)
                    )
                    if response.status_code == 429:
                        self.rate_limits += 1
                        retry = response.headers.get("retry-after", "30")
                        self.open_until = time.monotonic() + min(
                            300, max(1, float(retry) if retry.isdigit() else 30)
                        )
                    response.raise_for_status()
                    payload = response.json()
                    self.failures = 0
                    if len(self.cache) >= 100:
                        self.cache.clear()
                    self.cache[key] = (time.monotonic() + 10, payload)
                    return payload
            except Exception:
                self.failures += 1
                self.errors += 1
                if self.failures >= 3:
                    self.open_until = time.monotonic() + 30
                raise


class DexScreenerMarketDataProvider:
    def __init__(self, transport: HTTPTransport):
        self.transport = transport

    async def fetch(self, mints: list[str]) -> list[MarketSnapshot]:
        if not mints:
            return []
        payload = await self.transport.request(
            "https://api.dexscreener.com/tokens/v1/solana/" + ",".join(mints[:30])
        )
        if not isinstance(payload, list):
            raise ValueError("INVALID_PROVIDER_PAYLOAD")
        best: dict[str, dict] = {}
        for pair in payload:
            if (
                pair.get("chainId") != "solana"
                or pair.get("baseToken", {}).get("address") not in mints
            ):
                continue
            mint = pair["baseToken"]["address"]
            if mint not in best or D(str(pair.get("liquidity", {}).get("usd", 0))) > D(
                str(best[mint].get("liquidity", {}).get("usd", 0))
            ):
                best[mint] = pair
        snapshots = []
        for mint, pair in best.items():
            if not pair.get("priceUsd"):
                continue
            received = now()
            counts = pair.get("txns", {}).get("m5", {})
            snapshots.append(
                MarketSnapshot(
                    event_id=f"dex:{pair['pairAddress']}:{math.floor(time.time() / 10)}",
                    event_time=received,
                    received_time=received,
                    provider="DEXSCREENER",
                    token_mint=mint,
                    symbol=pair["baseToken"].get("symbol", "UNKNOWN")[:30],
                    pool_address=pair["pairAddress"],
                    price=D(str(pair["priceUsd"])),
                    liquidity=D(str(pair.get("liquidity", {}).get("usd", 0))),
                    volume=D(str(pair.get("volume", {}).get("m5", 0))),
                    buys=counts.get("buys"),
                    sells=counts.get("sells"),
                    data_quality_status="UNAVAILABLE",
                )
            )
        # API does not provide the timestamp of the underlying price. Observation
        # time is not proof of freshness; quality remains UNAVAILABLE for trading.
        return snapshots


class SolanaRPCProvider:
    """Fixed read-only public endpoint; no signing, arbitrary RPC or private APIs."""

    def __init__(self, transport: HTTPTransport):
        self.transport = transport

    async def call(self, method: str, params: list | None = None):
        if method not in {"getHealth", "getSlot", "getTokenSupply", "getAccountInfo"}:
            raise ValueError("READ_ONLY_METHOD_REQUIRED")
        return await self.transport.request(
            "https://api.mainnet-beta.solana.com",
            {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []},
        )
