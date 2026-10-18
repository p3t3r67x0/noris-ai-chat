# P0/A1: Chat-Suche

Stand: 18.10.2026. Ausgangspunkt ist `1337dc863fa766018178f9c42be1cd6c28bdcf3c`.
Geprüft wurden die bestehende Suche sowie F02/A1 aus dem
[Feature-Audit](https://github.com/p3t3r67x0/noris-ai-chat/blob/067304d179a582da9d9d9be56d54a7fa39cefcc4/docs/OPENWEBUI-FEATURE-GAP.md)
und der [Roadmap](https://github.com/p3t3r67x0/noris-ai-chat/blob/067304d179a582da9d9d9be56d54a7fa39cefcc4/docs/NORIS-DEVELOPMENT-ROADMAP.md).
Die Auditdokumentation wird unabhängig in PR #95 geführt.

## Befund und Ergebnis

Die Ausgangsversion suchte den gesamten kleingeschriebenen Suchtext als einen
Substring in Titel oder Nachricht. Archiv- und Pinzustände sowie seekbasierte
Pagination waren serverseitig bereits vorhanden. Der Dialog bot diese Filter
nicht an und sortierte Serverergebnisse nochmals nach Chataktivität.

A1 erweitert denselben Nuxt-/REST-/Service-/SQLAlchemy-/PostgreSQL-Pfad. Jede
Suchkomponente bleibt in der vorhandenen Architektur; es gibt weder einen
Suchdienst noch neue Paketabhängigkeiten. Chatdaten, Nachrichtenzweige,
Streaming, Entwürfe und Varianten verwenden weiterhin die bestehenden Modelle.

| Anforderung | Umsetzung / Codebeleg |
| --- | --- |
| Wort-AND über Titel und Nachrichten | `backend/src/noris_ai/chat/search.py`: Jeder Term muss im Titel oder in mindestens einer gespeicherten User-/Assistantnachricht vorkommen; verschiedene Terme dürfen verschiedene Nachrichten und Zweige treffen |
| Phrasen zuerst | `chat/pagination.py`: Zusammenhängende Phrase in einem Titel oder einer Nachricht vor den übrigen AND-Treffern; innerhalb beider Gruppen `updated_at DESC, id DESC` |
| Archiv und Pins | `api/v1/conversations.py`, `chat/schemas.py`, `ChatSearchDialog.vue`: unabhängig kombinierbare Status- und Pinfilter, auch ohne Suchtext |
| Cursor und Snippets | `chat/cursors.py`, `chat/pagination.py`, `chat/service.py`: Scopebindung, Rangwechsel und eine gebündelte Snippetauswahl pro Seite |
| Dialog und Chat-UX | `useConversationSearch.ts`: Debounce, Abbruch veralteter Anfragen, Cursorreset bei Filterwechsel; Serverreihenfolge bleibt erhalten |
| Archivtreffer auswählen | `ChatWorkspace.vue`, `pages/settings/archived.vue`: vorhandene Archivverwaltung mit gezielt fokussierter Wiederherstellen-Aktion; keine automatische Wiederherstellung, aktiver Entwurf bleibt erhalten |
| Unicode und Hervorhebung | `chat/search.py`, `lib/chat/searchCasefold.ts`, `searchHighlight.ts`: gemeinsame Foldregeln und sichere Textsegmente mit Originalgraphemen |
| Datenbank | Migration `0018_chat_search`, `chat/models.py`: zwei additive funktionale GIN-Trigrammindizes |

## Suchvertrag

1. Maximal 200 Unicode-Codepoints vor Normalisierung, höchstens 32 verschiedene
   Terme, kein NUL. Ungültige API-Abfragen liefern 422. Unicode `White_Space`
   trennt Terme; aufeinanderfolgende Trennzeichen werden für die Suchphrase zu
   einem ASCII-Leerzeichen zusammengezogen. Zero Width Space gehört nicht dazu.
2. Vergleich: NFC → vollständiges, sprachunabhängiges Unicode-Casefolding → NFC.
   Backend: Python 3.14 / Unicode 16 und PostgreSQL 18 `PG_UNICODE_FAST`.
   Frontend: vollständige Unicode-16-Foldtabelle mit 1.557 Einträgen
   in `searchCasefold.ts`, unabhängig von der Kleinschreibungstabelle des Browsers.
   NFC setzt einen aktuellen Browser mit Unicode-16-Unterstützung voraus.
   Bei einem Unicode-/Runtimeupgrade diese Regeln und
   die gemeinsamen Testvektoren erneut prüfen.
3. Substrings bleiben erlaubt: `log` findet `login`. `STRASSE` findet `Straße`,
   zusammengesetztes `Ä` findet `A` plus kombinierendes Trema. Akzente bleiben
   relevant: `apfel` findet `Äpfel` nicht. Es gibt kein Stemming, Transliteration
   oder NFKC-Kompatibilitätsnormalisierung. Emoji und Interpunktion bleiben
   literal; `%`, `_` und Backslash werden für SQL-LIKE maskiert. `v0.9.1` ist
   ein einzelner Term, Anführungszeichen besitzen keine Operatorsyntax.
4. Alle Terme müssen irgendwo im Chat vorkommen. Die vollständige normalisierte
   Suchphrase wird nur bevorzugt, wenn sie zusammenhängend innerhalb eines
   Feldes vorkommt. Dokumenttext, Dateinamen, Toolresultate und nicht gespeicherte
   Providerkontexte werden nicht zusätzlich durchsucht.
5. Eine leere oder ausschließlich aus White_Space bestehende Abfrage listet
   entsprechend den Filtern, ohne Snippets. Angeheftete Listen ohne Suchtext
   behalten ihre vorhandene Sortierung nach Pinzeit; Textsuchen verwenden die
   oben definierte Phrasen-/Aktivitätsreihenfolge.

Referenz sind die [Suchbeschreibung von Open WebUI](https://docs.openwebui.com/features/chat-conversations/chat-features/history-search/)
und die [Implementierung im Tag v0.12.3](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/models/chats.py).
Übernommen werden verteiltes AND, Substrings und Phrasenbevorzugung. Noris legt
Unicode-Whitespace und literale Interpunktion ausdrücklich fest; die Referenz
verwendet für die Wortzerlegung englische Buchstaben und Ziffern. Archiv und
Pins werden in Noris über Controls/API-Parameter bedient. Filterpräfixe im
Suchtext, Tags, Ordner, Freigaben und agentische Historytools sind nicht A1.

## API, Pagination und Sicherheit

`GET /api/v1/conversations?q=docker%20healthcheck&archiveFilter=archived&pinned=false&limit=50`

| Parameter | Vertrag |
| --- | --- |
| `archiveFilter` | `active`, `archived` oder `all`; der Dialog startet mit `active` |
| `pinned` | weglassen = beide; `true` = angeheftet; `false` = nicht angeheftet |
| `limit`, `cursor` | bestehende Grenzen 1–100, Standard 50; Cursor nur für genau denselben Suchscope gültig |
| `archived`, `archiveOnly` | bestehende Clients bleiben unterstützt; zusammen mit explizitem `archiveFilter` und einem wahren Legacyflag: 422 |

Der Legacyaufruf `pinned=true` ohne `archiveFilter` bleibt auf aktive Pins
begrenzt, auch bei `archived=true`. Neue Clients verwenden `archiveFilter` für
orthogonale Kombinationen. `preparedOnly` behält seinen vorhandenen Vertrag.

Cursor v2 bindet Owner, Archiv-/Pinfilter, Vorbereitungsstatus, Legacyverhalten,
SHA-256 der normalisierten Phrase, Rang, Zeitpunkt und UUID. Alte
Konversationscursor werden mit 422 abgelehnt; neu suchen lädt einen gültigen
Cursor. Nachrichten-/Pfadcursor bleiben kompatibel. Cursor sind kein
Berechtigungsnachweis: Jede Abfrage prüft unabhängig Owner und Löschstatus.

Phrasen- und AND-Blöcke sowie Snippets laufen pro Suchrequest in einer
schreibgeschützten Repeatable-Read-Transaktion. Die Snippetabfrage beschränkt
sich auf autorisierte IDs der aktuellen Seite. Auswahl: Phrase, danach erster
passender Suchterm, danach neueste Nachricht/UUID. Titel-only-Treffer erhalten
kein künstliches Nachrichtensnippet. Der Textausschnitt enthält den gesamten
Treffer und Kontext; die bestehende Nachrichten-ID ermöglicht Zweignavigation.

Authentifizierung/Originprüfung bleiben in `chat_access`. Eingaben gehen als
SQLAlchemy-Bindparameter in SQL ein; dynamische Indexnamen kommen ausschließlich
aus festen Migrations-/Modellkonstanten. Der Suchtext wird nicht in Cursor
kopiert. Vue rendert Hervorhebungen als Text und `mark`, ohne `v-html`.
Tests prüfen fremde Owner, fremde Cursor, gelöschte Chats, nichtaktive Zweige,
Injectionpayloads sowie literale LIKE-Sonderzeichen. Der bestehende feste
Single-Owner-Principal wird durch A1 nicht zu einer Mehrbenutzerverwaltung.

## PostgreSQL und Migration

PostgreSQL 18 mit UTF8 und der bereits vorhandenen Extension `pg_trgm` ist
Voraussetzung. Die [Stringfunktionen](https://www.postgresql.org/docs/18/functions-string.html)
liefern Normalisierung und Casefolding; [Trigrammindizes](https://www.postgresql.org/docs/18/pgtrgm.html)
unterstützen literale LIKE-Substrings. Der Indexausdruck entspricht exakt dem
Abfrageausdruck. Ein Integrationstest vergleicht beide über `pg_get_expr`.

Migration 0018 erstellt einen partiellen Titelindex ohne gelöschte Chats und
einen Nachrichtentextindex mit `CREATE INDEX CONCURRENTLY`. Vorhandene Daten
werden nicht umgeschrieben. Unterbrochene ungültige Indizes werden beim Retry
entfernt und neu aufgebaut. Downgrade entfernt nur diese beiden Indizes.
Wie bei vorhandenen Migrationen führt der Betreiber den Migrator mit seinen
bestehenden Rechten aus; A1 verändert keine produktiven Einstellungen.

GIN allein hilft bei häufigen oder sehr kurzen Termen wenig. Die Abfrage nutzt
deshalb eine auf 256 Nachrichten beschränkte Probe je Term: keine
Nachrichtentreffer → Titel prüfen; viele über mindestens 16 Chats verteilte
Treffer → lokale EXISTS-Prüfung; sonst indexierbare Kandidatenunion. Jede
Strategie liefert denselben booleschen Suchvertrag. Phrasen werden in zwei
geordneten Blöcken statt über eine Sortierung des gesamten Trefferkorpus
paginiert. Ein ASCII-Pfad im identischen Index-/Abfrageausdruck spart volle
Unicode-Normalisierung, wenn UTF8-Byte- und Zeichenanzahl gleich sind. Eine
separate Oracleprüfung vergleicht ASCII und Unicode mit Python-Casefolding.

## Reproduzierbarer Benchmark

Das Skript `backend/scripts/benchmark_chat_search.py` akzeptiert ausschließlich
Loopback-PostgreSQL-URLs mit Datenbanknamen `noris_search_benchmark_*_test`.
Es verlangt eine leere, bereits migrierte Datenbank. `--reuse-seed` ist nur für
eigene wiederholte Messungen mit passender Fixtureanzahl/-titeln gedacht.
Es enthält keine Produktionsbereinigung. Indexvergleiche entfernen und
erzeugen ausschließlich die beiden festen Suchindizes in dieser Testdatenbank.

Beispiel aus `backend/`, gegen einen ausdrücklich separat gestarteten lokalen
Testcluster (Port/User anpassen; URL enthält hier keine Credentials):

```sh
createdb -h 127.0.0.1 -p 56483 noris_search_benchmark_a1_final_test
export NORIS_MIGRATION_DATABASE_URL=postgresql+psycopg://127.0.0.1:56483/noris_search_benchmark_a1_final_test
uv run --locked alembic upgrade head
uv run --locked python scripts/benchmark_chat_search.py \
  --database-url "$NORIS_MIGRATION_DATABASE_URL" \
  --conversations 10000 --baseline-repetitions 3 --repetitions 20 \
  --compare-indexes --output ../docs/CHAT-SEARCH-A1-BENCHMARKS.json
```

10.000 Chats, je zehn Nachrichten, 10 % fremde Owner, deterministische Archive,
Pins und gelöschte Chats. Nachrichtentext überwiegend ASCII mit gezielten
Unicode-/Interpunktionsfällen; exakte Dockerphrase alle 125 Chats. Gemessen
wird die authentifizierte ASGI-API einschließlich Datenbank, Snippets und JSON,
ohne Netzwerk/Proxy/Browserdebounce. Ein Client, eine Aufwärmanfrage je Fall;
P50 als Median, P95 nach Nearest Rank. Die JSON-Datei enthält Einzelmessungen,
Hardware, PostgreSQL-Einstellungen und `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)`
der letzten gemessenen Abfragen mit ihren ursprünglichen Bindparametern.
Vorher/nachher bedeutet dieselbe neue Suchsemantik ohne/mit Unicodeindizes,
keinen irreführenden Vergleich mit der früheren einfacheren Phrasensuche.
Zwei Fälle messen zusätzlich die zweite Cursorseite; das Beschaffen des Cursors
liegt dabei vor Aufwärmung und Zeitmessung. Tiefe Seiten und parallele Clients
sind kein Bestandteil dieser Messreihe.

Die [vollständige Messreihe mit Einzelwerten und Queryplänen](CHAT-SEARCH-A1-BENCHMARKS.json)
wurde nach Ende aller anderen eigenen Lasttests erstellt: Intel Core i5-8265U
@ 1,60 GHz, acht logische CPUs, 15,0 GiB RAM, x86_64, PostgreSQL 18.6,
Python 3.14.4; `shared_buffers` 128 MiB, `work_mem` 4 MiB,
`effective_cache_size` 4 GiB, JIT an, maximal zwei parallele Worker pro Gather.
Der Host wurde gemeinsam genutzt; CPU-Takt und fremde Last waren nicht isoliert.

| Fall | Ohne neue Indizes P95 (3 Läufe) | Mit Indizes P50 (20 Läufe) | Mit Indizes P95 (20 Läufe) |
| --- | ---: | ---: | ---: |
| Seltener Nachrichtentreffer | 279,8 ms | 34,0 ms | 47,4 ms |
| `docker healthcheck`, Phrasen/AND | 776,3 ms | 83,5 ms | 113,5 ms |
| Dieselbe Suche, zweite Seite | 691,0 ms | 44,7 ms | 62,4 ms |
| `STRASSE ÄPFEL` | 583,1 ms | 84,8 ms | 99,3 ms |
| Kein Treffer | 120,0 ms | 12,4 ms | 17,2 ms |
| Literales `%_` | 52,8 ms | 52,8 ms | 58,4 ms |
| Kurzer Term `a` | 53,4 ms | 40,2 ms | 67,3 ms |
| Häufiger Term `synthetic` | 42,8 ms | 45,8 ms | 82,9 ms |
| Häufige Phrase `synthetic note` | 78,4 ms | 39,2 ms | 53,9 ms |
| Breites AND `synthetic operations` | 230,9 ms | 334,2 ms | 376,1 ms |
| Breites AND, zweite Seite | 162,6 ms | 297,3 ms | 356,7 ms |
| Archiviert + nicht angeheftet + Text | 867,9 ms | 100,3 ms | 138,3 ms |
| Nur Status-/Pinfilter | 13,7 ms | 10,9 ms | 12,5 ms |

Das Roadmap-Ziel **P95 unter 500 ms wird in allen 13 gemessenen Fällen erreicht**.
Die beiden zusätzlichen Indizes belegen zusammen etwa **9,8 MiB**. Selektive
Pläne verwenden die neuen GIN-Indizes. Breite Trefferlisten profitieren von
lokalen EXISTS-Prüfungen und der Aufteilung in Rangblöcke. Häufige Trigramme
können viele Kandidaten und Rechecks erzeugen; bei breitem AND ist der Lauf mit
GIN hier langsamer als ohne. Indizes sind deshalb keine allgemeine
Beschleunigungsgarantie. Die Vorherwerte mit nur drei Wiederholungen dienen der
Orientierung; für Kapazitätsentscheidungen beide Phasen mit mehr Wiederholungen,
realistischeren Textlängen und konkurrierenden Clients erneut messen.

## Prüfungen und Reproduktion

Die neuen Backendtests liegen in `tests/unit/test_chat_search.py` und
`tests/integration/test_chat_search.py`. Bestehende Paginationserwartungen
wurden auf AND angepasst, ohne Legacy-Pinregeln zu ändern. Frontendtests prüfen
Foldregeln, Hervorhebung, Serverreihenfolge, Filterwechsel, Abbruch und Reset;
Browserprüfungen ergänzen reale PostgreSQL-Pagination, alte Archivtreffer nach
Reload sowie den lokalen Demomodus. Alle Browserdaten und Referenzbilder sind
synthetisch. Visuelle Toleranzen bleiben unverändert.

Die vorhandenen Repositorybefehle bleiben gültig:

```sh
make lint
make typecheck
make check-api
make test-unit
NORIS_TEST_DATABASE_URL=<separate-test-database-url> make test-integration
make test-e2e
NORIS_DATABASE_URL=<migrated-browser-test-database-url> make test-e2e-websocket
make build
```

Für die gezielte Suchprüfung: im Frontend
`playwright test chat-search.spec.ts chat-search-layout.spec.ts chat-search-streaming.spec.ts`
und im WebSocketconfig `search-a1.spec.ts message-search.spec.ts pagination.spec.ts sidebar-pinning.spec.ts`.
`NORIS_UI_CAPTURE_PHASE` kann Layoutbelege außerhalb versionierter Verzeichnisse
ablegen. Im Backend benötigt der vollständige Proxytest zusätzlich nginx und
`NORIS_TEST_CADDY_BINARY`; beide liefen lokal gegen eigene Testprozesse. Der
Benchmark startet mit deaktiviertem LLM-Provider und erfordert keine Modellaufrufe.

Zusätzlich wurden alle 2.643 Unicode-Codepoints mit verändertem
NFC-/Casefold-Ergebnis zwischen der tatsächlichen Python-Funktion und dem
transpilierten TypeScriptmodul verglichen. Die vollständige Folddatentabelle
wird über alle Unicode-Codepoints mit Python 3.14 / Unicode 16 generiert;
konkrete Mehrzeichen- und Graphemfälle bleiben in den regulären Tests.

Lokale Ergebnisse (isoliertes PostgreSQL 18.6, Python 3.14; abschließende
Frontendprüfungen mit Node 24.22.0):

| Quality Gate | Ergebnis |
| --- | --- |
| Backend Unit/Contract/lokale HTTP-Provider | 1.191 bestanden |
| Vollständige PostgreSQL-Integration inkl. nginx/Caddy und Migrationen | 327 bestanden, keine übersprungen |
| Frontend Vitest | 607 bestanden, 46 Dateien |
| Suchdialog-/Layout-/Streamingbrowser, Desktop und Mobil | 77 bestanden; 19 planmäßige Skips für doppelte explizite Viewportfälle |
| WebSocket-Suche/Pagination/Pins/Archiv | 18 Szenarien geprüft; erster Lauf 17 bestanden, Reader-Anchor im Wiederholungslauf bestanden; sechs fokussierte Fälle zuletzt vollständig grün |
| ESLint, Nuxt/vue-tsc App und Tests, TypeScript Tools | bestanden |
| Ruff und Pyright strict | bestanden, keine Typfehler |
| Generierter API-Vertrag | aktuell, `--check` bestanden |
| Nuxt-Produktionsbuild | bestanden |
| Backend Wheel/sdist und Paketinhalt | bestanden |
| Unicode-Python/TypeScript-Abgleich | 2.643 Vektoren bestanden |

Im ersten parallel belasteten Browserlauf gab es einen mobilen
Reader-Anchor-Fehler und vier Desktop-Viewport-Timeouts. Die betroffenen
WebSocketfälle bestanden im gezielten Wiederholungslauf (sechs Desktop-/Mobilefälle,
einschließlich aller vier neuen Suchtests mit Archiv-Reload). Für den
Suchdialog wurde zusätzlich der komplette Lauf mit einem Worker und Node 24
wiederholt. Timeouts, Assertions und Screenshottoleranzen wurden nicht erhöht.

Bestehende Buildwarnungen aus Nuxt-UI-Abhängigkeiten zu BigInt/`es2019`,
`modelModifiers` und Bundler-Timings sind weiterhin sichtbar. Compose-Smoke,
die gesamte sonstige Browsersuite sowie Firefox/Safari/Screenreaderabnahme
wurden für A1 nicht lokal ausgeführt; dafür wird kein grünes Ergebnis behauptet.
Remote-CI bleibt vor einer Freigabe separat zu prüfen; es erfolgt kein
automatischer Merge.

## Grenzen

- Kein Snapshot über mehrere HTTP-Seiten: Gleichzeitige Titeländerungen,
  Archiv-/Pinänderungen oder neue Nachrichten können zwischen Seiten die
  Trefferposition ändern. Pro Request sind Liste und Snippets konsistent.
- Eine Phrase normalisiert Leerraum der Abfrage, nicht den gespeicherten Text.
  Unterschiedliche Leerraumfolgen im Dokument können deshalb AND statt Phrase
  treffen. Akzente, Satzzeichen und Skripte folgen dem veröffentlichten Vertrag.
- Lokal-/Demomodus sucht nur die lokal vorhandenen Nachrichten. Persistenter
  Modus verwendet die vollständige serverseitige Datenbasis.
- Indizes kosten Speicher und Schreibarbeit, auch für archivierte Nachrichten.
  Häufige Terme, fehlende Phrasen, sehr lange Unicodeantworten, große Owner und
  konkurrierende Suchen benötigen eigene Lastmessungen. Der synthetische
  Einzelclientlauf belegt keine allgemeine Latenzgarantie.
- Archivtreffer öffnen die Archivverwaltung; direkte schreibbare Archivchats
  und automatische Wiederherstellung sind nicht Teil des bestehenden UX.
