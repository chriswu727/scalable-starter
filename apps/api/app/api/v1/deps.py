"""Reusable FastAPI dependencies for v1.

Dependencies are how we inject the request-scoped session, build services, do
auth, and rate-limit — all without handlers knowing how any of it is wired.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request, params
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache.redis import Cache
from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import get_session
from app.exceptions import RateLimitedError, UnauthorizedError
from app.repositories.item import ItemRepository
from app.services.item import ItemService

log = get_logger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_cache(request: Request) -> Cache:
    return cast(Cache, request.app.state.cache)


CacheDep = Annotated[Cache, Depends(get_cache)]


def get_item_service(session: SessionDep) -> ItemService:
    return ItemService(ItemRepository(session))


ItemServiceDep = Annotated[ItemService, Depends(get_item_service)]


# --- Auth seam (no user store yet — wire to your IdP) -----------------------
_bearer = HTTPBearer(auto_error=False)


async def get_current_subject(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """Verify a bearer token and return its subject. Raises 401 if invalid.

    Apply with ``Depends(get_current_subject)`` to protect a route. Returns the
    ``sub`` claim; swap in your real user lookup when you add one. The subject is
    stashed on ``request.state`` so the rate limiter can bucket per authenticated
    caller rather than per source IP.
    """
    if credentials is None:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception as exc:  # normalise all JWT errors to 401
        raise UnauthorizedError("Invalid or expired token") from exc
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        # A validly-signed token with no subject must not authenticate as "".
        raise UnauthorizedError("Token has no subject")
    request.state.subject = subject
    return subject


CurrentSubject = Annotated[str, Depends(get_current_subject)]


# --- Simple Redis-backed rate limiter --------------------------------------
def rate_limit(*, limit: int = 60, window_seconds: int = 60) -> params.Depends:
    """Dependency factory: at most ``limit`` requests per ``window`` per client.

    Usage: ``dependencies=[Depends(rate_limit(limit=10, window_seconds=60))]``.
    """

    async def _dependency(request: Request, cache: CacheDep) -> None:
        # Client identity comes from request.client.host, which reflects the real
        # caller only when uvicorn runs with --proxy-headers and a trusted
        # FORWARDED_ALLOW_IPS; otherwise every caller behind the proxy shares one
        # bucket. Prefer the authenticated subject when one is present.
        subject = getattr(request.state, "subject", None)
        client = subject or (request.client.host if request.client else "anonymous")
        key = f"ratelimit:{window_seconds}:{request.url.path}:{client}"
        try:
            count = await cache.incr(key, ttl_seconds=window_seconds)
        except Exception:
            # Fail OPEN: a cache blip must not 500 every protected route.
            log.warning("rate_limit.cache_unavailable", path=request.url.path)
            return
        if count > limit:
            raise RateLimitedError(
                f"Rate limit exceeded: {limit} requests per {window_seconds}s",
                extra={
                    "headers": {
                        "Retry-After": str(window_seconds),
                        "X-RateLimit-Limit": str(limit),
                    }
                },
            )

    return cast(params.Depends, Depends(_dependency))
