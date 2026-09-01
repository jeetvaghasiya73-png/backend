"""
API Token & JWT usage tracking middleware.

Implemented as a pure ASGI middleware instead of BaseHTTPMiddleware
to avoid blocking the event loop.
"""

import time
import hashlib
import asyncio
from starlette.types import ASGIApp, Receive, Scope, Send

from app.database.session import SessionLocal
from app.repositories.api_token import api_token_repo, api_token_usage_repo


def hash_token_signature(token: str) -> str:
    """
    Hashes the signature part of a JWT to uniquely identify it 
    without storing the actual secret credentials.
    """
    parts = token.split(".")
    if len(parts) == 3:
        signature = parts[2]
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenUsageMiddleware:
    """
    Pure ASGI middleware that logs API key and JWT token usages after each HTTP response.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    def _log_api_key_usage(self, api_key: str, method: str, path: str, ip_address: str, duration_ms: float):
        try:
            db = SessionLocal()
            try:
                api_token = api_token_repo.get_by_token(db, token=api_key)
                if api_token:
                    usage_data = {
                        "token_id": api_token.id,
                        "endpoint": f"{method} {path}",
                        "ip_address": ip_address,
                        "duration_ms": duration_ms,
                    }
                    api_token_usage_repo.create(db, obj_in=usage_data)
            except Exception as e:
                print(f"Failed to log API token usage: {e}")
            finally:
                db.close()
        except Exception:
            pass

    def _log_jwt_usage(self, token: str, method: str, path: str, ip_address: str, user_agent: str, status_code: int, duration_ms: float):
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            if not payload or payload.get("type") != "access":
                return

            user_id_str = payload.get("sub")
            if not user_id_str:
                return

            try:
                user_id = int(user_id_str)
            except ValueError:
                return

            db = SessionLocal()
            try:
                from app.models.user import User
                from app.models.jwt_usage import JwtTokenUsage

                user = db.query(User).filter(User.id == user_id).first()
                username = user.username if user else "Unknown"

                token_hash = hash_token_signature(token)

                usage_entry = JwtTokenUsage(
                    user_id=user_id,
                    username=username,
                    token_hash=token_hash,
                    endpoint=f"{method} {path}",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    status_code=status_code,
                    duration_ms=duration_ms
                )
                db.add(usage_entry)
                db.commit()
            except Exception as e:
                print(f"Failed to log JWT token usage: {e}")
            finally:
                db.close()
        except Exception:
            pass

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        api_key = None
        auth_token = None
        user_agent = None

        # Extract headers from raw ASGI scope
        for header_name, header_value in scope.get("headers", []):
            if header_name == b"x-api-key":
                api_key = header_value.decode("utf-8", errors="ignore")
            elif header_name == b"authorization":
                auth_val = header_value.decode("utf-8", errors="ignore")
                if auth_val.lower().startswith("bearer "):
                    auth_token = auth_val[7:].strip()
            elif header_name == b"user-agent":
                user_agent = header_value.decode("utf-8", errors="ignore")

        if not api_key and not auth_token:
            # Neither key is present — skip logging, zero overhead
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        response_started = False
        status_code = None

        async def send_wrapper(message):
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message.get("status")
            await send(message)

        await self.app(scope, receive, send_wrapper)

        duration_ms = (time.time() - start_time) * 1000

        if response_started:
            method = scope.get("method", "UNKNOWN")
            path = scope.get("path", "")
            client = scope.get("client")
            ip_address = client[0] if client else None

            # Route logging tasks in background thread pools
            if api_key:
                asyncio.create_task(
                    asyncio.to_thread(
                        self._log_api_key_usage,
                        api_key,
                        method,
                        path,
                        ip_address,
                        duration_ms
                    )
                )
            elif auth_token:
                asyncio.create_task(
                    asyncio.to_thread(
                        self._log_jwt_usage,
                        auth_token,
                        method,
                        path,
                        ip_address,
                        user_agent,
                        status_code,
                        duration_ms
                    )
                )
