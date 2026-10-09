import json
from pathlib import Path

from noris_ai.main import create_app


def test_committed_openapi_matches_application() -> None:
    committed = Path(__file__).resolve().parents[3] / "docs/api/openapi.json"
    assert json.loads(committed.read_text(encoding="utf-8")) == create_app().openapi()


def test_foundation_and_llm_endpoints_are_exposed() -> None:
    schema = create_app().openapi()
    assert set(schema["paths"]) == {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/llm/models",
        "/api/v1/llm/chat",
        "/api/v1/llm/conversation-title",
    }
    assert schema["paths"]["/api/v1/health/ready"]["get"]["responses"]["503"]["content"][
        "application/json"
    ]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}


def test_llm_contract_preserves_transport_events_and_requires_authentication() -> None:
    schema = create_app().openapi()
    chat = schema["paths"]["/api/v1/llm/chat"]["post"]
    assert chat["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ChatRequest"
    }
    events = chat["responses"]["200"]["content"]["text/event-stream"]["schema"]
    assert len(events["oneOf"]) == 5
    assert chat["security"] == [{"HTTPBasic": []}]


def test_title_contract_is_bounded_and_cannot_supply_system_instructions() -> None:
    schema = create_app().openapi()
    endpoint = schema["paths"]["/api/v1/llm/conversation-title"]["post"]
    assert endpoint["operationId"] == "generateConversationTitle"
    assert endpoint["security"] == [{"HTTPBasic": []}]
    assert {"409", "429", "502", "503", "504"} <= set(endpoint["responses"])
    request = schema["components"]["schemas"]["ConversationTitleRequest"]
    assert request["additionalProperties"] is False
    assert set(request["properties"]) == {
        "conversationId",
        "inputMessageId",
        "modelId",
        "firstMessage",
    }
    assert request["properties"]["firstMessage"]["maxLength"] == 1024
    assert (
        schema["components"]["schemas"]["ConversationTitleResponse"]["properties"]["title"][
            "maxLength"
        ]
        == 40
    )
    assert "TitleInstruction" not in schema["components"]["schemas"]
    assert schema["components"]["schemas"]["LLMMessage"]["properties"]["role"]["enum"] == [
        "user",
        "assistant",
    ]
