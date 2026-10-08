"""Read-only connection diagnosis, also runnable via stdin in an existing image."""

import socket

import psycopg
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from noris_ai.core.config import Settings


def main() -> int:
    try:
        settings = Settings()
        url = make_url(
            (settings.migration_database_url or settings.database_url).get_secret_value()
        )
    except (ValueError, SQLAlchemyError, OSError) as error:
        print(f"Konfiguration: FEHLER ({type(error).__name__})", flush=True)
        return 1

    host = url.host
    port = url.port or 5432
    if not host or host.startswith("/"):
        print("Konfiguration: Diese Diagnose benötigt eine TCP-Verbindungsadresse.", flush=True)
        return 1
    print(f"Ziel: {host}:{port}/{url.database}", flush=True)

    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as error:
        print(f"DNS: FEHLER ({type(error).__name__})", flush=True)
        return 1
    print(
        "DNS: " + ", ".join(dict.fromkeys(str(address[4][0]) for address in addresses)), flush=True
    )

    try:
        with socket.create_connection((host, port), timeout=5):
            print("TCP: OK", flush=True)
    except OSError as error:
        print(f"TCP: FEHLER ({type(error).__name__})", flush=True)
        return 1

    try:
        conninfo = url.set(drivername="postgresql").render_as_string(hide_password=False)
        with psycopg.connect(conninfo, connect_timeout=5) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error as error:
        # Driver exceptions may contain credentials; report only their type.
        print(f"PostgreSQL: FEHLER ({type(error).__name__})", flush=True)
        return 1
    print("PostgreSQL: OK (Anmeldung und SELECT 1)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
