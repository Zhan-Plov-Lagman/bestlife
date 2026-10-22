"""Owned native launcher: stop requests request Uvicorn's graceful shutdown."""
import argparse
import asyncio
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import psutil
import uvicorn

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / ".run"
sys.path.insert(0, str(ROOT / "backend"))
from app.instance import InstanceLease


def stop():
    metadata = RUN / "owner.json"
    if not metadata.exists():
        print("No managed Meridian process")
        return
    owner = json.loads(metadata.read_text())
    try:
        process = psutil.Process(owner["pid"])
        if abs(process.create_time()-owner["created"]) > .1 or str(Path(__file__).resolve()) not in process.cmdline():
            raise RuntimeError("OWNERSHIP_MISMATCH; process not stopped")
    except psutil.NoSuchProcess:
        print("Managed process is already stopped")
        return
    (RUN / "stop.request").write_text(owner["nonce"])
    try:
        process.wait(45)
    except psutil.TimeoutExpired:
        raise RuntimeError("Graceful stop timed out; no unrelated process was terminated") from None
    print("Meridian stopped gracefully")


async def serve(backend_only: bool):
    RUN.mkdir(exist_ok=True)
    launcher = InstanceLease("sqlite:///" + str(RUN / "launcher")).acquire()
    frontend = None
    log = None
    os.chdir(ROOT / "backend")
    nonce = secrets.token_hex(16)
    server = uvicorn.Server(uvicorn.Config("app.main:app", host="127.0.0.1", port=8000, workers=1, ws_max_size=4096, limit_concurrency=64, timeout_graceful_shutdown=35))
    try:
        if not backend_only:
            log = (RUN / "frontend.log").open("a", encoding="utf-8")
            frontend = subprocess.Popen(["node", str(ROOT / "frontend/node_modules/next/dist/bin/next"), "start", "--hostname", "127.0.0.1"], cwd=ROOT / "frontend", stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        (RUN / "owner.json").write_text(json.dumps({"pid": os.getpid(), "created": psutil.Process().create_time(), "nonce": nonce}))
        async def watch():
            while not server.should_exit:
                request = RUN / "stop.request"
                if request.exists() and request.read_text() == nonce:
                    server.should_exit = True
                await asyncio.sleep(.25)
        watcher = asyncio.create_task(watch())
        try:
            await server.serve()
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
    finally:
        if frontend and frontend.poll() is None:
            frontend.terminate()  # only the child created above; it has no trading ledger
            frontend.wait(timeout=10)
        if log:
            log.close()
        launcher.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--backend-only", action="store_true")
    args = parser.parse_args()
    if args.stop:
        stop()
    else:
        asyncio.run(serve(args.backend_only))
