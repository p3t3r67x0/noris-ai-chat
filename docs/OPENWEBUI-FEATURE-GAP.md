# Open-WebUI-Funktionsaudit für Noris AI Chat

Auditdatum: **18.10.2026**. Untersuchte Noris-Basis: [`1337dc863fa766018178f9c42be1cd6c28bdcf3c`](https://github.com/p3t3r67x0/noris-ai-chat/commit/1337dc863fa766018178f9c42be1cd6c28bdcf3c). Auditbranch: `docs/openwebui-feature-audit`. Umsetzungsvorschläge stehen in der [Entwicklungsroadmap](NORIS-DEVELOPMENT-ROADMAP.md).

## Referenz, Methode und Aussagegrenzen

Die beim Audit über GitHub `/releases/latest` verifizierte stabile Referenz ist **[Open WebUI v0.12.3](https://github.com/open-webui/open-webui/releases/tag/v0.12.3)**, veröffentlicht am **16.10.2026, 11:46:21 UTC**, weder Draft noch Prerelease. Der vollständige Release-Tree verweist auf Commit `91ea4e3421d1d8069f13d4a463fcb5986d94ea60`; dessen `package.json` bestätigt Version `0.12.3`. Verglichen wurden die [offizielle Dokumentation](https://docs.openwebui.com/) und ausgewählte Quelldateien dieses Tags. Dokumentationsseiten sind fortlaufend aktualisiert und nicht automatisch versionsgebunden. Wo keine passende Release-Codeprüfung vorliegt, bezeichnet „Referenz“ den dokumentierten Funktionsumfang, keine lokal ausgeführte Open-WebUI-Abnahme.

Versionsgebundene Gegenproben:

| Bereich | Stabile Quellreferenz |
| --- | --- |
| Chats, Suche und Freigaben | [routers/chats.py](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/chats.py), [SearchModal.svelte](https://github.com/open-webui/open-webui/blob/v0.12.3/src/lib/components/layout/SearchModal.svelte) |
| Ollama-Verwaltung | [routers/ollama.py](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/ollama.py) |
| Audio und Realtime | [routers/audio](https://github.com/open-webui/open-webui/tree/v0.12.3/backend/open_webui/routers/audio), [Kokoro-Worker](https://github.com/open-webui/open-webui/blob/v0.12.3/src/lib/workers/kokoro.worker.ts) |
| Wissen, Skills, Benutzer | [knowledge.py](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/knowledge.py), [skills.py](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/skills.py), [users.py](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/users.py) |

Noris wurde entlang von UI → Vertrag → API → Domain → Persistenz → Provider geprüft. Berücksichtigt wurden `frontend/app`, `backend/src/noris_ai`, sämtliche Migrationsdateien, Testinventar, generierte Verträge, CI und Infrastrukturvorlagen. Ein Menüeintrag oder eine Designdatei gilt allein nicht als implementierte Funktion. Für Fehlbefunde wurden außerdem Begriffe wie `ollama`, `kokoro`, `whisper`, `mcp`, `oidc`, `oauth`, `skills`, `assistants`, `embeddings` und `pgvector` gesucht und Treffer gegen tatsächliche Ausführungspfade geprüft. Beispielsweise sind MCP-Beispieltitel keine MCP-Integration; die Erkennung eines Embedding-Modells im Katalog ist keine Embedding-Pipeline.

**Bewertungsmaßstab:** `vorhanden` = beschriebener Noris-Umfang durch Code belegt; `teilweise` = ausführbarer Teil vorhanden, relevante Referenzteile fehlen; `fehlt` = kein vollständiger Implementierungspfad im untersuchten Stand; `fehlerhaft` = reproduzierter Defekt; `nicht anwendbar` = kein entsprechender Vergleichsgegenstand. Fehlende Funktionen sind keine automatisch nachgewiesenen Fehler. In diesem Audit wurde kein Produktdefekt reproduziert, der die Gesamtbewertung `fehlerhaft` rechtfertigt. „Fehlt“ bezieht sich auf dieses Repository, nicht auf unbekannte externe Dienste.

Bewertet wird vorrangig der persistente WebSocket-Pfad. Die drei Transportarten `mock`, `real` und `websocket` sind in [useChatTransport.ts](../frontend/app/composables/useChatTransport.ts) getrennt. Die lokale Demo und die zustandslose HTTP-Vorschau beweisen keine Serverpersistenz. Aktive Produktionskonfiguration, private Modellfreigaben, Infrastrukturverschlüsselung und reale Providerqualität wurden nicht untersucht; diese Befunde bleiben ausdrücklich **offen**. Es wurden keine lokalen Secrets-Dateien ausgelesen, keine produktiven Einstellungen verändert, keine Dienste gestartet und keine Migrationen ausgeführt.

Aufwandsschätzungen sind zusätzliche **Personentage (PT, 8 Stunden)** für Implementierung, Migration, aussagekräftige Tests und Dokumentation durch eine mit dem Projekt vertraute Fachkraft. Sie sind Bandbreiten, keine Angebote; Betriebskosten und externe Freigaben sind nicht enthalten. Gemeinsame Grundlagen sind nur einmal zu planen. Die Zeilen dürfen deshalb nicht ungeprüft summiert werden.

## Ist-Zustand und Architektur

Noris besitzt einen umfangreichen Chatkern: PostgreSQL als Datenquelle, unveränderliche Nachrichtenbäume, Antwortvarianten, Entwürfe, Versionskonflikte, automatische Titel, Archivierung, Pinning und fortsetzbare WebSocket-Ereignisse. Datei- und Visionpfade, lokale PDF-Selektion, Lernmodus sowie eine begrenzte Webrecherche sind implementiert. Größte Paritätslücken bestehen bei Workspace-Funktionen, Audiowiedergabe, mehreren Providerverbindungen, Wissenssammlungen und echten Benutzeridentitäten.

Die zu erhaltenden Grenzen sind in [main.py](../backend/src/noris_ai/main.py), [ChatService](../backend/src/noris_ai/chat/service.py), [GenerationManager](../backend/src/noris_ai/chat/generation.py), [LLMProvider](../backend/src/noris_ai/llm/provider.py), [ToolRuntime](../backend/src/noris_ai/tools/runtime.py) und [useWorkspace](../frontend/app/composables/useWorkspace.ts) sichtbar:

- Nuxt/Vue/Nuxt UI: vorhandene Composables, ein Composer, getrennte Transportadapter und generierte TypeScript-Verträge.
- FastAPI: REST für Ressourcen und WebSocket für Generierung/Replay; kein zweiter Chatserver für neue Funktionen.
- SQLAlchemy/Alembic/PostgreSQL: Eigentümerprüfung, Nachrichtenbaum, Generierungen, Dateien, Tools und Budgets bleiben gemeinsam verwaltet.
- HTTPX-Provideradapter: derzeit eine konfigurierte OpenAI-kompatible Verbindung; Katalogdaten und lokale Sicherheits-/Fähigkeitsprofile sind getrennt.
- Tool-Runtime: typisierte Registry, persistente Runs, Freigaben, Budgets und Ereignisse; Websuche und Quellenabruf laufen durch diese Runtime.

Die Abhängigkeitsstände sind aus den [Frontend-](../frontend/package.json) und [Backend-Manifesten](../backend/pyproject.toml) abzuleiten. Ältere README-/Planungsangaben weichen teilweise ab. Insbesondere ist die frühere [FEATURE-ROADMAP.md](FEATURE-ROADMAP.md) eine Planung mit inzwischen umgesetzten Teilen, kein verlässlicher aktueller Fehlbestand. Ihre Bezeichnungen „P0–P12“ sind Paketnummern und nicht die Prioritätsklassen dieses Audits.

## Vollständige Übersicht der 24 angeforderten Bereiche

Die Detailprofile darunter enthalten Beschreibung, Referenz, Codebeleg, Abhängigkeiten, Sicherheitsanforderungen und Tests je Bereich. Die Statusangabe fasst den gesamten Bereich zusammen; Unterfunktionen werden im Profil einzeln abgegrenzt.

| ID | Funktion | Status | Belegter Bestand / wesentliche Lücke | Priorität | Zusätzlicher Aufwand |
| --- | --- | --- | --- | --- | --- |
| F01 | Chat und Konversationsverwaltung | teilweise | Persistenz, Zweige, Titel, Archiv, Pins vorhanden; Ordner, Teilen und vollständige Portabilität fehlen | P0 Kern/Portabilität; P2 Organisation | 10–18 PT |
| F02 | Chat-Suche und Filter | teilweise | Titel-/Nachrichtensuche, Snippets, Sprungziel; keine Token-AND-Semantik oder Filtergrammatik | P0 | 6–10 PT |
| F03 | Modellverwaltung und Wechsel | teilweise | Discovery, Auswahl, Limits, Fähigkeiten; keine mehreren Verbindungen oder administrierbaren Presets | P1 | 10–18 PT |
| F04 | Ollama | fehlt | Kein nativer Adapter oder Modell-Lifecycle; OpenAI-Protokoll allein reicht nicht | P1 | 8–15 PT |
| F05 | OpenAI-kompatible APIs | teilweise | Ausgehende Discovery/Chat-SSE vorhanden; keine allgemeine eingehende Kompatibilitäts-API | P1 ausgehend; P3 eingehend | 7–12 PT |
| F06 | Dokumenten-Uploads | teilweise | TXT/MD/PDF/PNG/JPEG vorhanden; Bibliothek, Office/OCR und Mehrfachbindung fehlen | P1 | 10–18 PT |
| F07 | RAG und Wissen | teilweise | Lokale lexikalische PDF-Selektion; keine Wissenssammlungen/Embedding-Suche | P1 | 20–35 PT |
| F08 | Spracheingabe/STT | teilweise | Browser-Web-Speech mit DE/EN; kein serverseitiger STT-Provider | P1 Basis; P3 weitere Engines | 6–10 PT |
| F09 | Kokoro/TTS | fehlt | Weder Audio-API noch Vorlesen, Stimmenwahl oder Kokoro-Worker | P1 | 8–14 PT Serverpfad; weitere 5–9 PT Browserpfad |
| F10 | Sprachgespräche | fehlt | Diktat ersetzt keinen Sprachdialog; VAD, Abspielen und Realtime fehlen | P3 | 15–25 PT Standard; weitere 12–20 PT Realtime |
| F11 | Websuche | teilweise | SearXNG, sichere Fetches, Grounding, Zitate vorhanden; Providerbreite und autonome Suche fehlen | P2 | 6–12 PT |
| F12 | Function Calling | fehlt | Modell-Toolcalls werden abgelehnt; interne Tool-Runtime ist bereits vorhanden | P2 | 12–20 PT |
| F13 | MCP und externe Werkzeuge | teilweise | Interne externe HTTP-Provider vorhanden; kein MCP-/OpenAPI-Serverkatalog | P2 | 12–20 PT |
| F14 | Benutzerdefinierte Assistenten | fehlt | Keine persistenten, bearbeitbaren Assistenten-Presets | P2 | 10–16 PT |
| F15 | Skills und Agenten | teilweise | Begrenzte Research-Orchestrierung vorhanden; keine Skills oder allgemeinen Agenten/Subagenten | P2 | 15–25 PT |
| F16 | Prompt-Bibliothek | fehlt | Keine Promptressourcen, Variablenformulare, Versionierung oder Freigaben | P2 | 7–12 PT |
| F17 | Slash-Kommandos | teilweise | Lokale Aktionsbefehle vorhanden; benutzerdefinierte Promptkommandos fehlen | P0 Bestand sichern; P2 Ausbau | 3–5 PT |
| F18 | Lernmodus | vorhanden | Persistenter Modus, serverseitige Tutoring-Policy und Zweigzustand | P2 Qualitätsausbau | 2–4 PT |
| F19 | Bildanalyse/-generierung | teilweise | PNG/JPEG-Vision vorhanden; Generieren, Bearbeiten und Sketch fehlen | P1 Vision sichern; P3 Ausbau | 15–25 PT |
| F20 | Benutzerverwaltung | fehlt | Basic-Auth für gemeinsamen Owner; keine individuellen Konten/SSO/MFA | P0 vor Mehrbenutzerbetrieb; P3 Komfort | 15–25 PT |
| F21 | Rollen/Berechtigungen | teilweise | Owner-Prüfungen und Tool-Policy vorhanden; keine Nutzer-/Gruppen-RBAC | P0 vor Mehrbenutzerbetrieb; P3 Verwaltung | 12–20 PT |
| F22 | Administration/Statistiken | teilweise | Health/Readiness, Budgets und Limits; keine Adminoberfläche oder Nutzungsanalytik | P3 | 10–18 PT |
| F23 | Datenschutz/Sicherheit | teilweise | Umfangreiche technische Schutzmaßnahmen; Retention, Hard-Delete und Betriebsnachweise offen | P0 Grundlagen; P3 Governance | 10–18 PT |
| F24 | Mobile UX/Accessibility | teilweise | Responsive Layouts, Tastatur/Fokus und Browserprüfungen; keine umfassende Accessibility-/PWA-Abnahme | P0 | 5–9 PT |

Es ergibt sich **1 × vorhanden, 16 × teilweise, 7 × fehlt** auf Bereichsebene. Das ist kein prozentualer Paritätsgrad: Aufwand und Umfang der Bereiche unterscheiden sich stark.

## Detailprofile

### F01 — Chat und Konversationsverwaltung

**Beschreibung/Referenz:** Dauerhafte Unterhaltungen bearbeiten, verzweigen, organisieren und übertragen. Open WebUI dokumentiert [Ordner/Projekte](https://docs.openwebui.com/features/chat-conversations/chat-features/conversation-organization), [Import/Export](https://docs.openwebui.com/features/chat-conversations/data-controls/import-export), [Multi-Modell-Chats](https://docs.openwebui.com/features/chat-conversations/chat-features/multi-model-chats) und [Nachrichtenwarteschlangen](https://docs.openwebui.com/features/chat-conversations/chat-features/message-queue).

**Ist/Status: teilweise.** Vorhanden: serverseitige Chats/Entwürfe/Präferenzen, Pagination, automatisches/manuelles Benennen, Archiv/Restore, Pin/Unpin, Soft-Delete, Edit als Zweig, Regenerate, Varianten, Abbruch, Fortsetzung und Stream-Replay. Ein lokaler Noris-Snapshot lässt sich in die Serverpersistenz importieren. Ein vollständiger Datei-Export, fremde Importformate, Ordner/Tags/Projektkontext, Freigabelinks, gleichzeitiger Modellvergleich, manuelle Ungelesen-Markierungen und eine Nutzer-Nachrichtenwarteschlange fehlen. Die interne Stream-Queue ist keine solche Produktwarteschlange. Gleichzeitiges Arbeiten mehrerer Tabs desselben Owners ist keine Mehrbenutzerkollaboration.

**Quellbelege:** [Chat-Modelle](../backend/src/noris_ai/chat/models.py), [REST-Routen](../backend/src/noris_ai/api/v1/conversations.py), [GenerationManager](../backend/src/noris_ai/chat/generation.py), [useChat](../frontend/app/composables/useChat.ts), [Import-/Persistenzadapter](../frontend/app/composables/useChatBackend.ts). **Abhängigkeiten:** Bestehenden Baum, Versionsprüfungen, Cursor und Draftqueue erweitern; Organisation/Freigaben benötigen neue relationale Ressourcen und F20/F21.

**Sicherheit:** Export nur aus autorisiertem Scope; Import mit Größen-/Topologiegrenzen; keine Dateipfade/Secrets; Freigaben mit explizitem Widerruf und separaten Rechten. **Tests:** Bestehend [Chat-API](../backend/tests/integration/test_chat_api.py), [WebSocket](../backend/tests/integration/test_chat_websocket.py), [Varianten](../frontend/tests/e2e/chat-branches.spec.ts), [Import](../frontend/tests/websocket/import.spec.ts). Ergänzen: Export→Import-Roundtrip mit Zweigen, Fehlerzuständen und Anhängen; manipulierte Snapshots; getrennte Rechte; Warteschlangen-Abbruch. **Aufwand/Priorität:** P0 Portabilität und Bestand 4–7 PT; P2 Ordner/Tags 6–11 PT. Kollaboration und Mehrmodell-UX sind zusätzliche, noch separat zu schneidende P3-Pakete.

### F02 — Chat-Suche und Suchfilter

**Beschreibung/Referenz:** Historie durchsuchen und Treffer eingrenzen. [History & Search](https://docs.openwebui.com/features/chat-conversations/chat-features/history-search) beschreibt Wort-AND, Phrasenbevorzugung und Präfixfilter. v0.12.3 erweitert außerdem die [Workspace-Suche](https://github.com/open-webui/open-webui/releases/tag/v0.12.3) über mehrere Ressourcentypen.

**Ist/Status: teilweise.** Vorhanden: ownerbegrenzte Suche in Titeln und User-/Assistant-Text, neuester Nachrichtentreffer je Gespräch, Textausschnitt, sichere Hervorhebung, Cursor, Request-Abbruch, 200-ms-Debounce und Sprung zur Nachricht. Die SQL-Abfrage behandelt den gesamten Suchtext als zusammenhängenden Substring. `docker healthcheck` findet daher keinen Chat, dessen Wörter auf Titel und verschiedene Nachrichten verteilt sind. Die API kennt `archived`, `archiveOnly` und `pinned`; der Suchdialog übermittelt keine entsprechende Filtergrammatik. Kategorien „Bilder“, „Dokumente“, „Pages“ und „Projekte“ sind ausdrücklich deaktiviert. Kein Ranking nach Relevanz, keine Tags/Ordner-/Freigabefilter. Nachrichtensuche berücksichtigt auch andere Zweige desselben Chats; das ist eine dokumentationsbedürftige Semantik, kein nachgewiesener Defekt.

**Quellbelege:** [`conversation_page`](../backend/src/noris_ai/chat/pagination.py), [Snippet-Abfrage](../backend/src/noris_ai/chat/service.py), [Suchkoordination](../frontend/app/composables/useConversationSearch.ts), [Suchdialog](../frontend/app/components/chat/ChatSearchDialog.vue), [Suchindizes](../backend/src/noris_ai/chat/models.py). Ein GIN-Trigrammindex existiert für `lower(title)`; für `lower(chat_message.content)` ist kein entsprechender Suchindex definiert. Daraus folgt ein **zu messendes** Skalierungsrisiko, kein gemessener Performancefehler.

**Abhängigkeiten:** Bestehende REST-/Cursor-Suche beibehalten; Filterparser, Suchvertrag und passende Indizes ergänzen. Ordner-/Tagfilter erst mit F01. **Sicherheit:** Parametrisierte Abfragen, `%`/`_` als Literal, Owner-/Archivscope vor Snippets, Cursor an Filter binden, kein HTML aus Treffern. **Tests:** Bestehend [Pagination](../backend/tests/integration/test_chat_pagination.py), [Nachrichtensprung](../frontend/tests/websocket/message-search.spec.ts), [Such-Unit](../frontend/tests/unit/conversation-search.spec.ts). Ergänzen: AND über mehrere Nachrichten, Unicode, kombinierte Filter, versteckte Zweige, fremde IDs, Cursorwechsel sowie `EXPLAIN ANALYZE` mit synthetischen Großbeständen. **Aufwand/Priorität:** **P0, 6–10 PT**, ohne erst später verfügbare Ressourcentypen.

### F03 — Modellverwaltung und Modellwechsel

**Beschreibung/Referenz:** Modelle entdecken, auswählen und konfigurieren. Open WebUI verbindet [mehrere Provider](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider) und bietet [Modell-Presets](https://docs.openwebui.com/features/workspace/models).

**Ist/Status: teilweise.** Vorhanden: `/models`-Discovery mit Cache/TTL, Fehler-/Stale-Behandlung, Katalog-Metadaten, exakte Modell-ID-Policies, Kontext-/Ausgabelimits, Preis-/Capability-Daten, Auswahl und gespeicherte Präferenz. Fähigkeiten werden nicht allein aus Marketingnamen abgeleitet. Modellwechsel für neue Turns und Regenerate vorhanden; Änderungen während laufender Generierung werden kontrolliert. Fehlend: mehrere administrierbare Verbindungen mit getrennten Zugangsdaten, Verbindungstest-UI, Alias-/Preset-CRUD, Gruppenfreigaben, Modell-Lifecycle und paralleler Vergleich.

**Quellbelege:** [Katalog](../backend/src/noris_ai/llm/catalog.py), [Registry](../backend/src/noris_ai/llm/registry.py), [Provider-Metadaten](../backend/src/noris_ai/llm/provider_models.py), [Modellauswahl](../frontend/app/composables/useModelSelection.ts), [Modelleinstellungen](../frontend/app/pages/settings/models.vue). **Abhängigkeiten:** Bestehendes `LLMProvider`/Katalog-Gateway um Verbindungsidentitäten erweitern; Presets siehe F14; Rechte siehe F21.

**Sicherheit:** Schlüssel ausschließlich serverseitig; Zielhost-Allowlist und TLS; Modellfreigabe beim Generieren erneut prüfen; abgelaufene Fähigkeiten sperren. **Tests:** Bestehend [Katalogtests](../backend/tests/unit/test_model_catalog.py), [Capability-Tests](../backend/tests/unit/test_provider_capabilities.py), [UI-Auswahl](../frontend/tests/unit/model-selection.spec.ts). Ergänzen: gleiche Modell-ID auf zwei Verbindungen, widerrufene Freigabe, Ausfall/Refresh beim Wechsel, Limits pro Verbindung. **Aufwand/Priorität:** **P1, 10–18 PT**, ohne Ollama-Lifecycle und Assistenteneditor.

### F04 — Ollama-Integration

**Beschreibung/Referenz:** [Native Ollama-Anbindung](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-ollama) einschließlich Modellverwaltung; der stabile [Ollama-Router](https://github.com/open-webui/open-webui/blob/v0.12.3/backend/open_webui/routers/ollama.py) implementiert unter anderem Tags, Pull und Create.

**Ist/Status: fehlt.** Kein Ollama-Provider, `/api/tags`-/Pull-/Delete-Pfad oder Modelfile-Editor im Noris-Code. Der OpenAI-kompatible Adapter könnte nach Vertragsprüfung einzelne Chatfunktionen eines kompatiblen Endpunkts nutzen; dies wurde nicht live geprüft und ist keine native Integration. Aktuelle Konfiguration verlangt API-Key und in Produktion HTTPS, weshalb eine übliche ungeschützte Ollama-HTTP-Adresse nicht einfach als unterstützt gelten kann.

**Quellbelege/Negativscope:** [Providerprotokoll](../backend/src/noris_ai/llm/provider.py), [einziger HTTP-Adapter](../backend/src/noris_ai/llm/openai_compatible.py), [Konfigurationsvalidator](../backend/src/noris_ai/core/config.py); kein Ollama-Modul unter `backend/src/noris_ai/llm`. **Abhängigkeiten:** F03-Verbindungen, separates Ollama-Protokoll im vorhandenen Providerinterface; Lifecycle als begrenzte Adminoperation.

**Sicherheit:** Lokale/private Ziele nur explizit erlauben; Downloadgröße, Parallelität und Registry-Ziele begrenzen; kein beliebiger Host-/Dateizugriff über Modelfiles. **Tests:** Ollama-HTTP-Fixtures für Discovery, NDJSON-Streaming, Abbruch, Pull-Fortschritt und Fehler; Lifecycle-Rechte; optionaler separater Ollama-Testcontainer. **Aufwand/Priorität:** **P1, 8–15 PT** für Chatadapter und grundlegenden Pull/Delete; erweiterte Modelfile-/Push-Funktionen zusätzlich schätzen.

### F05 — OpenAI-kompatible APIs

**Beschreibung/Referenz:** [Kompatible Provider anbinden](https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible); Open WebUI stellt daneben [eigene API-Endpunkte](https://docs.openwebui.com/reference/api-endpoints) bereit.

**Ist/Status: teilweise.** Der ausgehende Noris-Pfad für `GET /models` und `POST /chat/completions` mit SSE ist **vorhanden**, einschließlich Timeouts, Kontext-/Budgetprüfung, Fehlernormalisierung, Reasoning-Mapping und Vision. Eine Verbindung ist konfigurierbar. Streaming erwartet eine einzelne Choice. Responses/Open Responses, allgemeines Structured Output, mehrere Verbindungen und eingehende OpenAI-kompatible Chat-/Audio-/Embedding-Endpunkte fehlen. Auch die von Open WebUI als experimentell dokumentierten [direkten Browser-Verbindungen](https://docs.openwebui.com/features/chat-conversations/direct-connections) fehlen; ein solcher zusätzlicher Clientpfad benötigt eine eigene Entscheidung zur Credentialablage und ist nicht Teil des ersten Adapterausbaus. Noris-REST und WebSocket sind eigene Verträge. Die Konformität zu beliebigen kompatiblen Diensten bleibt ohne deren Vertragstests offen.

**Quellbelege:** [HTTPX-Adapter](../backend/src/noris_ai/llm/openai_compatible.py), [Gateway](../backend/src/noris_ai/llm/gateway.py), [LLM-Routen](../backend/src/noris_ai/api/v1/llm.py), [OpenAPI](api/openapi.json). **Abhängigkeiten:** Adaptergrenzen erhalten; F03 für mehrere Verbindungen; eingehenden Kompatibilitätsadapter ausdrücklich separat vom internen Chatvertrag planen.

**Sicherheit:** Keine Providerkeys an Browser, keine Redirects/Proxy-Vererbung, feste Hosts, Request-/Response-Limits und authentifizierte API-Nutzung. **Tests:** Bestehend [Provider-SSE](../backend/tests/unit/test_llm_provider.py), [HTTP-Streaming](../backend/tests/llm_integration/test_http_streaming.py), [API-Vertrag](../backend/tests/contract/test_openapi.py). Ergänzen: protokollspezifische Fixtures, Structured-Output-Validierung, stabile Fehlercodes; externe APIs nur nach gesonderter Freigabe. **Aufwand/Priorität:** P1 Kompatibilitätsausbau **4–7 PT**; P3 eingehender Adapter **3–5 PT**. Function Calling in F12, nicht doppelt schätzen.

### F06 — Dokumenten-Uploads

**Beschreibung/Referenz:** Dateien sicher verarbeiten und wiederverwenden; [Dateiverwaltung](https://docs.openwebui.com/features/chat-conversations/data-controls/files) und [Dokumentenextraktion](https://docs.openwebui.com/features/chat-conversations/rag/document-extraction).

**Ist/Status: teilweise.** TXT/Markdown, extrahierbare PDFs sowie PNG/JPEG sind authentifiziert hochladbar, privat gespeichert und nach Reload verfügbar. Parser laufen mit Ressourcenlimits in einem separaten Prozess. PDF-Seiten und Text werden begrenzt extrahiert; Bilder werden validiert. Standardlimits im Code: 10 MiB/Datei, fünf Dateien, 100 MiB/Owner, 100 PDF-Seiten; Laufzeitwerte wurden nicht geprüft. Fehlend: globale Dateibibliothek und Wiederverwendung über Memberships, Office/Tabellen/Präsentationen, OCR für Scans, Audio/Videoextraktion und Verarbeitungsschlange für große Jobs. Der Bibliothekseintrag im Plus-Menü besitzt keinen Handler.

**Quellbelege:** [AttachmentService](../backend/src/noris_ai/chat/attachments.py), [Parser](../backend/src/noris_ai/chat/attachment_parser.py), [Attachment-Routen](../backend/src/noris_ai/api/v1/attachments.py), [Upload-Composable](../frontend/app/composables/useChatAttachments.ts), [Menü](../frontend/app/lib/chat/composerMenu.ts). **Abhängigkeiten:** Bestehende Uploads/Quoten erhalten; [FILE-LIBRARY-DESIGN.md](FILE-LIBRARY-DESIGN.md) ist Vorarbeit, keine Implementierung; neue Extraktoren als Adapter.

**Sicherheit:** MIME/Signatur, Pfad- und Symlinkschutz, Parserlimits, Ownerrechte, Schadinhalt als untrusted data; Mehrfachbindung vor Löschung berücksichtigen. **Tests:** Bestehend [Attachments](../backend/tests/integration/test_attachments.py), [PDF](../backend/tests/unit/test_pdf_documents.py), [Browser-Upload](../frontend/tests/websocket/attachments.spec.ts). Ergänzen: OCR-/Office-Fixtures, Parserabsturz, Mehrfachbindung/Löschrace, Job-Recovery, Bibliothekspagination. **Aufwand/Priorität:** **P1, 10–18 PT** für Bibliothek und erste zusätzliche Extraktion; weitere Formate separat, gemeinsame RAG-Arbeit nur einmal buchen.

### F07 — RAG und Wissensdatenbanken

**Beschreibung/Referenz:** [RAG](https://docs.openwebui.com/features/chat-conversations/rag) und [Wissenssammlungen](https://docs.openwebui.com/features/workspace/knowledge) liefern gezielt Dokumentkontext und Quellen über mehrere Dateien/Gespräche.

**Ist/Status: teilweise.** Eine echte Retrieval-Vorstufe ist vorhanden: `pdf_request` gewichtet lexikalisch PDF-Abschnitte, wählt bei allgemeinen Fragen verteilt Abschnitte aus und hält Seitenbezüge und Kontextbudgets ein. Diese Funktion wird nicht neu geplant. Es fehlen beständige Wissenssammlungen, allgemeines Chunking/Embedding, Vektor-/hybride Suche, Reranking, Reindexierung und Collection-Rechte. Die Modellkategorie Embedding ist nur Katalogklassifikation. Textanhänge im Prompt und Web-Grounding ersetzen keine solche Wissensverwaltung.

**Quellbelege:** [PDF-Retrieval](../backend/src/noris_ai/chat/pdf_context.py), [Anhangsinhalte](../backend/src/noris_ai/chat/attachment_content.py), [Gatewayintegration](../backend/src/noris_ai/llm/gateway.py), [Attachment-Datenmodell](../backend/src/noris_ai/chat/models.py). **Abhängigkeiten:** F06-Mehrfachbindung, Index-/Embedding-Providervertrag, Alembic und begrenzte Indexjobs; Entscheidung für PostgreSQL-Erweiterung oder externen Index erst nach Qualitäts-/Betriebsvergleich. Bestehende PostgreSQL-Architektur erhalten.

**Sicherheit:** Rechte vor Retrieval und Quellenauflösung; Löschung bis in Index/Caches; kein Cross-Owner-Treffer; Indexversion und Embeddingmodell nachvollziehbar; Dokumentinstruktionen unvertrauenswürdig. **Tests:** Bestehend [PDF-Kontext](../backend/tests/unit/test_pdf_documents.py), [PDF-Integration](../backend/tests/integration/test_pdf_documents.py). Ergänzen: Goldfragen mit erwarteten Quellen, Recall und Antwortbeleg, mehrsprachige Dokumente, Reindexierung/Retry, Modellwechsel, ACL-/Delete-Leaktests. **Aufwand/Priorität:** **P1, 20–35 PT**, einschließlich Indexpipeline, Collections, Retrieval und Quellen-UI, ohne F06-Arbeit doppelt zu rechnen.

### F08 — Spracheingabe und Spracherkennung

**Beschreibung/Referenz:** [STT-Konfiguration](https://docs.openwebui.com/features/chat-conversations/audio/speech-to-text/stt-config) umfasst Browsererkennung, lokale Whisper- und externe Transkriptionsdienste.

**Ist/Status: teilweise.** `SpeechRecognition`/`webkitSpeechRecognition` diktieren bestätigte Ergebnisse in den vorhandenen Composer; DE/EN-Locale, Fehlerstatus und Abbruch beim Verlassen sind vorhanden. Keine Audio-Upload-/Transkriptionsroute, keine Whisperinstallation und kein STT-Providerwechsel. Browserunterstützung und Datenverarbeitung durch den jeweiligen Browserdienst bleiben geräteabhängig; lokale Verarbeitung ist dadurch nicht belegt.

**Quellbelege:** [Diktat](../frontend/app/composables/useComposerDictation.ts), [Composer](../frontend/app/components/chat/ChatComposer.vue), [API-Komposition](../backend/src/noris_ai/main.py), [öffentlicher Routenvertrag](api/openapi.json). **Abhängigkeiten:** Getrennter STT-Adapter, begrenztes Aufnahme-/Uploadformat, Audio-Service neben bestehendem Chat-Gateway; keine Änderung der Textpersistenz erforderlich.

**Sicherheit:** Explizite Mikrofonfreigabe, sichtbarer Aufnahmestatus, Stop auf Navigation, kurzer Audio-Lebenszyklus, Provider-/Datenweg transparent. **Tests:** Bestehend [Diktat-Unit](../frontend/tests/unit/composer-dictation.spec.ts). Ergänzen: verweigerte Berechtigung, fehlende API, reale Browser DE/EN, Format-/Zeit-/Bytelimits, STT-Ausfall und kein doppeltes Einfügen. **Aufwand/Priorität:** **P1, 6–10 PT** für einen serverseitigen STT-Pfad; weitere Engines P3 separat.

### F09 — Kokoro-TTS-Integration

**Beschreibung/Referenz:** Open WebUI besitzt **Kokoro.js im Browser**, belegt durch den [Worker in v0.12.3](https://github.com/open-webui/open-webui/blob/v0.12.3/src/lib/workers/kokoro.worker.ts). Zusätzlich beschreibt der [Kokoro-Web-Leitfaden](https://docs.openwebui.com/features/chat-conversations/audio/text-to-speech/kokoro-web-integration) einen externen OpenAI-kompatiblen TTS-Dienst. Letzterer ist eine Community-Anleitung und kein eingebauter Kokoro-Server.

**Ist/Status: fehlt.** Keine TTS-Schnittstelle, kein Speech-Provider, kein Audio-Player oder Kokoro-Modell im Repository. Browser-STT ist unabhängig davon. Die beiden Open-WebUI-Wege sind getrennte Paritätsziele.

**Quellbelege/Negativscope:** [Composer-Diktat](../frontend/app/composables/useComposerDictation.ts), [Nachrichtenaktionen](../frontend/app/components/chat/ChatMessage.vue), [Frontend-Abhängigkeiten](../frontend/package.json), [Backend-Abhängigkeiten](../backend/pyproject.toml). **Abhängigkeiten:** Zunächst einen authentifizierten serverseitigen TTS-Adapter für einen explizit konfigurierten Kokoro-Dienst und Vorleseaktionen ergänzen; kein Modellserver im Chatprozess. Browser-Kokoro optional als eigener Workerpfad mit Modellcache.

**Sicherheit:** Text nur nach Nutzeraktion übertragen, Stimmen/Modelle erlaubnisgebunden, Byte-/Zeit-/Kostenlimits, abbrechbare Ausgabe und private Audio-Caches. Browsermodell-Downloads müssen nachvollziehbare Herkunft/Version haben. Keine externen Keys im Client. **Tests:** Dienstfixture für Sprach-/Stimmenwahl, Satzsegmentierung, Stop/Navigation, lange Antworten, Audiofehler und ACL; Endgerätetests für DE/EN-Qualität und Latenz. Browserpfad zusätzlich Modellcache, Offlinebetrieb und Speichergrenzen prüfen. **Aufwand/Priorität:** **P1, 8–14 PT** für Dienst und Vorlesen; zusätzliche **5–9 PT** für Browser-Kokoro. Stimmen-/Sprachqualität vor Abnahme verifizieren.

### F10 — Sprachgespräche

**Beschreibung/Referenz:** [Voice Mode](https://docs.openwebui.com/features/chat-conversations/chat-features/voice-mode) verbindet Aufnahme, STT, Chat und satzweise TTS; Realtime ist ein zusätzlicher Speech-to-Speech-Modus.

**Ist/Status: fehlt.** Diktat liefert nur Text in den Composer. Es gibt keinen Anrufzustand, keine VAD/Endpunkterkennung, keine automatische Sprachausgabe, Unterbrechung einer gesprochenen Antwort oder Realtime-Sitzung. Visionanhänge sind kein Kamera-/Screenshare-Dialog.

**Quellbelege/Negativscope:** [Diktat](../frontend/app/composables/useComposerDictation.ts), [Chat-Transport](../frontend/app/composables/useChatTransport.ts), [WebSocket-Vertrag](websocket/chat-v1.json). **Abhängigkeiten:** F08/F09; zuerst Standarddialog als zusätzlicher UI-Zustand über bestehender Textgenerierung, danach eigener begrenzter Realtime-Provideradapter.

**Sicherheit:** Mikrofon/Kamera/Screen separat aktivieren, sichere Transportverbindung, ephemere Providerberechtigung und vollständiger Geräte-Stop bei Beenden/Disconnect. **Tests:** deterministische Aufnahme-/Wiedergabe-Fixtures, Unterbrechung, doppelte Transkripte, Race beim Gesprächswechsel, Wiederverbindung, Autoplay-/Mobilbrowser und Geräteverlust. **Aufwand/Priorität:** **P3, 15–25 PT** Standarddialog; weitere **12–20 PT** Realtime, ohne erneute STT-/TTS-Grundentwicklung.

### F11 — Websuche

**Beschreibung/Referenz:** [Websuche](https://docs.openwebui.com/features/chat-conversations/web-search) und [agentische Recherche](https://docs.openwebui.com/features/chat-conversations/web-search/agentic-search) verbinden Suchprovider, Quellen und Antwortbelege.

**Ist/Status: teilweise.** SearXNG-Adapter, kontrollierter Quellenabruf mit DNS-/Adressprüfung, Extraktion, persistente Tool-Runs, Budgets, Researchplan/-zustand, Grounding, Zitate und Quellenpanel sind vorhanden. Plus-Menü und `/suche` aktivieren den bestehenden Webmodus. Such-, Fetch- und Research-Flags sind im Code standardmäßig aus; UI-Capability und Betreiberrechte entscheiden zur Laufzeit. Die reale Aktivierung wurde nicht überprüft. `plan_research` ist eine deterministische, begrenzte Serverentscheidung. Es fehlen ein allgemeiner autonomer Modell-Suchloop, weitere Suchprovider, Speichern in Wissenssammlungen und ein separat nutzbarer umfangreicher Deep-Research-Modus. Der eigene Deep-Research-Menüeintrag hat keinen Handler; vorhandene Research-Orchestrierung wird dennoch wiederverwendet.

**Quellbelege:** [SearXNG](../backend/src/noris_ai/tools/providers/searxng.py), [Netzwerkschutz](../backend/src/noris_ai/tools/providers/network.py), [Orchestrator](../backend/src/noris_ai/research/orchestrator.py), [Planner](../backend/src/noris_ai/research/planner.py), [Quellenpanel](../frontend/app/components/chat/ResearchPanel.vue). **Abhängigkeiten:** F12 für modellgesteuerte Calls, F07 für Wissen; vorhandene Fetch-/Budgetruntime nicht ersetzen.

**Sicherheit:** Query-Datenminimierung, keine privaten Chatteile/Schlüssel in Suchanfragen, DNS-Rebinding-/SSRF-Schutz, Ergebnisbytes und Laufzeiten begrenzen, Quelleninhalt untrusted. Regex-Filter im Planner sind keine vollständige DLP-Garantie. **Tests:** Bestehend [Research](../backend/tests/unit/test_research.py), [Source-Network](../backend/tests/unit/test_source_network.py), [Browser-Websuche](../frontend/tests/websocket/web-search-ui.spec.ts). Ergänzen: Provider-Vertrag, schlechte/beleglose Quellen, Prompt-Injection, Resume/Abbruch bei mehrstufiger Recherche und opt-in Liveabnahme. **Aufwand/Priorität:** **P2, 6–12 PT** inkrementell; allgemeiner Agentloop separat F12/F15.

### F12 — Function Calling

**Beschreibung/Referenz:** [Tool-Calling-Modi](https://docs.openwebui.com/features/extensibility/plugin/tools#tool-calling-modes-default-vs-native) lassen Modelle strukturierte Werkzeugaufrufe erzeugen und Ergebnisse weiterverarbeiten. Open-WebUI-„Functions“ wie Pipes/Filters/Actions sind zusätzlich ein [Pluginmechanismus](https://docs.openwebui.com/features/extensibility/plugin/functions).

**Ist/Status: fehlt** für allgemeines modellgesteuertes Function Calling. Der Adapter erkennt `delta.tool_calls`, `function_call` und entsprechende Finish-Reasons, weist sie aber mit `INVALID_RESPONSE` zurück. Das ist eine ausdrückliche Protokollgrenze, kein belegter Parserfehler. Registry, Run-/Approval-Schema, Toolereignisse, Budgets, servergesteuerte Recherche und UI-Projektionen sind bereits implementiert. Aus `tool_calling`-Metadaten eines Modells folgt noch kein ausführbarer Toolloop. Python-Pipes/Filters/Actions können nicht importiert werden.

**Quellbelege:** [Ablehnung im Provideradapter](../backend/src/noris_ai/llm/openai_compatible.py), [Providerinterface](../backend/src/noris_ai/llm/provider.py), [Registry](../backend/src/noris_ai/tools/registry.py), [Runtime](../backend/src/noris_ai/tools/runtime.py), [Toolereignisse](../frontend/app/lib/chat/toolEvents.ts). **Abhängigkeiten:** Typisierte Text-/Tool-Deltas und Ergebnisnachrichten im vorhandenen Providervertrag, erlaubte Call-Schleife, dauerhafte Zuordnung und Replay; F21 für nutzerspezifische Rechte.

**Sicherheit:** Modelltext niemals als Code ausführen; JSON-Schema, Toolallowlist, maximale Schritte/Calls/Bytes/Tokens, Idempotenz, ausdrückliche Freigabe bei Seiteneffekten. Python-Plugin-Kompatibilität ist keine Voraussetzung und würde eine eigene Isolationsentscheidung benötigen. **Tests:** fragmentierte/fehlerhafte Argumente, mehrere Calls, unbekannte Tools, Freigabe/Reject, Crash nach Ausführung, Replay ohne Doppelausführung, Abbruch und Budgeterschöpfung. Bestehende [Runtime-Integration](../backend/tests/integration/test_tool_runtime.py) und [Policytests](../backend/tests/unit/test_tool_policy.py) erweitern. **Aufwand/Priorität:** **P2, 12–20 PT**.

### F13 — MCP und externe Werkzeuge

**Beschreibung/Referenz:** [Natives MCP](https://docs.openwebui.com/features/extensibility/mcp) unterstützt Streamable HTTP; [OpenAPI-Toolserver](https://docs.openwebui.com/features/extensibility/plugin/tools/openapi-servers) und ein MCP-Proxy sind weitere Integrationswege.

**Ist/Status: teilweise.** Externe HTTP-Dienste sind bereits als feste interne Provider eingebunden. Es fehlen MCP-Client/Discovery, generischer OpenAPI-Import, Verbindungskatalog, OAuth-Verbindungen und benutzerbezogene Toolauswahl. Die Registry enthält genau `web.search.v1` und `web.fetch.v1`. Vorhandene Toolapprovals sind eine Grundlage, keine Integration zu beliebigen MCP-Servern.

**Quellbelege:** [Registry](../backend/src/noris_ai/tools/registry.py), [Policy](../backend/src/noris_ai/tools/policy.py), [Tool-Routen](../backend/src/noris_ai/api/v1/tools.py), [Approval-/Run-Modelle](../backend/src/noris_ai/tools/models.py). **Abhängigkeiten:** F12 für native Modellaufrufe, F20/F21 für persönliche Verbindungen; Remote-MCP als Toolprovider unter der bestehenden Runtime, nicht als zweiter Ausführungsweg.

**Sicherheit:** Pro Server/Tool Rechte und Budget; OAuth-Token verschlüsselt und widerrufbar; Zielhosts einschränken; Schemaänderungen versionieren; schreibende Aktionen separat bestätigen. Keine frei konfigurierbaren lokalen `stdio`-Prozesse ohne eigenes Sandboxkonzept. **Tests:** MCP-Handshake, Discovery/Schemawechsel, OAuth-Ablauf, ungültige Argumente, Serverausfall, Cancellation, Zugriffswechsel und böse Toolbeschreibungen; getrennte OpenAPI-Vertragsfixtures. **Aufwand/Priorität:** **P2, 12–20 PT** für einen Remote-MCP-Pfad und begrenzte OpenAPI-Anbindung; keine universelle Pluginlaufzeit enthalten.

### F14 — Benutzerdefinierte Assistenten

**Beschreibung/Referenz:** [Model-Presets](https://docs.openwebui.com/features/workspace/models) kombinieren Basismodell, Instruktionen, Parameter, Wissen, Tools und Skills zu spezialisierten Assistenten.

**Ist/Status: fehlt.** Die Noris-Modellregistry und der fest implementierte Lernmodus sind keine vom Nutzer erstellbaren Assistenten. Kein CRUD, keine Versionen oder Freigaben für Assistenten, kein eigener Systemprompt-Editor. Browsernachrichten bleiben bewusst auf zulässige Chatrollen begrenzt.

**Quellbelege/Negativscope:** [Modellregistry](../backend/src/noris_ai/llm/registry.py), [Chat-/Modellschemata](../backend/src/noris_ai/llm/schemas.py), [Einstellungen](../frontend/app/lib/settings/registry.ts). **Abhängigkeiten:** F03-Verbindungsidentität, F07/F13/F15 optional referenzierte Ressourcen, F21-ACL; versioniertes Preset als neue Ressource, beim Generieren serverseitig auflösen.

**Sicherheit:** Nutzerinstruktionen dürfen Betreiberpolicy nicht überschreiben; Presetberechtigungen und alle gebundenen Ressourcen bei jedem Start prüfen; keine Schlüssel in exportierten Presets. **Tests:** CRUD/Version/Rollback, Modell entfernt, Wissen oder Tool widerrufen, Snapshot laufender Generierung, manipulierte Rolle und Cross-Owner-Zugriff. **Aufwand/Priorität:** **P2, 10–16 PT**, Grundeditor und Bindungen; Ressourcen selbst werden in ihren Bereichen entwickelt.

### F15 — Skills und Agenten

**Beschreibung/Referenz:** [Skills](https://docs.openwebui.com/features/workspace/skills) sind versionierte Instruktionen mit Dateien und bedarfsweisem Laden; [Subagenten](https://docs.openwebui.com/features/chat-conversations/chat-features/subagents) und [Task Management](https://docs.openwebui.com/features/chat-conversations/chat-features/task-management) erweitern agentische Chats.

**Ist/Status: teilweise.** Begrenzte Recherche mit Plan, Schritten, Status, Quellen und Budget ist vorhanden. Kein Skillspeicher/`$`-Menü, kein `view_skill`, kein Skillimport, keine allgemeine Plan-/Agentlaufzeit, Delegation oder Taskliste. `pydantic-ai-slim` als Abhängigkeit beweist keine solche Funktion. Lernmodus ist ein Gesprächsmodus, keine Agentenplattform.

**Quellbelege:** [Research-Orchestrator](../backend/src/noris_ai/research/orchestrator.py), [Research-Schemata](../backend/src/noris_ai/research/schemas.py), [Providerinterface](../backend/src/noris_ai/llm/provider.py), [Backend-Manifest](../backend/pyproject.toml). **Abhängigkeiten:** F12/F13, versionierte Instruktionsressourcen ähnlich F14/F16, dauerhafte Parent-/Child-Runzuordnung; bestehende Researchruntime schrittweise erweitern.

**Sicherheit:** Ein Skilltext ist keine Berechtigung; Dateien und importierte Instruktionen untrusted; globale Eltern-/Kindbudgets, maximale Tiefe/Parallelität, Abbruch vererben und Scope getrennt prüfen. **Tests:** Skillversion/Dateipfade/Größen, Manifest und bedarfsweises Laden, Rechteentzug, Kontextbudget, Delegationsgrenzen, Parent-Cancel und Crash-Recovery. Bestehende [Researchtests](../backend/tests/integration/test_research_runtime.py) weiterverwenden. **Aufwand/Priorität:** **P2, 15–25 PT** für Skills und begrenzte Agentläufe; allgemeine autonome Computersteuerung separat und außerhalb dieser Schätzung.

### F16 — Prompt-Bibliothek

**Beschreibung/Referenz:** [Workspace Prompts](https://docs.openwebui.com/features/workspace/prompts) bieten wiederverwendbare Vorlagen, Slash-Aufruf, typisierte Variablen, Versionen und Ressourcenzugriff.

**Ist/Status: fehlt.** Keine Prompttabelle/-API und kein Bibliothek-/Variableneditor. Die lokale Befehlsregistry öffnet Aktionen; sie speichert keine Nutzerprompts. Feste Systeminstruktionen für Titel, Fortsetzung und Lernen sind interne Policies.

**Quellbelege/Negativscope:** [Befehlsregistry](../frontend/app/lib/chat/commands.ts), [Einstellungsregistry](../frontend/app/lib/settings/registry.ts), [Chat-Datenmodelle](../backend/src/noris_ai/chat/models.py). **Abhängigkeiten:** Gemeinsame Ressourcenrechte und Versionierung mit F14/F15, persistente Promptressource, Einsetzen über denselben Composer.

**Sicherheit:** Vorlagenvariablen als Text, kein `eval`/Template-Code; Maximalgröße und Kontextbudget, expliziter Rollenvertrag, Rechte auch beim Slash-Aufruf prüfen. **Tests:** CRUD/Rollback, Variablentypen/Defaults, Escaping, Namenskollisionen, Unicode, leerer/zu langer Prompt, verlorene Freigabe, Entwurf und Cursorposition erhalten. **Aufwand/Priorität:** **P2, 7–12 PT** einschließlich Grundversionierung, ohne gemeinsamen Rechteunterbau doppelt zu zählen.

### F17 — Slash-Kommandos

**Beschreibung/Referenz:** Open WebUI ruft [gespeicherte Prompts mit `/`](https://docs.openwebui.com/features/workspace/prompts) auf; Noris nutzt denselben Auslöser bereits für Composeraktionen.

**Ist/Status: teilweise.** Vorhanden: `/lernen`, `/suche`, `/denken`, `/modell`, `/datei`, `/hilfe`, englische Aliasse, Kontext-/Verfügbarkeitsprüfung, Tastatursteuerung und Sendeguard. `/bild` ist registriert, aber mangels echter Bildgenerierung nicht verfügbar. Bildinput allein schaltet es nicht frei. Fehlend: persönliche/geteilte Promptbefehle mit Parametern und Konfliktauflösung.

**Quellbelege:** [commands.ts](../frontend/app/lib/chat/commands.ts), [useSlashCommands](../frontend/app/composables/useSlashCommands.ts), [Composerbindung](../frontend/app/components/chat/ChatComposer.vue). **Abhängigkeiten:** F16; bestehende Registry um dynamische Einträge erweitern, keine zweite Commandpalette.

**Sicherheit:** UI-Verfügbarkeit ist keine Serverautorisierung; Text bleibt normaler Nutzereingang; keine versteckte Ausführung deaktivierter Aktionen. **Tests:** Bestehend [Commands](../frontend/tests/unit/commands.spec.ts), [Slash-WebSocket](../frontend/tests/websocket/slash-commands.spec.ts). Ergänzen: Kollision statisch/dynamisch, Rechteentzug während Menü offen, IME/Paste/Mobil, Variablenabbruch und Wiederherstellung des Entwurfs. **Aufwand/Priorität:** P0 bestehende Interaktion sichern; **P2, 3–5 PT** dynamische Integration zusätzlich zu F16.

### F18 — Lernmodus

**Beschreibung/Referenz:** Schrittweises Tutoring mit Lernziel, Rückfragen und Feedback. In der untersuchten offiziellen Kernfunktionsdokumentation ist kein eigenständiger gleichnamiger Open-WebUI-Studymodus belegt. Der Vergleich eines identischen eingebauten Modus ist deshalb **nicht anwendbar**; ähnliche Konfigurationen sind über [Assistenten-Presets](https://docs.openwebui.com/features/workspace/models) möglich. Es wird keine fehlende Noris-Funktion daraus abgeleitet.

**Ist/Status: vorhanden.** `conversation_mode`, `LearningInstruction`, serverseitige Policy, Zweigaktivitätsprojektion, Moduswechsel über Plus/Slash und sichtbare Deaktivierung sind implementiert. Die Policy fördert kleine Schritte und erlaubt ausdrücklich eine direkte Lösung auf Nutzerwunsch. Aktivitätszähler werden nicht als Kompetenzmessung ausgegeben. Persistenz und Kontextprüfung beziehen die Instruktionen ein; im zustandslosen HTTP-Vorschaumodus ist die Funktion deaktiviert. Pädagogische Qualität realer Provider ist mit deterministischen Tests nicht bewiesen.

**Quellbelege:** [Policy](../backend/src/noris_ai/learning/policy.py), [Zweigzustand](../backend/src/noris_ai/learning/state.py), [Migration 0010](../backend/migrations/versions/0010_conversation_learning.py), [Composer](../frontend/app/components/chat/ChatComposer.vue). **Abhängigkeiten:** Bestehende Gesprächsmodi und Reasoning-Policies weiterverwenden, keine neue Lernengine.

**Sicherheit:** Nutzer-/Dateitext bleibt untrusted, keine Systemrollen aus Lerninhalten, keine unbegründeten Lernstandsbehauptungen oder erzwungene Herausgabe interner Instruktionen. **Tests:** Bestehend [Learning-Unit](../backend/tests/unit/test_learning.py), [Lernmodus-Browser](../frontend/tests/websocket/learning-mode.spec.ts). Ergänzen: qualitative Rubrik DE/EN für Hilfen, direkte Lösungen, Themenwechsel und widersprüchliche Dateianweisungen mit explizit freigegebenen Modellen. **Aufwand/Priorität:** **P2, 2–4 PT** Qualitätsevaluation; **keine Neuimplementierung**.

### F19 — Bildanalyse und Bildgenerierung

**Beschreibung/Referenz:** Vision-Chat sowie [Bildgenerierung/-bearbeitung](https://docs.openwebui.com/features/chat-conversations/image-generation-and-editing) über konfigurierbare Bildprovider.

**Ist/Status: teilweise.** Bildanalyse ist für bestätigte Visionmodelle implementiert: PNG/JPEG, Signatur-/Pixelprüfung, begrenzte Normalisierung, EXIF-freie Ausgabe, Data-URL-Payload, Kontext-/Bytebudget und Modellkompatibilitätsanzeige. Kein Bildgenerierungs-/Editadapter, kein atomarer Import generierter Dateien, keine Sketchoberfläche. Die Menüpunkte „Bild erstellen“ und „Skizze“ bleiben ohne Handler deaktiviert; Designdokumente beweisen keine Umsetzung. Reale Visionqualität bleibt providerabhängig und hier ungeprüft.

**Quellbelege:** [Visionvertrag](../backend/src/noris_ai/llm/vision.py), [Bildparser](../backend/src/noris_ai/chat/attachment_parser.py), [Providerpayload](../backend/src/noris_ai/llm/provider.py), [Composeraktionen](../frontend/app/lib/chat/composerMenu.ts). **Abhängigkeiten:** Bildprovider als eigener Adapter, Resultate über vorhandene Attachments/Quoten; [IMAGE-GENERATION-DESIGN.md](IMAGE-GENERATION-DESIGN.md) und [SKETCH-DESIGN.md](SKETCH-DESIGN.md) als Vorarbeiten.

**Sicherheit:** Generierte Dateibytes erneut validieren, keine beliebigen Resultat-URLs abrufen, Pixel-/Größen-/Kostenlimits, Nutzerbilder nicht ohne Aktion extern bearbeiten. **Tests:** Bestehend [Vision](../backend/tests/unit/test_vision.py), [Attachment-Integration](../backend/tests/integration/test_attachments.py). Ergänzen: Providerfehler/Abbruch, Teilresultat, Quotenreservation und genau einmal gespeicherte Bilder, Editrechte, Touch-/Sketch-Export. **Aufwand/Priorität:** P1 bestehenden Visionpfad sichern; **P3, 15–25 PT** für Generieren/Edit plus einfachen Sketch, Providerbreite später.

### F20 — Benutzerverwaltung

**Beschreibung/Referenz:** Individuelle Identitäten, Anmeldung und Kontenlebenszyklus. Open WebUI dokumentiert [Authentifizierung](https://docs.openwebui.com/features/authentication-access), [SSO](https://docs.openwebui.com/features/authentication-access/auth/sso), [MFA](https://docs.openwebui.com/features/authentication-access/mfa), LDAP und SCIM.

**Ist/Status: fehlt** für individuelle Benutzerverwaltung. `verify_basic` prüft ein konfiguriertes Zugangspaar; `chat_access` liefert immer `config.chat_owner_id`. Dieser ist eine serverseitige feste Owner-ID, kein angemeldeter Nutzer. Kein Benutzerkonto, Login-/Logout-Sitzungsmodell, OIDC, MFA, Einladung oder Selbstverwaltung. Ein Profilmenü ist kein Benutzerverzeichnis.

**Quellbelege:** [Basic-Zugriff](../backend/src/noris_ai/core/access.py), [Ownerzuordnung](../backend/src/noris_ai/api/v1/conversations.py), [Ownerkonfiguration](../backend/src/noris_ai/core/config.py), [Profilmenü](../frontend/app/components/chat/ProfileMenu.vue). **Abhängigkeiten:** Identitätsadapter und Session-/Principal-Vertrag, Zuordnung bestehender Daten zu einem expliziten Owner; Domain-Ownership weiterverwenden. Keine automatische Umverteilung vorhandener Chats.

**Sicherheit:** Sichere Sessions, CSRF-/Originprüfung, Revocation, IdP-Verifikation und nachweisbare Trennung von Chats, Dateien, Budgets und Tools; keine öffentiche Mehrbenutzerfreigabe mit gemeinsamem Basic-Owner. **Tests:** Login/Logout, abgelaufene/widerrufene Sitzung, falsche Issuer/Audience, Replay, Zuordnung von Bestandsdaten und zwei tatsächlich verschiedene Nutzer über REST/WS/Dateien. **Aufwand/Priorität:** **P0 vor Mehrbenutzerbetrieb, 15–25 PT** für Identität/SSO und Migration. LDAP/SCIM/komfortable Verwaltung bleiben zusätzliche P3-Pakete.

### F21 — Rollen und Berechtigungen

**Beschreibung/Referenz:** [Rollen](https://docs.openwebui.com/features/authentication-access/rbac/roles), [Gruppen](https://docs.openwebui.com/features/authentication-access/rbac/groups) und [Funktionsrechte](https://docs.openwebui.com/features/authentication-access/rbac/permissions) begrenzen administrative und geteilte Ressourcen.

**Ist/Status: teilweise.** Ownerbegrenzte Repositoryabfragen, serverseitige Zugriffsprüfung, DB-Approlle ohne Superuserrechte und eine Toolpolicy mit `allow`, `approval_required` oder `deny` sind vorhanden. Keine Nutzer-/Gruppenrollen, ACLs für Presets/Wissen/Prompts oder getrennte Adminrechte. Ein `owner_id`-Feld und die Existenz von Approvaltabellen ergeben noch keine vollständige Mehrbenutzer-RBAC. RLS ist im aktuellen Schema nicht eingerichtet.

**Quellbelege:** [Ownerabfragen](../backend/src/noris_ai/chat/repository.py), [Toolpolicy](../backend/src/noris_ai/tools/policy.py), [Toolapprovals](../backend/src/noris_ai/tools/models.py), [DB-Initialisierung](../infrastructure/docker/postgres-init.sh). **Abhängigkeiten:** F20-Principals, zentraler Autorisierungsvertrag pro Ressource; DB-RLS nur als begründete zusätzliche Absicherung, nicht als Ersatz für Domainprüfungen.

**Sicherheit:** Default-deny, serverseitige Prüfung bei Lesen/Schreiben/Streaming/Export, Rechteentzug auch für bereits geplante Calls, keine implizite Adminfreigabe neuer Ressourcen. Open WebUIs additive Gruppenlogik muss nicht ungeprüft kopiert werden; das Noris-Rechtemodell muss explizit festgelegt sein. **Tests:** Matrix aus Nutzer/Rolle/Ressource/Aktion, fremde IDs, Archiv/Löschung, Rechtewechsel während Generierung, Toolfreigabe und indirekte Suchleaks. Bestehende [Policytests](../backend/tests/unit/test_tool_policy.py) und [Attachmenttests](../backend/tests/integration/test_attachments.py) erweitern. **Aufwand/Priorität:** **P0 vor Mehrbenutzerbetrieb, 12–20 PT**; Admineditor P3.

### F22 — Administration und Statistiken

**Beschreibung/Referenz:** [Administration](https://docs.openwebui.com/features/administration), [Analytics](https://docs.openwebui.com/features/administration/analytics), [Evaluation](https://docs.openwebui.com/features/administration/evaluation), Banner, Defaultsettings und Taskmodelle.

**Ist/Status: teilweise.** `/status`, API-Health/Readiness, Request-IDs, Konfiguration, Providerlimits und persistente Budgetgrundlagen sind vorhanden. Keine Adminressource/-oberfläche, Nutzungsübersicht je Nutzer/Modell, Kostenreport, Modellarena, Feedbackbewertungen, Bannerverwaltung oder administrative Einstellungshistorie. Die Seite „Sicherung“ zeigt Persistenzzustände; sie erstellt kein Datenbankbackup. Titelgenerierung existiert, aber keine allgemeine konfigurierbare Taskmodellverwaltung.

**Quellbelege:** [Health](../backend/src/noris_ai/api/v1/health.py), [Statusseite](../frontend/app/pages/status.vue), [Budgets](../backend/src/noris_ai/tools/budget.py), [Sicherungsstatus](../frontend/app/pages/settings/backup.vue), [Titelservice](../backend/src/noris_ai/llm/titles.py). **Abhängigkeiten:** F20/F21, Datenminimierung, definierte Nutzungsereignisse und Aggregation; bestehende Budgetdaten wiederverwenden.

**Sicherheit:** Adminrechte getrennt, keine Chatvolltexte im Standardreport, anonymisierte/aggregierte Metriken, geprüfte Konfigurationsänderungen, Auditlog ohne Secrets. **Tests:** Aggregation/Zeitzonen, doppelte/abgebrochene Generierungen, unvollständige Usage-Daten, Rechte-/Exportgrenzen und Wiederherstellung eines Backups in isolierter Umgebung. **Aufwand/Priorität:** **P3, 10–18 PT** für grundlegende Admin-/Usageansicht; Arena, SCIM und volle Governance nicht enthalten.

### F23 — Datenschutz und Sicherheit

**Beschreibung/Referenz:** Die [Datenschutz-/Verschlüsselungsreferenz](https://docs.openwebui.com/security/chat-data-privacy-and-encryption) trennt Serverkontrolle, Infrastrukturverschlüsselung, Datenweitergabe und temporäre Chats. v0.12.3 ergänzt [temporär Ende-zu-Ende-verschlüsselte Kanäle](https://github.com/open-webui/open-webui/releases/tag/v0.12.3); das bedeutet keine allgemeine E2E-Verschlüsselung von KI-Prompts.

**Ist/Status: teilweise.** Belegt sind konstante Credentialvergleiche, Origin-/Hostprüfungen, kurzlebige einmalige WS-Tickets, Provider-Allowlist/TLS-Prüfung, `trust_env=False`, Request-/Output-/Budgetgrenzen, sichere Markdown-VNodes ohne Roh-HTML, isolierte Dateiparser, Source-SSRF-/DNS-Prüfung und Cleanup. Lücken: keine vollständige Konto-/Rechteverwaltung, keine temporären Chats, kein belegter Hard-Delete von Chattexten, keine konfigurierte vollständige Retention, kein E2E-Kanal und kein nachgewiesener Backup-/Restore- oder Verschlüsselungsbetrieb. `soft_delete_conversation` setzt nur den Löschzeitpunkt; Anhänge werden separat bereinigt. Aus dem Löschbutton darf keine sofortige physische Entfernung sämtlicher Nachrichten abgeleitet werden.

**Quellbelege:** [Zugriff](../backend/src/noris_ai/core/access.py), [WS-Tickets](../backend/src/noris_ai/chat/tickets.py), [Soft-Delete](../backend/src/noris_ai/chat/repository.py), [Attachment-Cleanup](../backend/src/noris_ai/chat/attachments.py), [Markdown](../frontend/app/components/chat/MarkdownContent.ts), [Caddy-Vorlage](../infrastructure/proxy/Caddyfile). **Abhängigkeiten:** F20/F21, Retention-/Purge-Vertrag über Nachrichten, Dateien, Tools, Events, Indizes und Backups. Der HTTP-Ingress in der Vorlage belegt kein produktives TLS; vorgeschalteter TLS-Betrieb bleibt offen.

**Sicherheit:** Datenfluss pro Provider/Browserdienst beschreiben; Löschumfang und Aufbewahrung explizit; Schlüssel getrennt halten; spätere RAG-/MCP-/Audioressourcen in denselben Schutz aufnehmen. Dies ist ein technischer Audit, keine Rechts- oder Zertifizierungsaussage. **Tests:** Bestehend [Source-Network](../backend/tests/unit/test_source_network.py), [WS-Handshake](../backend/tests/unit/test_chat_ws_handshake.py), [Vision](../backend/tests/unit/test_vision.py), [Markdown](../frontend/tests/unit/markdown.spec.ts). Ergänzen: Lösch-/Retention-End-to-End, Restore, Secretredaktion, Auth-/Rate-Limits und dokumentierter TLS-/Sessionbetrieb. **Aufwand/Priorität:** **P0, 10–18 PT** technische Lifecycle-/Betriebsgrundlagen, Identität separat; Governance/E2E später P3.

### F24 — Mobile UX und Accessibility

**Beschreibung/Referenz:** Open WebUI bietet responsive Chat- und [Tastaturinteraktionen](https://docs.openwebui.com/features/chat-conversations/chat-features/keyboard-shortcuts). Daraus folgt keine pauschale WCAG-Zertifizierung; ein vollständiger produktspezifischer Konformitätsnachweis war nicht Teil der Referenzprüfung.

**Ist/Status: teilweise.** Responsive Sidebar/Drawer, adaptiver Composer, Viewportbehandlung, Fokuswiederherstellung, ARIA-Labels/Live-Status, Tastaturbefehle, Hell/Dunkel und zahlreiche Desktop-/Mobile-Tests sind vorhanden. Suchdialog und Menüs verwenden Nuxt-/Reka-Fokussteuerung. Kein belegtes vollständiges Screenreader-/WCAG-Audit; keine installierbare PWA oder Offline-Synchronisierung im Quellstand. Mobile Chromium-Screenshots beweisen weder iOS/Safari-Verhalten noch Accessibility-Konformität. Die Einstellungen zeigen feste Tastaturhilfen, keine umfassende frei belegbare Shortcutverwaltung.

**Quellbelege:** [Viewport](../frontend/app/composables/useChatViewport.ts), [Suchdialog](../frontend/app/components/chat/ChatSearchDialog.vue), [Composer](../frontend/app/components/chat/ChatComposer.vue), [Styles](../frontend/app/assets/css/main.css), [Tastatureinstellungen](../frontend/app/pages/settings/keyboard.vue), [Nuxt-Konfiguration](../frontend/nuxt.config.ts). **Abhängigkeiten:** Bestehende Komponenten/Designsystem; Fokus und Semantik bei neuen Dialogen erhalten; PWA separat entscheiden.

**Sicherheit:** Keine Audio-/Datei-/Offline-Caches über Ownerwechsel hinweg; sensible Notifications im Hintergrund minimieren. **Tests:** Bestehend [aktive Tastatur](../frontend/tests/e2e/active-keyboard.spec.ts), [Suchlayout](../frontend/tests/e2e/chat-search-layout.spec.ts), [Composer](../frontend/tests/e2e/adaptive-composer.spec.ts). Ergänzen: VoiceOver/NVDA, Safari/Firefox, reale Bildschirmtastatur, Zoom/Reflow, Kontrast, reduzierte Animation, Touchziele und durchgehende reine Tastaturbedienung. **Aufwand/Priorität:** **P0, 5–9 PT** Prüfung und gezielte Korrekturen; PWA/Offline zusätzlich P3 schätzen.

## Weitere für vollständige Parität relevante Funktionen

Diese Ergänzungen verhindern, dass ein Audit der 24 Schwerpunkte angrenzende stabile Funktionen übersieht. Sie sind noch keine Beauftragung zur Implementierung. Wie bei den Hauptbereichen bedeuten die Schätzungen einen begrenzten ersten Lieferumfang.

| ID / Beschreibung / Referenz | Noris-Ist / Status und Quellbeleg | Technische Abhängigkeiten | Sicherheitsanforderungen | Benötigte Tests | Aufwand / Priorität |
| --- | --- | --- | --- | --- | --- |
| E01 — Gesprächsübergreifendes [Memory](https://docs.openwebui.com/features/chat-conversations/memory) | **fehlt**; [Preferences](../backend/src/noris_ai/chat/models.py) speichern Auswahl, keine persönlichen Fakten oder Memorytools | F12, F20/F21, getrennte widerrufbare Memoryressource | Opt-in, Einsicht/Korrektur/Löschung, keine heimliche Profilerstellung, ACL vor Retrieval | Erinnern über Chats, Widerspruch/Korrektur, Delete/Export, fremder Owner | 7–12 PT, P2 nach Rechtebasis |
| E02 — [Notes](https://docs.openwebui.com/features/notes) und eigenständige Dokumente | **fehlt**; [Textreferenzen](../frontend/app/lib/chat/textReferences.ts) sind Nachrichtenauszüge, kein persistenter Dokumenteditor | Neue versionierte Dokumentressource, vorhandener Composer/Chat, F21 | Freigaben, Konfliktkontrolle, sichere Darstellung, keine stillen Überschreibungen | Versionskonflikt, Passage bearbeiten, Chatkontext, Export und widerrufene Freigabe | 10–18 PT, P3 |
| E03 — [Codeausführung/Artefakte](https://docs.openwebui.com/features/chat-conversations/chat-features/code-execution), Mermaid/Mathe | **teilweise**: [CodeBlock](../frontend/app/components/chat/CodeBlock.vue) mit Hervorhebung/Kopieren vorhanden; [Markdownrenderer](../frontend/app/components/chat/MarkdownContent.ts) führt nichts aus und rendert kein Mermaid/LaTeX/HTML-Artefakt | F12/F13 für Interpreter; getrennte Ausführungssandbox; Parser/Renderer für Diagramme und Mathe | Kein Roh-HTML im Hauptdokument, isolierte Frames/Prozesse, CPU/RAM/Netzlimits | XSS/Navigation, Diagramm-/Mathegrenzen, Interpretertimeout, Dateiscope, Crash | 5–9 PT Rendering plus 15–25 PT isolierte Ausführung, P3 |
| E04 — [Channels](https://docs.openwebui.com/features/channels), DMs, geteilte Chats und Anwesenheit | **fehlt**; [Owner-Modell](../backend/src/noris_ai/chat/models.py) besitzt keine Mitgliedschaften oder Kanal-/DM-Ressourcen | F20/F21, Mitgliedschaften, Zustellung/Ungelesen, ggf. separater Kanal-Domainbereich | Teilnehmerwechsel, Widerruf, getrennte Rollen, E2E nur mit eigenem Schlüssel-/Bedrohungsmodell | Concurrent Edits, Beitritt/Austritt, Rechteentzug, unerlaubte Historie, Zustellung/Replay | 20–35 PT Basis, P3; E2E zusätzlich ungeschätzt |
| E05 — [Automationen](https://docs.openwebui.com/features/chat-conversations/chat-features/automations), [Timer](https://docs.openwebui.com/features/chat-conversations/chat-features/timers) und [Webhooks](https://docs.openwebui.com/features/administration/webhooks) | **fehlt** für Nutzerjobs; [Startup-Cleanup](../backend/src/noris_ai/main.py) ist Wartung, [Notifications](../frontend/app/composables/useAppNotifications.ts) sind lokale UI-Meldungen | Persistenter Scheduler/Worker, vorhandene Generierung/Budgets, F20/F21 | Eigentümerrechte zur Ausführungszeit prüfen, Ziel-Allowlist, Retry/Idempotenz, Jobs stoppen/löschen | RRULE/Zeitzone/Sommerzeit, Neustart, doppelte Zustellung, Widerruf und Budgetgrenze | 12–20 PT Basis, P3 |
| E06 — Antwortbewertung/Arena und [Follow-up-Prompts](https://docs.openwebui.com/features/chat-conversations/chat-features/follow-up-prompts) | **fehlt**; [Nachrichtenaktionen](../frontend/app/components/chat/ChatMessage.vue) bieten Kopieren/Varianten, keine persistente Bewertungsressource | Bewertungsmodell, F03 für Arena, vorhandener Task-/Titelprovider für Vorschläge | Einwilligung und Datenminimierung bei Auswertung/Export, sichtbare Zusatzkosten, kein unkontrollierter Trainingsdatenexport | doppelte Bewertung, Modellzuordnung, Vorschlagfehler, ACL und Exportfilter | 6–10 PT, P3 |

Separate Ökosystemprodukte wie Open WebUI Computer, Knowledge Base Sync und Open Terminal sind **nicht anwendbar als einzubauende Noris-Architektur**. Ihre Integrationsmöglichkeiten sind unter F07/F13/F15/E03 berücksichtigt; ihr gesamter eigener Funktionsumfang wird nicht als stabile Kernfunktion von Open WebUI ausgegeben. Enterprise-spezifische Orchestrierung und sämtliche denkbaren Drittanbieterplugins liegen außerhalb eines vollständigen Kern-Paritätsnachweises. Für eine spätere verbindliche „100-%-Parität“ ist ein versioniertes Abnahmeregister pro Unterfunktion nötig; dieses Dokument ist die belegte Bestandsaufnahme und Lieferplanung dafür.

## Die zehn wichtigsten Lücken

1. **P0 — Suche:** Wort-AND, nachvollziehbare Filter und belastbare Nachrichtensuch-Performance fehlen; Suche selbst ist bereits vorhanden (F02).
2. **P0 — Portabilität:** Vollständiger Dateiexport und validierter Restore mit Zweigen/Anhängen fehlen; lokaler Import wird weiterverwendet (F01).
3. **P0 vor Mehrbenutzerbetrieb — Identität:** Individuelle Principals, Sessions und Ownerzuordnung fehlen (F20).
4. **P0 — Datenlebenszyklus:** Soft-Delete ist kein belegter vollständiger Purge-/Retention-Vertrag (F23).
5. **P1 — Kokoro/TTS:** Sprachausgabe und Vorleseaktionen fehlen vollständig (F09; STT separat F08).
6. **P1 — Modellverbindungen:** Mehrere Provider und native Ollama-Verwaltung fehlen, trotz bestehendem Katalog/Modellwechsel (F03/F04).
7. **P1 — Wissenssammlungen:** Wiederverwendbare Dateien, Collections und allgemeines Retrieval fehlen; PDF-Selektion bleibt erhalten (F06/F07).
8. **P2 — Modelltools/MCP:** Allgemeines Function Calling, Remote-MCP und dynamische Toolverbindungen fehlen; die bestehende Runtime ist die Basis (F12/F13).
9. **P2 — Workspace-Bausteine:** Nutzbare Assistenten, Promptvorlagen und Skills fehlen (F14–F17).
10. **P3 — Erweiterte Interaktion/Betrieb:** Sprachdialoge, Bildgenerierung, isolierte Ausführung, Adminanalytik und Nutzerautomation fehlen (F10/F19/F22/E03/E05); als getrennte Lieferpakete planen.

## Technische Risiken und offene Nachweise

| Risiko | Beleg / praktische Folge | Nächster Nachweis |
| --- | --- | --- |
| Gemeinsamer Owner wird als Mehrbenutzerfähigkeit missverstanden | `chat_access` liefert festen Owner; alle Basic-Nutzer teilen denselben Scope | F20/F21-Abnahme mit zwei Identitäten vor Mehrbenutzerfreigabe |
| Mehrere API-Prozesse ohne Zustandskonzept | WS-Tickets, Peerqueues und laufende Generierungsaufgaben sind pro Prozess; Startup-Recovery markiert laufende Runs unter demselben Owner als unterbrochen | Isolierter Mehrprozess-/Neustarttest; erst danach Shared-State-/Workerentscheidung |
| Suchlatenz wächst mit Nachrichtenzahl | Substring-`EXISTS` ohne passenden Nachrichtentextindex; bisheriger Titelindex deckt das nicht ab | Synthetischer Lastfall plus Queryplan und P95; keine Produktionsdaten |
| Capability-Metadaten werden mit Produktfähigkeit verwechselt | Modell kann Toolcalling melden, während Adapter Calls absichtlich ablehnt | Adapter-Konformität pro Fähigkeit; UI aus ausführbarer Capability ableiten |
| Daten werden als vollständig gelöscht dargestellt | Chat-Soft-Delete, separates Attachment-Cleanup, Events/Toolresultate/Backups mit eigener Lebensdauer | Dokumentierter Löschgraph mit End-to-End-Purge-/Restore-Test |
| RAG-/Bibliotheksmigration verliert Beziehungen | Bisherige Anhänge gehören zu einem Gespräch/einer Nachricht | Additive Membershipmigration, referenzsichere Löschung und Expand/Contract-Abnahme |
| Tool-/Agentenwirkung überschreitet Grenzen | Bestehende Runtime ist begrenzt; allgemeine Calls erhöhen Ausführungs- und Exfiltrationsfläche | Policy-/Budget-/Approval-/Replaytests vor MCP/Agenten |
| Audio und Browserdienste ändern den Datenweg | Browsererkennung kann außerhalb der eigenen Infrastruktur arbeiten; Kokoro braucht Modell- oder Dienstbezug | Pro Engine Datenfluss, Sprachqualität, Gerätelimits und Löschung abnehmen |
| UI-Ähnlichkeit wird mit Vollständigkeit verwechselt | Mehrere Plus-/Suchkategorien sind deaktivierte Vorbereitungen; viele Goldens verwenden Fixtures | Für jede neue Funktion UI→API→DB→Provider-Test statt bloßem Screenshot |
| Veraltete Planungen/Toolversionen erschweren Reproduktion | README und alte Roadmap weichen vom aktuellen Code ab; pnpm-Manifest und CI-Installation nennen verschiedene Stände | Versionen aus Manifest/Lockfile prüfen; separate Wartungsänderung statt stiller Anpassung im Audit |

## Durchgeführte Prüfungen

Am Auditstand wurden folgende **bestehende** Tests erneut ausgeführt; keine neuen Produkttests oder Features wurden hinzugefügt:

| Prüfung | Ergebnis / Aussagegrenze |
| --- | --- |
| Backend: Learning, Provider, Katalog, PDF, Vision, Registry, Policy, Chatprotokoll, Research und Source-Network | **277 bestanden**, 5,23 s; lokale Unit-/Fixturetests, keine Liveprovider |
| Frontend: Conversation Search, Highlighting, Dictation, Modellauswahl, Commands, Learning, Research, Markdown und WebSocket-Transport | **85 bestanden in 9 Dateien**, 6,66 s; `happy-dom`, keine reale Mikrofon-/Mobilgeräteabnahme |
| Quell-/Vertragsinventar, SQL-/Migrationsprüfung, Open-WebUI-Release und ausgewählte stabile Quelldateien | Lesend geprüft; 24 Matrixzeilen und 24 Detailprofile, Statuszählung und sämtliche relativen Dateiverweise geprüft; keine fehlenden Linkziele |
| PostgreSQL-Integration, Playwright, Produktionsbuild, echte Dienste | **Nicht erneut ausgeführt**. Bestehende Tests werden oben als vorhandene Absicherung benannt, nicht als aktuelle erfolgreiche Laufzeitabnahme |

Reproduzierbare gezielte Befehle, vom Repository bzw. Backend aus:

```sh
# working directory: backend
.venv/bin/python -B -m pytest -p no:cacheprovider \
  tests/unit/test_learning.py tests/unit/test_llm_provider.py \
  tests/unit/test_model_catalog.py tests/unit/test_pdf_documents.py \
  tests/unit/test_vision.py tests/unit/test_tool_registry.py \
  tests/unit/test_tool_policy.py tests/unit/test_chat_protocol.py \
  tests/unit/test_research.py tests/unit/test_source_network.py -q

# working directory: repository root
node frontend/node_modules/vitest/vitest.mjs run --root frontend \
  tests/unit/conversation-search.spec.ts tests/unit/search-highlight.spec.ts \
  tests/unit/composer-dictation.spec.ts tests/unit/model-selection.spec.ts \
  tests/unit/commands.spec.ts tests/unit/learning-mode.spec.ts \
  tests/unit/research.spec.ts tests/unit/markdown.spec.ts \
  tests/unit/websocket-transport.spec.ts
```

Der normale pnpm-Aufruf scheiterte hier am schreibgeschützten globalen Package-Manager-Store; danach wurde derselbe lokal installierte Vitest direkt über Node ausgeführt. Es wurden keine Abhängigkeiten installiert. Datenbankintegrationstests verlangen ausdrücklich eine wegwerfbare `_test`-Datenbank und führen dort Downgrades aus; sie dürfen nicht gegen eine vorhandene Anwendungsdatenbank gestartet werden.
