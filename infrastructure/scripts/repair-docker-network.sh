#!/bin/sh
set -eu

# Repair only this project's intra-bridge traffic in the host's custom chain.
# Docker's own rules and the host's forwarding policy remain authoritative.
if [ "$(id -u)" != 0 ]; then
    printf '%s\n' 'Root-Rechte benötigt: sudo make network-repair' >&2
    exit 1
fi

command -v docker >/dev/null
command -v nft >/dev/null

active_chain=$(nft list chain inet filter forward)
case "$active_chain" in
    *'hook forward'*'policy drop;'*) ;;
    *)
        printf '%s\n' 'Die erwartete forward-Chain mit policy drop ist nicht aktiv. Keine Reparatur angewendet.' >&2
        exit 1
        ;;
esac

network=noris-ai-chat_default
project=$(docker network inspect --format '{{index .Labels "com.docker.compose.project"}}' "$network")
driver=$(docker network inspect --format '{{.Driver}}' "$network")
if [ "$project" != noris-ai-chat ] || [ "$driver" != bridge ]; then
    printf '%s\n' 'Das Netzwerk gehört nicht zur erwarteten noris-ai-chat-Bridge.' >&2
    exit 1
fi

icc=$(docker network inspect --format '{{index .Options "com.docker.network.bridge.enable_icc"}}' "$network")
if [ "$icc" = false ]; then
    printf '%s\n' 'Docker verbietet Container-Kommunikation in diesem Netzwerk (enable_icc=false).' >&2
    exit 1
fi

bridge=$(docker network inspect --format '{{index .Options "com.docker.network.bridge.name"}}' "$network")
case "$bridge" in
    ''|'<no value>')
        network_id=$(docker network inspect --format '{{.Id}}' "$network")
        case "$network_id" in
            ''|*[!a-f0-9]*) exit 1 ;;
        esac
        if [ "${#network_id}" -ne 64 ]; then
            printf '%s\n' 'Ungültige Docker-Netzwerk-ID.' >&2
            exit 1
        fi
        bridge=br-$(printf '%.12s' "$network_id")
        ;;
esac
case "$bridge" in
    ''|*[!A-Za-z0-9_.:-]*) exit 1 ;;
esac
if [ "${#bridge}" -gt 15 ]; then
    printf '%s\n' 'Ungültiger Bridge-Name.' >&2
    exit 1
fi

sh infrastructure/scripts/compose.sh exec -T postgres sh -c \
    'pg_isready -h 127.0.0.1 -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'

tag=noris-ai-chat:$bridge
case "$active_chain" in
    *"comment \"$tag\""*)
        printf '%s\n' "Freigabe für $bridge ist bereits vorhanden."
        exit 0
        ;;
esac

rule="insert rule inet filter forward iifname \"$bridge\" oifname \"$bridge\" counter accept comment \"$tag\""
printf '%s\n' "$rule" | nft --check -f -
printf '%s\n' "$rule" | nft -f -
printf '%s\n' "Verkehr innerhalb der Projekt-Bridge $bridge freigegeben."
printf '%s\n' 'Nächste Prüfung: make db-diagnose'
printf '%s\n' 'Die Regel gilt bis zum Neustart oder Neuladen der Host-Firewall.'
