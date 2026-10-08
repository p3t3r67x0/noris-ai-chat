import runpy
import socket
from collections.abc import Callable
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import psycopg
import pytest


@pytest.fixture
def diagnose(monkeypatch: pytest.MonkeyPatch) -> Callable[[], int]:
    monkeypatch.setenv(
        "NORIS_DATABASE_URL",
        "postgresql+psycopg://noris_app:app-test-secret@127.0.0.1:55432/noris_dev",
    )
    monkeypatch.setenv(
        "NORIS_MIGRATION_DATABASE_URL",
        "postgresql+psycopg://noris_migrator:migration-test-secret@postgres:5432/noris_dev",
    )
    script = Path(__file__).resolve().parents[2] / "scripts" / "check_database.py"
    return cast(Callable[[], int], runpy.run_path(str(script))["main"])


@pytest.fixture
def resolver(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    resolver = MagicMock(
        return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("172.20.0.2", 5432)),
            (socket.AF_INET6, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("fd00::2", 5432, 0, 0)),
        ]
    )
    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    return resolver


@pytest.fixture
def tcp_connect(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    tcp_connect = MagicMock()
    monkeypatch.setattr(socket, "create_connection", tcp_connect)
    return tcp_connect


@pytest.fixture
def database_connect(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    database_connect = MagicMock()
    monkeypatch.setattr(psycopg, "connect", database_connect)
    return database_connect


def test_checks_migration_address_and_read_only_query(
    diagnose: Callable[[], int],
    resolver: MagicMock,
    tcp_connect: MagicMock,
    database_connect: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert diagnose() == 0
    resolver.assert_called_once_with("postgres", 5432, type=socket.SOCK_STREAM)
    tcp_connect.assert_called_once_with(("postgres", 5432), timeout=5)
    database_connect.assert_called_once_with(
        "postgresql://noris_migrator:migration-test-secret@postgres:5432/noris_dev",
        connect_timeout=5,
    )
    database_connect.return_value.__enter__.return_value.execute.assert_called_once_with("SELECT 1")
    output = capsys.readouterr().out
    assert "Ziel: postgres:5432/noris_dev" in output
    assert "DNS: 172.20.0.2, fd00::2" in output
    assert "PostgreSQL: OK" in output
    assert "test-secret" not in output


def test_dns_failure_stops_before_tcp_and_authentication(
    diagnose: Callable[[], int],
    resolver: MagicMock,
    tcp_connect: MagicMock,
    database_connect: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    resolver.side_effect = socket.gaierror("private DNS error")
    assert diagnose() == 1
    output = capsys.readouterr().out
    assert "DNS: FEHLER (gaierror)" in output
    assert "private DNS error" not in output
    tcp_connect.assert_not_called()
    database_connect.assert_not_called()


@pytest.mark.parametrize(
    "error", [TimeoutError("private timeout"), ConnectionRefusedError("private")]
)
def test_tcp_failure_stops_before_authentication(
    diagnose: Callable[[], int],
    resolver: MagicMock,
    tcp_connect: MagicMock,
    database_connect: MagicMock,
    capsys: pytest.CaptureFixture[str],
    error: OSError,
) -> None:
    tcp_connect.side_effect = error
    assert diagnose() == 1
    output = capsys.readouterr().out
    assert f"TCP: FEHLER ({type(error).__name__})" in output
    assert "private" not in output
    database_connect.assert_not_called()


@pytest.mark.parametrize(
    "error", [psycopg.OperationalError("migration-test-secret"), psycopg.errors.ConnectionTimeout()]
)
def test_postgres_failure_is_redacted(
    diagnose: Callable[[], int],
    resolver: MagicMock,
    tcp_connect: MagicMock,
    database_connect: MagicMock,
    capsys: pytest.CaptureFixture[str],
    error: psycopg.Error,
) -> None:
    database_connect.side_effect = error
    assert diagnose() == 1
    output = capsys.readouterr().out
    assert "TCP: OK" in output
    assert f"PostgreSQL: FEHLER ({type(error).__name__})" in output
    assert "test-secret" not in output


def test_invalid_configuration_is_redacted(
    diagnose: Callable[[], int],
    monkeypatch: pytest.MonkeyPatch,
    resolver: MagicMock,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("NORIS_MIGRATION_DATABASE_URL", "sqlite:///migration-test-secret")
    assert diagnose() == 1
    output = capsys.readouterr().out
    assert "Konfiguration: FEHLER" in output
    assert "test-secret" not in output
    resolver.assert_not_called()
