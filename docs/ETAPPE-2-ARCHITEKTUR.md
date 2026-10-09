# Etappe 2: Noris-AI-Anbindung

Die ausdrückliche Aufgabenstellung erweitert den früheren Etappenplan: Dieser PR implementiert den LLM-Transport, nicht die zuvor für Etappe 2 vorgesehene Domain-/OIDC-Migration. Keine neuen Chat-Tabellen oder UI-Architektur. Basis ist `feat/chat-ux-polish` / PR #17, Commit `2d258f1b7c6312058c18047cc10ddb6df711181d`. PRs #14 → #15 → #16 → #17 sind bei Arbeitsbeginn offen. Die parallel laufende UI-Fidelity (#18) ist keine Voraussetzung. Arbeitskopie: `/tmp/noris-ai-integration`, ausschließlich Branch `feat/noris-ai-integration`.

## Bestand und wiederverwendete Schnittstellen

README, PLAN, Etappe-1-Architektur/-Testbericht, Backend-Router/Settings/Middleware, API-Generator, Compose/Docker/CI sowie Chat-Komponenten, Composables, Modelle und Tests wurden untersucht. Im Repository und den übergeordneten Workspace-Verzeichnissen existiert keine AGENTS.md.

| Bestehende Schnittstelle | Weiterverwendung |
| --- | --- |
| `ChatTransport.stream(ChatRequest, AbortSignal): AsyncIterable<StreamEvent>` | Mock und HTTP-Transport implementieren denselben Vertrag |
| `ChatRequest` | `generationId`, `conversationId`, `inputMessageId`, `modelId`, `messages`, `attempt`; dieselben JSON-Namen |
| `StreamEvent` | `seq` ab 1; started, output_text.delta, completed, cancelled, failed mit code/message |
| `useChatStream` | Unveränderte Zustandsmaschine, Textlimit, Stop und Fehleranzeige |
| `createChatState.generate` / `visiblePath` | Nur Parent-Pfad bis zur ausgewählten User-Nachricht; keine Schwesterantworten im Prompt |
| Regeneration/Edit/Retry | Neue Assistant-Variante; ursprüngliche Knoten und Entwürfe bleiben erhalten |
| `CHAT_MODELS` / `useModelSelection` | Bestehende Auswahl erhält im Real-Modus konfigurierte Backend-IDs |
| FastAPI `create_app`, Settings, Fehlerobjekte | Ergänzende `/api/v1/llm`-Router; bestehende Healthchecks bleiben unabhängig |
| Nuxt/Caddy | Relative Same-Origin-API; Caddy unterstützt bereits `flush_interval -1` |

## Tatsächliche Noris-API

Am 2026-10-09 anhand der vom Auftraggeber genannten [Noris-Dokumentation](https://noris.cloud/nai/) überprüft: Basis `https://ai.noris.de/v1`, [Bearer-Key](https://noris.cloud/nai/api/authentication/), [POST /chat/completions](https://noris.cloud/nai/api/chat-completions/) mit `stream: true` und `max_tokens`. Rollen system/user/assistant sind dokumentiert; diese Integration akzeptiert vom Browser ausschließlich user/assistant. Keine privilegierten System-/Developer-Anweisungen aus Nutzerdaten.

Die [Modellübersicht](https://noris.cloud/nai/models/) nennt Generierungs-, Embedding- und Reranking-Modelle. Der [GPT-OSS-Modellvertrag](https://noris.cloud/nai/models/gpt-oss-120b/) dokumentiert die stabile ID `vllm/release/gpt-oss-120b` und 128K Kontext. Konfigurationsbeispiele nutzen diese belegte ID, nicht die bisherigen Demo-Namen. Entitlements und aktuelle Laufzeitverfügbarkeit sind ohne Key ungeprüft. Modelle werden ausschließlich durch den Betreiber freigeschaltet; keine automatische Übernahme beliebiger Provider-Modelle.

401-Fehler mit `error.message/type` sind dokumentiert. Genaue Noris-Timeouts, Quotas und eine dedizierte Cancel-API sind nicht verifiziert; die Streaming-/Rate-Limit-Unterseiten waren beim Abruf nicht erreichbar. SSE wird gegen den dokumentierten OpenAI-kompatiblen [Chunk-Vertrag](https://developers.openai.com/api/reference/resources/chat/subresources/completions/streaming-events) und lokale HTTP-Fixtures geprüft. Die reale Noris-Verbindung bleibt bis zum ausdrücklich aktivierten Smoke-Test **BLOCKED**.

## Ergänzende API und Provider

`LLMProvider` ist ein austauschbares Python-Protokoll. `OpenAICompatibleProvider` kapselt HTTPX, Provider-Key, Endpoint, Chunk-Validierung, Statusübersetzung und HTTP-Schließung. FastAPI verwaltet den Client im vorhandenen Lifecycle. Kein Browserzugriff auf den Provider; kein Startup-Provider-Request und keine automatischen kostenpflichtigen Retries.

| Endpoint | Vertrag |
| --- | --- |
| `GET /api/v1/llm/models` | Authentifizierter Modellkatalog: ID, Name, available, streaming, Kontext-/Outputlimit, Default-ID |
| `POST /api/v1/llm/chat` | Bestehende ChatRequest als JSON; sequenzierte Etappe-1-Ereignisse als `text/event-stream` |

Vor Streaming gelten die bestehenden `{error:{code,message,request_id}}`-JSON-Fehler. Danach erfolgt `response.failed`; HTTP-Status bleibt 200. Keine internen Exception-/Provider-Texte in Antworten. OpenAPI und TS-Generator werden für POST und SSE erweitert, vorhandene GET-Typen bleiben erhalten. Stop benötigt keinen zusätzlichen Cancel-Endpoint: Fetch-Abbruch schließt die Verbindung und beendet die serverseitige Provider-Iteration.

## Grenzen, Sicherheit und Kontext

Standard ist Provider `disabled` und Frontend `mock`. Real-Modus verlangt explizite URL, Host-Allowlist, Key, Modell-Allowlist, Default-ID, Browser-Origin-Allowlist und separate HTTP-Basic-Zugangsdaten. Provider-Key und Anwendungspasswort dürfen nicht identisch sein. Basic schützt alle LLM-Endpunkte unabhängig vom Reverse-Proxy; produktive Origins und Provider-URLs verlangen HTTPS. Für lokale HTTP-Fixtures ist ausschließlich Loopback in development/test erlaubt. Keine Redirects, Umwelt-Proxys, Browser-Provider-URLs, Toolaufrufe oder Bilder/URL-Inhalte.

Anfragen sind vor Pydantic bytebegrenzt, Nachrichtenanzahl/-länge und Rollenfolge werden validiert. Der gesamte aktive Pfad wird kontrolliert gegen den konfigurierten Kontext geprüft: UTF-8-Bytes plus konservative Nachrichten-/Outputreserve. Das ist keine exakte modellabhängige Tokenisierung; es kann gültige lange Kontexte früher ablehnen. Keine stille Kürzung, Zusammenfassung oder Übernahme ungewählter Varianten.

Nach Stop vor dem ersten Textdelta hält das bestehende Nachrichtenmodell eine leere Assistant-Nachricht im aktiven Pfad. Diese ist als Kontext zulässig und bleibt in Reihenfolge erhalten; leere User-Nachrichten sind unzulässig. Eine neu generierte leere oder reine Whitespace-Antwort endet weiterhin mit INVALID_RESPONSE. Fortsetzung nach frühem Stop wird auch im Browser geprüft.

Verbindungs-, Lese- und Gesamttimeouts, aktive Generierungen, Requestfrequenz, tägliche konservative Tokenreservation und Provider-/Antwortbytes sind begrenzt. Die Tages-/Ratenbudgets sind pro Prozess, reservieren auch fehlgeschlagene Anfragen und überleben keinen Neustart. Für Betrieb dieser Etappe gilt ein Backend-Worker; echte kontenweite Kostenlimits müssen zusätzlich beim Provider gesetzt werden. Kein Claim verteilter Quotas, OIDC, Multi-Tenant-Identität oder serverseitiger Gesprächsautorität.

SSE-Parser puffern unvollständige UTF-8-/Zeilen-/Eventgrenzen begrenzt. Der Adapter verlangt einen gültigen Stop-Finish, nichtleeren Text und `[DONE]`; abgeschnittene Streams sind Fehler. Finish `length` führt zu OUTPUT_LIMIT mit erhaltener Teilantwort. Verbindungsabbruch cancelt auch während Provider-Stille und schließt dessen HTTP-Response. Ob Noris dadurch die GPU-Generierung und Abrechnung sofort stoppt, ist ohne Live-Test **NOT TESTED**; es wird kein Cancel-Endpoint erfunden.

## Parallelentwicklung und Merge

Keine CSS-/Design-Token-, Sidebar-, Composer- oder Scroll-Änderungen. Einzige Komponentenänderung: drei Script-Zeilen in `ChatWorkspace.vue` verdrahten Transport und Modus; Template und Fokus-/Scrollcode bleiben unverändert. `CHAT_MODELS` wird ein Array mit stabiler reaktiver Identität; `ChatModelId` erweitert sich kompatibel von Demo-Literalen auf konfigurierte String-IDs. Header/Composer verwenden ihre vorhandenen Imports und Auswahlkomponenten unverändert. Gemeinsame Dateien: Workspace-Script, useModelSelection, nuxt.config, README und generierte API-Dateien. Bei Zusammenführung mit #18 diese wenigen Schnittstellenänderungen auf dessen UI übernehmen; keine alte Komponentenversion kopieren. Contract-/Branch-/Mock-Regressionstests sichern das ab.

Prüfergebnisse werden nach tatsächlicher Ausführung in `ETAPPE-2-TESTERGEBNISSE.md` mit PASS/FAIL/BLOCKED/NOT TESTED ergänzt. Kein automatischer Merge nach main.
