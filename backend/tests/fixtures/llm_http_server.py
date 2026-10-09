"""Loopback-only HTTP fixture for browser tests. Never deployed in Compose."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

app = FastAPI()
calls: list[dict[str, object]] = []
title_calls: list[dict[str, object]] = []
cancelled = 0
title_cancelled = 0
attempts: dict[str, int] = {}


@app.get("/fixture/state")
async def state() -> dict[str, object]:
    return {
        "calls": calls,
        "cancelled": cancelled,
        "title_calls": title_calls,
        "title_cancelled": title_cancelled,
    }


@app.post("/v1/chat/completions", response_model=None)
async def completion(request: Request) -> StreamingResponse | JSONResponse:
    if request.headers.get("authorization") != "Bearer fixture-provider-key-never-real":
        return JSONResponse(
            {"error": {"message": "fixture authentication failed"}}, status_code=401
        )
    body = await request.json()
    is_title = body["messages"][0]["role"] == "system"
    (title_calls if is_title else calls).append(body)
    prompt = str(body["messages"][-1]["content"])
    if not is_title:
        attempts[prompt] = attempts.get(prompt, 0) + 1
    if (not is_title and prompt.startswith("/retry") and attempts[prompt] == 1) or (
        is_title and prompt.startswith("/title-error")
    ):
        return JSONResponse({"error": {"message": "fixture rate limit"}}, status_code=429)

    async def stream() -> AsyncIterator[bytes]:
        global cancelled, title_cancelled
        completed = False
        try:
            if (not is_title and prompt.startswith("/quiet")) or (
                is_title and prompt.startswith("/title-timeout")
            ):
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
            if is_title:
                await asyncio.sleep(0.4)
                title = "Docker DNS-Probleme"
                if "Rust" in prompt:
                    title = "Rust vs. C++"
                if "Chat-Titelgenerierung" in prompt:
                    title = "Automatisierte Chat-Titel Implementierung"
                if prompt.startswith("/title-wide"):
                    title = "Docker DNS Troubleshooting Guide"
                if prompt.startswith("/title-invalid"):
                    title = "x" * 51
                chunks = [title]
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
                if is_title:
                    title_cancelled += 1
                else:
                    cancelled += 1

    return StreamingResponse(stream(), media_type="text/event-stream")
