"""Real HTTPS/WSS through nginx -> Caddy -> Uvicorn and a disposable PostgreSQL DB.

Set NORIS_TEST_CADDY_BINARY to a Caddy 2.10.2 executable and install nginx/openssl.
These optional local tools are never used to connect to a deployed application.
"""

import json
import os
import shutil
import socket
import ssl
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from pydantic import SecretStr
from uvicorn import Config, Server
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus
from websockets.typing import Origin, Subprotocol

from noris_ai.core.config import EnvironmentSettings
from noris_ai.main import create_app

pytestmark = pytest.mark.integration
AUTH = ("fixture-user", "fixture-application-password-never-real")


@contextmanager
def proxy_process(args: list[str], directory: Path) -> Iterator[None]:
    # Executables are selected by the test operator, never by application input.
    environment = os.environ | {
        "XDG_CONFIG_HOME": str(directory / "config"),
        "XDG_DATA_HOME": str(directory / "data"),
    }
    with subprocess.Popen(  # noqa: S603
        args, cwd=directory, env=environment, stdout=subprocess.DEVNULL
    ) as process:
        try:
            yield
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def unused_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


@dataclass
class ProxyChain:
    origin: str
    tls: ssl.SSLContext
    tls_port: int
    plain_port: int

    def protocols(self) -> list[Subprotocol]:
        with httpx.Client(verify=self.tls, trust_env=False) as client:
            response = client.post(
                self.origin + "/api/v1/chat/ws-ticket",
                auth=AUTH,
                headers={"origin": self.origin},
                json={},
            )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        return [Subprotocol("noris-chat.v1"), Subprotocol("ticket." + response.json()["ticketId"])]


@pytest.fixture
def proxy_chain(tmp_path: Path, migration_config: AlembicConfig) -> Iterator[ProxyChain]:
    caddy = os.environ.get("NORIS_TEST_CADDY_BINARY") or shutil.which("caddy")
    nginx = shutil.which("nginx")
    openssl = shutil.which("openssl")
    if not caddy or not nginx or not openssl:
        pytest.skip("Real proxy tests require Caddy (NORIS_TEST_CADDY_BINARY), nginx and openssl")
    command.upgrade(migration_config, "head")
    tls_port, caddy_port, plain_port = unused_port(), unused_port(), unused_port()
    origin = f"https://127.0.0.1:{tls_port}"
    config = EnvironmentSettings(
        environment="production",
        database_url=SecretStr(os.environ["NORIS_TEST_DATABASE_URL"]),
        llm_provider="disabled",
        llm_access_username=AUTH[0],
        llm_access_password=SecretStr(AUTH[1]),
        llm_allowed_origins=(origin,),
        chat_ws_allowed_hosts=(),
        chat_ws_ticket_ttl_seconds=5,
    )
    certificate, key = tmp_path / "tls.crt", tmp_path / "tls.key"
    subprocess.run(  # noqa: S603
        [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=127.0.0.1",
            "-addext",
            "subjectAltName=IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(certificate),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    tls = ssl.create_default_context(cafile=str(certificate))
    with ExitStack() as stack:
        listener = stack.enter_context(socket.socket())
        listener.bind(("127.0.0.1", 0))
        backend_port = int(listener.getsockname()[1])
        server = Server(
            Config(
                create_app(config),
                host="127.0.0.1",
                port=backend_port,
                proxy_headers=True,
                forwarded_allow_ips="127.0.0.1",
                ws="websockets-sansio",
                log_level="warning",
            )
        )
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()

        def stop_backend() -> None:
            server.should_exit = True
            thread.join(timeout=10)
            assert not thread.is_alive()

        stack.callback(stop_backend)
        caddyfile = tmp_path / "Caddyfile"
        caddyfile.write_text(
            "{\n admin off\n auto_https off\n servers {\n"
            "  trusted_proxies static 127.0.0.1/32\n }\n}\n"
            f":{caddy_port} {{\n bind 127.0.0.1\n"
            f" reverse_proxy 127.0.0.1:{backend_port}\n}}\n"
        )
        stack.enter_context(proxy_process([caddy, "run", "--config", str(caddyfile)], tmp_path))
        nginx_conf = tmp_path / "nginx.conf"
        nginx_conf.write_text(
            f"pid {tmp_path}/nginx.pid;\nerror_log stderr warn;\nevents {{}}\n"
            "http {\n access_log off;\n"
            f" client_body_temp_path {tmp_path}/body;\n proxy_temp_path {tmp_path}/proxy;\n"
            f" server {{\n listen 127.0.0.1:{tls_port} ssl;\n"
            f" listen 127.0.0.1:{plain_port};\n"
            f" ssl_certificate {certificate};\n ssl_certificate_key {key};\n"
            f" location / {{\n proxy_pass http://127.0.0.1:{caddy_port};\n"
            " proxy_http_version 1.1;\n proxy_set_header Host $http_host;\n"
            " proxy_set_header X-Forwarded-Proto $scheme;\n"
            " proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
            " proxy_set_header Upgrade $http_upgrade;\n proxy_set_header Connection upgrade;\n"
            " }\n }\n}\n"
        )
        stack.enter_context(
            proxy_process(
                [nginx, "-p", str(tmp_path), "-c", str(nginx_conf), "-g", "daemon off;"], tmp_path
            )
        )
        with httpx.Client(verify=tls, trust_env=False, timeout=1) as client:
            for _ in range(100):
                try:
                    if client.get(origin + "/api/v1/health/ready").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("Isolated nginx/Caddy/Uvicorn chain did not become ready")
        yield ProxyChain(origin, tls, tls_port, plain_port)


async def test_https_ticket_then_wss_through_both_proxies(proxy_chain: ProxyChain) -> None:
    protocols = proxy_chain.protocols()
    url = proxy_chain.origin.replace("https:", "wss:") + "/api/v1/chat/ws"
    async with connect(
        url,
        origin=Origin(proxy_chain.origin),
        subprotocols=protocols,
        ssl=proxy_chain.tls,
        proxy=None,
    ) as websocket:
        assert websocket.response is not None and websocket.response.status_code == 101
        assert websocket.subprotocol == "noris-chat.v1"
        assert json.loads(await websocket.recv())["type"] == "chat.connected"
        await websocket.send('{"version":1,"type":"chat.ping"}')
        assert json.loads(await websocket.recv())["type"] == "chat.pong"
    with pytest.raises(InvalidStatus) as rejected:
        async with connect(
            url,
            origin=Origin(proxy_chain.origin),
            subprotocols=protocols,
            ssl=proxy_chain.tls,
            proxy=None,
        ):
            pass
    assert rejected.value.response.status_code == 403


@pytest.mark.parametrize("failure", ["expired", "origin", "host", "scheme"])
async def test_proxy_handshakes_still_reject_unsafe_connections(
    proxy_chain: ProxyChain, failure: str, caplog: pytest.LogCaptureFixture
) -> None:
    import asyncio

    protocols = proxy_chain.protocols()
    origin = "https://evil.example" if failure == "origin" else proxy_chain.origin
    if failure == "expired":
        await asyncio.sleep(5.1)
    headers = {}
    url = proxy_chain.origin.replace("https:", "wss:") + "/api/v1/chat/ws"
    tls: ssl.SSLContext | None = proxy_chain.tls
    port = proxy_chain.tls_port
    if failure == "host":
        url = url.replace("127.0.0.1", "evil.example")
    if failure == "scheme":
        url = url.replace("wss:", "ws:")
        port = proxy_chain.plain_port
        # Preserve an allowed Host so this exercises the production WSS check.
        headers = {"X-Forwarded-Proto": "https"}
        tls = None
    with pytest.raises(InvalidStatus) as rejected:
        async with connect(
            url,
            origin=Origin(origin),
            subprotocols=protocols,
            ssl=tls,
            additional_headers=headers,
            proxy=None,
            host="127.0.0.1",
            port=port,
            server_hostname="127.0.0.1" if tls else None,
        ):
            pass
    assert rejected.value.response.status_code == 403
    reasons = {
        "expired": "TICKET_INVALID_OR_EXPIRED",
        "origin": "ORIGIN_NOT_ALLOWED",
        "host": "HOST_NOT_ALLOWED",
        "scheme": "INVALID_SCHEME",
    }
    assert f"reason={reasons[failure]}" in caplog.text
    assert all(protocol not in caplog.text for protocol in protocols[1:])
