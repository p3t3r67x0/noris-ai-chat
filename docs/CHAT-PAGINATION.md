# Chat-Pagination

## Bestandsaufnahme auf main (e2c9a8f)

`ChatBackend.load()` lädt derzeit alle Konversationsmetadaten, alle Entwürfe und anschließend mit einem unbegrenzten `Promise.all` sämtliche Nachrichtenbäume. Die Sidebar, Archivansicht und Titelsuche arbeiten ausschließlich mit diesen lokalen Daten. Damit wachsen Startkosten und Speicherbedarf mit dem gesamten Datenbestand.

Der einzige Chat-State liegt in `useChat`: immutable Nachrichten mit Parent-IDs, aktive Leaf-ID und bevorzugte Leaves. `visiblePath` setzt bisher voraus, dass sämtliche Eltern geladen sind. Varianten werden aus geladenen Geschwistern berechnet. Deshalb darf eine paginierte Seite nicht als vollständiger Baum behandelt werden. Bearbeiten und Regenerieren erzeugen Geschwister; ein Variantenwechsel muss auch noch ungeladene Nachfahren auflösen können.

`useChatBackend` verbindet diesen State mit REST, persistierten Entwürfen und WebSocket-Metadaten. Sein bisheriger Metadaten-Callback lädt bei einer unbekannten Leaf den gesamten Nachrichtenbaum nach. Dies muss auf die aktive Ansicht begrenzt werden. WebSocket-Deltas und Snapshots sind generation- und nachrichtenbezogen; dieser Vertrag bleibt bestehen. Laufende Generierungen und ungesicherte Änderungen müssen vor Cache-Verdrängung geschützt werden.

Im Backend laden sowohl `active_path` als auch `begin_generation` bisher alle Nachrichten einer Unterhaltung und rekonstruieren den ausgewählten Pfad in Python. Der Provider braucht den vollständigen ausgewählten Pfad, während die UI nur einen Abschnitt benötigt. Diese zwei Anforderungen werden getrennt. Ownership, immutable Parent-Beziehungen, optimistische Versionierung und der bestehende Provider-Gateway bleiben verbindlich.

Die vorhandenen Indizes enthalten keine vollständigen deterministischen Sortierschlüssel. Listen werden bisher unbeschränkt ausgegeben. `archived=true` bedeutet weiterhin **einschließlich** archivierter Chats. Die neue Sortierung verwendet `updated_at DESC, id DESC`, passend zur bestehenden Sidebar und ihren Titel-/Aktivitätsupdates.

Risiken: fehlende Eltern bei Teilpfaden; falsche Variantenzahl bei ungeladenen Geschwistern; verspätete Antworten nach einem Chatwechsel; Überschreiben von Streaming-Text durch alte REST-Snapshots; Entwürfe außerhalb der ersten Seite; aktive Unterhaltung außerhalb der ersten Seite; lokale Suche über unvollständige Metadaten. Die Implementierung und Tests adressieren diese Abhängigkeiten ausdrücklich.

## Datenmodell und Indexmigration

Keine neuen Tabellen. PostgreSQL bleibt die maßgebliche Quelle für Metadaten, den immutable Nachrichtenbaum, aktive Leaf, Generationen, Titel, Entwürfe und Präferenzen. Cache-Verdrängung löscht keine Datenbankzeilen.

Migration `0005_chat_pagination` ergänzt fünf Indizes: zwei partielle B-Tree-Indizes auf `(owner_id, updated_at DESC, id DESC)` (nicht gelöscht / zusätzlich nicht archiviert), einen Nachrichtenindex auf `(conversation_id, created_at DESC, id DESC)`, einen Geschwisterindex auf `(conversation_id, parent_message_id, role, created_at, id)` und einen partiellen GIN-Trigrammindex auf `lower(title)` für nicht gelöschte Chats. `last_message_at` bleibt als Metadatum erhalten; es ist hier kein Sortierschlüssel, damit die vorhandene Aktivitäts-/Titel-Sortierung erhalten bleibt.

Die Indizes werden mit `CREATE INDEX CONCURRENTLY` erstellt. Wiederanlauf repariert ausschließlich ungültige Indizes dieser Migration. `pg_trgm` ist eine vertrauenswürdige Erweiterung; der Migrationsbenutzer benötigt CREATE auf der Datenbank. Der Anwendungsbenutzer erhält keine DDL-Rechte. Downgrade entfernt ausschließlich die neuen Indizes; Tabellen, Nachrichten, Entwürfe und die möglicherweise anderweitig genutzte Erweiterung bleiben erhalten. Die Rollback- und Alembic-Drift-Prüfungen verwenden ausschließlich ausdrücklich benannte, verwerfbare Testdatenbanken.

SQLAlchemy beschreibt die Operator-Klasse über `postgresql_ops` an einer benannten Expression, entsprechend der [SQLAlchemy-Dokumentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#operator-classes). Das vermeidet einen unprüfbaren Unterschied zwischen ORM-Metadaten und Migration.

## HTTP- und Cursor-Vertrag

| Endpunkt | Verhalten |
| --- | --- |
| `GET /api/v1/conversations` | Default `limit=50`, Maximum 100; `cursor`, `q`, `archived`, `archiveOnly` |
| `GET /api/v1/conversations/{id}` | Gezielte Metadaten, auch außerhalb der ersten Seite |
| `GET /api/v1/conversations/{id}/messages` | Default 50, Maximum 200; chronologische Seek-Pagination, `completeTree=false` |
| `GET /api/v1/conversations/{id}/active-path` | Default 50, Maximum 200; zusammenhängender Abschnitt des ausgewählten Pfades samt Variantenzahlen |
| `GET /api/v1/chat/drafts?keys=__new__&keys={id}` | Gezielte Entwürfe; höchstens 101 Schlüssel pro Anfrage |

Listen liefern zusätzlich `nextCursor` und `hasMore`. Bestehende Felder bleiben erhalten. `archived=true` schließt archivierte Chats weiterhin ein; `archiveOnly=true` dient der eigenen Archivansicht. Ohne Parameter liefert eine Liste künftig höchstens 50 Datensätze. Clients, die vollständige Listen benötigen, müssen bis `nextCursor=null` weiterblättern. Der TypeScript-Generator bildet nun benannte und typisierte Query-/Path-Parameter ab.

Cursor sind kanonisches Base64url ohne Padding über einem strikt validierten JSON-Vertrag, Version 1. Sie enthalten Ressourcentyp und Scope (serverseitiger Besitzer, Filter/Suchtext beziehungsweise Conversation-ID), UUID und bei chronologischen Listen den vollständigen timezone-aware Zeitstempel. Sortierung und Seek-Vergleich erfolgen gemeinsam in PostgreSQL: Conversations `(updated_at,id)` absteigend, Nachrichten `(created_at,id)` absteigend. Die Nachrichten einer einzelnen chronologischen Seite werden aufsteigend ausgegeben, damit `messages.at(-1)` weiterhin die neueste Nachricht dieser Seite bezeichnet. Ältere Seiten werden vorangestellt.

Maximal 2.048 Cursorzeichen; unbekannte Felder, falsche Ressource/Filter/Besitzer, nicht kanonisches Encoding, ungültige UUIDs und Zeitstempel ohne Zeitzone werden abgelehnt. Cursor sind keine Zugangsdaten. Jede Abfrage prüft den serverseitigen Besitzer und nicht gelöschte Conversation erneut. Nachrichten- und Pfadgrenzen werden auf ihre tatsächliche Zugehörigkeit geprüft.

Bei stabilen Daten gibt es weder doppelte noch ausgelassene Datensätze. Seitenübergreifend wird keine MVCC-Snapshot-Sitzung gehalten: Bei gleichzeitigen Aktivitätsupdates können Chats ihre Position verändern. Das Frontend dedupliziert IDs; „Neueste Chats laden“ startet einen neuen Durchlauf. Path-Seiten werden jeweils aus einem konsistenten Repeatable-Read-Snapshot gelesen.

## Pfadabschnitte und Varianten

`active-path` liefert `conversation`, `leafMessageId`, `messages`, `variants`, `boundaryParentId`, `nextCursor` und `hasMore`. Der Abschnitt folgt Parent-Beziehungen, nicht bloß Zeitstempeln. Die zuerst dargestellte Nachricht darf einen noch ungeladenen Parent besitzen. Diese Grenze ist ausdrücklich benannt; die Legacy-Funktion `visiblePath` bleibt ohne eine solche Grenze strikt und erkennt weiterhin fehlende Eltern, fremde Nachrichten und Zyklen.

Weitere Seiten verwenden den Pfad-Cursor. Alternativ kann `beforeMessageId` die schon bekannte Parent-Grenze angeben. Der Server prüft mit einer rekursiven Abfrage, dass sie auf dem aktuell ausgewählten Pfad liegt. Damit bleiben ältere, bereits geladene Abschnitte auch nach einer neuen Generierung weiter paginierbar. Eine alte Leaf im Cursor ergibt nach einem Branch-Wechsel einen Konflikt; fremde oder nicht ausgewählte Grenzen werden verweigert.

`messageId` löst einen Variantenwechsel auf. `preferredLeafId` wird nur verwendet, wenn sie tatsächlich von dieser Nachricht abstammt. Andernfalls folgt eine einzelne rekursive Abfrage jeweils dem neuesten Kind (Zeitstempel, UUID); der gesamte Baum wird nicht geladen. Der Client persistiert die neue Leaf über das bestehende versionierte PATCH, bevor er den aufgelösten Abschnitt präsentiert.

Variantenzusammenfassungen enthalten `messageId`, `total`, den 1-basierten `index` sowie vorherige/nächste Geschwister-ID. Eine Window-Function-Abfrage berechnet alle benötigten Geschwistergruppen gemeinsam. Die UI muss keine Geschwistertexte laden, um Anzahl und Navigation darzustellen. Bearbeiten, Regenerieren und Fortsetzen erzeugen weiterhin immutable Varianten. Ein noch ungeladener Parent beim Regenerieren wird gezielt über eine weitere Pfadseite geladen.

Der Provider erhält unabhängig von der UI-Pagination **alle ausgewählten Vorgänger** über einen rekursiven Repository-Pfad. Nicht ausgewählte Varianten werden ausgeschlossen. Der interne `PersistedChatRequest` erlaubt bis zu 10.001 Datenbank-Nachrichten; der öffentliche SSE-Vertrag behält seine 100-Nachrichten-Grenze. Die bestehenden Kontext-, Größen-, Token-, Budget- und Rate-Limits gelten weiterhin. Überlange Pfade werden ausdrücklich abgelehnt, niemals still abgeschnitten.

## Lazy Loading, Cache und Request-Koordination

Beim Start werden parallel nur die erste Metadatenseite und Nutzerpräferenzen geladen. Die Sidebar kann bereits mit diesen Metadaten rendern. Eine aktive ID außerhalb Seite 1 wird gezielt nachgeladen. Anschließend kommen nur ihr Pfadabschnitt und die Entwürfe für diesen Chat sowie `__new__`. Inaktive Sidebar-Chats erzeugen keine Nachrichtenanfragen.

„Weitere Chats laden“ lädt jeweils eine neue Seite. Ein Loading-Guard verhindert gleichzeitige doppelte Seitenanfragen; IDs werden dedupliziert. Höchstens 500 Sidebar-Zeilen bleiben im aktuellen Listenfenster; danach können weitere ältere Seiten geladen oder über „Neueste Chats laden“ die neuesten wieder geöffnet werden. Auch dieses explizite Neuladen betrifft ausschließlich Metadaten und ersetzt keinen laufenden Nachrichtenstream. Metadaten werden auf ungefähr 600 Einträge begrenzt, zuzüglich geschützter Einträge.

Der Nachrichten-Cache umfasst höchstens zehn geladene Conversations und ein zusätzliches geschätztes 8-MiB-Budget (`2 * content.length + 512` pro Nachricht). LRU-Reihenfolge und 30 Sekunden Gültigkeit koordinieren Wiederöffnen. Aktive Chats, laufende Generierungen, laufende Reads und ungesicherte Entwürfe sind geschützt. Synchronisierte Entwürfe werden mit verdrängten Nachrichtenfenstern freigegeben und beim Wiederöffnen gezielt geladen. Die Messung zeigt für das typische 50-Nachrichten-Fenster einen wesentlich kleineren Gesamt-Heap; zehn solche Fenster bieten Reserve für Navigation. Sehr große Antworten lösen die zusätzliche Byte-Grenze aus. Dies ist ein Arbeitsbudget, keine exakte Heap-Garantie. Explizit nachgeladene Nachrichten der aktiven Unterhaltung dürfen dieses Budget überschreiten.

Es bleibt bei `useChat` als einzigem gerenderten State. `ChatLoadCache` speichert ausschließlich Versions-/Zeit-/Request-Koordination. Reads pro Chat werden dedupliziert, vorherige Ansichts-Reads mit `AbortController` beendet und Ergebnisse an Conversation-ID und Version gebunden. Ein verspätetes Ergebnis wählt keinen Chat aus. Es gibt kein Prefetch über sämtliche Conversations; der normale aktive Read umfasst höchstens Pfad und Entwurf parallel. Ein Abschluss-Read für eine inzwischen inaktive Generierung ist davon getrennt und darf den aktiven Read nicht abbrechen. Bei beiden gleichzeitig sind höchstens vier solche Ressourcenrequests offen.

WebSocket-Protokoll, generation-bezogene Sequenzen, Deltas, Stop, Retry, Reconnect und Snapshot-Recovery bleiben erhalten. Titelereignisse aktualisieren nur Metadaten. Wird ein Chat außerhalb der ersten Seite durch ein Live-Update wieder aktuell, erscheint er auch in der Sidebar; seine Nachrichten bleiben erhalten. Ein veränderter aktiver Pfad wird gezielt geladen; ein inaktiver Chat löst dadurch keinen Nachrichten-Read aus. Neue autoritative Abschlussdaten werden in schon geladene Vorfahren eingefügt. Laufende Generierungen bleiben unabhängig von der Sidebar-Navigation geschützt.

LocalStorage enthält im Backend-Modus keine vollständigen Nachrichten-Snapshots mehr. Cache v2 enthält nur bevorzugte Leaves. Der ursprüngliche Browserbestand und der alte Cache bleiben unangetastet. Offline-Entwürfe bleiben separat gesichert, einschließlich noch nicht geladener Chats. Ihr Import wird weiterhin ausdrücklich gestartet. Neue Cache-Daten werden niemals als vollständige Legacy-Bäume geparst.

Scrollpositionen werden im PostgreSQL-Modus als bis zu zehn lokale Nachrichtenanker mit Offset/Follows-Flag gespeichert. Reload kann ausschließlich für den aktiven Chat bis zu 20 ältere Seiten zum gespeicherten Anker laden. Ältere Seiten halten den aktuellen Viewport über die Höhendifferenz; manuelles Scrollen pausiert Following weiterhin. Modellwahl, aktive ID und Entwürfe kommen vom Backend.

## Suche und Fehlerzustände

Suche läuft debounced und abbrechbar über alle autorisierten, nicht archivierten Titel. Der Suchtext wird als wörtlicher, case-insensitiver Teilstring behandelt; `%`, `_` und Backslash sind keine vom Nutzer vorgegebenen SQL-Wildcards. Maximal 50 Treffer pro Seite, mit einem Hinweis zum Eingrenzen bei weiteren Treffern. Die UI filtert diese Ergebnisse nicht erneut über einen unvollständigen lokalen Bestand. Das Archiv hat einen eigenen paginierten Read und Retry.

Loading, Empty, Fehler und Retry sind sichtbar. Fehler bei älteren Nachrichten oder weiteren Metadaten erhalten vorhandene Daten. Ein initialer Fehler löscht weder den Legacy-Bestand noch Offline-Entwürfe. Fehler enthalten ausschließlich die vorhandenen sicheren API-Texte. Der Offline-Modus erlaubt die Wiederherstellung lokaler Entwürfe, aber keine erfundene erfolgreiche Serverpersistenz.

## Reproduzierbare Messungen

Die Rohdaten samt EXPLAIN ANALYZE/BUFFERS liegen in [CHAT-PAGINATION-BENCHMARKS.json](CHAT-PAGINATION-BENCHMARKS.json). PostgreSQL 18.6, Chromium/Playwright 1.63.0, Produktionsbuilds, Loopback. Vorher: unverändertes Frontend von `e2c9a8f` und eine ausschließlich lokale Fixture mit den ursprünglichen unbeschränkten Repository-Reads. Nachher: der implementierte Lazy-Loading-Client. Provider sind deaktiviert. Es gibt keinerlei kostenpflichtige Anfragen.

Datensätze: 100 / 1.000 / 10.000 Conversations. Je ein Verlauf mit 1.000 Nachrichten, zehn mit 100 und die restlichen mit zehn; insgesamt 2.890 / 11.890 / 101.890 Nachrichten. Die Browserzahlen sind Einzelmessungen, API-Latenzen haben 25 Stichproben. Gezählt werden Chat-Datenrequests für Conversations, Nachrichten/Pfade, Präferenzen und Entwürfe; Modelle, Health, Tickets und WebSocket-Frames gehören nicht zu dieser Request-/Byte-Zählung. Parallelität bezeichnet offene Browserrequests von Start bis Abschluss, einschließlich auf eine Verbindung wartender Requests. Parallel laufende lokale Qualitätsprüfungen beeinflussen CPU und Latenzen; Ergebnisse sind keine Produktionsgarantie.

| Chats | Start bis aktiver Verlauf vorher / nachher | Chat-Datenrequests vorher / nachher | Max. offene Requests vorher / nachher | JS-Heap vorher / nachher |
| --- | --- | --- | --- | --- |
| 100 | 5.755 / 1.610 ms | 104 / 5 | 100 / 2 | 155,2 / 28,7 MB |
| 1.000 | 26.594 / 1.514 ms | 1.004 / 5 | 1.000 / 2 | 292,8 / 28,7 MB |
| 10.000 | FAIL / 1.996 ms | 10.003 / 5 | 10.000 / 2 | nicht vergleichbar / 28,7 MB |

Bei 10.000 Conversations scheitert das ursprüngliche Frontend mit `ERR_INSUFFICIENT_RESOURCES` vor dem Rendern; es gibt dafür keine erfundene erfolgreiche Startzeit oder Speichervergleichszahl. Der neue Client rendert bei allen Datensatzgrößen 50 Sidebar-Zeilen und 50 Nachrichten.

| Chats | Sidebar sichtbar vorher / nachher | SQL-Abfragen vorher / nachher | Übertragene Chat-Daten vorher / nachher |
| --- | --- | --- | --- |
| 100 | 5.702 / 1.563 ms | 207 / 10 | 1.557.079 / 35.840 Bytes |
| 1.000 | 26.452 / 1.470 ms | 2.007 / 10 | 4.895.211 / 35.840 Bytes |
| 10.000 | FAIL / 1.917 ms | abgebrochener Lauf / 10 | abgebrochener Lauf / 35.840 Bytes |

Bei 10.000 Chats beträgt die gemessene Median-Latenz für Metadaten 854,5 ms vorher und 9,5 ms nachher; Antwortgröße 3.038.947 versus 15.517 Bytes. Der ursprüngliche Nachrichten-Read für den 1.000-Nachrichten-Chat liefert 565.421 Bytes, das neue 50-Nachrichten-Fenster 35.002 Bytes. Der Nachher-Median dafür beträgt 22,0 ms. Für die selektive Suche sind es 15,5 ms. Die JSON-Datei enthält p95 und die tatsächlichen Query-Pläne. Listen- und Nachrichtenqueries nutzen ihre Seek-Indizes, die rekursive Pfadabfrage indizierte Nachrichten-IDs. Für die Titelsuche wählt PostgreSQL je nach Statistiken und GIN-Zustand zwischen Seq Scan und Trigrammindex; beide beobachteten Pläne sind enthalten.

Reproduktion auf einer **separaten leeren** Datenbank mit Suffix `_test`:

```sh
NORIS_DATABASE_URL="$BENCHMARK_DATABASE_URL" NORIS_MIGRATION_DATABASE_URL="$BENCHMARK_DATABASE_URL" make migrate
PYTHONPATH=backend/src backend/.venv/bin/python backend/scripts/benchmark_chat_pagination.py --database-url "$BENCHMARK_DATABASE_URL" --count 100
# Später --count 1000 und --count 10000; der Seeder ergänzt, ohne Daten zu löschen.
```

API-Fixture in einem eigenen Terminal starten:

```sh
export NORIS_ENVIRONMENT=test NORIS_DATABASE_URL="$BENCHMARK_DATABASE_URL"
export NORIS_LLM_PROVIDER=disabled NORIS_LLM_MODELS='[]'
export NORIS_CHAT_OWNER_ID=00000000-0000-0000-0000-00000000002a
export NORIS_LLM_ACCESS_USERNAME=fixture-user
export NORIS_LLM_ACCESS_PASSWORD=fixture-application-password-never-real
export NORIS_LLM_ALLOWED_ORIGINS='["http://127.0.0.1:8597","http://127.0.0.1:8598"]'
export NORIS_CHAT_WS_ALLOWED_HOSTS='["127.0.0.1:8596","127.0.0.1:8595"]'
PYTHONPATH=backend/src backend/.venv/bin/python -m uvicorn --app-dir backend tests.fixtures.pagination_server:app --host 127.0.0.1 --port 8596
```

Für Vorher-Port 8595 zusätzlich `NORIS_BENCHMARK_LEGACY=1`. Danach das Seed-Skript mit `--output`, `--base-url` und optional `--legacy --measure-only` ausführen. Produktiv gebaute Clients über `scripts/serve-browser-fixture.mjs` auf getrennten Ports starten: nach `NUXT_PUBLIC_CHAT_TRANSPORT=websocket NUXT_PUBLIC_CHAT_WEBSOCKET_URL=ws://127.0.0.1:8596/api/v1/chat/ws pnpm --dir frontend build` aus `frontend/` mit `NORIS_E2E_FRONTEND_PORT=8597 NORIS_E2E_BACKEND_PORT=8596 node ../scripts/serve-browser-fixture.mjs`. Vorher analog mit unverändertem Checkout und den Ports 8598/8595. `.output` jeweils isolieren, damit weitere Builds laufende Browser nicht verändern.

```sh
node frontend/scripts/benchmark-chat-browser.mjs http://127.0.0.1:8597 http://127.0.0.1:8596 after 100 /tmp/after-100.json
```

Das Fixture-Modul verweigert aktive Provider und Datenbanken ohne Test-Suffix. Der Seeder verweigert fremde Datensätze. Benchmarkzugangsdaten sind die bestehenden ausschließlich synthetischen Fixture-Credentials. Keine echten Schlüssel verwenden.

## Prüfungen und bekannte Grenzen

| Prüfung | Status | Ergebnis |
| --- | --- | --- |
| `make lint` | PASS | Ruff, Format und ESLint |
| `make typecheck` | PASS | Pyright, Nuxt/Vue und Tool-Skripte |
| `make check-api` | PASS | OpenAPI und generierte TypeScript-Verträge aktuell |
| `make test-unit` | PASS | 241 Backend-/Vertrags-/Provider- und 224 Frontend-Tests |
| `make test-integration` | PASS | 30 PostgreSQL-/WebSocket-/Migrationsprüfungen |
| `make test-e2e` | PASS | 147 UI-/Screenshot- und 40 SSE-Browsertests |
| `make test-e2e-websocket` | PASS | 18 Desktop-/Mobile-Fälle, einschließlich >1.000 Nachrichten und Varianten |
| `make build` | PASS | Python-Paket und Nuxt-Produktionsbuild |
| Compose-Smoke | PASS | Isolierter Stack, Readiness, Migration 0005 und eingeschränkte DB-Rolle |
| Compose-Produktionsbrowser | PASS | 18 WebSocket- und 147 UI-/Screenshot-Prüfungen über Caddy |
| Synthetische Benchmarks | PASS | 100, 1.000, 10.000 Chats; Vorher-Fehler bei 10.000 ausdrücklich dokumentiert |

Die Integrationstests prüfen 1.002-Nachrichten-Branches und die tatsächliche Weitergabe von 1.003 ausgewählten Nachrichten über WebSocket an den bestehenden lokalen Provider, Cursor-/Ownership-/Archiv-/Suchfälle sowie Index-Rollback mit Datenerhalt und Alembic-Drift. Neue Unit-Tests prüfen deduplizierte Reads, späte Antworten, Cache-Verdrängung, inaktive Generierungsabschlüsse, frühe Eingaben und Offline-Entwürfe. Desktop und Mobile prüfen ältere Seiten, ungeladene Varianten, Titel, Suche, Entwürfe, Stop, Reconnect/Reload und gespeicherte Lesepositionen. Keine bestehenden Assertions wurden abgeschwächt; Screenshot-Baselines bleiben unverändert.

Die bestehenden Foundation-CI- und Compose-Smoke-Jobs erfassen diese Tests automatisch. CI verwendet ausschließlich lokale Provider-Simulatoren und separate PostgreSQL-18-Testdatenbanken. Der konkrete GitHub-Laufstatus ist in den PR-Checks sichtbar.

Bewusste Grenzen: Listen-Cursor sind keine über mehrere HTTP-Aufrufe gehaltenen DB-Snapshots. Sehr kurze Teilstrings können den Trigrammindex nicht sinnvoll nutzen. Die Such-UI fordert das Eingrenzen von mehr als 50 Treffern; die API selbst erlaubt weitere Cursorseiten. Explizites Nachladen der aktiven Unterhaltung wächst mit den angeforderten Seiten, eine Timeline-Virtualisierung ist nicht Teil dieser Änderung. Scroll-Recovery endet nach maximal 20 Seiten. Der Single-Owner-Betrieb und die Single-Process-Generierungsverwaltung aus Etappe 3 bleiben bestehen.
