"""Loopback-only HTTP fixture for browser tests. Never deployed in Compose."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
calls: list[dict[str, object]] = []
cancelled = 0
attempts: dict[str, int] = {}


@app.get("/fixture/state")
async def state() -> dict[str, object]:
    return {"calls": calls, "cancelled": cancelled}


@app.post("/v1/chat/completions", response_model=None)
async def completion(request: Request) -> StreamingResponse | JSONResponse:
    if request.headers.get("authorization") != "Bearer fixture-provider-key-never-real":
        return JSONResponse(
            {"error": {"message": "fixture authentication failed"}}, status_code=401
        )
    body = await request.json()
    calls.append(body)
    prompt = str(body["messages"][-1]["content"])
    attempts[prompt] = attempts.get(prompt, 0) + 1
    if prompt.startswith("/retry") and attempts[prompt] == 1:
        return JSONResponse({"error": {"message": "fixture rate limit"}}, status_code=429)

    async def stream() -> AsyncIterator[bytes]:
        global cancelled
        completed = False
        try:
            if prompt.startswith("/quiet"):
                yield b": waiting\n\n"
                await asyncio.Event().wait()
            chunks = ["Echte ", "HTTP-Antwort ", "mit Grüße 🌍."]
            if prompt == "Erkläre in zwei Sätzen, was ein MCP-Server ist.":
                chunks = [
                    "Ein MCP-Server stellt ",
                    "Werkzeuge und Daten bereit. ",
                    "Er nutzt dafür das Model Context Protocol.",
                ]
            if prompt == "Zähle die Zahlen von 1 bis 100, jede Zahl in einer eigenen Zeile.":
                chunks = [f"{number}\n" for number in range(1, 101)]
            if prompt.startswith("/slow"):
                chunks += [" weiterer Text"] * 100
            for text in chunks:
                data = (
                    "data: "
                    + json.dumps(
                        {
                            "choices": [
                                {"index": 0, "delta": {"content": text}, "finish_reason": None}
                            ]
                        },
                        ensure_ascii=False,
                    )
                    + "\r\n\r\n"
                ).encode()
                for index in range(0, len(data), 7):
                    yield data[index : index + 7]
                await asyncio.sleep(0.08)
            yield b'data: {"choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
            yield b"data: [DONE]\n\n"
            completed = True
        finally:
            if not completed:
                cancelled += 1

    return StreamingResponse(stream(), media_type="text/event-stream")
