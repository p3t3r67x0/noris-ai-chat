# Etappe 0: Implementierung und Prüfstand

**Stand: 2026-10-08.** Die Foundation aus Abschnitt 11 der vollständig gelesenen `PLAN.md` ist implementiert. Die vollständige Abnahme bleibt für die unten aufgeführten Laufzeit- und CI-Prüfungen offen. Etappe 1 wurde nicht begonnen und benötigt weiterhin die ausdrückliche Freigabe.

## Erfolgreiche Prüfungen

| Prüfung | Befehl | Ergebnis |
| --- | --- | --- |
| Python-Lockfile | `uv lock --check --project backend` | 44 Pakete aufgelöst; Lockfile aktuell |
| Python-Installation | `uv sync --project backend --locked` | Erfolgreich aus privatem Offline-Cache |
| Node-Lockfile | `pnpm install --frozen-lockfile --offline --ignore-scripts` | Erfolgreich; Lockfile unverändert, Einschränkungen unten |
| Lockfile-Inhalt | Abgleich der Importer mit beiden `package.json` und Workspace-Overrides | Exakte Übereinstimmung; Linux-Bindings für Rolldown, Rollup und Tailwind enthalten; keine temporären Pfade |
| Python Unit und API Contract | `uv run --project backend --locked pytest backend/tests/unit backend/tests/contract -q` | **38 bestanden**, einschließlich sieben Diagnosefällen und zwölf Prüfungen der Netzwerk-Reparatur |
| Python Lint | `uv run --project backend --locked ruff check backend` | Bestanden |
| Python Format | `uv run --project backend --locked ruff format --check backend` | 24 Dateien bestanden |
| Frontend Unit | `pnpm test` | **6 bestanden**, 2 Testdateien |
| Frontend Lint | `pnpm lint` | Bestanden mit ESLint **10.10.0**; kein ESLint 9 im Lockfile |
| Frontend-Typen | `pnpm typecheck` | Nuxt-Typecheck und `vue-tsc` für Unit-/E2E-Tests bestanden |
| Skript-Typen | `pnpm typecheck:tools` | Strikte TypeScript-Prüfung der Generierung bestanden |
| API-Drift | `pnpm api:check` | OpenAPI-Datei und generierte TypeScript-Verträge aktuell |
| Python-Paketbuild | `uv build --project backend` | sdist und Wheel erfolgreich gebaut |
| Frontend-Produktionsbuild | `pnpm build` | Nuxt-Client, SSR und Nitro-Server erfolgreich gebaut |
| Alembic SQL-Export | `uv run --directory backend --locked alembic upgrade head --sql` | Transaktion, Alembic-Versionstabelle und Baseline-Stempel generiert; keine Domänentabellen |
| Compose Basis und Entwicklung | `docker-compose --env-file .env.example config --quiet` sowie mit `-f compose.yaml -f compose.dev.yaml` | Beide Konfigurationen gültig |
| PostgreSQL-Init-Skript | `sh -n infrastructure/docker/postgres-init.sh` | Shell-Syntax gültig |
| CI-Konfiguration | YAML-Parsing der Workflow- und Dependabot-Dateien | Gültiges YAML; Trigger und beide Jobs überprüft |
| Playwright-Testauswahl | `pnpm --dir frontend exec playwright test --list` | **6 Fälle** erkannt: 3 Szenarien jeweils auf Desktop und Mobile |

Insgesamt wurden **44 automatisierte Unit-/Contract-Tests erfolgreich ausgeführt**. Die Browser-Testauswahl zählt nicht als bestandener Browserlauf. SQL-Export und Compose-Validierung zählen nicht als erfolgreiche Datenbankmigration oder Containerstart. Die sechs Frontend-Tests stammen aus der ursprünglichen Prüfung; der unveränderte Frontend-Code wurde für die anschließenden Docker-Startkorrekturen nicht erneut geprüft.

Die letzte Prüfung verwendete Python **3.13.15**, Node.js **22.22.3**, uv **0.12.5**, pnpm **11.1.3** und Docker Compose **2.39.4**. Compose war hier als eigenständiges `docker-compose` verfügbar. Dockerfiles und CI verwenden Node 24; der Host-Build mit Node 24 wurde in dieser Umgebung nicht ausgeführt.

## Nicht ausführbare Prüfungen und beobachtete Grenzen

| Prüfung | Tatsächliches Ergebnis | Ursache / verbleibender Nachweis |
| --- | --- | --- |
| PostgreSQL-Integrationstests | Drei Fixture-Fehler vor den Testassertionen | SQLAlchemy/psycopg meldet beim Unix-Socket `Operation not permitted`. Auch TCP-Sockets sind gesperrt. Upgrade, Downgrade, Schema-Check, Rollback und DB-Readiness müssen mit erreichbarem PostgreSQL ausgeführt werden. |
| Desktop-/Mobile-E2E | API-Webserver beendet sich mit Exit-Code 3; kein Browser-Test ausgeführt | Uvicorn darf `127.0.0.1:8000` nicht binden. Die Tests starten API und Nuxt selbst und benötigen die migrierte Datenbank. |
| Vollständiger Compose-Start und Docker-Builds | Start scheitert vor dem Image-Build | Verbindung zu `/var/run/docker.sock` wird mit `operation not permitted` verweigert. Ein frischer Volume-Start, Init-Rollen, Migration und Proxy-Routing bleiben offen. |
| Pyright strict | Nach Veröffentlichung erstmals in CI ausgeführt; zwölf Fehler im ersten Lauf. Korrektur lokal mit Pyright 1.1.409 bestanden. | Die gepinnte CI-Version 1.1.408 war lokal nicht verfügbar. Ein später gefundener vorhandener Node-Cache enthält 1.1.409; der erneute CI-Lauf prüft weiterhin 1.1.408. |
| Normaler Node-Installationslauf einschließlich Installationsskripten | esbuild-Installationsskript beendet sich mit `spawnSync ... EPERM` | Die Umgebung sperrt den Unterprozess im Versionscheck. Abhängigkeiten wurden für die Codeprüfungen mit `--ignore-scripts` installiert; die native esbuild-Datei ist vorhanden. CI und Dockerfiles führen die normale Installation mit Skripten aus. |
| GitHub Actions | Erster Remote-Lauf: Compose-Smoke bestanden, Checks an Pyright gescheitert. | [PR #1](https://github.com/p3t3r67x0/noris-ai-chat/pull/1) wurde über die GitHub-Anbindung veröffentlicht. Ein erneuter Lauf nach der Typkorrektur steht noch aus. |
| actionlint | Nicht ausgeführt | CLI nicht installiert; YAML-Parsing ersetzt keine semantische Actions-Prüfung. |

Der PostgreSQL-Testlauf wurde explizit mit einer auf `_test` endenden Test-URL versucht. Die Fixture erzwingt diesen Namenssuffix und setzt sowohl Anwendungs- als auch Migrations-URL auf die disposable Testdatenbank. Ohne explizite Test-URL bricht sie ab, statt die Entwicklungsdatenbank zu verändern.

Für die erfolgreiche Offline-Node-Installation wurden private Cache-Kopien unter `/tmp` verwendet und deren Paketmetadaten auf tatsächlich verfügbare stabile Paketversionen beschränkt. Die vollständigen Metadaten für optionale native Pakete wurden mit einbezogen. Der Lockfile enthält die öffentlichen Registry-Integritäten aus diesen Metadaten. `minimumReleaseAge: 0` war ausschließlich eine temporäre Einstellung für den Cache-Lauf und wurde anschließend entfernt. Die Skriptprüfungen verwendeten `pnpm_config_verify_deps_before_run=warn`, um in dieser Cache-Umgebung eine automatische erneute Installation zu vermeiden. Diese Ausnahmen sind nicht in der Repository- oder CI-Konfiguration hinterlegt.

Eine Paket-Download-Anfrage mit erhöhten Rechten wurde durch die automatische Freigabeprüfung abgelehnt, weil Sandbox-Eskalationen in dieser Sitzung nicht zulässig sind. Die Arbeit wurde mit den vorhandenen Caches fortgesetzt; Netzwerk- und Docker-Sperren wurden nicht umgangen.

Im Node-Abhängigkeitsbaum verbleiben zwei Hinweise aus Upstream-Paketen: `glob@10.5.0` ist veraltet; die optionale CLI-Vervollständigung `@bomb.sh/tab@0.0.19` erwartet `cac ^6.7.14`, während die Nuxt-CLI `cac 7.0.0` verwendet. Die ausgeführten Nuxt-, Lint-, Typ- und Unit-Prüfungen bestehen. CLI-Vervollständigung wurde nicht geprüft. Die Hinweise sollten bei den nächsten Dependency-Updates mit überprüft werden.

## Architekturabgleich und Abnahme

- Monorepo und modularer Monolith; Router, Konfiguration, DB-Basis und Readiness haben eigene Module. Keine späteren Domänenmodule vorgezogen.
- Typisierte und unveränderliche Pydantic-Konfiguration, strikte API-Schemas, strikte Python-/TypeScript-Prüfungen eingerichtet. Provider-SDKs, Gateway und echte Modellaufrufe bleiben Etappe 3.
- Nuxt 4, Vue 3 und Tailwind eingerichtet. Nuxt UI und die Chat-Komponenten folgen mit Etappe 1. Die Foundation-Seite prüft ausschließlich den Dienststatus und Retry.
- FastAPI ist die Quelle der OpenAPI- und Frontend-Typen. Generierung benötigt weder einen laufenden Server noch eine DB-Verbindung und scheitert bei unbekannten Vertragsformen.
- Gleiche Origin über Caddy bzw. Nuxt-Dev-Proxy. Kein allgemeines CORS-Freigabemuster und keine Provider-Keys im Frontend.
- Kontrollierter Migrationsdienst; keine automatische Migration pro Backend-Replikat. Baseline verwaltet ausschließlich Alembic-Metadaten.
- Anwendung und Migration verwenden getrennte DB-Rollen. `noris_app` besitzt weder Superuser- noch `BYPASSRLS`-Rechte. Die tatsächlichen Rollenrechte werden im Compose-CI-Job geprüft; RLS-Tabellen und Mandantentrennung folgen in Etappe 2.
- `.env` und Laufzeitartefakte sind ausgeschlossen. Eingecheckte Beispielwerte und Testzugangsdaten sind lokale Platzhalter; keine echten Provider-/OIDC-Zugangsdaten wurden hinzugefügt.

Der erste erfolgreiche Compose-Smoke-Job bestätigt einen frischen Checkout mit Image-Builds, PostgreSQL-Initialisierung, Online-Migration, gesundem Stack, Frontend über den Proxy und DB-Readiness über dieselbe Origin. Die Anwendung meldet weder Superuser- noch BYPASSRLS-Rechte. „CI grün“ sowie der separate Datenbankintegrations- und Browserlauf bleiben bis zum erfolgreichen Checks-Job **offen**. Die Start- und Prüfkommandos sind in der [README](../README.md) dokumentiert.

## Korrektur des lokalen Backend-Starts

Die Docker-CLI dieser Umgebung besitzt kein `docker compose`-Plugin; das eigenständige `docker-compose` v2.39.4 ist vorhanden. `infrastructure/scripts/compose.sh` wählt jetzt die verfügbare v2-Variante. `make db-up`, `make dev-up`, `make up` und `make down` verwenden diesen Wrapper. Plugin-Auswahl, Standalone-Fallback, fehlende CLI, Ablehnung von v1 und unveränderte Argumentweitergabe einschließlich Leerzeichen wurden mit isolierten CLI-Stubs erfolgreich geprüft. `sh -n` und die tatsächliche Compose-Konfigurationsprüfung bestehen.

Der gemeldete Migrationsfehler zeigte einen bereits erreichbaren PostgreSQL-Server auf Host-Port 5432 ohne Rolle `noris_migrator`. Die Projekt-Datenbank verwendet im Entwicklungsprofil jetzt den konfigurierbaren Host-Port **55432**; innerhalb von Compose bleibt es bei **5432**. Die lokalen Beispiel-URLs, die Default-Konfiguration und die vorhandene `.env` wurden entsprechend angepasst. Andere Datenbanken und bestehende Datenvolumes wurden nicht verändert. Host-Port und beide wirksamen Verbindungs-URLs wurden geprüft.

Nach der Korrektur: **19 Backend-Unit-/Contract-Tests bestanden**, Ruff-Lint und Formatprüfung bestanden, Basis- und Entwicklungs-Compose-Konfiguration gültig. `make db-up` wählt erfolgreich die vorhandene Standalone-CLI, bleibt hier jedoch am gesperrten Docker-Daemon-Socket hängen (`operation not permitted`). Ein tatsächlicher Containerstart und eine erfolgreiche Online-Migration sind weiterhin nicht nachgewiesen. Die Frontend-Prüfungen wurden für diese Backend-Startkorrektur nicht erneut ausgeführt; die zuvor dokumentierten Ergebnisse gelten für ihren unveränderten Code.

## DNS-Fehler beim Anwendungsbuild

Der anschließende Nutzer-Build erreicht `uv sync` im Migrationsimage, scheitert aber beim Auflösen von `files.pythonhosted.org`. Damit ist für diesen Versuch ein tatsächlicher DNS-Fehler im Docker-Build belegt; weder ein Versionskonflikt noch ein HTTP-404 wurde gemeldet. Die Host-Installation war laut vorherigem Nutzerlauf erfolgreich. Daraus ergibt sich der Ansatz, die Linux-Builds optional über das Hostnetzwerk auszuführen; ein erfolgreicher Download ist dadurch noch nicht nachgewiesen.

Die drei Compose-Builds verwenden jetzt `NORIS_BUILD_NETWORK` mit Default `default`. `NORIS_BUILD_NETWORK=host make dev-up` aktiviert den dokumentierten Docker-Build-Netzwerkmodus `host` für die `RUN`-Schritte. Laufzeit-Netzwerke, Ports, Zugangsdaten, TLS-Prüfung und Lockfiles bleiben bei dieser Korrektur erhalten. Globale Docker-/DNS-Konfigurationen wurden nicht verändert.

Basis- und Entwicklungs-Konfiguration wurden jeweils mit `default` und `host` validiert. Der aufgelöste Compose-Inhalt bestätigt die Einstellung für Migration, Backend und Frontend sowie die unveränderte Dienst-Netzwerkkonfiguration. Ein tatsächlicher Docker-Build kann in der Agent-Umgebung weiterhin wegen des gesperrten Daemon-Zugriffs nicht ausgeführt werden. Unit-Tests wurden für diese ausschließlich Compose- und Dokumentationsänderung nicht wiederholt.

## Verbindungs-Timeout beim Migrationsstart

Die nachgereichten Nutzerlogs belegen einen gestarteten Migrationscontainer und die erfolgreiche Initialisierung von PostgreSQL 18.6 einschließlich `CREATE ROLE`, Grants und anschließendem Lauschen auf IPv4/IPv6-Port 5432. Die Migration scheitert beim Verbindungsaufbau mit `psycopg.errors.ConnectionTimeout`. Damit sind Datenbankinitialisierung und gestarteter Server für diesen Nutzerlauf belegt; eine erfolgreiche Migration oder die Ursache des Verbindungs-Timeouts ist weiterhin nicht nachgewiesen. Die Ergebnisse des DNS-/TCP-Tests aus dem Migrationscontainer stehen noch aus.

Ein zusätzlicher Fehler im Startablauf wurde korrigiert: Compose und der PostgreSQL-Service in GitHub Actions prüfen jetzt ausdrücklich TCP auf `127.0.0.1:5432`. Der bisherige Unix-Socket-Check konnte bereits den temporären Server während der Initialisierung als bereit markieren. Die Korrektur verhindert diese verfrühte Freigabe; sie bestätigt oder behebt nicht automatisch den gemeldeten Netzwerk-Timeout. Das Verhalten des temporären Servers ist im [offiziellen PostgreSQL-Image-Entrypoint](https://github.com/docker-library/postgres/blob/master/docker-entrypoint.sh#L264) dokumentiert.

Nach der Korrektur: **19 Backend-Unit-/Contract-Tests bestanden in 0,74 s**, Ruff-Lint bestanden. Die vier Compose-Konfigurationen (Basis/Entwicklung jeweils mit Build-Netzwerk `default`/`host`) sind gültig und enthalten den TCP-Healthcheck sowie die unveränderte Abhängigkeit der Migration vom gesunden PostgreSQL-Service. Das CI-YAML ist gültig und verwendet ebenfalls den TCP-Check; actionlint und Remote-CI wurden nicht ausgeführt. Die README enthält einen Diagnosebefehl für die wirksame Migrationsadresse, DNS und TCP ohne Passwortausgabe. Ein erfolgreicher erneuter Containerstart bleibt mangels Docker-Daemon-Zugriff hier offen. Frontend-Code, Lockfiles, Datenvolumes und Firewall-Konfigurationen wurden nicht geändert; Etappe 1 wurde nicht begonnen.

Auf Wunsch des Nutzers wurde der Verbindungstest direkt versucht. Die Sandbox verweigert den Docker-Daemon-Zugriff weiterhin mit `connect: operation not permitted`, bevor ein Diagnosecontainer gestartet wird. Damit wurden weder DNS noch TCP im tatsächlichen Container geprüft.

Damit kein mehrzeiliger Code kopiert werden muss, führt jetzt `make db-diagnose` das Skript `backend/scripts/check_database.py` über stdin im bereits gebauten Migrationsimage aus. Der Befehl prüft die wirksame Migrationsadresse, IPv4-/IPv6-DNS-Auflösung, TCP mit fünf Sekunden Timeout sowie die PostgreSQL-Anmeldung mit `SELECT 1` und fünf Sekunden Verbindungstimeout. Er führt keine Migration und keinen Image-Build aus; Treiberfehler werden ausschließlich als Fehlerklasse ausgegeben, damit auch fehlerhafte Anmeldungen keine Passwörter protokollieren.

Mit der Diagnosehilfe bestehen **26 Backend-Unit-/Contract-Tests in 0,68 s**. Die sieben neuen Fälle prüfen das Migrationsziel und die reine Leseabfrage, DNS-Fehler, TCP-Timeout, verweigerte TCP-Verbindung, Datenbankfehler, Datenbank-Timeout und die Redaktion ungültiger Konfiguration. Ruff-Lint und die Formatprüfung aller **23 Python-Dateien** bestehen. Die Argumente und stdin-Übergabe des Make-Ziels wurden mit einem isolierten Compose-Stub geprüft; diese Prüfung ersetzt keinen Docker-Lauf. Die aktuelle Ursache des Nutzer-Timeouts bleibt bis zur Diagnose in dessen Terminal offen.

## Docker-Bridge und Host-Firewall

Der Nutzerlauf von `make db-diagnose` zeigt das korrekte Ziel `postgres:5432/noris_dev`, erfolgreiche DNS-Auflösung auf `172.21.0.2` und anschließend `TCP: FEHLER (TimeoutError)`. Damit ist die TCP-Unerreichbarkeit aus dem Diagnosecontainer belegt; eine Datenbankanmeldung wurde in diesem Lauf nicht versucht.

Lesbar sind die Host-Dateien unter `/etc`: `/etc/nftables.conf` definiert eine `inet filter forward`-Chain mit `policy drop` und Freigaben ausschließlich für Ethernet/WLAN und LXD. `nftables.service` ist beim Boot aktiviert und seine Invocation-Markierung vom 5. Oktober ist vorhanden. Diese Konfiguration ist eine konkrete Erklärung für den beobachteten Timeout, falls die Chain weiterhin so aktiv ist. Die aktuell geladenen Regeln sind hier wegen `Operation not permitted` bei nft-/iptables-/Netlink-Zugriff nicht prüfbar. Die lesbaren sysctls zeigen IPv4-Forwarding aktiv; UFW ist laut Konfiguration deaktiviert. Daraus folgt keine Bestätigung der gesamten aktiven Firewall.

`sudo make network-repair` ist als konkrete Korrektur für diese Host-Konfiguration vorbereitet. Das Skript prüft vor jeder Änderung die aktive Chain und ihre Drop-Policy, den Projekteigentümer und Bridge-Treiber des Docker-Netzwerks, erlaubte Container-Kommunikation, den Bridge-Namen sowie PostgreSQL-TCP auf Loopback. Es validiert die nftables-Regel mit `nft --check`, bevor es genau eine kommentierte Freigabe für **denselben Projekt-Bridge-Namen als Ein- und Ausgangsinterface** einfügt. Der Aufruf ist idempotent. Es ändert weder globale Policies noch Docker-Regeln oder Dateien unter `/etc`; die Regel ist eine Laufzeitänderung bis zum Neustart/Firewall-Reload. README dokumentiert Voraussetzungen, erneute Ausführung nach Netzwerk-Neuerstellung und gezieltes Entfernen über den nftables-Handle.

Nach Ergänzung bestehen **36 Backend-Unit-/Contract-Tests in 2,34 s**, Ruff-Lint und Formatprüfung aller **24 Python-Dateien**. Die zehn neuen Fälle verwenden isolierte Docker-/nft-/id-Stubs und prüfen die Regelbegrenzung auf die Projekt-Bridge, die Syntaxprüfung vor Anwendung, fehlende Root-Rechte, unerwartete aktive Policy, fremden Projekteigentümer, ungeeigneten Netzwerktreiber, deaktivierte Container-Kommunikation, ungültigen Bridge-Namen, fehlgeschlagene Syntaxprüfung, fehlende PostgreSQL-Bereitschaft und die Wiederholbarkeit ohne doppelte Regel. Shell-Syntaxprüfung und Make-Zielprüfung bestehen. Der eigentliche Firewall-Eingriff wurde vom Agenten nicht ausgeführt; eine reale nftables-Syntaxprüfung und erfolgreiche TCP-/Migrationsprüfung bleiben bis zum Nutzerlauf offen. Etappe 1 wurde nicht begonnen.

## Dauerhafte Firewall-Regel mit festem Bridge-Namen

Für die gewünschte dauerhafte Freigabe verwendet `compose.yaml` jetzt ein explizites Default-Netzwerk mit Bridge-Treiber und `com.docker.network.bridge.name: noris-chat0`. Der Docker-Netzwerkname bleibt `noris-ai-chat_default`. Eine Firewall-Regel über `iifname` und `oifname` kann so auch nach einer Neuerstellung des Netzwerks dasselbe Projektinterface treffen. Die Regelvorlage `infrastructure/nftables/noris-ai-chat-forward.nft` ist zum Einfügen in die vorhandene Host-Chain bestimmt; sie wird nicht automatisch geladen.

Die README beschreibt das Sichern und Bearbeiten von `/etc/nftables.conf`, das Ergänzen der markierten Regel direkt nach `policy drop;`, die Prüfung mit `nft --check`, das Aktivieren des Boot-Dienstes und die einmalige Netzwerk-Neuerstellung mit erhaltenem PostgreSQL-Datenvolume. Die sofortige Freigabe verwendet weiterhin das geprüfte `network-repair`-Skript. Ein Reload der vorhandenen Host-Datei würde durch ihr `flush ruleset` auch Docker-Regeln löschen und ist deshalb kein Teil der Anleitung. `/etc/nftables.conf` und der nftables-Dienst wurden vom Agenten nicht verändert.

Nach dieser Änderung bestehen **38 Backend-Unit-/Contract-Tests in 3,78 s**, Ruff-Lint und Formatprüfung aller **24 Python-Dateien**. Zwei zusätzliche Fälle prüfen den konfigurierten Namen für beide Interface-Matches und die Erkennung einer bereits vorhandenen Regel für den festen Namen. Die vier Compose-Konfigurationen (Basis/Entwicklung jeweils mit Build-Netzwerk `default`/`host`) sind gültig, enthalten `noris-chat0` und ordnen weiterhin alle fünf Dienste dem gemeinsamen Default-Netzwerk zu. Tatsächliche Bridge-Erstellung, Host-Konfigurationsänderung, nftables-Laufzeit-/Boot-Prüfung und erneute DB-Migration sind hier weiterhin gesperrt und werden nicht als erfolgreich ausgegeben. Frontend-Code und Lockfiles wurden nicht geändert; Etappe 1 wurde nicht begonnen.
