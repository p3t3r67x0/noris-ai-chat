#!/bin/sh
set -eu

# Allow DNS/HTTPS from the opt-in search bridge in this host's custom chain.
# Docker's own rules and all other host firewall chains remain authoritative.
if [ "$(id -u)" != 0 ]; then
    printf '%s\n' 'Root-Rechte benötigt: sudo make searxng-network-repair' >&2
    exit 1
fi

command -v docker >/dev/null
command -v nft >/dev/null
command -v ip >/dev/null

active_chain=$(nft list chain inet filter forward)
case "$active_chain" in
    *'hook forward'*'policy drop;'*) ;;
    *)
        printf '%s\n' 'Die erwartete forward-Chain mit policy drop ist nicht aktiv. Keine Reparatur angewendet.' >&2
        exit 1
        ;;
esac

network=${NORIS_SEARXNG_NETWORK:-noris-searxng}
project=$(docker network inspect --format '{{index .Labels "com.docker.compose.project"}}' "$network")
role=$(docker network inspect --format '{{index .Labels "com.docker.compose.network"}}' "$network")
driver=$(docker network inspect --format '{{.Driver}}' "$network")
internal=$(docker network inspect --format '{{.Internal}}' "$network")
if [ "$project" != noris-searxng ] || [ "$role" != search ] || [ "$driver" != bridge ] || [ "$internal" != false ]; then
    printf '%s\n' 'Das Netzwerk ist nicht die erwartete ausgehende noris-searxng-Suchbridge.' >&2
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

# Use the IPv4 route to an external DNS resolver; an explicit override supports
# hosts where search egress is deliberately routed through another interface.
uplink=${NORIS_SEARXNG_UPLINK:-}
if [ -z "$uplink" ]; then
    route=$(ip -4 route get 1.1.1.1)
    uplink=$(printf '%s\n' "$route" | awk '{for (i=1; i<NF; i++) if ($i == "dev") {print $(i+1); exit}}')
fi
for interface in "$bridge" "$uplink"; do
    case "$interface" in
        ''|lo|*[!A-Za-z0-9_.:-]*)
            printf '%s\n' 'Ungültiger Bridge- oder Uplink-Name.' >&2
            exit 1
            ;;
    esac
    if [ "${#interface}" -gt 15 ]; then
        printf '%s\n' 'Ungültiger Bridge- oder Uplink-Name.' >&2
        exit 1
    fi
    ip link show dev "$interface" >/dev/null
done
if [ "$bridge" = "$uplink" ]; then
    printf '%s\n' 'Suchbridge und Uplink müssen unterschiedliche Interfaces sein.' >&2
    exit 1
fi

tag=noris-searxng:$bridge:$uplink
rules=
add_rule() {
    suffix=$1
    expression=$2
    case "$active_chain" in
        *"comment \"$tag:$suffix\""*) return ;;
    esac
    rules="${rules}insert rule inet filter forward $expression counter accept comment \"$tag:$suffix\"
"
}

add_rule dns "meta nfproto ipv4 iifname \"$bridge\" oifname \"$uplink\" udp dport 53 ct state { new, established }"
add_rule https "meta nfproto ipv4 iifname \"$bridge\" oifname \"$uplink\" tcp dport { 53, 443 } ct state { new, established }"
add_rule replies "meta nfproto ipv4 iifname \"$uplink\" oifname \"$bridge\" ct state { established, related }"

if [ -z "$rules" ]; then
    printf '%s\n' "DNS-/HTTPS-Freigaben für $bridge über $uplink sind bereits vorhanden."
    exit 0
fi

# Check and apply all missing rules as a single nftables transaction.
printf '%s' "$rules" | nft --check -f -
printf '%s' "$rules" | nft -f -
printf '%s\n' "DNS und HTTPS von $bridge über $uplink mit Antwortverkehr freigegeben."
printf '%s\n' 'Die Regeln gelten bis zum Neustart, Firewall-Reload oder Wechsel der Netzwerkinterfaces.'
printf '%s\n' 'Jetzt SearXNG neu starten und DNS/HTTPS im Container erneut prüfen; siehe docs/SEARXNG-PROVIDER.md.'
