"""Export the WebSocket contract separately from OpenAPI."""

import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from noris_ai.chat.ws_protocol import ClientMessage, ServerEvent

client: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
server: TypeAdapter[ServerEvent] = TypeAdapter(ServerEvent)
schema = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "NorisChatWebSocketV1",
    "type": "object",
    "properties": {
        "client": client.json_schema(),
        "server": server.json_schema(mode="serialization"),
    },
    "required": ["client", "server"],
    "additionalProperties": False,
}
Path(sys.argv[1]).write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
