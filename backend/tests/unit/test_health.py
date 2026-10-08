from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app


class FixedProbe:
    def __init__(self, ready: bool) -> None:
        self.ready = ready

    async def is_ready(self) -> bool:
        return self.ready


@asynccontextmanager
async def app_client(
    application: FastAPI, *, raise_app_exceptions: bool = True
) -> AsyncGenerator[AsyncClient]:
    async with (
        application.router.lifespan_context(application),
        AsyncClient(
            transport=ASGITransport(app=application, raise_app_exceptions=raise_app_exceptions),
            base_url="http://test",
        ) as client,
    ):
        yield client


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with app_client(
        create_app(EnvironmentSettings(environment="test"), FixedProbe(True))
    ) as c:
        yield c


async def test_liveness_is_independent_of_database_availability() -> None:
    async with app_client(create_app(probe=FixedProbe(False))) as client:
        response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_readiness_success(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    assert response.headers["cache-control"] == "no-store"
    UUID(response.headers["x-request-id"])


async def test_readiness_failure_is_sanitized_and_correlated() -> None:
    async with app_client(create_app(probe=FixedProbe(False))) as client:
        response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "NOT_READY"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]
    assert "postgresql" not in response.text


async def test_not_found_uses_standard_error_contract(client: AsyncClient) -> None:
    response = await client.get("/api/v1/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "HTTP_ERROR"
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


async def test_internal_failure_does_not_expose_exception_details() -> None:
    application = create_app(probe=FixedProbe(True))

    async def fail() -> None:
        raise RuntimeError("sensitive provider credential")

    application.add_api_route("/test-error", fail, methods=["GET"])
    async with app_client(application, raise_app_exceptions=False) as client:
        response = await client.get("/test-error")
    assert response.status_code == 500
    assert "sensitive" not in response.text
    assert response.json()["error"]["request_id"] == response.headers["x-request-id"]


async def test_validation_failure_does_not_echo_input() -> None:
    application = create_app(probe=FixedProbe(True))

    async def validate(request: Request, count: int) -> dict[str, int]:
        return {"count": count}

    application.add_api_route("/test-validation", validate, methods=["GET"])
    async with app_client(application) as client:
        response = await client.get("/test-validation?count=sensitive-user-input")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "sensitive-user-input" not in response.text


async def test_production_disables_interactive_docs() -> None:
    async with app_client(
        create_app(EnvironmentSettings(environment="production"), FixedProbe(True))
    ) as client:
        assert (await client.get("/api/v1/docs")).status_code == 404


async def test_request_ids_are_generated_per_request(client: AsyncClient) -> None:
    first = await client.get("/api/v1/health/live", headers={"X-Request-ID": "untrusted-value"})
    second = await client.get("/api/v1/health/live")
    assert first.headers["x-request-id"] != "untrusted-value"
    assert first.headers["x-request-id"] != second.headers["x-request-id"]
