# P1b: Sichere Tool-Runtime und dauerhafte Budgets

Stand: 2026-10-13. Basis ist `main` bei `bb8428e` mit PR #56 und #62.
Dieser PR implementiert ausschließlich P1b aus der [Roadmap](FEATURE-ROADMAP.md).
Die [P1a-Registry und Tabellen](TOOL-FOUNDATION.md) bleiben die Grundlage.
`web.search.v1` und `web.fetch.v1` bleiben ohne Handler/Providerbindung und öffentlich
`unavailable`. Es gibt weder Webmodus noch neuen Chattransport oder Conversationstore.

## Ausführung und Berechtigungen

`ToolRuntime.execute(owner, ToolRunCreate, payload)` ist ein internes Interface für
vertrauenswürdige Serverorchestrierung. Registry und Policy werden beim Appstart
fest zusammengestellt; in der produktiven Composition-Root ist die Policy leer.
Kein Modelloutput und keine HTTProute kann einen Toolnamen zur Ausführung bringen.
Die SearXNG-Implementierung aus PR #62 wird in diesem PR noch nicht dispatcht.

Die bestehende Eingabevalidierung, Normalisierung, Step-ID/Digest-Idempotenz und
atomare Resultatpersistenz werden wiederverwendet. Handler erhalten einen
eingefrorenen `GenerationToolContext` mit Owner-, Conversation-, Generation-,
Run-, Parent-, Reservation- und optionaler Approval-ID, geprüftem Provider/
Konfigurationssnapshot, Permission, Ressourcenobergrenzen, Deadline und Cancelhandle.
Die Kontextdaten kommen ausschließlich vom Server. Handler müssen kooperativ
abbrechbare I/O verwenden und ihre deklarierten Transportgrenzen einhalten.

Policyentscheidungen sind `allow`, `approval_required` und `deny`. Fehlender Handler,
Provider, begrenzte Kostenpolicy oder Betreibergrant sperren die Invocation. Ein
expliziter Decimal-Kostenbound von null kann einen geprüften kostenlosen Provider
abbilden; ein fehlender Betreibergrant erlaubt keine kostenpflichtige Ausführung.
Provider-, Konfigurations-, Schema-, Invocation- und Policy-Snapshots werden vor
Dispatch und Ergebniscommit erneut geprüft. Eine Ausweitung nach Claim verlangt
eine neue Ausführung/Freigabe; vorhandene Reservationen werden nicht vergrößert.

Approvals binden Owner, Run, normalisierten Eingabedigest, Provider, Konfigurations-
version, Permission, Währung, maximale Calls/Kosten und Ablaufzeit. Entscheidungen
sind per Request-ID idempotent; andere Digests, fremde Ressourcen, abgelaufene
Grants und widersprüchliche Entscheidungen werden abgewiesen. Die Entscheidung
startet keinen Providerrequest. Der Orchestrator muss nach Freigabe explizit
fortfahren. Der gemeinsame Basiczugang identifiziert weiter einen gemeinsamen
Owner, keine natürliche Person oder neue Mandantenidentität.

Claim, Budgetreservation und Audit-Snapshot committen gemeinsam. Netzwerk läuft
außerhalb der DBtransaktion. Ein nur durch erfolgreichen Claim erhaltener
Execution-Token schützt den Resultatcommit und die Finalisierung; ein zweiter
Dispatcher darf einen fremden laufenden Claim nicht abschließen. Gleiche aktive
Requests teilen lokal einen Task. Gespeicherte Ergebnisse können idempotent gelesen
werden; terminale Runs erhalten keine neue Providerausführung.

## Budget und Gateway

`BudgetCoordinator` serialisiert Reservationen unter einem PostgreSQL-Ownerlock.
Das UTC-Tagesledger enthält Calls, Tokens, Bytes und Decimal-Kosten/Währung.
Reservationen sind nach Owner, Budgetbereich, Phase und Versuch eindeutig, auch
über Tageswechsel hinweg. Toolreservationen sind zusätzlich an den ToolRun
gebunden. Tages- und Generationsobergrenzen werden atomar vor Dispatch geprüft.
Retries erhalten eine eigene Reservation und prüfen Policy, Grant, Parent und
Deadline erneut. Es gibt höchstens einen Retry für ausdrücklich idempotente Tools;
die produktiven Search-/Fetchdefinitionen haben weiterhin null Retries.

Die Zustände des Ledgers sind `reserved`, `dispatched`, `accounted`, `released`,
`unknown`. Nur nachweislich ungenutzte, noch nicht dispatchte Reservationen werden
freigegeben. Nach Dispatch bleibt die vollständige konservative Obergrenze
belastet. Unbekannte Nutzung wird nicht als null gemessen: `measured` bleibt null.
Unklare nicht idempotente Providerabschlüsse bleiben `outcome_unknown`; kein
automatischer Wiederanlauf, keine öffentliche Reconciliation-/Resetroute.

Die App injiziert denselben Coordinator **hinter** die vorhandene
`LLMGateway`-Admission. Modellfreigabe, Kontext-/Bild-/PDFprüfung, Token-/Bytegrenzen,
Parallelitäts- und Ratelimits bleiben aktiv. Normale Textphasen, Titel und
automatische Fortsetzungen reservieren jeweils einmal anhand ihrer vorhandenen
Phase-ID. Dieses zusätzliche globale Textledger begrenzt Tokens/Calls; es behauptet
keine Geldobergrenze für unbekannte Textmodellpreise. Die vorhandenen Preisinformationen
bleiben Schätzungen. Persistenzfehler verhindern den Providerstart.

## Deadlines, Stop und Recovery

Die deklarierte Deadline bleibt für Idempotenz erhalten. Beim Claim wird die
effektive Ausführungsdeadline aus absoluter Deadline, Tooltimeout und verbleibender
Parentdeadline berechnet und gespeichert. Dispatch und Commit prüfen sie erneut.
Kurze DBtransaktionen begrenzen Lockwartezeit auf 1,5 s und einzelne Statements
auf 3 s (`SET LOCAL`, keine Änderung an globalen PostgreSQLeinstellungen).

Bestehendes `chat.cancel` ruft den injizierten Runtime-Cancelpfad auf. Der DB-Cancelfence
wird vor dem lokalen Signal gespeichert und umfasst rekursiv Children. Handler-I/O
wird abgebrochen, DBfinalisierung geschützt ausgeführt. Der Monitor erkennt auch
externen Generationabschluss, Archivierung und Soft Delete. Akzeptierter Cancel
verhindert einen Erfolgscommit. Ergebnisse/Reservation/Erfolgsstatus bilden eine
Transaktion; immutable Resultatdaten behalten ihre bisherigen Rollenrechte.

Shutdown beendet aktive Tool-I/O. Startup finalisiert Toolruns und Textreservationen,
bevor der bestehende Chat-Recoverypfad Generierungen unterbricht. Nicht dispatchte
Reservationen werden freigegeben; möglicherweise ausgeführte nicht idempotente Calls
bleiben unbekannt und belastet. Recovery funktioniert auch auf archivierten oder
gelöschten Chats und entwertet alte Pending-/Approved-Grants. Ein periodischer
Cleanup finalisiert abgelaufene wartende Runs/Approvals. Kein Startup startet Tools
oder Textprovider erneut. Das bestehende Single-Worker-Betriebsmodell bleibt bindend.

## REST-Verträge

Alle Ressourcen verwenden vorhandene Basic-, Origin- und Ownerprüfungen sowie
`ErrorResponse(error:{code,message,request_id})`. Nachrichten stammen aus einem
festen Fehlerkatalog; Providerkörper, Exceptions, Eingaben, Credentials und private
Audit-Snapshots werden nicht veröffentlicht.

| Route unter `/api/v1` | Vertrag |
| --- | --- |
| GET `/chat/tools/capabilities` | `schemaVersion:1`, feste Tool-IDs, `available/unavailable`, sichere reasonCodes; keine Endpoints/Keys |
| GET `/chat/tool-runs/{run_id}` | Owner-/Conversation-geprüfter Run, sicherer Fehlercode, validiertes `latestResult`, optionales Approval; kein Rohinput |
| POST `/chat/tool-approvals/{approval_id}/decision` | `{requestId,inputDigest,decision:"approve"\|"deny"}`; autoritativer Grantsnapshot |

Die Approvaleingabe übernimmt die bestehende REST-JSON/UUID-Konvention aus
`JsonApiSchema`; zusätzliche Felder bleiben verboten. Interne Toolpayloads behalten
ihre strikte JSONvalidierung. OpenAPI/TypeScript werden mit dem bestehenden Generator
exportiert. WebSocket-v1, seine Sequenzierung, Replay und generierten WS-Verträge
bleiben unverändert. Toolereignisse und Eventwriter folgen erst in P2.

## Migration und Betrieb

`0014_tool_runtime` folgt auf den vorhandenen Mergehead `0013_conversation_pinning`.
Sie ergänzt `reservation_id`, `execution_id`, `execution_deadline_at`, `approval_id`,
`dispatched_at` und einen begrenzten `policy_snapshot` auf `chat_tool_run` sowie
`chat_budget_day` und `chat_budget_reservation`. Zusammengesetzte FKs binden Run,
Owner, Reservation und Tagesledger; Constraints schützen Beträge, Währung,
Versuche, Digests und JSONgrößen. Kein Backfill und keine Änderung an Chatzeilen.
Readiness verlangt den neuen Head vor Freigabe des Backends.

Die App-Rolle bekommt DML auf Budgettabellen; das bisherige Verbot für Updates
auf Toolresults bleibt bestehen. Ein Downgrade entfernt Runtime-/Budgetdaten und
ist kein verlustfreier Betriebsrollback. Upgrade, wiederholtes Upgrade, Driftprüfung
und Downgrade werden ausschließlich in einer flüchtigen `_test`-Datenbank geprüft.
Es wurden keine Produktivdienste, Providerkonten, Firewallregeln oder Deployments
verändert. Vor Deployment ist die Migration separat durch den Betreiber auszuführen.

## Validierung und verbleibende Abhängigkeiten

Neue Fälle verwenden ausschließlich lokale Fakehandler und eine isolierte PostgreSQL-
Instanz mit synthetischen Zugangsdaten. Sie prüfen Policy/Grants, Ownergrenzen,
budgetierte Konkurrenz, Step-/Resultatidempotenz, Fencing, UTC-Tageswechsel,
Neustart, unbekannte Abschlüsse, Retrybudgets, Deadlines, Parent-/Childcancel,
Archivierung/Soft Delete, sichere Fehler und REST-Reload. Gatewaytests zählen
Text, Titel und Fortsetzung genau einmal und prüfen unveränderte Modell-/Tokenlimits.

Abschlussprüfung: 640 Backend-Unit-/Vertrags-/HTTPfälle bestanden; anschließend
97 betroffene Fälle einschließlich eines zusätzlichen Budget-Ausfallfalls bestanden
(641 verschiedene Fälle insgesamt). 162 PostgreSQLfälle einschließlich acht echter
Proxytests, 468 Frontend-Unitfälle und 70 Browserfälle bestanden. 14 Browserfälle
wurden gemäß vorhandener Desktop-/Mobile-Regeln bewusst ausgelassen. Ruff,
striktes Pyright, Nuxt/Vue-/Generator-Typchecks, Frontend-Lint, API-/WS-v1-Drift
und Backend-/Frontendbuilds waren erfolgreich.

Lokal wurden
Tempdateien und Playwright-Traces in ein ignoriertes Workspaceverzeichnis umgeleitet,
weil `/tmp` seine Schreibquota überschritten hatte. Ein Fortsetzungs-Bestandstest
wartet nun explizit auf die unabhängige Titelphase, bevor er eine Conversationversion
für Regeneration übernimmt. Dies ändert keine Produktlogik.

P2 muss gemeinsame versionierte Toolereignisse, persistente Sequenzen und Replay
ergänzen. P6 bindet den vorhandenen SearXNGProvider an und speichert Sources. P7
liefert sicheren Source-ID-Fetch, Extraktion, budgetierten Quellenkontext, überprüfbare
Zitate und UX. Reale Engines, GPT-OSS/DeepSeek, Egress und Produktionsperformance
werden erst mit diesen Funktionen abgenommen. Dieser PR aktiviert keine Websuche.
