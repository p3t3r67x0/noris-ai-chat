# P2: versionierte Toolereignisse und persistentes Replay

Grundlage: aktuelles `main` auf `75f35d839c930c1e57205f0eed1b42e6ee8236a9`,
Merge von PR #63 (P1b). P2 ergänzt Transport und Synchronisation der vorhandenen
Runtime. Produktive Handler/Grants bleiben deaktiviert. Keine zweite Registry,
Eventdatenbank, Chatarchitektur oder WebSocket-Verbindung.

## Bestand und Integrationsstellen

Chatereignisse laufen über `/api/v1/chat/ws`, Subprotokoll `noris-chat.v1`,
einmalige authentisierte Tickets, bestehende Origin-/Hostprüfung, Heartbeat,
begrenzte Peerqueues und denselben `GenerationManager`. Metadatenereignisse
haben keine Generationsequenz und werden nach Reconnect über REST aufgefrischt.

`ChatGeneration.last_sequence` und der Primärschlüssel
`chat_stream_event(generation_id, sequence)` existierten bereits. Chatantwort,
Nachrichtenstatus und Replayevent committen zusammen. Der Browser nutzt
`chat.resume {generationId,lastReceivedSeq}`. Lücken, große Replays und
Fortsetzungs-Replays werden mit `chat.resume.snapshot` ersetzt. Bisherige
lokale Chatsequenzen mussten für konkurrierende Toolwrites durch eine gemeinsame
DB-seitige Vergabe ersetzt werden.

P1b speichert Runs, immutable validierte Results, Approvals, Executiontokens,
Cancelfences und Budgetreservationen in PostgreSQL. Conversation-/Generationlocks
schützen Claim, Commit und Finalisierung; Netzwerk liegt außerhalb der Transaktion.
Stop ruft bereits `ToolRuntime.cancel` auf. Startup finalisiert verwaiste Tools vor
der Chat-Recovery; Shutdown beendet aktive I/O. `LLMGateway` bleibt der einzige
Textproviderpfad mit unveränderten Admission-, Modell-, Kontext- und Budgetprüfungen.

Frontend: `webSocketTransport.ts` liefert in `useChatStream` und `useChat`;
`ChatBackend` lädt autoritative History und Metadaten, Browserstorage ist Cache.
Reconnect erfolgt mit frischem Ticket und dem zuletzt konsumierten Cursor.
`useChatBackend.applyPath` kann bereits die Generation-IDs geladener Nachrichten
für eine Toolrekonstruktion verwenden. Die bestehende Active-Path-Projektion
ergänzt `toolGenerationIds` (maximal 50): ownergeprüfte Toolgenerationen aller
angezeigten Antwortnachrichten, einschließlich früherer expliziter Fortsetzungen.
Fehler bleiben im vorhandenen
Transport-/Notificationpfad. Composer und Layout erhalten keine Tool-UI.

## Vertrag und Versionierung

`chat.generate` und `chat.resume` erlauben optional `toolEventVersion: 1`.
Nur solche Abonnements erhalten Toolereignisse. Fehlendes Feld bleibt zulässig;
alte Clients erhalten bei Toolsequenzen einen vorhandenen Chat-Snapshot, dessen
Cursor die übersprungenen Sequenzen einschließt. Bestehende v1-Felder bleiben gleich.
Für reine History-/Toolbeobachtung ergänzt `chat.resume` optional
`toolEventsOnly:true`. Dieser Modus verlangt `toolEventVersion:1`, verwendet
denselben Scope und dieselbe Outbox und liefert ausschließlich Toolprojektionen
und Toolereignisse. Er spielt keine bereits geladene Chatantwort erneut ab.

Jedes Lifecycleereignis enthält:

| Feld | Vertrag |
| --- | --- |
| `version` | Chattransportversion, aktuell `1` |
| `eventVersion` | Toolpayloadversion, aktuell `1` |
| `type` | Einer der acht unten definierten Typen |
| `conversationId`, `generationId`, `runId` | Servergebundene UUIDs |
| `seq` | Positive gemeinsame Generationsequenz |
| `timestamp` | UTC-Zeit mit Zeitzone |
| `payload` | Strikte `ToolProjection`, zusätzliche Felder verboten |

`ToolProjection` enthält `runId`, allowlist-geprüfte `toolId`
(`web.search.v1` oder `web.fetch.v1`), `state`, `lastSequence`, `updatedAt`,
`cancelRequested`, optionales Approval, Resultatreferenz und festen `errorCode`.
`lastSequence` entspricht bei Lifecycleevents `seq`; `updatedAt` entspricht
`timestamp`. Bool-/Integerfelder werden nicht aus Strings koerziert.

Approvaldaten sind ausschließlich `{approvalId,inputDigest,state,expiresAt}`.
Der Digest ist der bereits öffentliche P1b-Bindungswert, kein Rohinput.
Approvaldetails werden nur im Zustand `awaiting_approval` projiziert.
Ergebnisse sind ausschließlich `{resultVersion:1,sourceCount:number|null}`;
die Quellenzahl stammt aus erneuter Validierung des gespeicherten `SearchResult`.
Fetchresults liefern keine Textkörper und keine erfundenen Fortschrittszahlen.

Pydantic ist die Vertragsquelle. `pnpm api:generate` exportiert OpenAPI,
WebSocket-JSON, TypeScripttypen und die kleinen öffentlichen Tool-JSONschemas
für die Browservalidierung. `pnpm api:check` prüft alle Artefakte auf Drift.
Künftige inkompatible Payloads benötigen eine neue explizit unterstützte
`toolEventVersion`; unbekannte Versionen werden verworfen, nicht geraten.

## Zustände und Ereignisse

| Persistenter Zustand/Änderung | Öffentliches Ereignis |
| --- | --- |
| Neuer `queued` Run | `tool.progress` mit `state:queued` |
| `awaiting_approval` mit neuem Grant | `tool.approval_required` |
| Idempotente Approvalentscheidung `approved` | Einmal `tool.progress`, weiterhin wartend |
| Claim nach Policy-/Budgetprüfung: `running` | `tool.started` |
| Persistierter Cancelfence während `running` | `tool.progress`, `cancelRequested:true` |
| Validiertes Ergebnis und `succeeded` | `tool.result`, danach `tool.completed` in derselben Transaktion |
| `failed`, `interrupted`, `outcome_unknown` | `tool.failed`, interner Zustand bleibt unterscheidbar |
| `cancelled` | `tool.cancelled` |
| `timed_out` | `tool.timed_out` |

`tool.result` ist eine Ergebnisankündigung; nur `tool.completed` ist das
erfolgreiche Lifecycleterminal. Beide projizieren bereits `succeeded`, sodass
auch ein Replay zwischen ihnen keinen laufenden Run vortäuscht. Idempotente
Creation, Resultcommit, Approvalentscheidung und Finalisierung schreiben kein
zweites Lifecycleterminal. Die vorhandenen erlaubten Zustandsübergänge bleiben
bindend. P2 erzeugt keine zeitgesteuerten Fortschrittstexte oder Prozentwerte.

## Atomare Persistenz und Versand

`chat.stream.append_event` vergibt Sequenzen unter Conversation- und Generationlock
in genau dieser Reihenfolge. ToolRunänderung, Resultat, Approval-/Budgetänderung,
Run-Projektionscursor und `chat_stream_event` committen in derselben Transaktion.
Alle Toolübergänge einschließlich Timeout, Denial, Cancel und Recovery verwenden
den Writer. Ein Fehler beim Eventwrite rollt auch den Ergebnis-/Statuswrite zurück.

Die bestehende Eventtabelle ist die Transactional Outbox. Ein serialisierter
Drain liefert ausschließlich committed Rows in Sequenzreihenfolge. Chatwrites
stoßen denselben Drain an; der bestehende Socket prüft zusätzlich alle 100 ms
die Sequenzen abonnierter Generierungen. Dadurch bleiben auch Toolabschlüsse
nach dem Chatterminal oder ohne lokalen Publisher sichtbar. Keine DBtransaktion
wartet auf WebSocket-I/O. Das bestehende Single-Worker-Betriebsmodell bleibt bestehen.

Crash vor Commit hinterlässt weder Status noch Ereignis. Crash nach Commit oder
vor Versand hinterlässt beides für Replay. Crash nach Providerdispatch folgt
P1b: konservative Reservation, kein Redispatch, bei nicht idempotenten Calls
`outcome_unknown`. Persistierter Cancel wird nach Restart bei bekanntem Ausgang
als `cancelled` rekonstruiert, unbekannter Ausgang bleibt ausdrücklich unbekannt.

## Replay, Reconnect und Reload

Replay liest Generation, Antwort und Tools unter denselben Scope-Locks wie die
Writer. Ein Snapshot kann dadurch nicht einen neuen Cursor mit alten Zuständen
kombinieren. Abonnement und Queuecursor werden unter dem gemeinsamen Drainlock
installiert, bevor neue committed Events geliefert werden.

Auf `chat.resume` folgt `chat.resume.accepted`. Opt-in-Clients erhalten zuerst
`tool.snapshot`: dieselben Versions-/Scope-/Zeitfelder, `lastSequence` als
Generation-Watermark und bis zu 16 `ToolProjection`-Einträge pro Nachricht.
Mehrere Seiten teilen dieselbe Watermark. Snapshots sind Synchronisationsnachrichten
und verbrauchen keine neuen Outboxsequenzen. Danach kommen die vorhandenen
geordneten Lifecycleevents oder der bestehende Chat-Snapshot bei Lücken/Überlauf.
Tool-Snapshots stehen vor einem Chatterminal, dessen Verarbeitung den Textstream beendet.

Der Browser validiert die generierten Schemas, bindet Events an bekannte
Conversation-/Generationpaare, konsumiert Toolsequenzen im selben Textstreamcursor
und ignoriert doppelte/alte Runsequenzen. Eine Snapshot-Watermark entwertet alte
Lifecycleevents. Terminale Projektionen können nicht durch verspätete laufende
oder widersprüchliche Terminalevents überschrieben werden.

`useChat.toolRuns` ist die wiederverwendbare interne Projektion im vorhandenen
Chatstate. Geladene History abonniert auch abgeschlossene Generation-IDs über
denselben Socket mit `toolEventsOnly:true`. Da eine explizite Fortsetzung eine
neue Antwort und Generation erzeugt, liefert die vorhandene Active-Path-API zusätzlich
die über `ChatGeneration.source_message_id` gefundenen früheren Toolgeneration-IDs.
Die Quellkette ist auf die bestehenden 20 Fortsetzungen begrenzt. Diese
Abfrage liegt im bestehenden konsistenten History-Snapshot und prüft Owner und
Conversation auf Run und Generation. Nach Seitenreload wird die Projektion aus PostgreSQL aufgebaut;
lokaler Toolstorage ist keine Autorität. Idle-Reconnect fordert diese Projektionen
erneut an. Conversationlöschung entfernt die entsprechenden Cacheeinträge.

## Fehler, Abbruch und Approval

Stop setzt wie bisher erst den DB-Cancelfence und dann lokale Cancelsignale.
Queued/wartende Runs werden sofort terminal; laufende I/O wird geschlossen und
geschützt finalisiert. Wiederholter Stop schreibt keinen zweiten Cancelfenceevent.
Terminale Runs bleiben terminal. Nach einem committed Erfolg ist Stop wirkungslos
für diesen Run; nach einem accepted Fence ist Erfolgscommit verboten.

Grants werden ausschließlich über
`POST /api/v1/chat/tool-approvals/{approval_id}/decision` entschieden.
Ein Approvalevent oder eine Entscheidung startet keine Ausführung; nur der
vertrauenswürdige Orchestrator setzt den bestehenden Run ausdrücklich fort.
Decisionrequest-ID und Executiontoken verhindern doppelte Dispatches.

## Sicherheitsgrenzen und Limits

Authentisierung, Owner-/Conversation-/Generationbindung und Soft-Deleteprüfung
erfolgen serverseitig bei Subscription und Replay. Rawinput, private Audits,
Prompts, Credentials, Providerkörper, unbekannte Toolnamen und freie Exceptiontexte
gelangen nicht in die Projektion. Persistierte Toolevents werden beim Replay
erneut validiert und gegen Scope und Sequenz geprüft. Clientfilter ergänzen diese
Grenzen. Eingehende `tool.*`-Kommandos bleiben ungültig; keine Execute-API entsteht.

Lifecycleevent und Snapshotnachricht sind auf 16 KiB begrenzt. Ergebnisse bleiben
einmalig im vorhandenen Resultatspeicher und werden über
`GET /api/v1/chat/tool-runs/{run_id}` autorisiert nachgeladen. P1b-Eingabe-/Ausgabelimits
bleiben unverändert. Neu angelegte Generierungen erlauben höchstens 128 Toolruns.
Peerqueues bleiben begrenzt; Überlauf trennt den Socket und führt zu Snapshotrecovery.
Pro Socket werden höchstens 64 Generierungen abonniert, pro Historyfenster höchstens
50 rekonstruiert. Der Browsercache hält höchstens 1024 Toolprojektionen.

## Retention und Migration

Die bestehende `chat_stream_event_retention_hours`-Policy (Default 168 Stunden)
pruned nur abgeschlossene Generationstreams beim Ticketabruf. Laufende Generationen
werden nicht gepruned. Run-/Result-/Approvalzeilen bleiben die dauerhaft
rekonstruierbare Projektion, auch nach Eventpruning. Ihr bestehender Ressourcen-
und Löschlebenszyklus wird nicht ersetzt. Browsercursor werden nicht dauerhaft
benötigt, da Reload immer die autoritative Projektion liest.

Migration `0015_tool_events` folgt auf `0014_tool_runtime` und ergänzt nur
`chat_tool_run.event_sequence` (Default 0, nicht negativ) und `event_updated_at`.
Bestehende Runs bleiben mit Sequenz 0 rekonstruierbar; Chatdaten werden nicht
umgeschrieben. Readiness folgt dem neuen Head. Upgrade ist vor einem späteren
Deployment separat erforderlich. Downgrade entfernt nur diese Projektionsfelder,
nicht Tool-/Chatdaten; alte Anwendungen sind weiterhin ohne Tool-Opt-in nutzbar.

## Integrationsvertrag für P6 und P7

P6 darf den vorhandenen `ToolRuntime.execute`-/Policy-/Handlerpfad aufrufen und
Sources autorisiert persistieren. P2 liefert ausschließlich tatsächliche
Zustände und validierte Ergebniszahlen. Für neue echte Fortschrittsschritte
braucht es einen serverseitig geprüften, atomaren Zustands-/Eventwrite, keine
freien LLMtexte als Fortschrittsnachricht.

P7 kann `useChat.toolRuns` für Status und Approvaldarstellung verwenden und
Ergebnisse nach Run-ID über die vorhandene REST-Projektion laden. Quellenprüfung,
Source-ID-Fetch, Quellenkontext, Zitate und Such-UI werden hier nicht implementiert.
Weder P6 noch P7 werden durch Empfang, Replay oder Approvalentscheidung gestartet.

## Prüfstand

Die Fehleranalyse zu PR-Head `d238184` umfasst alle 15 gespeicherten
Playwright-Traces: sieben aus dem PR-Lauf `38406843098` (fünf `checks`, zwei
`compose-smoke`) und acht aus dem Push-Lauf `38406379645` (sechs `checks`, zwei
`compose-smoke`). Die vollständigen Trace-/Network-Datensätze zeigen keine
Consolefehler oder fehlgeschlagenen Generierungs-HTTP-Anfragen. Die in den
Assertionfehlern enthaltenen Ereignisarrays zeigen zweimal
`chat.generation.started` mit identischer Sequenz 1 (acht Traces) und die
Terminalfolge `tool.completed:7, tool.completed:9, tool.completed:7,
tool.completed:9` (sieben Traces). Die Traces enthalten keine vollständige separate
WebSocket-Frameaufzeichnung; die wiederholten Payloads sind in den Assertions
erhalten. Nach Chatabschluss geladene Active Paths lösten im Head einen normalen
`chat.resume` ab Sequenz 0 aus. Damit wurde die vorhandene Outbox erneut
abgespielt. Das war ein Fehler der Toolbeobachtung, keine zweite Toolausführung.

`toolEventsOnly` behebt die Ursache im vorhandenen Replaypfad. Die ursprünglichen
Zähl- und Reihenfolgeassertions in `auto-continuation.spec.ts` und
`tool-events.spec.ts` bleiben unverändert. Deterministische Regressionen prüfen
Commit zwischen Snapshot und Subscription, mehrfachen Drain, Toolzustände nach
Chatterminal, Idle-Reconnect und Reload einer explizit fortgesetzten Antwort.

Alle neuen Ausführungsfälle verwenden deterministische
Fakehandler. Die Browserfixture ist eine explizite Testapp mit `_test`-DBguard,
keine Produktroute. Bestehende Compose-Produktbrowsertests verwenden weiterhin
die normale App und überspringen ausschließlich diese lokalen Fakehandlerfälle.
Die tatsächlich ausgeführten vollständigen Qualitätsgates, Wiederholungen und
CI-Ergebnisse werden in der Beschreibung von [PR #64](https://github.com/p3t3r67x0/noris-ai-chat/pull/64)
mit Laufreferenzen protokolliert. Fehlgeschlagene Erstläufe gelten dort nicht als
erfolgreiche Prüfungen.
