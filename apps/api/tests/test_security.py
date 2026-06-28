"""Auth seam + production-safety guard tests."""

from __future__ import annotations

from types import SimpleNamespace

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import ValidationError

from app.api.v1.deps import get_current_subject
from app.core.config import Settings, settings
from app.core.security import create_access_token, decode_access_token
from app.exceptions import UnauthorizedError


def _request() -> object:
    return SimpleNamespace(state=SimpleNamespace())


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_decode_rejects_token_without_exp() -> None:
    forever = jwt.encode({"sub": "u1"}, settings.secret_key, algorithm=settings.jwt_algorithm)
    with pytest.raises(jwt.PyJWTError):
        decode_access_token(forever)


def test_decode_accepts_valid_token() -> None:
    payload = decode_access_token(create_access_token("user-123"))
    assert payload["sub"] == "user-123"


def test_decode_accepts_aud_token_when_audience_unset() -> None:
    # Most real IdP tokens carry an `aud`; with JWT_AUDIENCE unset they must pass.
    token = create_access_token("u", extra_claims={"aud": "https://api.example.com"})
    payload = decode_access_token(token)
    assert payload["aud"] == "https://api.example.com"


async def test_blank_subject_is_rejected() -> None:
    with pytest.raises(UnauthorizedError):
        await get_current_subject(_request(), _creds(create_access_token("")))


async def test_valid_subject_is_stashed_on_request() -> None:
    request = _request()
    subject = await get_current_subject(request, _creds(create_access_token("user-9")))
    assert subject == "user-9"
    assert request.state.subject == "user-9"  # rate limiter reads this


def test_production_rejects_default_secret_key() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


def test_production_accepts_strong_config() -> None:
    cfg = Settings(
        environment="production",
        secret_key="a" * 64,
        cors_origins=["https://app.example.com"],
    )
    assert cfg.is_production
