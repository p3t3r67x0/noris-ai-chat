"""Shared application access checks (HTTP Basic and browser origin)."""

from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from noris_ai.chat.errors import ChatError
from noris_ai.core.config import Settings

security = HTTPBasic(auto_error=False, realm="noris-ai-chat")


def verify_basic(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)], config: Settings
) -> None:
    password = config.llm_access_password
    if not config.llm_access_username or password is None:
        # Unconfigured credentials must never grant access.
        raise ChatError("ACCESS_DENIED", 401)
    username_ok = compare_digest(
        (credentials.username if credentials else "").encode(), config.llm_access_username.encode()
    )
    password_ok = compare_digest(
        (credentials.password if credentials else "").encode(),
        (password.get_secret_value() if password else "").encode(),
    )
    if not (credentials and username_ok and password_ok):
        raise ChatError("ACCESS_DENIED", 401)


def verify_write_origin(request: Request, config: Settings) -> None:
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin is not None and origin not in config.llm_allowed_origins:
            raise ChatError("ORIGIN_DENIED", 403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise ChatError("ORIGIN_DENIED", 403)


def verify_origin_header(request: Request, config: Settings, *, required: bool) -> None:
    """WebSocket variant: browsers always send Origin; other clients may not."""
    origin = request.headers.get("origin")
    if origin is None:
        if required:
            raise ChatError("ORIGIN_DENIED", 403)
        return
    if origin not in config.llm_allowed_origins:
        raise ChatError("ORIGIN_DENIED", 403)
