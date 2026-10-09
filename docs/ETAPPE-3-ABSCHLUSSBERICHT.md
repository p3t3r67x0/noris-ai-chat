# Etappe 3 – Abschlussbericht

Stand: 2026-10-09. Bewertung des vollständigen PR-Stacks gegenüber `main`.
`PASS` bedeutet ausgeführt und erfolgreich beziehungsweise implementiert und
geprüft; `FAIL` fehlgeschlagen; `BLOCKED` extern verhindert; `NOT TESTED` nicht
geprüft. Der Bericht enthält keine behauptete öffentliche Produktivfreigabe.

## Umsetzung

| Bereich | Status | Ergebnis |
| --- | --- | --- |
| 1. Architektur | PASS | PostgreSQL als maßgeblicher Chatbestand im WebSocket-Modus, bestehender `useChat`-State und Provider-Gateway; [Audit/Architektur](ETAPPE-3-ARCHITEKTUR.md) |
| 2. Schema | PASS | Sechs normalisierte Tabellen; Branches über Parent-Beziehungen und aktive Blatt-ID, keine redundante Branch-Tabelle; UUIDs, Composite-FKs, Indizes, Sequenz-Unique-Constraint |
| 3. Alembic | PASS | 0002 Persistenz/DML-Grants, 0003 immutable Topologie/lange Texte, 0004 unvollständige Antworten und Fortsetzungsvarianten; Up/Down/Up, Drift und Transaktionsrollback auf PostgreSQL 18.6 geprüft |
| 4. REST | PASS | Owner-begrenzte Conversation CRUD, Nachrichtenlesen, Entwürfe, Präferenzen und atomarer Import; Versionskonflikte serverseitig; Vertrag in [OpenAPI](api/openapi.json) |
| 5. WebSocket | PASS | Bidirektionale Generate/Cancel/Resume/Ping-Befehle und Streaming-/Titel-/Statusereignisse; [Vertrag v1](WEBSOCKET-CHAT-V1.md) und [JSON-Schema](websocket/chat-v1.json) |
| 6. Authentifizierung | PASS | Expliziter Single-Owner-Modus; Basic-Anwendungszugang, einmalige 60-s-Tickets im Subprotokoll, Origin/Host-Prüfung, WSS-Pflicht in production; keine Client-Owner-IDs oder Provider-Keys |
| 7. Reconnect | PASS | Bounded Backoff, idempotenter Annahmeretry, gesperrtes Replay/Live-Subscribe, Snapshot-Ersatz, monotone Sequenzen; Disconnect-Grace 60 s, danach interrupted; Startup-Recovery |
| 8. Streaming | PASS | Sichtbare Deltas vor Providerabschluss, Flush 100 ms/512 Zeichen, begrenzte Queues und Sende-Timeouts; Textsnapshot und Replay-Event werden vor Sendung atomar committed |
| 9. Persistenz | PASS | Nachrichten, Varianten, Titel, Entwürfe und aktive Auswahl über Reload erhalten; Provider-Kontext ausschließlich aus validiertem DB-Pfad; gemessene Tokenfelder NULL statt erfundener Usage |
| 10. Browser-Migration | PASS | Expliziter Dialog/Start, Vorabvalidierung, IDs/Bäume/Titel/Entwürfe erhalten, identischer Import übersprungen, Konflikt ohne Teilimport; alte lokale Sicherung unverändert |
| 11. GLM 5.3 | PASS | Katalog-GET bestätigt `vllm/qsu/glm-5-3-flash`; kein erfundener Modellname oder Reasoning-Parameter; Anzeige nur bei aktueller Listung/Freigabe |
| 12. Tests | PASS | Lokale Unit-, Provider-, PostgreSQL-, WS- und persistente Desktop-/Mobile-Browserprüfungen; Details unten |
| 13. CI | PASS | REST/WS-Drift, PostgreSQL 18, lokale Provider, Produktionsbuilds und Caddy-WebSocket-Browserlauf lokal und in GitHub geprüft; aktuelle Remote-Ergebnisse bei den sechs verlinkten PRs |
| 14. Pull Requests | PASS | Sechs abhängige, konfliktfrei reviewbare PRs A–F erstellt, ohne Merge; Links unten |
| 15. Betriebsgrenzen | PASS | Single-Owner/Single-Worker und fehlende öffentliche TLS-/OIDC-Abnahme ausdrücklich dokumentiert |

## Ausgeführte Qualitätsgates

| Prüfung | Status | Nachweis |
| --- | --- | --- |
| `make lint` | PASS | Ruff + Format + ESLint |
| `make typecheck` | PASS | Pyright ohne Fehler, Nuxt/vue-tsc und Tool-TypeScript |
| `make check-api` | PASS | OpenAPI und WS-v1-Schema/TypeScript ohne Drift |
| `make test-unit` | PASS | 241 Backend-Unit-/Contract-/HTTP-Simulatortests, 214 Frontend-Unit-Tests |
| `make test-integration` | PASS | 25 PostgreSQL-/REST-/WebSocket-/Migrationsfälle auf PostgreSQL 18.6 |
| `make build` | PASS | Python-Wheel/SDist und Nuxt-Produktionsbuild |
| WebSocket Desktop/Mobile | PASS | 12 Fälle: Streaming während Generierung, Stop/Retry, Reload/Resume, Import, Titel, Modellwahl, Fortsetzung/Varianten, Archivieren/Restore/Löschen, Overflow |
| Caddy/Compose WebSocket Desktop/Mobile | PASS | Dieselben 12 Fälle gegen isolierten Produktionsstack auf Port 8089; echtes Upgrade über Caddy und PostgreSQL-App-Rolle |
| Bisherige UI-/Screenshot-Suite | PASS | 147 Desktop-/Mobile-Fälle mit unveränderten Assertions und Screenshot-Baselines |
| SSE-Kompatibilitäts-Browser | PASS | 40 Desktop-/Mobile-Fälle gegen den lokalen HTTP-Simulator, einschließlich langer Antworten, Fortsetzung und Katalog-Refresh-Race |
| Compose-Konfigurationen | PASS | production, dev und ausdrücklicher lokaler Testoverride validiert |
| PR A eigenständig | PASS | 6 PostgreSQL-/Schema-/Migrationsfälle im separaten Checkout |
| PR B eigenständig | PASS | 11 PostgreSQL-/REST-/Migrationsfälle und strikte Python-Typprüfung im separaten Checkout |
| Kostenpflichtige Noris-Generierung | NOT TESTED | Nicht freigegeben; keine reale Textgenerierung oder kostenpflichtige CI-Anfrage ausgeführt |
| Öffentliche Domain/HTTPS/WSS | NOT TESTED | Keine Domain-/TLS-Bereitstellung beauftragt; WSS-Policy und Same-Origin-Routing implementiert |

Die CI verwendet ausschließlich synthetische Provider. `compose.test.yaml`
betreibt den Fixture-Provider auf Loopback im Netzwerk-Namespace des Backends;
zusätzliche öffentliche Provider-/Backendports werden nicht geöffnet. Die
Browsertests arbeiten mit dem Produktionsbuild; sämtliche bestehenden
Screenshot-Baselines und Assertions bleiben erhalten.

Ein zusätzlicher CI-Lauf deckte einen zuvor bestehenden Klickverlust bei
Fortsetzung während eines laufenden Modellkatalog-Refreshs auf. Fortsetzung
und Regeneration warten nun auf diesen Refresh und prüfen anschließend die
aktuelle Freigabe. Ein deterministischer Desktop-/Mobile-Regressionstest hält
die Katalogantwort zurück und prüft die Verarbeitung des Klicks nach Freigabe.

Der lokale neue Smoke-Netzwerkbridge wurde zunächst durch die vorhandene
Host-Firewall blockiert. Für den erfolgreichen Lauf wurden ausschließlich
Testcontainer unter eindeutigen `stage3-*`-Aliasen an die bereits freigegebene
Projektbridge angeschlossen. Firewall, vorhandene Dienste und Datenvolumes
wurden nicht verändert. Der Teststack besitzt ein eigenes PostgreSQL-Volume.

## Tatsächliche GLM-Version

Nur `GET https://ai.noris.de/v1/models` am 2026-10-09, HTTP 200:
`vllm/qsu/glm-5-3-flash`, Anzeigename `Glm5.3Flash`, `is_ready=true`,
`is_free=false`, Textinput/-output, Kontext 1.048.576 Token, katalogisiertes
Ausgabelimit beziehungsweise `max_tokens` 1–1.048.576, `streaming=true`,
`temperature` 0–2, `top_p` 0–1, höchstens vier Stop-Sequenzen, DE-Rechenzentrum.
Die Anwendung begrenzt die Ausgabe weiterhin konservativ auf 8192 Token.
Reasoning-Fähigkeit bleibt UNKNOWN; der Katalog dokumentiert keinen
Reasoning-Parameter. Der bestehende Noris-Adapter wird unverändert verwendet.
Dokumentationsreferenz: [Noris Chat-Completions](https://noris.cloud/nai/api/chat-completions/).

## Wiederherstellung und Grenzen

Die erhaltene Browser-Sicherung `noris-ai:chat:v1` bleibt im Mock-Modus lesbar;
der PostgreSQL-Modus überschreibt sie nicht. Der separate Cache und
unbestätigte Offline-Entwürfe ersetzen keine persistierten Nachrichten oder
aktiven Pfade. Import ist ausdrücklich manuell und auf 8 MiB beschränkt.
Bei Konflikten bleibt der komplette neue Import aus; identische Wiederholung
ändert keine später serverseitig bearbeiteten Entwürfe.

Eine DB-Sicherung ist vor freigegebenen Downgrades erforderlich. Der Downgrade
von 0002 entfernt die neu angelegten Tabellen; er wurde ausschließlich auf
wegwerfbaren Testdatenbanken ausgeführt. Für Code-Rollback die DB erhalten.
`docker compose down` erhält Volumes; kein `down --volumes` wurde verwendet.

Genau ein Backend-Worker wird unterstützt. Aktive Jobs, Tickets und die
bestehenden Rate-/Tokenbudgets sind prozesslokal; mehrere Worker oder Replicas
benötigen verteilte Admission, Tickets und Pub/Sub. HTTP Basic ist ein geteilter
Single-Owner-Zugang. OIDC-Multi-User/RLS und öffentliche TLS-Abnahme sind nicht
implementiert. Stream-Events werden sieben Tage aufbewahrt; finale Texte und
Generierungsdatensätze bleiben bestehen. Ein Crash kann ausschließlich noch
nicht bestätigte Providerdeltas verlieren; bereits gesendeter Text ist vorher
committed. Eine abgebrochene Generierung wird niemals als completed ausgegeben.

## Pull Requests

Abhängigkeiten: A → B → C → D → E → F. Keine eigenmächtigen Merges.

| PR | Inhalt | Basis |
| --- | --- | --- |
| [A – #28](https://github.com/p3t3r67x0/noris-ai-chat/pull/28) | PostgreSQL-Schema und Migrationen | main |
| [B – #29](https://github.com/p3t3r67x0/noris-ai-chat/pull/29) | Repository, REST und GLM-5.3-Flash-Registry | A |
| [C – #30](https://github.com/p3t3r67x0/noris-ai-chat/pull/30) | Persistentes WebSocket-Gateway und Replay | B |
| [D – #31](https://github.com/p3t3r67x0/noris-ai-chat/pull/31) | Frontendtransport und Backend-Synchronisierung | C |
| [E – #32](https://github.com/p3t3r67x0/noris-ai-chat/pull/32) | Ausdrücklicher Browser-Import | D |
| [F – #33](https://github.com/p3t3r67x0/noris-ai-chat/pull/33) | Browser/Compose/CI und Abschlussdokumentation | E |
