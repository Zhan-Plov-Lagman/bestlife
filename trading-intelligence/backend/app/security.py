"""Local session protection and explicit, independent remote access scopes."""

import os
import secrets
import time
from collections import OrderedDict
from ipaddress import ip_address

from starlette.responses import JSONResponse


def is_local(host: str) -> bool:
    if host == "testclient":  # Starlette's in-process transport, not a network address
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


class AccessPolicy:
    ttl = 900

    def __init__(self):
        self.remote = os.environ.get("MERIDIAN_REMOTE_MODE", "false").lower() == "true"
        self.read_token = os.environ.get("MERIDIAN_READ_TOKEN", "")
        self.control_token = os.environ.get("MERIDIAN_CONTROL_TOKEN", "")
        if self.remote and (
            min(len(self.read_token), len(self.control_token)) < 32
            or self.read_token == self.control_token
        ):
            raise ValueError(
                "Remote mode requires separate read/control credentials (32+ characters)"
            )
        self.sessions: OrderedDict[str, float] = OrderedDict()

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = time.monotonic() + self.ttl
        while len(self.sessions) > 64:
            self.sessions.popitem(last=False)
        return token

    def valid_session(self, token: str) -> bool:
        return self.sessions.get(token, 0) > time.monotonic()

    def authorize(self, host: str, authorization: str, mutate: bool) -> bool:
        if not self.remote:
            return is_local(host)
        token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
        return secrets.compare_digest(token, self.control_token) or (
            not mutate and secrets.compare_digest(token, self.read_token)
        )


class BodyLimitMiddleware:
    """Limits actual ASGI bytes, including chunked bodies, before JSON parsing."""

    def __init__(self, app, max_bytes: int = 65536):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                return await JSONResponse({"detail": "REQUEST_TOO_LARGE"}, status_code=413)(
                    scope, receive, send
                )
            chunks.append(message)
            if not message.get("more_body", False):
                break

        async def replay():
            if chunks:
                return chunks.pop(0)
            return await receive()

        await self.app(scope, replay, send)
