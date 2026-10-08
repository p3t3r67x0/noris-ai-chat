#!/bin/sh
set -eu

if docker compose version >/dev/null 2>&1; then
    exec docker compose "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
    case "$(docker-compose version --short 2>/dev/null)" in
        2.*|v2.*) exec docker-compose "$@" ;;
    esac
fi

printf '%s\n' 'Docker Compose v2 fehlt. Installiere das Compose-Plugin oder docker-compose v2.' >&2
exit 1
