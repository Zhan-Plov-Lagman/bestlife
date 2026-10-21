import asyncio
import json
import logging
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Literal

import httpx
import psutil
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, ConfigDict

from .analytics import FEATURE_CATALOG
from .database import Store
from .domain import Settings
from .engine import TradingEngine
from .providers import (
    DemoMarketDataProvider,
    DexScreenerMarketDataProvider,
    HTTPTransport,
    SolanaRPCProvider,
)

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("trading")
ORIGINS = ["http://127.0.0.1:3000", "http://localhost:3000"]


class Runtime:
    def __init__(self):
        self.engine = TradingEngine(Store())
        self.clients: set[asyncio.Queue] = set()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.lag_ms = 0.0
        self.coalesced = 0
        self.process = psutil.Process()
        self.transport: HTTPTransport | None = None
        self.provider_error: str | None = None
        self.csrf = secrets.token_urlsafe(32)
        self.last_scan = 0.0

    async def produce(self, client: httpx.AsyncClient):
        self.transport = HTTPTransport(client, asyncio.Semaphore(2))
        demo = DemoMarketDataProvider()
        dex = DexScreenerMarketDataProvider(self.transport)
        while True:
            cfg = self.engine.cfg
            # Watch markets while stopped to permit emergency exits and explain skips.
            try:
                snapshots = await (demo if cfg.provider == "DEMO" else dex).fetch(cfg.token_mints)
                self.provider_error = None if snapshots else "NO_CONFIGURED_OR_AVAILABLE_TOKENS"
                if not snapshots:
                    self.engine.state["provider_healthy"] = False
                for snapshot in snapshots:
                    await self.queue.put(snapshot)  # backpressure, never drop critical events
                self.last_scan = time.monotonic()
            except Exception as exc:
                self.engine.state["provider_healthy"] = False
                self.provider_error = type(exc).__name__
                logger.warning(json.dumps({"event": "provider_error", "error": type(exc).__name__}))
            await asyncio.sleep(
                10
                if cfg.provider == "DEXSCREENER"
                else {"ECO": 5, "BALANCED": 2, "PERFORMANCE": 1}[cfg.performance]
            )

    async def consume(self):
        while True:
            item = await self.queue.get()
            try:
                if not self.engine.state["fault"]:
                    await asyncio.to_thread(self.engine.process, item)
            except Exception as exc:
                logger.error(json.dumps({"event": "pipeline_halted", "error": type(exc).__name__}))
            finally:
                self.queue.task_done()

    def snapshot(self):
        state = self.engine.snapshot()
        lat = sorted(self.engine.latencies)
        t = self.transport
        state["monitor"] = {
            "cpu_percent_one_core": self.process.cpu_percent(),
            "rss_mb": self.process.memory_info().rss / 1024**2,
            "event_loop_lag_ms": self.lag_ms,
            "queue_depth": self.queue.qsize(),
            "coalesced_ui_updates": self.coalesced,
            "provider_error": self.provider_error,
            "requests": t.requests if t else 0,
            "api_errors": t.errors if t else 0,
            "rate_limit_events": t.rate_limits if t else 0,
            "cache_hits": t.cache_hits if t else 0,
            "p50_ms": lat[len(lat) // 2] if lat else None,
            "p95_ms": lat[min(len(lat) - 1, int(len(lat) * 0.95))] if lat else None,
            "p99_ms": lat[min(len(lat) - 1, int(len(lat) * 0.99))] if lat else None,
        }
        return state

    async def broadcast(self):
        while True:
            delay = {"ECO": 3, "BALANCED": 1, "PERFORMANCE": 0.5}[self.engine.cfg.performance]
            started = time.monotonic()
            await asyncio.sleep(delay)
            self.lag_ms = max(0, (time.monotonic() - started - delay) * 1000)
            if self.clients:
                snapshot = self.snapshot()
                for queue in tuple(self.clients):
                    if queue.full():
                        queue.get_nowait()
                        self.coalesced += 1
                    queue.put_nowait(snapshot)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = Runtime()
    app.state.runtime = runtime
    async with httpx.AsyncClient(
        timeout=10,
        limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        follow_redirects=False,
    ) as client:
        tasks = [
            asyncio.create_task(runtime.produce(client)),
            asyncio.create_task(runtime.consume()),
            asyncio.create_task(runtime.broadcast()),
        ]
        yield
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await asyncio.to_thread(runtime.engine.control, "stop")
        runtime.engine.store.engine.dispose()


app = FastAPI(title="Solana Intelligence • Paper only", lifespan=lifespan)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver", "backend"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)
requests_window: deque[float] = deque(maxlen=300)


@app.middleware("http")
async def guard(request: Request, call_next):
    from starlette.responses import JSONResponse

    ts = time.monotonic()
    while requests_window and requests_window[0] < ts - 60:
        requests_window.popleft()
    if len(requests_window) >= 240:
        return JSONResponse({"detail": "Rate limit"}, status_code=429)
    requests_window.append(ts)
    origin = request.headers.get("origin")
    if origin and origin not in ORIGINS:
        return JSONResponse({"detail": "Origin rejected"}, status_code=403)
    if request.method in {"POST", "PUT", "DELETE", "PATCH"}:
        expected = request.app.state.runtime.csrf
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), expected):
            return JSONResponse({"detail": "Session token required"}, status_code=403)
    return await call_next(request)


@app.get("/api/session")
def session(request: Request):
    return {"csrf": request.app.state.runtime.csrf}


@app.get("/api/state")
def state(request: Request):
    return request.app.state.runtime.snapshot()


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["start", "stop", "kill", "clear-halt", "reset", "close-all"]


@app.post("/api/control")
async def control(command: Command, request: Request):
    try:
        await asyncio.to_thread(request.app.state.runtime.engine.control, command.action)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return request.app.state.runtime.snapshot()


@app.put("/api/settings")
async def settings(settings: Settings, request: Request):
    try:
        await asyncio.to_thread(request.app.state.runtime.engine.control, "settings", settings)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return request.app.state.runtime.snapshot()


@app.get("/api/history/{kind}")
def history(
    kind: Literal[
        "decisions",
        "paper_orders",
        "paper_fills",
        "paper_positions",
        "portfolio_snapshots",
        "market_snapshots",
    ],
    request: Request,
):
    engine = request.app.state.runtime.engine
    return engine.store.recent(kind, engine.state["session_id"], 200)


@app.get("/api/models")
def models():
    return {
        "active": {
            "version": "baseline-v1",
            "type": "RULE_BASED",
            "validation": "ENGINEERING_TESTS_ONLY",
            "trained": False,
            "probabilities_calibrated": False,
        },
        "candidates": [],
        "training": "NOT_STARTED_NO_VERIFIED_DATASET",
        "features": FEATURE_CATALOG,
        "promotion": "MANUAL_REVIEW_REQUIRED",
        "governor": "Suspends entries after three consecutive realized losses; never raises limits",
    }


@app.get("/api/rpc-health")
async def rpc_health(request: Request):
    try:
        rpc = SolanaRPCProvider(request.app.state.runtime.transport)
        return await rpc.call("getHealth")
    except Exception as exc:
        raise HTTPException(503, type(exc).__name__) from exc


@app.websocket("/ws")
async def updates(ws: WebSocket):
    runtime = ws.app.state.runtime
    if ws.headers.get("origin") not in ORIGINS or len(runtime.clients) >= 8:
        await ws.close(code=1008)
        return
    await ws.accept()
    queue: asyncio.Queue = asyncio.Queue(maxsize=1)
    try:
        hello = await asyncio.wait_for(ws.receive_json(), timeout=5)
        if not secrets.compare_digest(str(hello.get("csrf", "")), runtime.csrf):
            await ws.close(code=1008)
            return
        runtime.clients.add(queue)
        await ws.send_json(runtime.snapshot())
        while True:
            await ws.send_json(await queue.get())
    except (WebSocketDisconnect, TimeoutError, RuntimeError):
        pass
    finally:
        runtime.clients.discard(queue)
