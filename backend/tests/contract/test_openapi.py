import json
from pathlib import Path

from noris_ai.main import create_app


def test_committed_openapi_matches_application() -> None:
    committed = Path(__file__).resolve().parents[3] / "docs/api/openapi.json"
    assert json.loads(committed.read_text(encoding="utf-8")) == create_app().openapi()


def test_only_foundation_endpoints_are_exposed() -> None:
    schema = create_app().openapi()
    assert set(schema["paths"]) == {"/api/v1/health/live", "/api/v1/health/ready"}
    assert schema["paths"]["/api/v1/health/ready"]["get"]["responses"]["503"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
