# SearXNG-Provider: Vorbereitung parallel zu P1b

Stand: 2026-10-13. Der Adapter ist unabhängig testbar; die Chat-Websuche bleibt
deaktiviert. Grundlage ist `main` bei `02aff47` mit der gemergten
[P1a-Grundlage](TOOL-FOUNDATION.md). Die [Registry](../backend/src/noris_ai/tools/registry.py)
enthält weiterhin ausschließlich nicht ausführbare `web.search.v1`/`web.fetch.v1`.
Runtime, Policy, Budgets, Quellenpersistenz, WebSocket-Integration und Frontend
folgen der [Roadmap](FEATURE-ROADMAP.md) und dem [Websuche-Design](WEB-SEARCH-DESIGN.md).

## Adaptervertrag

`tools/providers/searxng.py` verwendet vorhandenes `httpx` und die bestehenden
`SearchInput`, `SearchSource`, `SearchResult` sowie die Registry-Größenlimits.
Es gibt keine neue Laufzeitabhängigkeit, Migration, HTTProute oder Promptintegration.

Ein Aufruf sendet ausschließlich die validierte Suchfrage per POST an
`<konfigurierte Basisadresse>/search`. Fest gesetzt sind `format=json`,
`categories=general`, `pageno=1`, `safesearch=1`; Sprache ist `de`/`en`, Zeitfilter
optional `day`/`month`/`year`. SearXNG unterstützt Zeit-/Safe-Search-Filter abhängig
von den gewählten Engines. JSON muss in `search.formats` freigegeben sein;
andernfalls kann die API 403 liefern. [Offizielle Such-API](https://docs.searxng.org/dev/search_api.html).

Die Frage darf höchstens 1000 Zeichen haben. Leere Fragen, Steuerzeichen,
ungültiges Unicode, überschrittene Registry-Bytes und SearXNG-Operatoren am
Tokenanfang (`!`, `?`, `:`, numerische `<...`-Timeouts) werden vor HTTP abgewiesen.
Normale Satzzeichen am Wortende und beispielsweise `site:example.org` bleiben
möglich. Es gibt keinen frei übergebenen Provider-/Engine-/Endpointparameter.

Der Adapter erhält Reihenfolge und liefert höchstens `limit` (1–8) Quellen:

- HTTP(S)-URLs ohne Credentials, mit Standardports; erkennbare private,
  Loopback-, Link-local-, Multicast- und Metadaten-IP-Ziele werden entfernt.
  Single-label-Hosts und `.local`, `.internal`, `.localhost` sind gesperrt.
- Fragmente und bekannte Trackingparameter entfallen; andere Queryparameter
  bleiben erhalten. Kanonisch gleiche URLs werden innerhalb der Antwort dedupliziert.
- Titel und Snippets werden zu begrenztem Text normalisiert. Jede Quelle bekommt
  eine UUID; das JSONresultat passt auch mit UTF-8 in das vorhandene 64-KiB-Limit.
- Publikationsdaten werden nur aus parsebarem `publishedDate` mit expliziter
  Zeitzone übernommen. `fetched_at` bezeichnet ausschließlich den Abrufzeitpunkt.
- Ungültige Treffer oder ausgefallene Engines erzeugen feste Warnungen und
  `partial=true`. Reine Textkürzung/Datumswarnung wird ebenfalls ausgewiesen;
  Nulltreffer ohne Providerfehler sind ein erfolgreiches leeres Resultat.

Quellen bleiben **nicht vertrauenswürdige Daten**. HTMLentfernung ist keine
Freigabe für HTMLrendering oder Systemanweisungen. Der spätere Kontextbuilder
muss Quellen als Daten behandeln und die Anzeige escapen. Antworten, Infoboxen,
Enginefehlermeldungen und andere Rohproviderfelder werden nicht übernommen.

## Fehler, Limits und Lebenszyklus

| Situation | Bestehender Toolcode | Fester `SearXNGError.reason` |
| --- | --- | --- |
| 403 | `PROVIDER_ERROR` | `forbidden` |
| 429 | `PROVIDER_RATE_LIMIT` | `rate_limit` |
| 5xx | `PROVIDER_ERROR` | `server_error` |
| sonstiger HTTPfehler | `PROVIDER_ERROR` | `http_error` |
| 3xx | `PROVIDER_ERROR` | `redirect` |
| Verbindungs-/Transportfehler | `PROVIDER_ERROR` | `connection_error` |
| Verbindungs-, Idle- oder Gesamtdeadline | `TOOL_TIMEOUT` | `timeout` |
| JSON-/Schema-/MIME-/Kompressionsfehler | `PROVIDER_ERROR` | `invalid_response` |
| Antwort zu groß | `PROVIDER_ERROR` | `response_too_large` |

Es gibt keine automatische Wiederholung oder Redirectverfolgung. `Retry-After`
führt zu keinem Sleep. Providerkörper und Transportdetails erscheinen nicht in
der sicheren Fehlernachricht. Task-Cancellation wird als `CancelledError`
weitergereicht; der HTTPstream wird geschlossen. P1b muss den Runzustand danach
konsistent persistieren und darf akzeptierte Abbrüche nicht als Erfolg committen.

Der Adapter besitzt einen separaten Client mit `trust_env=False`, überprüftem TLS,
maximal vier Verbindungen und standardmäßig 3 s Connect-/Pool-, 10 s Idle-/Write-
und 15 s Gesamtlimit. Dekodierte Kompression wird vermieden: `Accept-Encoding:
identity`, andere Content-Encodings werden verworfen. Unkomprimierte Antwortbytes
werden beim Streamen auf standardmäßig 1 MiB begrenzt (maximal konfigurierbar 2 MiB),
das JSONschema erlaubt höchstens 1000 Rohresultate.

Die Konfiguration kommt nur aus Betreiberumgebung oder expliziten Serverwerten:

| Umgebungsvariable | Vorgabe |
| --- | --- |
| `NORIS_SEARXNG_BASE_URL` | erforderlich, exakte HTTP(S)-Basisadresse |
| `NORIS_SEARXNG_ALLOWED_HOSTS` | erforderlich, JSONliste exakter Hosts |
| `NORIS_SEARXNG_CONFIG_VERSION` | erforderlich, nicht geheime Reviewversion |
| `NORIS_SEARXNG_CONNECT_TIMEOUT_SECONDS` | 3, positiv und höchstens Gesamtlimit |
| `NORIS_SEARXNG_READ_TIMEOUT_SECONDS` | 10, positiv und höchstens Gesamtlimit |
| `NORIS_SEARXNG_TOTAL_TIMEOUT_SECONDS` | 15, positiv und höchstens 15 |
| `NORIS_SEARXNG_MAX_RESPONSE_BYTES` | 1048576, zwischen 1024 und 2097152 |

`SearXNGSettings.from_environment()` liest diese Variablen ohne implizite
`.env`-Datei. Es gibt keine Defaultadresse und keinen automatischen Start/Dispatch.
Die Settings sind eingefroren und validiert; URLcredentials, Query/Fragment,
Whitespace und nicht allowlistete Hosts werden verworfen. Native SearXNG benötigt
hier keinen API-Schlüssel. Der Instanzschlüssel `SEARXNG_SECRET` wird ausschließlich
dem Suchcontainer gegeben, niemals dem Frontend.

Die interne Provideradresse darf gezielt im privaten Netz liegen. Diese Ausnahme
gilt **nicht** für Ergebnisfetches. Ergebnis-DNS wird noch nicht aufgelöst und
Seiten werden nicht abgerufen; DNS-Rebinding und Redirect-/IP-Bindung sind Gates
des späteren `web.fetch`-PRs. Ein syntaktisch gültiger Domainname beweist weder
eine öffentliche DNSauflösung noch fachliche Richtigkeit.

## Eigenständiger optionaler Docker-Stack

`compose.searxng.yaml` ist ein separater Stack mit Profil `search`. Es werden keine
Hostports veröffentlicht und keine vorhandenen Chatservices geändert. Das eigene
Bridge-Netz erlaubt ausgehende Enginezugriffe; `internal: true` würde diese
blockieren. Das Netz ist nur für SearXNG und später den Backendservice vorgesehen.
Keine Anbindung an einen öffentlichen Proxy.
Bei eigener Forward-/Egress-Firewall müssen DNS und die freigegebenen Engineziele
für dieses zusätzliche Netz geprüft werden; die vorhandene Regel für `noris-chat0`
gilt nicht automatisch dafür. Dieser PR ändert keine Firewallregeln.

Das Image muss ausdrücklich gewählt werden. Vor Produktivfreigabe einen geprüften
Digest pinnen und beim Upgrade UID/Paths/Healthcheck erneut prüfen. Das Profil
folgt dem aktuellen offiziellen Image mit UID/GID 977 und
`/usr/local/searxng/.venv/bin/python`. [Offizieller Imagebau](https://github.com/searxng/searxng/blob/master/container/dist.dockerfile),
[Containerinstallation](https://docs.searxng.org/admin/installation-docker.html).

Nur die Vorlage `infrastructure/searxng/settings.yml.example` liegt im Repository;
der Container mountet ein **externes**, bereits vorhandenes Konfigurationsverzeichnis
read-only. Der Secretwert liegt in einer externen, nur für den Betreiber lesbaren
Env-Datei. Folgende Befehle beschreiben eine spätere lokale/Betriebsinstallation;
dieser PR verändert keinen Produktivserver:

```sh
sudo install -d -m 0755 /opt/noris-searxng/config
sudo install -m 0644 infrastructure/searxng/settings.yml.example \
  /opt/noris-searxng/config/settings.yml
sudo install -m 0600 /dev/null /opt/noris-searxng/searxng.env
# Mit einem Editor außerhalb des Repositorys eintragen:
# NORIS_SEARXNG_IMAGE=docker.io/searxng/searxng@sha256:<geprüfter Digest>
# NORIS_SEARXNG_CONFIG_DIR=/opt/noris-searxng/config
# NORIS_SEARXNG_CONFIG_VERSION=<Reviewversion>
# SEARXNG_SECRET=<mit openssl rand -hex 32 erzeugter Wert>
sudo docker compose --env-file /opt/noris-searxng/searxng.env \
  -f compose.searxng.yaml --profile search config --quiet
sudo docker compose --env-file /opt/noris-searxng/searxng.env \
  -f compose.searxng.yaml --profile search up -d --wait
```

Initiale Limits: eine CPU, 512 MiB RAM, 128 Prozesse, ein Granianworker;
`cap_drop=ALL`, Non-root, `no-new-privileges`. Der Cache verwendet ein separates
Named Volume. Bei abweichendem Image dessen Eigentümerrechte prüfen; keine
automatische Änderung fremder Hostverzeichnisrechte. Logs sind auf zweimal
5 MiB begrenzt. Bei realer Last Speicher, PIDs, Enginezeiten und OOMs beobachten;
die Limits sind Startwerte, keine nachgewiesene Kapazitätsgarantie.

Healthcheck: `/healthz` im Suchcontainer alle 15 s, Timeout 5 s, Startfrist 30 s.
Er prüft die Anwendungserreichbarkeit, **nicht** JSONfreigabe oder Suchqualität.
`limiter=false` ist für dieses private Backendnetz vorgesehen. Öffentliche
Bereitstellung braucht ein eigenes Zugriffsschutz-/Limiter-/Egresskonzept.

## Späterer Anschluss und Qualitätsprobe

Nach P1b kann `compose.searxng-backend.yaml` bewusst zusätzlich zu `compose.yaml`
geladen werden. Es verbindet ausschließlich das Backend mit dem externen Suchnetz
`noris-searxng` und setzt die drei Providerkonfigurationsvariablen. Basis-Compose
und Frontend erhalten keine Änderung. Derselbe Netzname muss in beiden Stacks
über `NORIS_SEARXNG_NETWORK` gesetzt sein, wenn der Default geändert wird.

Die spätere Composition-Root erstellt/lifecycle-managed den Provider; ein Handler
ruft erst **nach** Runtime-Policy, Budget und Deadlineprüfung Folgendes auf:

```python
from noris_ai.tools.providers.searxng import SearXNGProvider, SearXNGSettings
from noris_ai.tools.schemas import SearchInput

async with SearXNGProvider(SearXNGSettings.from_environment()) as provider:
    result = await provider.search(SearchInput(query="Open Data Flensburg", language="de"))
```

Vor Featurefreigabe explizit an der eigenen Instanz prüfen:
„OpenStreetMap Schleswig-Holstein“, „Open-Source-WebGIS Deutschland“ und
„Open Data Flensburg“. Je Thema Rang 1–8, relevante Domains, veraltete Treffer,
Engineausfälle und Antwortzeiten dokumentieren. Die gleiche Probe mit `en` und
Zeitfilter wiederholen. Suchfragen verlassen die Instanz zu den gewählten Engines;
keine Chatgeschichte oder Anhänge als Testpayload senden.

Beispiel innerhalb des Suchcontainers ohne Hostport:

```sh
sudo docker compose --env-file /opt/noris-searxng/searxng.env \
  -f compose.searxng.yaml --profile search exec -T searxng \
  /usr/local/searxng/.venv/bin/python - <<'PY'
import http.client
import json
import urllib.parse
form = urllib.parse.urlencode({
    'q': 'Open Data Flensburg', 'format': 'json', 'language': 'de',
    'categories': 'general', 'pageno': 1, 'safesearch': 1,
}).encode()
connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=15)
try:
    connection.request('POST', '/search', form, {
        'Content-Type': 'application/x-www-form-urlencoded', 'Accept': 'application/json',
    })
    response = connection.getresponse()  # follows no redirects
    assert response.status == 200, response.status
    body = response.read(1048577)
    assert len(body) <= 1048576
    data = json.loads(body)
finally:
    connection.close()
print(json.dumps([
    {key: row.get(key) for key in ('title', 'url', 'engine')}
    for row in data['results'][:8]
], ensure_ascii=False, indent=2))
PY
```

## Reproduzierbare Validierung

Unitfälle stehen in `tests/unit/test_searxng_provider.py`, echte lokale
HTTPsimulation in `tests/llm_integration/test_http_search.py`. Letztere läuft mit
den bisherigen Provider-Integrationstests auch in `make test-unit`/CI. Keine
Live-Suchmaschine, SearXNGinstallation, Betreibercredentials oder DB erforderlich.
Die CI prüft beide zusätzlichen Compose-Dateien nur als Konfiguration.

```sh
uv run --project backend --locked pytest \
  backend/tests/unit/test_searxng_provider.py backend/tests/llm_integration/test_http_search.py
uv run --project backend --locked ruff check backend
uv run --project backend --locked ruff format --check backend
make python-typecheck
```

P1b und End-to-End-Websuche sind damit vorbereitet, aber noch nicht freigegeben.
Ein Qualitätsnachweis mit echten Engines/DeepSeek/GPT-OSS-120B und ein
Containerstart-Smoke sind gesonderte Abnahmen; eine Compose-Syntaxprüfung oder
ein Simulatorergebnis ersetzt diese nicht.

Lokale Abschlussprüfung auf dieser `main`-Basis:

| Prüfung | Ergebnis |
| --- | --- |
| neue Provider-Unitfälle / echte lokale HTTPintegration | 103 / 12 bestanden |
| gesamte Backend-Unit-/Vertrags-/HTTPsuite | 631 bestanden |
| Ruff Check / Format, striktes Backend-Pyright | bestanden |
| API-/WebSocket-Vertragsdrift | unverändert aktuell |
| Backend-Sourcepaket und Wheel | erfolgreich gebaut |
| Basis-/Dev-/Such-/Backendanschluss-Compose | Konfiguration gültig |
| Compose-Isolation / bestehende Services | ohne Hostport, nur bewusster Backendanschluss |

Keine Produktivänderung, neue Migration, Liveprovideranfrage oder Aktivierung
des Webmenüs wurde vorgenommen.
