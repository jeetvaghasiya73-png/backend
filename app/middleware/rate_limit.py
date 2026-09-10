"""
In-memory sliding-window rate limiter for login endpoints.

Tracks failed login attempts per IP. After LOGIN_MAX_ATTEMPTS failures
within LOGIN_LOCKOUT_SECONDS, the IP is blocked for LOGIN_LOCKOUT_SECONDS.

This is intentionally kept simple (dict-based) for single-process deployments.
Swap for Redis if you need multi-process / production resilience.

NOTE: Implemented as a pure ASGI middleware instead of BaseHTTPMiddleware
to avoid blocking the event loop (a known FastAPI/Starlette issue).
"""

import time
import threading
from collections import defaultdict, deque
from typing import Deque

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

# Thread-safe locks per IP
_lock = threading.Lock()

# { ip: deque([timestamp, ...]) } — sliding window of FAILED attempt timestamps
_failed_attempts: dict[str, Deque[float]] = defaultdict(deque)

# { ip: lockout_until_timestamp }
_lockouts: dict[str, float] = {}

# The exact path prefixes to rate-limit
_RATE_LIMITED_PATHS = (
    "/api/v1/auth/login",
)


def _is_login_path(path: str) -> bool:
    return any(path.startswith(p) for p in _RATE_LIMITED_PATHS)


def record_failed_attempt(ip: str) -> None:
    """Call this from the auth endpoint on a failed login."""
    now = time.time()
    window = settings.LOGIN_LOCKOUT_SECONDS

    with _lock:
        dq = _failed_attempts[ip]
        # Prune old entries outside the window
        while dq and now - dq[0] > window:
            dq.popleft()
        dq.append(now)

        if len(dq) >= settings.LOGIN_MAX_ATTEMPTS:
            _lockouts[ip] = now + window
            dq.clear()  # reset so the window restarts after lockout expires


def clear_failed_attempts(ip: str) -> None:
    """Call this from the auth endpoint on a successful login."""
    with _lock:
        _failed_attempts[ip].clear()
        _lockouts.pop(ip, None)


def get_ip(request: Request) -> str:
    # Respect X-Forwarded-For for reverse-proxy setups
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class LoginRateLimitMiddleware:
    """
    Pure ASGI middleware that rejects login requests from locked-out IPs
    before they reach the endpoint. This prevents any database hit during a
    brute-force attack.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if not _is_login_path(path) or method != "POST":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        ip = get_ip(request)
        now = time.time()

        with _lock:
            lockout_until = _lockouts.get(ip, 0)

        if now < lockout_until:
            retry_after = int(lockout_until - now) + 1
            response = JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Too many failed login attempts. "
                        f"Try again in {retry_after} seconds."
                    )
                },
                headers={"Retry-After": str(retry_after)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
