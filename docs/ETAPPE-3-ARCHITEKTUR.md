# Etappe 3 – Architektur: PostgreSQL-Chat-Persistenz, WebSocket-Streaming, GLM 5.3

Stand: 2026-10-09. Dieses Dokument beschreibt den Ist-Zustand nach Etappe 2, die
Zielarchitektur von Etappe 3 und die Umsetzungsentscheidungen. Es ist der
maßgebliche Review-Einstieg für die Pull Requests A–F.

## 1. Ist-Zustand (Audit)

### Backend (`backend/src/noris_ai/`)

- **Layout**: `api/v1` (Router: health, llm), `core` (config, schemas,
  middleware), `db` (Base mit Naming-Conventions, Readiness-Probe),
  `llm` (gateway, provider, catalog, registry, sse, limits, errors, titles).
- **LLM-Gateway**: Single-Worker-Admission mit `llm_max_concurrent`,
  `llm_requests_per_minute`, `llm_daily_token_budget` (konservative
  Tokenschätzung beziehungsweise ausdrücklich konfiguriertem Offline-Tokenizer; Reasoning-Reserve getrennt). Keine gemessenen
  Provider-Usage-Daten – Usage-Chunks des Providers werden explizit
  ignoriert; es werden keine erfundenen Verbrauchswerte gespeichert.
- **Provider**: `OpenAICompatibleProvider` (httpx) gegen
  `https://ai.noris.de/v1`, strikte Chunk-Validierung, `[DONE]`-Terminal,
  UTF-16-Output-Grenze. Kein zweiter LLM-Stack – Etappe 3 baut ausschließlich
  auf `LLMProvider`/`LLMGateway` auf.
- **Modellkatalog**: `ModelCatalogService` (TTL, stale never authorizes) plus
  exakte ID-Registry (`REGISTRY_VERSION 2026-10-09.1`) mit GPT-OSS 120B,
  GLM 5.2, Gemma 4, Qwen 3.6, smart_router.
- **API**: `GET /health/live`, `GET /health/ready`, `GET /llm/models`,
  `POST /llm/chat` (SSE), `POST /llm/conversation-title`. Auth: HTTP Basic
  (Nutzer/Passwort ≠ Provider-Key), Origin-Allowlist + `sec-fetch-site`-Prüfung
  für POST. Keine Sessions, keine Cookies.
- **Datenbank**: Alembic-Baseline `0001_foundation` ohne Domänentabellen;
  Rollen `noris_migrator` (Migrationen) und `noris_app` (App, derzeit nur
  SELECT-Default-Privilegien). Chat-Persistenz backendseitig: **keine**.

### Frontend (`frontend/app/`)

- **Chat-State** (`useChat`, `useConversations`): flache
  `MessageRecords`-Map, Baum über `parentMessageId` (Immutable Branches,
  Antwortvarianten als Geschwister, `activeLeafMessageId` wählt den aktiven
  Pfad, `preferredLeaves` merken Variantenwahl). Titel: `fallback` /
  `generated` / `manual`. Entwürfe pro Konversation plus `__new__`.
- **Persistenz**: ausschließlich localStorage (`noris-ai:chat:v1`, Snapshot
  v1, strenge Validierung in `parseChatSnapshot`), 120 ms debounce,
  Cross-Tab-Erkennung, Legacy-Key-Migration.
- **Transport**: `ChatTransport`-Vertrag (`stream(request, signal)` →
  `AsyncIterable<StreamEvent>`, `generateTitle?`). Implementierungen:
  `MockTransport`, `RealTransport` (SSE via POST `/llm/chat`).
- **UI**: `ChatWorkspace.vue` mit Scroll-Following (`useChatScroll`),
  Markdown/Shiki, Composer-Fokus, Editieren/Regenerieren/Varianten,
  Modellmenü aus `/llm/models`.

### Bewertung

Alle Voraussetzungen für Etappe 3 sind vorhanden: Transportabstraktion,
Baumsemantik, Provider-Gateway mit Budgets, Alembic-Rollensplit. Fehlend:
Domänentabellen, Chat-Repository, REST-Ressourcen, WebSocket-Endpunkt,
Server-seitiger Generierungs-Orchestrator, WS-Transport im Frontend,
Import der Browser-Chats.

## 2. Zielbild und Entscheidungen

### 2.1 PostgreSQL als Source of Truth

- PostgreSQL speichert Konversationen, Nachrichten (Baum inkl. Varianten),
  Generierungen, Stream-Events (reproduzierbare Deltas), Entwürfe und
  Nutzerpräferenzen.
- Der Browser hält nur: temporäre Eingaben, optimistische Updates, lokalen
  Cache (localStorage bleibt als Cache/Offline-Draft erhalten, ist aber nicht
  mehr autoritativ), Scroll-/UI-Zustand.
- Der LLM-Kontext wird **serverseitig** aus dem ausgewählten, validierten Pfad geladen; der
  Browser überträgt keine Verläufe mehr als autoritativen Kontext.

### 2.2 Datenbankschema (Migration `0002_chat_persistence`)

| Tabelle | Kernfelder | Besonderheiten |
| --- | --- | --- |
| `chat_conversation` | `id`, `owner_id`, `title`, `title_source` (fallback/generated/manual), `created_at`, `updated_at`, `archived_at`, `deleted_at`, `version`, `last_message_at`, `active_leaf_message_id` | Optimistische Versionierung (`version`); weiche Löschung; `active_leaf` per Composite-FK an `chat_message(conversation_id,id)` gebunden |
| `chat_message` | `id`, `conversation_id`, `parent_message_id`, `role` (user/assistant), `content`, `model_id`, `status`, `generation_id`, `edited_from_message_id`, `created_at`, `updated_at` | Immutable per PostgreSQL-Trigger (0003): Bearbeitungen/Regenerierungen erzeugen Geschwister. Composite-FK `(conversation_id,parent_message_id)→(conversation_id,id)` verhindert Parents fremder Unterhaltungen; Parents müssen vor dem Kind existieren → zyklenfrei. Kein `system`/`developer` aus Nutzereingaben |
| `chat_generation` | `id`, `conversation_id`, `input_message_id`, `assistant_message_id`, `model_id`, `status` (queued/running/completed/incomplete/cancelled/failed/interrupted), `started_at`, `completed_at`, `cancelled_at`, `error_code`, `output_tokens`, `input_tokens`, `last_sequence` | `input_tokens`/`output_tokens` nur für **gemessene** Werte; der Provider liefert keine → Felder bleiben NULL (Schätzungen werden nicht als Messwerte gespeichert) |
| `chat_stream_event` | `generation_id`, `sequence`, `event_type`, `payload` (jsonb), `created_at` | `UNIQUE(generation_id,sequence)`; Deltas werden gebündelt (Batch pro Flush-Intervall bzw. Größenlimit), nicht pro Token |
| `chat_draft` | `owner_id`, `draft_key` (Konversations-UUID oder `__new__`), `content`, `updated_at` | PK `(owner_id,draft_key)` |
| `chat_user_preferences` | `owner_id`, `active_conversation_id`, `model_id`, `updated_at` | Wiederherstellung aktiver Chat/Modell nach Reload |

Indizes: Owner+Zeit (Sidebar-Gruppierung), `conversation_id+created_at`
(Pfad-Laden), Status-Lookups auf `chat_generation`.

Die Migration vergibt `SELECT, INSERT, UPDATE, DELETE` an `noris_app` für die
neuen Tabellen (der Init-Script-Default bleibt SELECT-only). Keine destruktiven
Operationen; `downgrade()` entfernt nur die neuen Tabellen.

### 2.3 Ownership und Authentifizierung (Option A: Single-User-Modus)

- Es bleibt beim HTTP-Basic-Anwendungszugang, **abermals** mit serverseitig
  fester Besitzer-Identität: `NORIS_CHAT_OWNER_ID` (Default
  `00000000-0000-0000-0000-000000000001`, UUID). Kein Endpunkt akzeptiert eine
  client-seitige `owner_id`; jede Abfrage filtert serverseitig.
- Keine scheinbare Multi-User-Trennung über das gemeinsame Basic-Passwort:
  dokumentiert als Single-Owner-Modus; OIDC-fähig vorbereitet (`owner_id` als
  Spalte überall, Repository-Filter als einzige Stelle).
- **WebSocket-Auth**: Browser-WS kann keine Authorization-Header setzen.
  deshalb kurzlebige, einmalige Tickets: `POST /api/v1/chat/ws-ticket` (Basic)
  → `{ticketId, expiresInSeconds}` (TTL 60 s, Single-Use, In-Memory).
  Verbindung: `GET /api/v1/chat/ws` mit den Subprotokollen `noris-chat.v1`
  und `ticket.<Einmalticket>`. Origin-Allowlist gilt für beides;
  fremde Origins werden vor dem Accept mit 403 geschlossen. Nach dem Accept
  sendet der Server `chat.connected`. Die URL enthält kein Ticket. Proxy-Logging des `Sec-WebSocket-Protocol`-Headers muss deaktiviert bleiben.

### 2.4 REST (Ressourcen) und WebSocket (Live)

REST (`/api/v1`, Basic + Origin-Checks wie bisher):

- `GET /api/v1/conversations` (inkl. `archived=`-Filter, ohne gelöschte)
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{id}`
- `PATCH /api/v1/conversations/{id}` (`title`→manual, `archived`,
  `activeLeafMessageId`, `version` für optimistische Sperre)
- `DELETE /api/v1/conversations/{id}` (Soft-Delete)
- `GET /api/v1/conversations/{id}/messages`
- `PUT /api/v1/conversations/{id}/draft`
- `POST /api/v1/conversations/import` (Browser-Migration, s. 2.7)
- `GET /api/v1/chat/drafts`, `PUT /api/v1/chat/drafts/new`
- `GET/PUT /api/v1/chat/preferences`

WebSocket `/api/v1/chat/ws` (Protokoll `version: 1`):

Client→Server: `chat.generate`, `chat.cancel`, `chat.resume`, `chat.ping`.
Server→Client: `chat.connected`, `chat.message.created`,
`chat.generation.started`, `chat.generation.delta`,
`chat.generation.completed`, `chat.generation.incomplete`, `chat.generation.failed`,
`chat.generation.cancelled`, `chat.generation.interrupted`,
`chat.conversation.updated`, `chat.title.updated`, `chat.resume.snapshot`,
`chat.error`, `chat.heartbeat`, `chat.pong`, `chat.resume.accepted`.

`chat.generate` übernimmt nur **Referenzen** (`requestId`=generationId,
`conversationId`, `inputMessageId`, `modelId`, `attempt`, sowie die neue
Nutzernachricht `{id,parentMessageId,content}` zur idempotenten Persistierung)
– **keinen Nachrichtenverlauf**. Der Server lädt den aktiven Pfad selbst.

Das WS-Protokoll ist als versioniertes JSON-Schema zusätzlich zu OpenAPI in
`docs/websocket/chat-v1.json` festgeschrieben; ein Contract-Test prüft Drift.

### 2.5 Generierungsfluss und Disconnect-Policy

1. `chat.generate` → Ownership/Validierung → Nutzernachricht idempotent
   speichern (ON CONFLICT DO NOTHING, Abweichungen → 409) →
   `chat_generation` (queued→running) + Assistant-Nachricht (status
   streaming) → Admission über das **bestehende** Gateway
   (Budget/Rate/Concurrency/Modellfreigabe) → `chat.generation.started`.
2. Provider-Stream wird serverseitig konsumiert; Deltas werden gebündelt
   (Flush ≥ 100 ms oder ≥ 512 Zeichen) als `chat_stream_event` persistiert
   (monotone `sequence`) und mit derselben `sequence` als
   `chat.generation.delta` versendet.
3. Abschluss: Assistant-`content` final gespeichert (dauerhaft, Textverlust
   ausgeschlossen), Generation `completed`, Abschluss-Event.
4. **Disconnect ≠ Abbruch**: Ein verlorener Browser-Socket bricht die
   Generierung nicht ab; sie läuft unter den bestehenden Timeouts/Budgets
   weiter und wird persistiert, höchstens 60 Sekunden ohne verbundenen
   Teilnehmer. Danach wird sie `interrupted`. Reconnect stoppt die Frist.
   Expliziter Abbruch nur per
   `chat.cancel`. Backend-Neustart: Startups markieren verwaiste `queued`-/`running`-
   Generierungen als `interrupted` (keine scheinbar vollständigen Antworten).
5. **Resume**: `chat.resume {generationId,lastReceivedSeq}` → Ownership-
   Checks → Replay persistierter Events `> lastReceivedSeq`; läuft die
   Generierung noch, folgt die Verbindung dem Live-Strom; ist sie terminal
   und kein Replay möglich, sendet der Server einen autoritativen Snapshot
   (`chat.resume.snapshot` mit vollständigem Text, Status und Sequenz).
   Fortsetzungen verwenden stets Snapshots für das vorhandene Präfix. Dupletten
   sind durch die monotone `sequence` ausgeschlossen.
6. **Backpressure**: Pro Verbindung eine begrenzte Queue (256 Events) mit
   Sende-Timeout (15 s); überlaufene/langsame Verbindungen werden kontrolliert
   geschlossen (1013), die Generierung läuft persistiert weiter; der Client
   resume-t. Batchung hält die DB-Schreiblast begrenzt.
7. **Retention**: `chat_stream_event` wird für abgeschlossene Generierungen
   älter als `NORIS_CHAT_STREAM_EVENT_RETENTION_HOURS` (Default 168 h)
   opportunistisch bereinigt (Lazy-Pruning beim Ticketkauf); der finale Text
   bleibt in `chat_message` dauerhaft.

### 2.6 Frontend

- Neuer `WebSocketTransport` (`chatTransport: 'websocket'`) innerhalb der
  bestehenden `ChatTransport`-Abstraktion: gleiche `StreamEvent`-Kohärenz
  (zwingend monotone `seq`), Reconnect mit Exponential-Backoff + Resume,
  Stop per `chat.cancel`. `MockTransport`/`RealTransport` bleiben kompatibel; der SSE-Adapter serialisiert weiterhin ausschließlich seinen bisherigen Vertrag.
- `useChat` erhält einen optionalen Backend-Sync (`useChatBackend`): Erstellen/
  Umbenennen/Archivieren/Löschen/Variantenwahl/Entwürfe werden gegen REST
  durch die gemeinsame Domain-Schicht validiert. Der Cache liegt separat unter
  `noris-ai:chat-cache:v1`, unbestätigte Offline-Entwürfe unter
  `noris-ai:offline-drafts:v1`; der alte `noris-ai:chat:v1`-Bestand bleibt
  ausschließlich für ausdrücklich gestarteten Import oder Mock-Rückkehr.
  Beim Reload werden Konversationen, aktive Auswahl, Nachrichten und Entwürfe
  vom Backend geladen. Cachetexte/aktive Blätter überschreiben die DB niemals.
- `ChatWorkspace.vue` wird nicht neu geschrieben; UI, Scroll-Following,
  Markdown, Fokus bleiben erhalten.
  Fortsetzung und Regeneration warten auf einen laufenden Modellkatalog-Refresh,
  damit ein währenddessen ausgeführter Klick nach erneuter Freigabe verarbeitet wird.

### 2.7 Browser-Migration

- `POST /api/v1/conversations/import` erhält einen validierten Snapshot
  (Strukturäquivalent zu `ChatSnapshot v1`). Der Server validiert Besitz,
  Baum-Konsistenz (Rollen-Alternation, keine Zyklen, Blatt-Eigentum) und
  übernimmt die bestehenden IDs. Idempotent: identisch existierende
  Konversationen werden übersprungen; fachliche Importkonflikte stehen im
  `conflicts`-Feld des Importberichts (HTTP 200). Bei Konflikt wird keine
  neue Konversation importiert; bereits vorhandene identische Bestände werden
  ausgewiesen. Bereits serverseitig bearbeitete Entwürfe werden nicht überschrieben.
- Auslösung ausschließlich durch Nutzeraktion (Dialog im Sidebar-Fuß), niemals
  automatisch. Der lokale Bestand wird **nicht** gelöscht; Rollback ist damit
  der lokale Snapshot selbst (Dokumentation im Dialog und hier).

### 2.8 GLM 5.3

Live-Katalogprüfung (nur `GET /v1/models`, keine Generierung) am 2026-10-09:

- **`vllm/qsu/glm-5-3-flash`** ist verfügbar (`is_ready: true`).
- Dokumentiert: Kontext 1.048.576 Token, Ausgabeparameter `max_tokens`
  (1–1.048.576), Streaming `true`, `stop`/`temperature`/`top_p`, DE-Rechenzentrum.
- **Kein** Reasoning-Parameter dokumentiert → Aufnahme als CHAT-Modell ohne
  `reasoning_parameter` (keine erfundene `chat_template_kwargs`-Nutzung).
  Policy-Output-Limit 8192 (lokal, konservativ wie GLM 5.2), Lifecycle
  EXPERIMENTAL als lokale Policy, Evidence DOCUMENTED. Reasoning-Fähigkeit
  bleibt UNKNOWN, weil der Katalog keine entsprechende Aussage liefert. Keine erfundene ID; GLM 5.2
  (`vllm/release/glm-5-2`) bleibt unverändert.

### 2.9 Bereitstellung

Caddy leitet `/api/*` bereits unbuffered an FastAPI weiter
(`flush_interval -1`); WebSocket-Upgrades behandelt `reverse_proxy`
transparent. Kein zweiter Proxy. `chat.ws`-Pfad: lokal
`ws://127.0.0.1:8080/api/v1/chat/ws`, öffentlich `wss://<domain>/api/v1/chat/ws`.
Der Backend-Port 8000 bleibt unveröffentlicht. PostgreSQL-Volumes bleiben.

### 2.10 Pull-Request-Gliederung

- **PR A** – Schema + Alembic-Migration + Grants + Readiness (dieses Dokument)
- **PR B** – Repository, REST-Ressourcen, Owner-Modell, GLM-5.3-Registry
- **PR C** – WS-Protokoll, Tickets, Generierungs-Orchestrator, Resume
- **PR D** – Frontend WebSocketTransport + Backend-Sync
- **PR E** – Browser-Import
- **PR F** – E2E/Stabilisierung, Contract-Drift-Wächter, Abschlussbericht

## 3. Migrationen, Schnittstellenfolgen und Wiederherstellung

- `0002_chat_persistence`: sechs normalisierte Tabellen und gezielte DML-Grants.
  `chat_branch` wird nicht zusätzlich angelegt: Elternbeziehungen, aktive Blatt-ID
  und Geschwistervarianten repräsentieren bereits sämtliche Branch-Semantik.
- `0003_chat_integrity`: Datenbank-Trigger erzwingt Rollenalternation und
  unveränderliche IDs/Parents/Modelle/Generierungszuordnung. Finaler Inhalt ist
  immutable; ausschließlich pending/streaming-Assistant-Inhalt wird während der
  Generierung aktualisiert. Inhaltsgrenze 1 MiB Zeichen bewahrt bestehende lange
  Antworten. Eltern müssen schon existieren, Änderungen der Topologie sind
  gesperrt: damit können keine Zyklen entstehen.
- `0004_chat_continuation`: `incomplete`, Fortsetzungszähler, sichere Fehlerdaten,
  Generierungsoperation und Composite-FK zur Quellantwort. Fortsetzung erzeugt
  eine neue Antwortvariante mit serverseitig geladenem Präfix. Original,
  Markdown, Codeblöcke, Continue/Stop/Retry und Modellbindung bleiben erhalten.
- REST-PATCH verlangt genau eine Ressourcenänderung und die aktuelle Version.
  Zeilensperren und optimistische Versionen schützen konkurrierende Änderungen;
  Präferenzen verwenden atomare Upserts. Generierungsannahme und Import sind
  atomare Transaktionen. Nur vollständige DB-Commits werden bestätigt.
- Shared interfaces: `LLMGateway.events()` liefert typisierte Ereignisse für WS;
  der bestehende SSE-Encoder verwendet dieselben Ereignisse. Keine zweite
  Providerintegration. `ChatTransport` wird nur optional um Backend-Ressourcen,
  Verbindungsaufbau und Dispose erweitert. Derselbe `useChat`-State rendert alle
  Modi, samt Scroll-Following, Fokus und Antwortvarianten.
- Der Frontend-Adapter normalisiert Serverzeitstempel auf UTC; Branches werden
  chronologisch nach geparsten Zeitpunkten sortiert, auch bei abweichenden
  PostgreSQL-/Browser-Zeitzonen.

Upgrade: Migrationsrolle führt `alembic upgrade head` aus; Runtime-Role besitzt
keine Migrationsrechte. Readiness verlangt exakt `0004_chat_continuation`.
Produktionsdaten werden durch Upgrades nicht gelöscht. Down/Up- und Alembic-
Driftprüfungen laufen ausschließlich gegen wegwerfbare `_test`-Datenbanken.
Ein Downgrade von 0002 entfernt neue Chat-Tabellen und benötigt deshalb eine
separate Freigabe und eine verifizierte DB-Sicherung. 0003-Downgrade kürzt keine
langen Antworttexte; 0004 lässt PostgreSQL-Enumwerte zur Datenerhaltung stehen,
entfernt aber Fortsetzungsmetadaten. Für Anwendungscode-Rollback bevorzugt die
vorherige UI-Version mit unverändertem Schema betreiben, statt Tabellen zu
löschen. Der erhaltene Browserbestand ist eine zusätzliche Vor-Import-Sicherung;
spätere serverseitige Änderungen benötigen eine PostgreSQL-Sicherung.

Details des ausführbaren Vertrags: [WEBSOCKET-CHAT-V1.md](WEBSOCKET-CHAT-V1.md).
Prüfstatus und PRs: [ETAPPE-3-ABSCHLUSSBERICHT.md](ETAPPE-3-ABSCHLUSSBERICHT.md).

## 4. Offene Einschränkungen

- Single-Worker-Admission (Budgets/Rate-Limits) bleibt prozesslokal; verteilte
  Quotas und OIDC-Multi-User sind Etappe 4.
- Token-Usage: Provider sendet keine verlässlichen Usage-Werte; gemessene
  Felder bleiben NULL, geschätzte Reservierungen nur im Speicher.
- Nitro-devProxy leitet in der Entwicklung kein WS weiter; WS-Entwicklung und
  -Tests laufen über die Caddy-Origin (Compose/Dev-Stack) oder direkt gegen
  den Backend-Port mit passender Origin-Allowlist.
