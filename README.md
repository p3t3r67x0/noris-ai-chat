# noris AI Chat

Das Monorepo enthält die Foundation, die bestehende Chat-Oberfläche, die Noris-Anbindung und **Etappe 3: PostgreSQL-Persistenz mit WebSocket-Streaming**. Im WebSocket-Modus speichert das Backend Chats, Varianten, Titel und Entwürfe dauerhaft und lädt den LLM-Kontext aus PostgreSQL. Die credentialfreie Beispielkonfiguration bleibt eine lokale Mock-Demo. `/status` prüft Nuxt, API und PostgreSQL. [Architektur](docs/ETAPPE-3-ARCHITEKTUR.md), [WebSocket-Vertrag](docs/WEBSOCKET-CHAT-V1.md) und [Abnahmebericht](docs/ETAPPE-3-ABSCHLUSSBERICHT.md) beschreiben den Single-Owner-Betrieb und die Prüfungen. OIDC und öffentlicher TLS-Betrieb bleiben separat vorzubereiten.

## Voraussetzungen und Versionen

Für den vollständigen Containerstart: Docker Engine und Docker Compose v2 mit `--wait`. Für Entwicklung auf dem Host zusätzlich Python 3.13, uv ab 0.12.5 (Container: 0.12.23), Node.js 24 LTS und pnpm 11.1.3. Node 22 ab 22.22.3 wird ebenfalls unterstützt. `.python-version` und `.nvmrc` legen die empfohlenen Laufzeiten fest.

Die Make-Ziele verwenden das Compose-Plugin (`docker compose`) oder automatisch das eigenständige `docker-compose` v2. Damit funktionieren die Startbefehle auch ohne installiertes Docker-CLI-Plugin.

| Komponente | Version |
| --- | --- |
| Nuxt / Vue | 4.5.2 / 3.5.43 |
| Nuxt UI | 4.11.3 |
| Tailwind CSS | 4.3.3 |
| FastAPI / Pydantic | 0.142.2 / 2.13.5 |
| Pydantic AI | 2.54.0 (`pydantic-ai-slim`) |
| SQLAlchemy / Alembic / psycopg | 2.1.3 / 1.20.0 / 3.3.6 |
| PostgreSQL | 18.6 |
| ESLint / TypeScript | 10.12.0 / 5.9.3 |

`backend/uv.lock` und `pnpm-lock.yaml` fixieren auch die transitiven Abhängigkeiten. pnpm 11 erhält dafür explizit `lockfile: true` im Workspace; `optimisticRepeatInstall: false` stellt sicher, dass Installationsbefehle ihre Lockfile-Prüfung ausführen. Die Vue-Compiler und Laufzeitpakete bleiben über Overrides auf derselben Version. Der ESLint-Konfigurationsinspektor ist auf 3.4.0, `enhanced-resolve` auf 5.24.5 und `vue-component-type-helpers` auf 3.3.11 fixiert (vue-tsc 3.3.12); die aktuelle Kombination wird durch Lint-, Typ- und Buildprüfungen abgesichert. Updates dieser Overrides sollen gemeinsam mit den Lint-, Typ- und Buildprüfungen erfolgen.

Pydantic AI ist als schlanke Basis ohne Provider-Extras installiert. Das neue `LLMProvider`-Protokoll und der OpenAI-kompatible HTTPX-Adapter verwenden den bestehenden Chat-Transportvertrag. Nuxt UI und Tailwind bilden das Chat-Designsystem. Die native Statuskomponente aus Etappe 0 bleibt unter `/status` verfügbar.

## Vollständiger Start mit Docker

```sh
cp .env.example .env
make up
curl --fail http://127.0.0.1:8080/api/v1/health/ready
```

Die Anwendung ist unter **http://127.0.0.1:8080** erreichbar. Caddy führt Frontend und `/api/*` unter derselben Origin zusammen. Die Datenbank besitzt in dieser Konfiguration keinen veröffentlichten Port. PostgreSQL 18 speichert seine Daten im Volume unter `/var/lib/postgresql`.

Der einmalige `migrate`-Dienst führt `alembic upgrade head` nach dem Datenbankstart aus. Der PostgreSQL-Healthcheck prüft TCP auf `127.0.0.1:5432`, damit der temporäre Unix-Socket-Server während der Initialisierung nicht bereits als bereit gilt. Das Backend startet erst nach erfolgreicher Migration. Die Baseline `0001_foundation` verwaltet ausschließlich den Alembic-Revisionsstand; die Chat-Migrationen 0002–0004 ergänzen Persistenz, immutable Topologie und Fortsetzungsvarianten.

`noris_migrator` ist der lokale Bootstrap-/Migrationsbenutzer. Die Anwendung verbindet sich als `noris_app`, ohne Superuser- oder `BYPASSRLS`-Rechte. Das Init-Skript vergibt für die Foundation nur Verbindungs-, Schema-Nutzungs- und Tabellen-Leserechte. Die Chat-Migration vergibt gezielte DML-Rechte auf die sechs Chat-Tabellen; Ownership prüft die Domain-Schicht. RLS und OIDC-Multi-User sind noch nicht implementiert. Die Migration-Zugangsdaten werden dem Backend-Container nicht übergeben.

Die Werte in `.env.example` sind ausschließlich lokale Entwicklungswerte. Eigene Passwörter müssen für die interpolierten Compose-URLs URL-kompatibel sein oder percent-kodiert werden. Auf dem Host stehen vollständige URLs in `NORIS_DATABASE_URL` und `NORIS_MIGRATION_DATABASE_URL`. Änderungen an Init-Passwörtern wirken nur bei einem frischen PostgreSQL-Volume; bestehende Rollen müssen in der Datenbank aktualisiert werden.

```sh
sh infrastructure/scripts/compose.sh logs --follow backend frontend
make down
```

`down` erhält das Datenvolume. Dieser Stack ist eine lokale Foundation. TLS, Betriebshärtung und Produktivfreigabe gehören zu Etappe 4.

## Entwicklung

Entwicklung vollständig in Containern mit Hot Reload und auf Loopback beschränkten Ports:

```sh
cp .env.example .env
make dev-up
```

Die Quellen unter `frontend/app` und `backend/src` werden eingebunden. Frontend: Port 3000, API: 8000, PostgreSQL auf dem Host: 55432, gemeinsame Origin über Caddy: 8080. Im Container bleibt PostgreSQL auf Port 5432. `NORIS_POSTGRES_PORT` steuert den Host-Port; bei einer Änderung müssen auch die beiden Host-Verbindungs-URLs in `.env` angepasst werden. Bei geänderten Abhängigkeiten oder Konfigurationen die Container neu bauen.

Alternativ nur PostgreSQL im Container starten und beide Anwendungen auf dem Host ausführen:

```sh
cp .env.example .env
make db-up
npm install --global pnpm@11.1.3
make install
make migrate
```

Danach in zwei Terminals `make backend-dev` und `make dev` ausführen. Nuxt leitet `/api` während der Entwicklung an `NORIS_DEV_API_TARGET` weiter. Die Dokumentation der Entwicklungs-API steht unter http://127.0.0.1:8000/api/v1/docs; in `production` ist die interaktive Dokumentation deaktiviert.

Für ausschließlich das Backend nach dem einmaligen Anlegen von `.env`:

```sh
make db-up
uv sync --project backend --locked
make migrate && make backend-dev
```

Die Datenbank muss vor der Migration erfolgreich starten. Bei `role "noris_migrator" does not exist` die Verbindungs-URL und `make db-up` prüfen: Auf dem bisherigen Port 5432 kann bereits ein anderer PostgreSQL-Server laufen. Die Beispielkonfiguration verwendet deshalb den separaten Host-Port 55432. Eine vorhandene `.env` auf diese Werte umstellen, statt sie mit `cp` zu überschreiben. Vorhandene Datenvolumes werden bei dieser Korrektur erhalten.

### DNS-Fehler beim Docker-Build unter Linux

Wenn `uv sync` oder npm im Image-Build mit `dns error` / `failed to lookup address information` scheitert, obwohl Paket-Downloads auf dem Host funktionieren, den Build über das Hostnetzwerk versuchen:

```sh
NORIS_BUILD_NETWORK=host make dev-up
```

Für den regulären Containerstart entsprechend `NORIS_BUILD_NETWORK=host make up`. Die Einstellung betrifft die `RUN`-Schritte aller drei Anwendungsbuilds, einschließlich des Migrationsimages. Die laufenden Dienste behalten ihr Compose-Netzwerk und ihre Portbelegungen. Standardmäßig bleibt das Build-Netzwerk `default`. Das Verhalten ist in der [Docker-Compose-Dokumentation zu `build.network`](https://docs.docker.com/reference/compose-file/build/#network) beschrieben.

Ob der Host selbst DNS auflösen kann, lässt sich ohne Zugangsdaten prüfen:

```sh
getent hosts files.pythonhosted.org
getent hosts registry.npmjs.org
```

Wenn auch diese Auflösung scheitert, muss die Host-/VPN-DNS-Konfiguration korrigiert werden. Der Build-Netzwerkmodus behebt keine allgemeine Host-Netzwerkstörung. Paketversionen und TLS-Prüfung werden für diese Fehlerbehandlung nicht verändert.

### Verbindungs-Timeout im Migrationscontainer

Ein `psycopg.errors.ConnectionTimeout` trotz vollständig gestarteter Datenbank benötigt einen Verbindungstest aus dem Migrationscontainer. Der folgende Befehl prüft die tatsächlich verwendete Adresse, DNS-Auflösung, TCP-Erreichbarkeit und Datenbankanmeldung, ohne Passwörter auszugeben. Er verwendet das bereits gebaute Image, führt ausschließlich `SELECT 1` aus und benötigt weder eine Migration noch einen erneuten Image-Build:

```sh
make db-diagnose
```

PostgreSQL muss dafür bereits laufen. Die TCP- und Datenbankverbindungen verwenden jeweils ein Timeout von fünf Sekunden. Der Prozess endet bei einem fehlgeschlagenen Schritt mit Exit-Code 1.

Im Compose-Stack ist das erwartete Ziel `postgres:5432`, nicht die Host-Adresse mit Port 55432. Schlägt die DNS-Auflösung fehl, die gemeinsame Compose-Netzwerkzuordnung prüfen. Gelingt DNS, aber TCP läuft in einen Timeout, die Erreichbarkeit im Docker-Netzwerk und die Host-/VPN-Firewall prüfen. `TCP: OK` bestätigt die Erreichbarkeit; `PostgreSQL: OK` bestätigt zusätzlich Anmeldung und Testabfrage. `NORIS_BUILD_NETWORK=host` wirkt ausschließlich beim Image-Build und ändert diese Laufzeitverbindung nicht. Bestehende Datenvolumes müssen für die Diagnose nicht gelöscht werden.

Auf dem betroffenen Linux-Host enthält `/etc/nftables.conf` eine eigene `inet filter forward`-Chain mit `policy drop` und Freigaben für Ethernet/WLAN und LXD. Eine solche aktive Chain kann zusätzlich zu den Docker-Regeln den Verkehr zwischen den Projektcontainern blockieren. Für genau diese Konfiguration steht eine gezielte Laufzeitkorrektur bereit:

```sh
sudo make network-repair
make db-diagnose
NORIS_BUILD_NETWORK=host make dev-up
```

`network-repair` prüft die aktive Chain, die Eigentümerkennzeichnung und den Treiber des Netzwerks `noris-ai-chat_default`, die Docker-Einstellung für Container-Kommunikation und die lokale TCP-Bereitschaft von PostgreSQL. Es ermittelt den tatsächlichen Bridge-Namen und fügt nach einer nftables-Syntaxprüfung eine kommentierte Regel für Verkehr mit **dieser Bridge als Eingangs- und Ausgangsinterface** ein. Wiederholte Aufrufe erkennen die vorhandene Regel. Die globale Forward-Policy und die Docker-Regeln werden nicht geändert. Das Skript verändert keine Konfigurationsdatei unter `/etc`.

Die Korrektur benötigt Root-Rechte und gilt bis zum Neustart oder Neuladen der Host-Firewall. Sie erlaubt ausschließlich den Verkehr innerhalb dieser Projekt-Bridge; die Build-DNS-Korrektur bleibt davon unabhängig. Die markierte Regel lässt sich mit `sudo nft -a list chain inet filter forward` anzeigen und über ihren Handle mit `sudo nft delete rule inet filter forward handle <HANDLE>` gezielt entfernen. Die Verarbeitung mehrerer Firewall-Chains wird in der [Docker-Dokumentation](https://docs.docker.com/engine/network/firewall-nftables/#migrating-accept-rules) erläutert.

### Dauerhafte nftables-Freigabe auf diesem Linux-Host

Compose legt die Projekt-Bridge jetzt unter dem festen Linux-Interfacenamen **`noris-chat0`** an. Damit kann eine eng begrenzte Firewall-Regel auch nach einer Neuerstellung des Netzwerks weiter gelten. Der Docker-Netzwerkname bleibt `noris-ai-chat_default`. Die Treiberoption ist in der [Docker-Dokumentation](https://docs.docker.com/engine/network/drivers/bridge/#options) beschrieben.

Zuerst die bestehende Host-Konfiguration sichern und bearbeiten:

```sh
sudo cp -a /etc/nftables.conf /etc/nftables.conf.bak
sudoedit /etc/nftables.conf
```

Innerhalb der vorhandenen `table inet filter` / `chain forward`, direkt nach `policy drop;`, die folgende Zeile ergänzen. Dieselbe Vorlage steht unter `infrastructure/nftables/noris-ai-chat-forward.nft`:

```nft
iifname "noris-chat0" oifname "noris-chat0" counter accept comment "noris-ai-chat:noris-chat0"
```

Die Konfiguration ohne Anwendung prüfen und das Laden beim Boot aktivieren:

```sh
sudo nft --check --file /etc/nftables.conf && sudo systemctl enable nftables
```

Die vorhandene `/etc/nftables.conf` enthält `flush ruleset`. Ein Reload oder Restart des nftables-Dienstes würde dadurch auch die dynamischen Docker-Regeln entfernen. Zum sofortigen Anwenden der einzelnen Freigabe dient deshalb weiterhin `network-repair`.

Für einen bereits existierenden Stack einmalig das Netzwerk mit dem neuen Interface-Namen neu anlegen. Diese Umstellung stoppt die Projektcontainer; `make down` erhält das PostgreSQL-Datenvolume:

```sh
make down
make db-up
sudo make network-repair
make db-diagnose
NORIS_BUILD_NETWORK=host make dev-up
```

Bei einem späteren Host-Neustart lädt `nftables.service` die gespeicherte Regel vor dem Netzwerkstart; Docker baut anschließend seine eigenen Regeln auf. `iifname`/`oifname` verweisen auf den Namen und benötigen kein bereits vorhandenes Interface beim Laden; siehe [nft-Handbuch](https://netfilter.org/projects/nftables/manpage.html). Nach einem tatsächlichen Neustart mit gestarteter Anwendung erneut `make db-diagnose` prüfen. Die Host-Datei wurde vom Agenten nicht geändert; Boot- und Docker-Laufzeitprüfungen sind in der Sandbox gesperrt.

## Architektur und API-Verträge

```text
frontend/app/         Nuxt-Seiten, Statuskomponente, Composable und API-Zugriff
frontend/tests/       Vitest-Unit- und Playwright-Desktop-/Mobiltests
backend/src/noris_ai/ API-Router, Konfiguration, Fehlerverträge, Readiness, DB-Basis
backend/migrations/  Versionierte Alembic-Migrationen
backend/tests/       Unit-, OpenAPI-Contract- und PostgreSQL-Integrationstests
scripts/             OpenAPI-Export und TypeScript-Generierung
docs/api/            Eingecheckter OpenAPI-Vertrag
infrastructure/      Dockerfiles, Datenbank-Initialisierung und Reverse Proxy
.github/             CI und Dependency-Updates
```

Die Backend-Konfiguration ist unveränderlich und typisiert. DB-URL und Provider-Zugangsdaten bleiben `SecretStr`. Der App-Lifecycle verwaltet den asynchronen SQLAlchemy-Pool und den optionalen HTTPX-Provider; ein austauschbarer Readiness-Probe erlaubt Unit-Tests ohne Datenbank. Reine ASGI-Middleware ergänzt Request-IDs ohne Streaming-Antworten zu puffern; LLM-Anfragen werden vor der Validierung begrenzt.

| Endpoint | Verhalten |
| --- | --- |
| `GET /api/v1/health/live` | 200, wenn der API-Prozess antwortet; unabhängig von der DB |
| `GET /api/v1/health/ready` | 200 nach erfolgreichem DB-Check und Revision `0004_chat_continuation`; sonst 503 |
| `GET /api/v1/openapi.json` | Versionierter API-Vertrag |
| `GET /api/v1/llm/models` | Zugriffsgeschützter, dynamischer Chatmodellkatalog mit serverseitigem Discovery-Cache |
| `POST /api/v1/llm/chat` | Zugriffsgeschützte Chat-Anfrage mit Etappe-1-Ereignissen als SSE |

Fehler verwenden `{ "error": { "code", "message", "request_id" } }`. Antworten tragen `X-Request-ID` und `Cache-Control: no-store`. Interne Ausnahmen und Validierungseingaben werden nicht in Fehlerantworten ausgegeben. Das Frontend nutzt relative API-URLs und benötigt keine Provider-Zugangsdaten.

```sh
make generate-api
make check-api
```

Die Generierung exportiert OpenAPI direkt aus der FastAPI-App, ohne laufenden Server oder DB-Verbindung. Daraus entstehen `docs/api/openapi.json` und `frontend/app/types/generated/api.ts`; die HTTP-Funktionen verwenden diese Typen. `check-api` verhindert Drift in beiden Dateien. Der Generator unterstützt die vorhandenen REST-Methoden, JSON und SSE-Verträge und bricht bei unbekannten Vertragsformen ab. Zusätzlich werden der versionierte WebSocket-Vertrag und seine TypeScript-Unions auf Drift geprüft.

## Checks und Tests

```sh
make lint
make typecheck
make check-api
make test-unit
make build
```

`make typecheck` führt Pyright im strikten Modus, Nuxt-/Vue-Typprüfungen einschließlich der Tests und die Typprüfung der Generierungsskripte aus. Die Pyright-CLI 1.1.408 wird über `uv tool run` bezogen. Ruff prüft Stil, Format und Sicherheitsregeln. Vitest prüft die Statuskomponente sowie Erfolg, Fehler und Abbruch beim API-Zugriff.

Integrationstests benötigen eine **separate, disposable Datenbank mit dem Namenssuffix `_test`**. Sie führen Upgrade, wiederholtes Upgrade, Schema-Drift-Check, Downgrade, erneutes Upgrade, Readiness und Transaktions-Rollback aus. Sie verändern den Alembic-Stand der Testdatenbank.

Bei laufendem Entwicklungs-PostgreSQL mit den Beispielwerten:

```sh
sh infrastructure/scripts/compose.sh exec postgres createdb -U noris_migrator noris_test
export NORIS_TEST_DATABASE_URL='postgresql+psycopg://noris_migrator:noris-local-development-only@127.0.0.1:55432/noris_test'
make test-integration
```

Für die Browser-Tests die normale Entwicklungsdatenbank migrieren und Chromium installieren. Playwright startet API und Nuxt selbst; die Ports 8000 und 3000 müssen dafür frei sein.

```sh
make migrate
pnpm --dir frontend exec playwright install --with-deps chromium
make test-e2e
```

Die sechs Foundation-Playwright-Fälle bleiben unter `/status` erhalten. Die Chat-Tests prüfen Desktop und Mobile, Markdown/Clipboard, IME, Streaming/Stop/Fehler, Verzweigungen, Entwürfe, lange Verläufe, Shortcuts, Fokus und Light/Dark-Screenshots. Referenzen liegen unter `frontend/tests/e2e/__screenshots__/linux`. Nach einer beabsichtigten Designänderung können sie mit `pnpm --dir frontend test:e2e chat-visual.spec.ts --update-snapshots` neu erzeugt werden; neue Bilder vor dem Commit visuell prüfen.

Unter `/` läuft standardmäßig die lokale Chat-Demo ohne Provider-Schlüssel. Im Mock-Modus erzeugen `/lang` und `/fehler` deterministische Fixtures. Im Real-Modus werden normale Nachrichten an den konfigurierten Provider übertragen; verfügbare Modelle kommen ausschließlich aus dem Backend. Im Mock-/SSE-Kompatibilitätsmodus bleiben Chats und Entwürfe lokal; im WebSocket-Modus lädt und speichert das Backend sie in PostgreSQL. Anhänge und Benutzerbereich sind vorbereitete Demo-Funktionen. Enter sendet, Shift+Enter fügt einen Zeilenumbruch ein. Neue Fragen rücken unter den Header; manuelles Hochscrollen pausiert das Folgen. `Ctrl/Cmd+Shift+O` startet einen Chat, `Ctrl/Cmd+K` öffnet die Suche und Escape stoppt außerhalb von Dialogen eine Antwort.

Konfiguration, Anmeldung für Real-Modus, Sicherheitsgrenzen und lokale HTTP-/Browser-Tests: [Etappe-2-Betrieb](docs/ETAPPE-2-BETRIEB.md). Der Provider ist standardmäßig deaktiviert; es gibt keine implizite externe Zieladresse. Echte Provider-Smoke-Tests verlangen einen ausdrücklichen Opt-in und Zugangsdaten außerhalb des Repositories.

Neue Chats erhalten automatisch kurze [Gesprächstitel](docs/AI-CONVERSATION-TITLES.md), ohne das Antwort-Streaming zu verzögern. Manuell vergebene Namen haben Vorrang. Im WebSocket-Modus bleiben Titel in PostgreSQL erhalten, im Mock-/SSE-Kompatibilitätsmodus im Browser. Der Mock-Modus erzeugt ausschließlich lokale synthetische Titel. Für Noris-Titelanfragen gelten die gemeinsamen Backend-Kostenlimits.

GitHub Actions führt Lint, strikte Typprüfung, API-Drift-Check, Unit-, DB- und Browser-Tests sowie Produktionsbuilds aus. Ein zweiter Job baut den vollständigen Compose-Stack aus einem frischen Checkout und prüft Proxy-Routing und DB-Rollenrechte. Browserläufe liefern Reports und Screenshots als Artefakt; fehlgeschlagene Fälle ergänzen Traces.

Die Nachweise der Foundation stehen in [docs/ETAPPE-0-TESTERGEBNISSE.md](docs/ETAPPE-0-TESTERGEBNISSE.md). Aufbau und Prüfstand der Chat-Oberfläche: [Etappe-1-Architektur](docs/ETAPPE-1-ARCHITEKTUR.md), [Etappe-1-Tests](docs/ETAPPE-1-TESTERGEBNISSE.md). Die ausdrücklich beauftragte Integration ist in [Etappe-2-Architektur](docs/ETAPPE-2-ARCHITEKTUR.md), [Betrieb](docs/ETAPPE-2-BETRIEB.md) und [Testergebnissen](docs/ETAPPE-2-TESTERGEBNISSE.md) beschrieben.

### Browserprüfung des Produktionsstacks

Nach `make up` führt `make test-e2e-production` dieselben Desktop-/Mobile-Interaktions- und Screenshot-Tests über Caddy auf `http://127.0.0.1:8080` aus. Die bestehenden Baselines und die Toleranz bleiben unverändert. Der Compose-CI-Job startet den Stack aus einem frischen Checkout und führt diese Prüfung automatisch aus; die zusätzlichen Artefakte heißen `production-browser-test-results`. Die regulären Entwicklungs- und RealTransport-Tests bleiben erhalten. Beide Transport-Testmodi verwenden synthetische Daten und einen lokalen Simulator; Live-Aufrufe erfolgen ausschließlich mit gesondertem Opt-in und Freigabe.

Lange Antworten, bestätigte 128K-Kontextkonfiguration, manuelle Fortsetzung und die vollständige Limit-/Kostenpolitik: [LONG-CONTEXT-RESPONSES.md](docs/LONG-CONTEXT-RESPONSES.md).
## Dynamische Noris-Modellauswahl

Im Real-Modus liest der bestehende Backend-Provider die vollständigen validierten Modellmetadaten aus `GET /v1/models` (Schema 2.4 und strukturell kompatible Versionen) über die konfigurierte Server-URL und den serverseitigen Key. Modalitäten bestimmen Fähigkeiten; die exakte lokale Registry bestätigt zusätzlich den Chat-Completions-Vertrag. DeepSeek V4.1 Flash und Qwen3.8 27B werden bei aktueller Bereitschaft automatisch berücksichtigt. Unbekannte IDs erfordern belegte Betreiberfreigabe; Embeddings und Reranker bleiben ausgeschlossen. Smart Router erscheint nur bei tatsächlicher Verfügbarkeit. Gemeldete Kontext-/Ausgabemaxima bleiben getrennt von konservativen Anwendungslimits. Preise erscheinen als USD pro Million Tokens mit Abrufdatum, unbekannte Preise bleiben unbekannt. Mapping, Defaults, Overrides und Unsicherheiten: [Modellfähigkeiten](docs/NORIS-MODEL-CAPABILITIES.md).

Der gemeinsame Katalog schützt Modellmenü, Chat und Titel. TTL standardmäßig 300 Sekunden, zusammengefasste Parallelaufrufe und begrenzte Timeouts. Stale standardmäßig aus; optionale veraltete Anzeige gibt keine Generierungsberechtigung. Modellabhängige Kontext-/Ausgabelimits und belegte Reasoning-/Tokenparameter erhalten Sicherheits- und Kostenlimits. Metadaten kennzeichnen DOCUMENTED/VERIFIED/UNKNOWN; Echtzeitpreise werden nicht behauptet.

Header und Composer zeigen verständliche, gruppierte Namen. Ein Wechsel startet keine Generierung und erhält Chats, Varianten und Entwürfe. Bei Berechtigungsentzug erklärt die UI den Zustand und bietet ein bewusstes Fallback. Konfiguration, zusätzliche Modellfreigaben, Cache-Policy und Fehlerbehandlung: [Betriebsdokumentation](docs/ETAPPE-2-BETRIEB.md#dynamischer-modellkatalog-und-zusätzliche-modelle).


## Persistenter Chat mit WebSocket

Chats werden im WebSocket-Modus [paginiert und bei Bedarf geladen](docs/CHAT-PAGINATION.md): initial höchstens 50 Sidebar-Metadaten, die aktiven Präferenzen/Entwürfe und ein 50-Nachrichten-Pfadfenster. Ältere Nachrichten, weitere Chats und Varianten werden gezielt nachgeladen; die Suche läuft über alle autorisierten Titel in PostgreSQL. Der LLM-Kontext bleibt vollständig serverseitig. REST-Listen liefern `nextCursor` und `hasMore`; Clients müssen für vollständige Listen weiterblättern. Migration `0005_chat_pagination` ergänzt Indizes ohne Daten zu löschen. [Reproduzierbare Messungen](docs/CHAT-PAGINATION-BENCHMARKS.json) umfassen bis zu 10.000 synthetische Unterhaltungen.

`NUXT_PUBLIC_CHAT_TRANSPORT=websocket` aktiviert die bestehenden UI-Komponenten
mit dem PostgreSQL-Backend. Setze die serverseitigen Noris- und Basic-
Zugangsdaten sowie `NORIS_LLM_ALLOWED_ORIGINS` für die Caddy-Origin; migriere mit
`make migrate` beziehungsweise dem Compose-Migrationsdienst. Der Provider-Key
bleibt im Backend. Alle Zugangsberechtigten teilen im ausdrücklich begrenzten
Single-Owner-Modus dieselben Chats. Nutze genau einen Backend-Worker.

Browserlokale Chats werden unter „Einstellungen → Datenkontrollen → Lokale Chats
importieren“ nach einem Hinweisdialog und ausdrücklichem Start übernommen.
Der ursprüngliche localStorage-Bestand bleibt
stehen. Rückkehr zur Demo mit `NUXT_PUBLIC_CHAT_TRANSPORT=mock` liest diese
Sicherung; neue PostgreSQL-Änderungen werden dadurch nicht zurückkopiert. Sichere
vor einem Datenbank-Downgrade die DB: Migration 0002 entfernt beim Downgrade die
neuen Tabellen. Solche Downgrades gehören ausschließlich in freigegebene
Wiederherstellungsabläufe oder wegwerfbare Testdatenbanken.

`real` bleibt der bisherige SSE-Kompatibilitätsmodus mit lokalem Chatbestand.
Für PostgreSQL-Persistenz verwende `websocket`. Nuxt-devProxy unterstützt keine
WS-Upgrades: nutze Caddy oder setze für lokale Entwicklung
`NUXT_PUBLIC_CHAT_WEBSOCKET_URL=ws://127.0.0.1:8000/api/v1/chat/ws` und ausdrücklich
passende `NORIS_CHAT_WS_ALLOWED_HOSTS`/Origins. Im öffentlichen Betrieb ist WSS
mit einer HTTPS-Origin erforderlich.

GLM 5.3 Flash ist mit der tatsächlich bestätigten ID
`vllm/qsu/glm-5-3-flash` registriert. Die Anzeige verlangt weiterhin aktuelle
Listung und Freigabe im Noris-Katalog; Reasoning-Parameter werden nicht erfunden.

`make test-e2e-websocket` benötigt eine migrierte, isolierte Datenbank über
`NORIS_DATABASE_URL` und startet ausschließlich lokale Provider-Simulatoren.
Die Tests löschen ihre synthetischen Chats: niemals gegen Nutzerdaten starten.
Mit `compose.test.yaml` und `NORIS_E2E_COMPOSE_URL=http://127.0.0.1:8080` prüft
dieselbe Suite den Produktionsbuild über Caddy. Diese Testkonfiguration enthält
nur synthetische Zugangsdaten und darf nicht öffentlich betrieben werden.
