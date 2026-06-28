"""Security primitives: JWT encode/verify.

This is a *seam*, not an auth system. There is no user store and no login flow —
wire this to your identity provider (Auth0, Clerk, Cognito, or your own) when you
build authentication. The verification dependency lives in ``app/api/v1/deps.py``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings


def create_access_token(
    subject: str,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Mint a signed JWT. ``subject`` is typically the user id."""
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(UTC)}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jwt.PyJWTError`` on any failure.

    ``exp`` is required, so a token minted without an expiry is rejected rather
    than accepted forever. Audience/issuer are validated when configured.
    """
    kwargs: dict[str, Any] = {}
    if settings.jwt_audience:
        kwargs["audience"] = settings.jwt_audience
    if settings.jwt_issuer:
        kwargs["issuer"] = settings.jwt_issuer
    # verify_aud must track whether an audience is configured: otherwise PyJWT
    # rejects every token that *carries* an aud claim (i.e. most real IdP tokens)
    # when JWT_AUDIENCE is left unset.
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp"], "verify_aud": bool(settings.jwt_audience)},
        **kwargs,
    )
