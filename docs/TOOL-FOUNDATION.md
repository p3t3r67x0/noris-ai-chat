# P1a: Tool-Registry und persistentes Grundschema

Status: implementiert als separater P1a-PR auf `main` bei
`f367e33a02757f6d4c31e072d63632d182699299`. Grundlage ist der gemergte
[Architektur-PR #51](https://github.com/p3t3r67x0/noris-ai-chat/pull/51), insbesondere
[Tool-Architektur](TOOL-ARCHITECTURE.md), [P1a/P1b-Roadmap](FEATURE-ROADMAP.md)
und [Websuche](WEB-SEARCH-DESIGN.md). P1b folgt erst nach Merge von P1a auf
aktualisiertem `main`; kein automatischer Merge oder Deployment.

## Bestand und Wiederverwendung

Der aktuelle Stand enthält bereits Lernmodus, persistente Titelclaims,
Modell-/Reasoningauswahl und die bestehenden Chat-, Upload-, PDF- und
Textreferenzpfade. `ChatSearchDialog` und `useConversationSearch` durchsuchen
Unterhaltungen, keine Webseiten. Eine Toolruntime, Searchprovider oder Quellenfetcher
waren nicht vorhanden. Der LLM-Provideradapter weist native `tool_calls` und
`function_call` weiterhin ab.

Die Implementierung verwendet dieselbe FastAPI-Composition-Root, denselben
`async_sessionmaker`, `db.Base`/SQLAlchemy-Metadaten, `ApiSchema` mit
`strict=True`, `extra=forbid`, `frozen=True` sowie den vorhandenen `ModelDatabase`-
Typ und die UTC-Zeitfunktion aus `ChatRepository`. Owner, Conversation und
Generation bleiben bestehende Chatressourcen. `GenerationManager`,
`LLMGateway.reserve/events/release`, Provideradapter, `AttachmentService`,
WebSocket-v1, SSE und Frontend werden fachlich nicht geändert.

Die uncommittete Arbeit im ursprünglichen Checkout wurde nicht übernommen.
Die Implementierung entstand in einer isolierten Arbeitskopie von `main`.

## Registry und interne Verträge

`tools/registry.py` definiert generische, eingefrorene
`ToolDefinition[InputT, OutputT]` mit Schema-/Tool-ID, Schemaarten, deklarierter
Berechtigung, zulässigen Aufrufarten, Providerbindung, Handler sowie Timeout-,
Retry-, Größen- und Kostenpolicy. Die Registry wird bei App-Erstellung fest
zusammengestellt. Doppelte IDs und widersprüchliche Schemaversionen verhindern
den Start; eine öffentliche Registrierungs-/Importfunktion existiert nicht.

| Fester Vertrag | Eingabe | Ausgabe | Aufrufarten |
| --- | --- | --- | --- |
| `web.search.v1` | `SearchInput`: query, de/en, optional day/month/year, 1–8 Treffer | `SearchResult`: maximal acht typisierte Treffer, Warnungen, Provider-/Konfigurationsversion, Abrufdatum, partial | web_mode, research_step |
| `web.fetch.v1` | `FetchInput`: ausschließlich source_id als UUID | `SourceDocument`: source_id, begrenzter Text, SHA-256, MIME, finale HTTP(S)-URL, Abrufdatum | web_mode, research_step |

Beide Definitionen sind **nicht ausführbar**: `handler=None`, `provider_key=None`,
`cost_policy=disabled`. Registriert bedeutet weder freigegeben noch UI-verfügbar.
Der separat [vorbereitete SearXNG-Provider](SEARXNG-PROVIDER.md) verwendet dieselben
Suchtypen, ohne diese Definitionen oder ihre Ausführbarkeit zu ändern.
`validate_input(payload: bytes, kind)` prüft den erlaubten Aufrufkontext und
verwendet Pydantic-JSONvalidierung. Unbekannte Felder, Typkoercion, doppelte
JSONschlüssel, ungültige Unicode-/JSONdaten und überschrittene Bytegrenzen werden
mit festen Fehlercodes verworfen. Dieselbe Prüfung gilt für Ausgaben.
Fetch akzeptiert keine frei gelieferte URL; spätere Quellen-/SSRFprüfung bleibt P7.

`ToolRunCreate` enthält ausschließlich serverseitig zusammengestellte
Identitäts-/Scope-/Provider-/Deadlinefelder. Der Owner wird separat aus dem
bestehenden Serverzugang übergeben. Es gibt keine neue HTTProute und keinen
neuen WScommand. OpenAPI und WebSocket-v1 bleiben unverändert; interne Schemas
werden nicht als handgepflegte Frontendtypen exportiert.

## Neue Tabellen und Migration

Additive Alembicrevision: `0011_tool_foundation`, Vorgänger
`0010_conversation_learning`. Keine vorhandene Zeile oder Spalte wird verändert;
ein Backfill ist für bislang nicht vorhandene Tooldaten nicht erforderlich.

| Tabelle | Inhalt / Invarianten |
| --- | --- |
| `chat_tool_run` | UUID, owner/conversation/generation, optionaler Parentrun, feste Tool-/Schemaversion, step_key, Aufrufart, begrenzte normalisierte JSONeingabe und Digest, Provider-/Konfigurationssnapshot, Zustand, Versuch, Deadline, Cancel-/Start-/Endzeit, sicherer Fehlercode |
| `chat_tool_result` | Primärschlüssel run_id/result_version, Ausgabeschema, begrenztes JSONresultat, Digest, Erstellzeit; kein Updatepfad und kein UPDATErecht für `noris_app` |
| `chat_tool_approval` | owner/run/input_digest und Provider-/Konfigurationsbindung, Scope, Call-/Decimal-Kostenobergrenze mit Währung, pending/approved/denied/expired, Ablauf-/Entscheidungszeit und eindeutige decision_request_id |

Zusätzliche UNIQUEconstraints auf `chat_conversation(owner_id,id)` und
`chat_generation(owner_id,conversation_id,id)` ermöglichen zusammengesetzte
Fremdschlüssel. Runs können nur ihrem Owner/Chat/Generation zugeordnet werden;
Parents gehören derselben Generation. Approval-FKs binden Owner, Eingabedigest
und Providersnapshot an den konkreten Run. JSONB ist in PostgreSQL auf 64 KiB
Eingabe beziehungsweise 256 KiB Ausgabe begrenzt, zusätzlich zu den engeren
Registrylimits. Negative oder NaN-Kostenobergrenzen werden abgewiesen.

Die Migration gewährt der vorhandenen nicht privilegierten App-Rolle DML auf
Runs/Approvals und SELECT/INSERT/DELETE auf Ergebnisse. Readiness folgt wie
bisher der Alembic-Headrevision. Das neue Backend benötigt deshalb die neue
Migration vor erfolgreicher Readiness. Es wurden ausschließlich lokale Testdaten
migriert, keine laufende Anwendungsdatenbank.

Rollback im Betrieb erfolgt zunächst über das bisherige Backend mit vorhandenen
Chatpfaden. Ein Downgrade entfernt Tooltabellen und deren Inhalte; er ist kein
verlustfreier Tooldatenrollback und wird hier nur in der flüchtigen Testdatenbank
geprüft. Bestehende Chatdaten bleiben beim Upgrade und beim Downgrade zu 0010
erhalten.

## Zustände und Transaktionen

`queued → awaiting_approval → running → succeeded` beziehungsweise
`queued → running`. Alternative Endzustände:
`failed`, `cancelled`, `timed_out`, `interrupted`, `outcome_unknown`.
Terminale Runs können nicht erneut gestartet werden.

`ToolRepository.create_run(owner, request, payload)` validiert und normalisiert
die Eingabe, berechnet SHA-256 und serialisiert unter Conversation-/Generationlocks.
`(generation_id, step_key)` ist eindeutig. Identische Wiederholungen mit denselben
IDs und serverseitigen Snapshots liefern den vorhandenen Run; abweichende Daten
ergeben Konflikt. Dies ist DBidempotenz, keine Exactly-once-Garantie für spätere
externe Provider. Childdeadlines dürfen die Parentdeadline nicht überschreiten.

`transition(owner, run_id, expected, target)` prüft erwarteten Zustand und
zulässige Transition unter Zeilenlock. `complete(owner, run_id, payload)` validiert
das Outputschema und speichert Ergebnis und `succeeded` in einer Transaktion.
Direktes `transition(..., succeeded)` ist gesperrt. Fehler beim Ergebnisinsert
rollen auch den Erfolgszustand zurück. Gleiches Ergebnis kann idempotent gelesen
werden; abweichendes Ergebnis überschreibt nichts.

Vor Start und Ergebnisabschluss werden Deadline sowie Generation-/Parentstatus
geprüft. Akzeptierter Cancel verhindert einen späteren Erfolgscommit.
`get_run`/`get_result` prüfen Owner und Chatzugehörigkeit erneut. Fremde oder
soft-deleted Ressourcen sind nicht lesbar, archivierte Chats nicht beschreibbar.
Diese Methoden sind Persistenzbausteine, keine Ausführungsfreigabe. P1b muss
Providerdispatch ausschließlich nach Policy-, Grant- und Budgetprüfung zulassen.

## Lokale Validierung

Es wurden nur von diesen Änderungen betroffene lokale Tests ausgeführt;
auf CI wurde nicht gewartet. Keine Liveproviderjobs und keine Frontendänderung.

| Prüfung | Ergebnis |
| --- | --- |
| Registry/Schemas/Zustände: neue Unitfälle | 40 bestanden |
| Readiness/Health/OpenAPI/WS-v1: bestehende Unit-/Vertragsfälle | 20 bestanden |
| Neue PostgreSQL-Tool-/Migrationstests | 13 bestanden |
| Bestehende DB-/Chatschema-/CRUD-/WSstream-/Stopregressionen | 11 bestanden |
| Ruff-Lint/Format und striktes Pyright für betroffene Dateien | bestanden |

Insgesamt **84 unterschiedliche Tests**. Migrationtests prüfen wiederholtes
Upgrade, Alembic-Schemadrift und unveränderte Altbestandzeilen einschließlich
Lernmodus, Titelclaim, aktivem Nachrichtenpfad, PDFmetadaten, Streamereignissen,
Entwürfen und Modellpräferenz. Integration prüft konkurrierende Run-/Ergebnisrequests,
Inputkonflikte, Owner-/FKgrenzen, Datenbankgrößenlimits, Approvalbindungen,
Resultatrollback, Timeoutzustand, Parent-/Generationabschluss und Cancel-vs-Commit.
App-Rollenrechte verhindern Ergebnisupdates.

Die DBtests benutzen ausschließlich einen neu gestarteten PostgreSQLcontainer mit
synthetischen Zugangsdaten und Datenbanknamen mit `_test`-Suffix. Voraussetzung
für den Rollenprüfungstest ist die vorhandene Initialisierung
`infrastructure/docker/postgres-init.sh`, wie auch in CI. Bestehende Container
und Datenbanken werden nicht angefasst. UI-/Modellprovider-/Uploadparser-Suites
wurden für diesen begrenzten Backenddiff nicht erneut ausgeführt.

## Offene Abhängigkeiten für PR B / P1b

Nach Merge dieses PRs: neues Checkout von aktualisiertem `main`, dann eigener
Runtime-PR. Er umfasst Dispatcher, allow/approval_required/deny-Policy,
digest-/expirygebundene Approvalentscheidungen und Auth-/Origin-geprüfte
Capability-/Run-/Approvalrouten. Laufende Requests benötigen kooperativen
Parent-/Childabbruch, begrenzte Timeouts/Retrypolicy und Startup-Recovery samt
Finalisierung auf archivierten/gelöschten Chats.

Durable Budgetledger und Reservationen, UTC-Tageswechsel, konkurrierende
Reservierungen, konservative Kosten und unbekannte Providerabschlüsse sind
noch nicht implementiert. Textphasen müssen hinter der bestehenden
Gatewayadmission genau einmal budgetiert werden, einschließlich Titel und
automatischer Fortsetzungen. Dafür folgen eigene Unit-/Integrationstests in P1b.

P2 ergänzt den gemeinsamen WS-v2-Eventwriter und Replay. P6/P7 implementieren
Searchprovider, Quellenpersistenz, SSRF-Fetcher und den tatsächlichen Webmodus.
Providerkonfiguration, Egressfreigabe, Qualitätsprobe und Menüintegration bleiben
deren spätere Gates. Keine neue Menüaktion wird durch P1a aktiviert.
