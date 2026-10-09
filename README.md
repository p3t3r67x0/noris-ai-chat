# noris AI Chat

Das Monorepo enthält die Foundation aus **Etappe 0**, die Chat-Oberfläche aus **Etappe 1** und die ausdrücklich beauftragte **Etappe 2: LLM-Anbindung**. Unter `/` läuft standardmäßig die lokale Chat-Demo; der konfigurierbare Real-Transport streamt über ein zugriffsgeschütztes FastAPI-Gateway. `/status` prüft weiterhin Nuxt, API und PostgreSQL. Die neue Aufgabenstellung erweitert den ursprünglichen [PLAN.md](PLAN.md); Domain-/OIDC-Migration und Chat-Datenbanktabellen sind weiterhin offen. Die Live-Verbindung zu Noris ist ohne Provider-Zugangsdaten noch nicht verifiziert.

## Voraussetzungen und Versionen

Für den vollständigen Containerstart: Docker Engine und Docker Compose v2 mit `--wait`. Für Entwicklung auf dem Host zusätzlich Python 3.13, uv 0.12.5, Node.js 24 LTS und pnpm 11.1.3. Node 22 ab 22.22.3 wird ebenfalls unterstützt. `.python-version` und `.nvmrc` legen die empfohlenen Laufzeiten fest.

Die Make-Ziele verwenden das Compose-Plugin (`docker compose`) oder automatisch das eigenständige `docker-compose` v2. Damit funktionieren die Startbefehle auch ohne installiertes Docker-CLI-Plugin.

| Komponente | Version |
| --- | --- |
| Nuxt / Vue | 4.5.2 / 3.5.42 |
| Nuxt UI | 4.11.3 |
| Tailwind CSS | 4.3.3 |
| FastAPI / Pydantic | 0.142.2 / 2.13.5 |
| Pydantic AI | 1.107.6 (`pydantic-ai-slim`) |
| SQLAlchemy / Alembic / psycopg | 2.0.54 / 1.20.0 / 3.3.6 |
| PostgreSQL | 18.6 |
| ESLint / TypeScript | 10.10.0 / 5.9.3 |

`backend/uv.lock` und `pnpm-lock.yaml` fixieren auch die transitiven Abhängigkeiten. pnpm 11 erhält dafür explizit `lockfile: true` im Workspace; `optimisticRepeatInstall: false` stellt sicher, dass Installationsbefehle ihre Lockfile-Prüfung ausführen. Die Vue-Compiler und Laufzeitpakete bleiben über Overrides auf derselben Version. Der ESLint-Konfigurationsinspektor ist auf 3.4.0, `enhanced-resolve` auf 5.24.5 und `vue-component-type-helpers` passend zu den Vue-Typwerkzeugen auf 3.3.11 fixiert; diese kompatiblen Versionen waren in der eingeschränkten Entwicklungsumgebung verfügbar. Updates dieser Overrides sollen gemeinsam mit den Lint-, Typ- und Buildprüfungen erfolgen.

Pydantic AI ist als schlanke Basis ohne Provider-Extras installiert. Das neue `LLMProvider`-Protokoll und der OpenAI-kompatible HTTPX-Adapter verwenden den bestehenden Chat-Transportvertrag. Nuxt UI und Tailwind bilden das Chat-Designsystem. Die native Statuskomponente aus Etappe 0 bleibt unter `/status` verfügbar.

## Vollständiger Start mit Docker

```sh
cp .env.example .env
make up
curl --fail http://127.0.0.1:8080/api/v1/health/ready
```

Die Anwendung ist unter **http://127.0.0.1:8080** erreichbar. Caddy führt Frontend und `/api/*` unter derselben Origin zusammen. Die Datenbank besitzt in dieser Konfiguration keinen veröffentlichten Port. PostgreSQL 18 speichert seine Daten im Volume unter `/var/lib/postgresql`.

Der einmalige `migrate`-Dienst führt `alembic upgrade head` nach dem Datenbankstart aus. Der PostgreSQL-Healthcheck prüft TCP auf `127.0.0.1:5432`, damit der temporäre Unix-Socket-Server während der Initialisierung nicht bereits als bereit gilt. Das Backend startet erst nach erfolgreicher Migration. Die Baseline `0001_foundation` verwaltet ausschließlich den Alembic-Revisionsstand; Domänentabellen folgen in Etappe 2.

`noris_migrator` ist der lokale Bootstrap-/Migrationsbenutzer. Die Anwendung verbindet sich als `noris_app`, ohne Superuser- oder `BYPASSRLS`-Rechte. Das Init-Skript vergibt für die Foundation nur Verbindungs-, Schema-Nutzungs- und Tabellen-Leserechte. Spätere Schreibrechte und RLS-Regeln müssen zusammen mit den Domänenmigrationen eingeführt werden. Die Migration-Zugangsdaten werden dem Backend-Container nicht übergeben.

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
| `GET /api/v1/health/ready` | 200 nach erfolgreichem DB-Check und erwarteter Baseline; sonst 503 |
| `GET /api/v1/openapi.json` | Versionierter API-Vertrag |
| `GET /api/v1/llm/models` | Zugriffsgeschützter, serverseitig konfigurierter Modellkatalog |
| `POST /api/v1/llm/chat` | Zugriffsgeschützte Chat-Anfrage mit Etappe-1-Ereignissen als SSE |

Fehler verwenden `{ "error": { "code", "message", "request_id" } }`. Antworten tragen `X-Request-ID` und `Cache-Control: no-store`. Interne Ausnahmen und Validierungseingaben werden nicht in Fehlerantworten ausgegeben. Das Frontend nutzt relative API-URLs und benötigt keine Provider-Zugangsdaten.

```sh
make generate-api
make check-api
```

Die Generierung exportiert OpenAPI direkt aus der FastAPI-App, ohne laufenden Server oder DB-Verbindung. Daraus entstehen `docs/api/openapi.json` und `frontend/app/types/generated/api.ts`; die HTTP-Funktionen verwenden diese Typen. `check-api` verhindert Drift in beiden Dateien. Der Generator unterstützt GET/POST, JSON und SSE-Verträge und bricht bei unbekannten Vertragsformen ab.

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

Unter `/` läuft standardmäßig die lokale Chat-Demo ohne Provider-Schlüssel. Im Mock-Modus erzeugen `/lang` und `/fehler` deterministische Fixtures. Im Real-Modus werden normale Nachrichten an den konfigurierten Provider übertragen; verfügbare Modelle kommen ausschließlich aus dem Backend. Chats und Entwürfe bleiben im Browser gespeichert. Anhänge und Benutzerbereich sind vorbereitete Demo-Funktionen. Enter sendet, Shift+Enter fügt einen Zeilenumbruch ein. Neue Fragen rücken unter den Header; manuelles Hochscrollen pausiert das Folgen. `Ctrl/Cmd+Shift+O` startet einen Chat, `Ctrl/Cmd+K` öffnet die Suche und Escape stoppt außerhalb von Dialogen eine Antwort.

Konfiguration, Anmeldung für Real-Modus, Sicherheitsgrenzen und lokale HTTP-/Browser-Tests: [Etappe-2-Betrieb](docs/ETAPPE-2-BETRIEB.md). Der Provider ist standardmäßig deaktiviert; es gibt keine implizite externe Zieladresse. Echte Provider-Smoke-Tests verlangen einen ausdrücklichen Opt-in und Zugangsdaten außerhalb des Repositories.

GitHub Actions führt Lint, strikte Typprüfung, API-Drift-Check, Unit-, DB- und Browser-Tests sowie Produktionsbuilds aus. Ein zweiter Job baut den vollständigen Compose-Stack aus einem frischen Checkout und prüft Proxy-Routing und DB-Rollenrechte. Browserläufe liefern Reports und Screenshots als Artefakt; fehlgeschlagene Fälle ergänzen Traces.

Die Nachweise der Foundation stehen in [docs/ETAPPE-0-TESTERGEBNISSE.md](docs/ETAPPE-0-TESTERGEBNISSE.md). Aufbau und Prüfstand der Chat-Oberfläche: [Etappe-1-Architektur](docs/ETAPPE-1-ARCHITEKTUR.md), [Etappe-1-Tests](docs/ETAPPE-1-TESTERGEBNISSE.md). Die ausdrücklich beauftragte Integration ist in [Etappe-2-Architektur](docs/ETAPPE-2-ARCHITEKTUR.md), [Betrieb](docs/ETAPPE-2-BETRIEB.md) und [Testergebnissen](docs/ETAPPE-2-TESTERGEBNISSE.md) beschrieben.
