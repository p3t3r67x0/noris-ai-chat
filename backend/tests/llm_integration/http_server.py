import asyncio
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI


@asynccontextmanager
async def serve(
    app: FastAPI, *, key: Path | None = None, certificate: Path | None = None
) -> AsyncGenerator[str]:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    listener.setblocking(False)
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="critical",
            access_log=False,
            ws="none",
            ssl_keyfile=str(key) if key else None,
            ssl_certfile=str(certificate) if certificate else None,
        )
    )
    task = asyncio.create_task(server.serve(sockets=[listener]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        scheme = "https" if certificate else "http"
        yield f"{scheme}://127.0.0.1:{listener.getsockname()[1]}"
    finally:
        server.should_exit = True
        async with asyncio.timeout(5):
            await task
        listener.close()
