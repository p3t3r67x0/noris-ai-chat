# Deep Research: persistenter mehrstufiger Recherche-Orchestrator

Status: geplant, keine Agentenschleife implementiert. Stand: 2026-10-12.

Gemeinsame Basis: [Tool-Architektur](TOOL-ARCHITECTURE.md), [Webtools](WEB-SEARCH-DESIGN.md), [Bibliothek](FILE-LIBRARY-DESIGN.md), [Roadmap](FEATURE-ROADMAP.md).

## 1. Bestandsaufnahme

Vorhanden sind persistente Chatgenerationen/Replay, begrenzte Gatewayadmission, normale Textmodelle, serverseitiger Nachrichtenpfad, PDFseitenauswahl, Textreferenzen, Bildkontext und Stop. Sie sind keine mehrstufige Recherche: Es fehlen Researchrun, Plan, Quellensammlung, Belegstruktur, Checkpoints, dauerhafte Jobclaims und Resume nach Serverneustart.

`GenerationManager` ist heute browserunabhängig, endet aber nach Disconnect-Grace und markiert beim Restart laufende Generationen interrupted. Gatewaybudgets sind derzeit pro Prozess im Speicher. Diese Eigenschaften müssen für ausdrücklich gestartete Researchjobs gezielt erweitert werden; normale Chatgenerationen behalten ihr Verhalten.

## 2. Fehlende Komponenten und Orchestrierungsentscheidung

Ein persistenter Python-State-Machine-Orchestrator läuft initial im bestehenden FastAPIprozess mit einem Worker. PostgreSQLclaims/Checkpoints verhindern verlorenen Fortschritt; Cancellation und Scheduling kommen aus der gemeinsamen Toolruntime. Keine bloße `BackgroundTasks`-Kette ohne Jobpersistenz, kein zweiter LLMclient und keine rekursive freie Agentenschleife.

Research verwendet dieselben `web.search/web.fetch`-Tools und lokalen Attachment-/PDFreader. Ein Model darf einen begrenzten Plan vorschlagen, aber nicht Registry-/Provider-/Berechtigungen ändern. Externe Searchprovider erhalten nur aktuelle Frage/freigegebene Suchbegriffe; lokale Dateiinhalte gelangen ausschließlich in den bereits vorgesehenen LLMkontext. „Recherche nur in Dateien“ funktioniert ohne Searchprovider, sofern geeignete Textquellen vorliegen.

## 3. Datenmodell, Checkpoints und Zustände

| Tabelle | Felder / Invarianten |
| --- | --- |
| `chat_research_run` | id, owner/conversation/generation/input/assistant IDs, question, normalized scope/limits, planVersion, state, currentStep, background, cancel_requested_at, deadline/active_elapsed_ms, attempt, leaseOwner/leaseUntil/fencingToken, reportMessageId, safe limitations; genau ein aktiver Researchrun je Generation. |
| `chat_research_step` | run_id, step_key, ordinal/dependencies, kind, input_digest, tool_run_id/phase_id, state, attempt, reservation, bounded validated output, started/finished; unique `(run_id,step_key,attempt)`. |
| `chat_source` | gemeinsame Quellen aus Websuche plus source_kind=`attachment/pdf/text_reference`, canonical attachmentId, page/section, digest, fetched/selectedAt und extrahierte Ausschnitte. Gleiche Source-ID im ganzen Run. Diskriminierter Herkunftsvertrag: Webquellen brauchen URL, lokale Quellen Attachment-ID; DBchecks verhindern beliebige/fehlende Locator, lokale Quellen brauchen keine erfundene Web-URL. |
| `chat_research_evidence` | run_id, claim_key, source_id, page/section/textlocator, bounded excerpt, support=`supports/contradicts/unclear`, source_digest, provenance; keine unbelegte Wahrheitsbewertung durch Feldnamen. |
| `chat_research_checkpoint` | run_id + revision, abgeschlossene Step-/Result-IDs, Planversion, budget-used/reserved, report-prefix-digest, lastSequence, created_at; persistentes Resumeinput. |

Ownership und Conversation-/Generationzugehörigkeit durch zusammengesetzte FKs/DBconstraints absichern. Run-/Steppayloads begrenzen; Quellen/Toolresults immutable. Alle Dateien bleiben canonical Attachments im bestehenden Store, nicht in Researchblobtabellen. Ein Pin/Inputlink hält explizit ausgewählte lokale Quellen; laufender Run darf deren Cleanup nicht unbemerkt verlieren.

Runzustände: `queued → planning → collecting → synthesizing → verifying → completed`. `awaiting_approval` kann vor dem nächsten Dispatch auftreten. Terminalalternativen `partial`, `cancelled`, `failed`, `interrupted`. Ein Partialreport braucht tatsächlich vorhandenen Reporttext und sichtbare Einschränkungen; ein leeres Ergebnis ist kein erfolgreicher Teilbericht.

Stepzustände: `queued/running/succeeded/failed/cancelled/interrupted`. Toolstep nutzt zugeordneten ToolRun einschließlich timed_out/outcome_unknown. Exakte geplante Phasenkindtypen: `plan`, `search`, `fetch`, `local_extract`, `summarize`, `synthesize`, `verify`. Das sind keine vom Model neu erfindbaren Funktionsnamen.

### Mehrstufiger Ablauf

1. **Aufnahme:** bestehender Manager/Repository legt Usernachricht und einen Assistantplaceholder an; Owner/Version/Model/Attachments/Scope/Budget werden geprüft und gespeichert.
2. **Plan:** Gateway-Textphase liefert ein begrenztes JSONplanobjekt; nach abgeschlossenem Stream Pydantic-validieren. Höchstens eine budgetierte Korrektur oder definierter Planfehler, keine endlose JSONreparatur. Der Provider braucht dafür keine native Tool-/Structured-Output-Fähigkeit.
3. **Sammeln:** begrenzte Suchqueries, Source-IDgeprüfte Fetches und lokale PDF-/Textauszüge; stabile Stepkeys/Digests, dedup, Herkunft/Datenalter, maximal zwei parallele read-only Websteps.
4. **Auswertung:** Evidenz-/Widerspruchsliste und thematische Kurzfassungen als persistierte intermediäre Resultate. Zwischenphasen erscheinen nicht als zusätzliche User-/Assistantnachrichten im Variantenbaum.
5. **Synthese:** Manager `run_phase` nutzt denselben Gateway und erhält budgetierten Quellkontext. Bericht streamt in den einen vorhandenen Assistantknoten; Quellenregister liefert kontrollierte Citation-IDs.
6. **Prüfen:** referenzierte IDs/Locators müssen existieren und zum Run gehören. Begrenzte Modellprüfung kann widersprüchliche/fehlende Belege markieren, beweist aber keine Wahrheit. Nicht gedeckte Aussagen entfernen/als unsicher kennzeichnen; unbekannte LLMlinks werden nicht freigegeben.
7. **Abschluss:** Report, Source-/Evidenceprojektion, Runzustand, Snapshot und finales Ereignis committen. Vollständigkeit nur behaupten, soweit tatsächlich verarbeitet; begrenzte Auswahl, fehlende Quellen und Restfragen im Bericht sichtbar.

Die phasenspezifische Kontextvorbereitung verwendet vorhandene `attachment_context`, `pdf_request`, `_image_request`-Logik und Gatewaycheck, über ein gemeinsam genutztes internes Contextbuilderinterface. Für lokale Recherche initial TXT/MD/PDF/Textreferenzen; Bilder ohne geeignete Visionmodelle sind keine Textbelege. Physische PDFseiten bleiben erhalten, gescannte PDFs ohne OCR liefern `no_text`.

### Persistenz-/Claimprotokoll

Claim unter kurzer Transaktion: erwarteter Run-/Stepstatus, Owner/Chatstatus, Budget, Lease und Fencingtoken → dispatch marker commit. Netzwerk/LLM außerhalb der Transaktion. Resultat nur committen, wenn Lease/Fencingtoken weiterhin gültig und kein Cancel/Chatdelete vorliegt. Stepresultat, Evidence, Checkpoint, Parentsequenz und Progressereignis bilden eine Transaktion. Zentraler Generationwriter verhindert konkurrierende Sequenzvergabe.

Leasevorschlag: 30 s, Heartbeat alle 10 s; Schedulerpoll maximal 1 s. Zeiten sind konfigurierbar. Ein Scheduler mit `FOR UPDATE SKIP LOCKED` kann später Jobs verteilen, erlaubt jedoch aktuell keine zusätzlichen Backendworker wegen der noch lokalen Gateway-/Ticket-/Eventzustände.

Crashfälle: vor Dispatchmarker sicher erneut claimbar; nach möglichem Dispatch ohne Ergebnis keine garantierte exactly-once Providerwirkung. Such-/Fetchsteps können unter ihrer read-only Retrypolicy neu gestartet werden, wobei eine neue Reservation nötig sein kann. Bereits persistierte abgeschlossene Steps nie nochmals ausführen. Unklarer LLM-/kostenpflichtiger Step bleibt interrupted/unknown mit konservativer Budgetbelastung; Resume fordert eine bewusste neue Phase innerhalb bestätigter Restlimits an.

## 4. API-Verträge

Start über v2 `chat.generate.responseMode`:

```ts
type ResearchScope = {
  sources: 'web' | 'files' | 'web_and_files'
  localAttachmentIds: string[]
  domains: string[] // maximal 10 exakte Hostnamen, nur Einschränkung
  language: 'de' | 'en'
  timeRange: 'day' | 'month' | 'year' | null
}
type ResearchLimits = {
  maxQueries: number
  maxDocuments: number
  maxSteps: number
  maxModelCalls: number
  maxReservedTokens: number
  maxActiveSeconds: number
}
```

Startprofil als Vorschlag: maximal 20 Queries, 30 Dokumente, 40 Steps, 8 Textmodellphasen, 60.000 konservativ reservierte Tokens und 600 aktive Sekunden; Geld-/Tageslimit zusätzlich vom Betreiber. Kleinere gewünschte Limits sind erlaubt; Servermaxima gelten immer. Modeltoken-/Request-/Contextlimits können einen früheren Teilabschluss erzwingen. Kein Anspruch, dass alle erlaubten Maxima gleichzeitig erreicht werden können. `domains` schränkt erlaubte öffentliche Quellen zusätzlich ein und erteilt keine private Netzfreigabe.

`content` enthält die aktuelle Frage. localAttachmentIds müssen exakt den explizit ausgewählten Inputattachments des Commands entsprechen; keine fremden/globalen Dateien automatisch heranziehen. `background` ist ausdrücklich im UI bestätigter Startscope, default false. grantId verweist auf konkrete Freigabe des Providers/Budgets; Moneyobergrenze ist kein frei erhöhtes Clientfeld.

| Geplante Route unter `/api/v1` | Vertrag |
| --- | --- |
| GET `/chat/research-runs/{id}` | Snapshot mit state, plan, steps, sources/evidence summary, lastCheckpoint, reportMessageId und limits/usage. |
| GET `/conversations/{id}/research-runs` | Paginierte eigene Runs des aktiven/lesbaren Chats, keine globale Jobliste. |
| POST `/chat/research-runs/{id}/cancel` | `{requestId}` → persistierte cancel-Anforderung; delegiert an bestehenden GenerationManager-Stop, idempotent. |
| POST `/chat/research-runs/{id}/resume` | `{requestId,checkpointRevision,conversationVersion,grantId}` → neuer autoritativer Versuch mit denselben Run-/Generation-/Assistant-IDs. Nur `interrupted`; staler Checkpoint/aktive andere Generation 409. |

`chat.resume` stellt weiterhin **Transportreplay** her, nicht Researchausführung. Ausführungsresume erfolgt bewusst über die RESTaktion, reserviert weitere tatsächliche Calls und prüft frische Modell-/Toolfreigabe. Kein doppelter Resume durch zwei Tabs. Cancelled/failed/completed Runs können nicht durch Replay neu starten; „Neue Recherche“ ist ein neuer expliziter Auftrag.

## 5. WebSocket-Ereignisse

`chat.tool.*` beschreibt einzelne Toolcalls; `chat.research.*` beschreibt den gesamten Rechercheablauf. Plan- und Step-Events enthalten erlaubte Tätigkeiten/kurze Beschreibungen, keinen privaten Modellgedankengang.

| Ereignis | Payload |
| --- | --- |
| `chat.research.plan` | planVersion, bounded steps/Fragen, Scope und limits |
| `chat.research.step.started` | stepId/kind/label, checkpointRevision |
| `chat.tool.progress` | konkrete Suche/Fetch/Phase, gezählte Quellen/Calls |
| `chat.sources.updated` | normalisierte Quellen, Ausschnitt-/Volltext-/Fehlerstatus |
| `chat.research.step.completed` | Stepresultat-ID, source/evidence IDs, sichere warnings |
| `chat.research.checkpoint` | revision, completedSteps, budgetUsed, resumable flag |
| `chat.generation.delta` | Reporttext in bestehendem Assistantknoten |
| `chat.research.report.ready` | reportMessageId, sourceIds, limitations, runState completed/partial |

Gemeinsame Sequenz-/Commitregeln aus der Tool-Architektur. `partial` mappt in v2 auf `chat.generation.incomplete` mit eigenem reason `research_limits` oder `research_sources`; v1 `incomplete.reason=output_limit` wird nicht umgedeutet. `failed/cancelled/interrupted` erhalten entsprechenden Parentterminal. Stop kann einen vorhandenen Berichtpräfix erhalten, ohne diesen als vollständigen Bericht auszugeben.

Resume nach Reportunterbrechung darf den bereits persistierten Präfix nicht still überschreiben: neue begrenzte Gatewaycontinuation mit vorhandener ContinuationFilterlogik und separater Phase-ID, unter denselben Report-/Sequenz-IDs. Wenn Context/Modell/Prefix nicht mehr fortsetzbar ist, wird ein neuer expliziter Auftrag angeboten. Keine automatische Berichtrekonstruktion, die alte Aussagen unbemerkt verändert.

## 6. Frontend-UX

Plus → „Deep Research“ öffnet einen kompakten bestehenden Dialog/Sheet für Quelle (`Web`, `Dateien`, `Web und Dateien`), optional Domains/Sprache und Startumfang. Danach zeigt derselbe Composer den Researchchip; Inhalt/Dateien/Modellauswahl bleiben erhalten. Zum Dateiauswählen denselben Bibliothekspicker verwenden.

Vor Start zeigt die UI Umfang/Provider-/Kostenscope und ob das Schließen des Tabs die Recherche weiterlaufen lässt. Hintergrund wird ausdrücklich ausgewählt. Das anschließende Senden startet den tatsächlichen Run. Bei Scope-/Budgetausweitung folgt eine neue konkrete Approvalaktion; kein allgemeiner „Agent darf alles“-Schalter.

In derselben Assistantansicht: nachvollziehbarer Plan, Phase, fertige/gesperrte Quellen, Stop und Gesamtstatus. Fortschritt nennt erledigte Aufgaben statt geschätzter Prozentzahlen. Desktop darf Details in Drawer zeigen, Mobile als Sheet; Bericht bleibt in normaler Timeline mit Markdown/Citations. Plan-/Quellenansichten brauchen keinen zweiten Chatstate.

Reload/Tabwechsel liest durable Runs; Hintergrundjob läuft bis Stop/Deadline. Unterbrochene Jobs zeigen gespeicherten Fortschritt und „Fortsetzen“. Browser reconnect allein erzeugt keinen Resumeaufruf. `Esc` schließt zuerst Dialog/Sheet; expliziter Stop ist nötig, um eine im Hintergrund laufende Recherche zu beenden. Während aktiver Researchgeneration bleibt Schreiben in denselben Chat exklusiv, Lesen/Wechseln anderer Chats möglich; konkurrierende Starts 409 statt stiller Branchänderung.

## 7. Sicherheits-, Budget- und Recoverykonzept

Server entscheidet maximalen Planumfang, Toolset und parallele read-only Steps. Planschema erlaubt keine Shell, Python, frei gewählten Providers oder MCPendpoints; unknown kinds/additionalProperties denied. Jeder Step wird erneut mit frischen Berechtigungen/Sourceownership geprüft. SearXNGprivate-Serviceallowlist gilt nicht für Quellenfetch. URLdomainfilter sind Restriktionen, keine Zugriffsfreigaben.

Quelltext/Dateien sind untrusted Userdata, nicht privilegierte Instruktionen. Injection darf weder Dateien ins Web übertragen noch Providerwechsel, Budgeterhöhung oder Toolausführung auslösen. Validierte Citation-ID belegt nur die Herkunft einer Aussage; fachliche Qualität/Widersprüche sichtbar bewerten, keine algorithmisch garantierte Wahrheit.

Durable Budgetledger zählt jede Phase und automatische Textfortsetzung einschließlich Titel genau einmal gegen globale und Rungrenzen. Tokenmessung ist nur bei tatsächlicher Providerusage möglich, sonst konservative Reservation. Vorab reservierte Obergrenzen/Stepcounts begrenzen Schleifen, auch wenn Modelle keine Tokenusage liefern. Bei Budget-/Source-/Zeitende Teilreport nur aus bereits vorhandener Evidenz erzeugen, sofern noch reservierter Synthesebudgetraum besteht; dafür einen finalen Synthesescope vorab reservieren.

Parentdeadline und cancel_requested_at gelten für alle Steps/HTTPstreams/LLMphasen/Approvalwaits. Laufender DBcommit wird geschützt, danach keine weiteren Steps. Soft Delete eines Chats canceln und Zugriffe sofort sperren. Keine neuen Claims für archivierte Chats; laufenden Schreibjob bei Archivierungsanfrage kontrolliert abbrechen/konfliktieren.

Neustartrecovery: Scheduler zuerst stoppen/Claims schließen, reguläre Startupmarkierung mit Researchrecovery abstimmen, abgelaufene Leases fenced invalidieren und Researchgeneration `interrupted` plus Checkpoint persistieren. Bewusstes Resume prüft Conversationversion/aktiven Leaf und requeued ausschließlich diesen unterbrochenen Researchrun samt Generation unter neuer Attempt-/Fencingnummer. Normale v1-Generationen bleiben terminal interrupted. Alte Writer und alte Approvals können nach Resume nicht committen. Maximum drei Resumeversuche je Run als Startpolicy; zusätzliche Arbeit als neuer Auftrag.

## 8. Tests

Unit: erlaubtes Planschema/DAG/Stepbudget, invalid JSON/unknown actions, source dedup, Evidenzlocators, Widersprüche, Context-/PDFseitenauswahl, result/terminal state mapping, Parent-/Childcancel, reservierter Synthesescope und Deadlineberechnung. Injectionfixture verlangt geheime Dateien/Netze/mehr Budget; Registry muss nichts ausführen.

Integration: deterministische lokale Search-/Fetch-/LLMsimulatoren und disposable PostgreSQL. Gesamtlauf mit mehreren Stufen, dokumentierten Zitaten, teilweise fehlenden Quellen und explizitem Partialreport; duplicate start/resume; foreign owner; revoked Model/Toolcapability; Cancel während Search/LLM/Commit; Budget-/Deadlineende; Sourcechatdelete. Prozessabsturz jeweils vor Claim, nach Dispatch, nach Resultatcommit und während Report; Resume überspringt nachweislich abgeschlossene Schritte, unknown Calls werden nicht still dupliziert. Lease-/Fencingrace mit zwei Claimern trotz weiterhin Einworkerbetriebsgrenze testen.

Gatewayintegration prüft, dass **jede** Researchtextphase über den vorhandenen Provider/gateway reserve/events/release läuft; keine verkürzte Admission. PDFsections/Textreferenzen/Datei-IDs und ausgewählte Seiten bleiben bei Neustart erhalten. Reconnects, lange Eventqueues, abgelaufene Replayretention und Snapshots sind konsistent.

Playwright Desktop/Mobile: Plus → Scope → Researchchip → Start → Plan/Quellen/Report; Stop, Hintergrundwahl/Tabwechsel, Reload, serverseitige Unterbrechung und explizites Fortsetzen. Budget-/Providerfehler, Tastaturdialog, keine unfreiwillige Webweitergabe und normaler Chat danach. Tests zeigen öffentlichen Progress, nicht private Chain-of-thought.

## 9. Abnahmekriterien

- Ein Auftrag durchläuft mehrere gespeicherte Plan-/Sammlungs-/Syntheseschritte und erzeugt nachvollziehbaren Bericht mit zugänglichen Quellen und Einschränkungen.
- Crash/Reload verliert keine bestätigten Stepresults; abgeschlossene Steps werden nicht nochmals ausgeführt.
- Transportreplay, Jobresume und neuer Auftrag sind unterscheidbar und idempotent.
- Endliche Steps, Zeit, Calls, Tokens und Moneylimits begrenzen jede Recherche; kein LLM kann sie erweitern.
- Stop/Delete/Revocation verhindern weitere Claims; late Writer/Approvalresultate sind wirkungslos.
- Normaler Chat, Modellkatalog, Upload/PDF/Textreferenzen, Varianten und WS-v1 bleiben funktionsfähig.
- Teilbericht und fehlende Quellen sind wahrheitsgemäß dargestellt; keine behauptete Vollrecherche bei Ausschnitt-/Limitende.

## 10. Abhängigkeiten und Nichtvoraussetzungen

P1 gemeinsame Runtime/durables Budget, P2 WS-v2, P3 lokale Attachmentbezüge, P6/P7 Websearch/Fetcher und P10/P11 Researchstate/UX. P4 Picker erleichtert Dateienauswahl, P8 Bildprovider ist keine Researchvoraussetzung. Kein Spezialmodell mit „deep research“ im Namen, kein externes Agenten-SDK, keine Vektor-DB oder Codex-Rustausführung notwendig. OCR, Headlessbrowser, aktive Webseiteninteraktion und unbegrenzte autonome Suche bleiben außerhalb dieser Roadmap.
