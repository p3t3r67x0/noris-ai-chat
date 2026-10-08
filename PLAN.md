# noris AI Chat – Implementierungsplan

**Status:** Planungsstand / verbindliche Grundlage für die schrittweise Umsetzung  
**Stand:** 2026-10-08  
**Produkt:** noris AI Chat  
**Ziel:** Self-hostbare, mandantenfähige Chat-Plattform mit ChatGPT-ähnlichen Kernabläufen.

> Dieser Plan beschreibt **Funktionsmuster** und Bedienqualität, nicht das Kopieren fremder Logos, Marken oder geschützter Gestaltungselemente. Noris AI bekommt ein eigenständiges Branding.

## 1. Zielbild und Abgrenzung

Ein moderner KI-Chat mit schneller, zugänglicher Oberfläche, Gesprächsverlauf, Live-Streaming, Stoppen, Regenerieren, Bearbeiten früherer Nutzernachrichten und nachvollziehbaren Antwortvarianten. Startzielgruppe ist das interne Team mit Firmen-SSO. Das Daten- und Rechtemodell unterstützt von Beginn an mehrere Organisationen.

### MVP – zwingend

- Desktop und Mobile: Startseite, einklappbare Sidebar, Chatverlauf, neue Chats, Chat suchen.
- Eingabefeld: mehrzeilig, Enter senden, Shift+Enter Zeilenumbruch, Entwurf pro Chat erhalten.
- Antworten: SSE-Streaming, Stoppen, Lade-/Fehlerzustände, Markdown, Tabellen, Code-Blöcke mit Kopieren.
- Gesprächsaktionen: Nutzer-Nachricht bearbeiten, Antwort neu generieren, Antwortvarianten wählen.
- Gesprächsverwaltung: umbenennen, archivieren, löschen; aktive Auswahl nach Neuladen wiederherstellen.
- Automatisches Scrollen nur, wenn der Nutzer am Ende des Gesprächs ist; Anzeige „Zur neuesten Nachricht“ sonst.
- Light/Dark/System Theme, Tastatur- und Screenreader-Bedienbarkeit.
- Login über OIDC-Firmen-SSO, serverseitige Autorisierung, Organisationsgrenzen.
- Mindestens ein produktiv konfigurierbarer noris-AI-Provider; weitere Provider über Adapter.
- Persistente Generierungszustände, Verbrauchs-/Fehlerdaten, Logs und Betriebschecks.

### Explizit nach dem MVP

Datei-Uploads, Projekte, RAG, Websuche, MCP, agentische Aktionen, Sprachmodus, Sharing, Billing und öffentliche Registrierung. Das Datenmodell darf diese Möglichkeiten nicht blockieren, sie werden aber **nicht** vorgezogen.

### Nicht-Ziele

- Pixelgenaue Kopie der ChatGPT-Oberfläche.
- Vollständige Multi-Agent-Plattform in V1.
- Mehrere Microservices ohne konkrete Skalierungsnotwendigkeit.
- Freie Ausführung beliebiger Tools oder Shell-Kommandos durch Modelle.

## 2. Vorläufige Produktentscheidungen

| ID | Entscheidung | Begründung |
|---|---|---|
| ADR-001 | Monorepo, modularer Monolith | Schnellere Lieferung, klare Modulgrenzen |
| ADR-002 | Nuxt 4 + Vue 3 + TypeScript + Nuxt UI/Tailwind | Gut wartbare responsive Chat-Oberfläche |
| ADR-003 | Python + FastAPI + Pydantic v2 | Typisierte API und OpenAPI |
| ADR-004 | Pydantic AI hinter eigener Model-Gateway-Schicht | Herstellerwechsel und spätere Tools |
| ADR-005 | PostgreSQL + SQLAlchemy 2 + Alembic | Transaktionen, Relationen, Versionierung |
| ADR-006 | SSE via POST für Antwortstream, GET zum Wiederaufnehmen | Einfaches Server→Client-Streaming mit Resume |
| ADR-007 | Persistenter Nachrichtenbaum | Bearbeiten und Regenerieren ohne Überschreiben |
| ADR-008 | OIDC/SSO, Backend-Sessions mit HttpOnly-Cookies | Unternehmensanmeldung ohne Tokenhaltung im Browser |
| ADR-009 | Mandantentrennung im Service und über PostgreSQL RLS | Defense in Depth |
| ADR-010 | Docker Compose für Entwicklung/kleine Deployments | Reproduzierbarer Betrieb |
| ADR-011 | OpenAPI-generierte Client-Typen | Keine doppelte Handpflege von Verträgen |
| ADR-012 | Ausführliche E2E-Tests für Chatinteraktionen | UX ist Produktkern |

**Offene Integrationsentscheidung:** Die genaue noris-AI-API (Protokoll, Auth, unterstützte Modelle, Streaming-Format, Token-Nutzungsdaten) wird vor der echten Provider-Integration anhand einer Spezifikation/Probe ermittelt. Bis dahin dient ein deterministischer Fake-Provider als Referenz.

## 3. Architektur

```text
Browser (Nuxt 4)
   │ HTTPS, REST, SSE
   ▼
Reverse Proxy / gleiche Origin
   │
   ▼
FastAPI (modularer Monolith)
   ├── OIDC Session / Organizations / RBAC
   ├── Conversation + Message Tree
   ├── Generation Orchestrator + SSE Event Log
   ├── Model Registry / Policy / Usage
   └── Pydantic AI Gateway
         ├── Fake Provider (Entwicklung/Tests)
         ├── noris-AI Provider
         └── optionale Provider (OpenAI, Azure, vLLM ...)
   │
   ├── PostgreSQL (verbindlicher Zustand)
   └── Worker (asynchrone Nebenarbeiten; anfangs optional)
```

**Prinzip:** Das Frontend ist nie maßgebliche Quelle für Nachrichtenstatus. Der Backend-Service erhält die vollständige Benutzeridentität aus der überprüften Session und ermittelt Organisationszugriff serverseitig. Provider-Keys verlassen nie das Backend.

### Repository

```text
noris-ai-chat/
├── PLAN.md
├── README.md
├── .env.example
├── frontend/
│   ├── app/components/{chat,sidebar,settings}/
│   ├── app/composables/
│   ├── app/pages/
│   ├── app/stores/
│   ├── app/types/generated/
│   ├── tests/{unit,e2e}/
│   ├── nuxt.config.ts
│   └── package.json
├── backend/
│   ├── src/noris_ai/
│   │   ├── api/v1/
│   │   ├── auth/
│   │   ├── organizations/
│   │   ├── conversations/
│   │   ├── messages/
│   │   ├── generations/
│   │   ├── models/
│   │   ├── providers/
│   │   ├── db/
│   │   └── core/
│   ├── migrations/
│   ├── tests/{unit,integration,contract}/
│   └── pyproject.toml
├── infrastructure/{docker,proxy}/
├── docs/{architecture,api,security,ux}/
└── .github/workflows/
```

## 4. Datenmodell und Invarianten

PostgreSQL-UUIDs als Primärschlüssel; Zeitstempel als `timestamptz` in UTC. Organisationseigentum wird an jeder sensiblen Entität explizit abgebildet. Alle Fremdschlüssel und Indizes werden in Alembic-Migrationen definiert.

### Kerntabellen

| Tabelle | Wichtige Felder / Zweck |
|---|---|
| `users` | id, display_name, status, created_at |
| `identities` | id, user_id, issuer, subject, unique(issuer,subject) |
| `organizations` | id, slug, name, status |
| `organization_memberships` | org_id, user_id, role, status |
| `sessions` | id, user_id, expiry, revoked_at, hashed_token_ref |
| `model_providers` | id, kind, display_name, credential_ref, enabled |
| `models` | id, provider_id, model_key, label, capabilities, limits, enabled |
| `conversations` | id, organization_id, owner_user_id, title, active_leaf_message_id, archived_at, deleted_at, created_at, updated_at |
| `messages` | id, conversation_id, organization_id, parent_message_id, role, content_json, status, created_at, edited_from_message_id, generation_id |
| `generations` | id, conversation_id, organization_id, input_message_id, response_message_id, model_id, status, started_at, ended_at, error_code, cancellation_requested_at, provider_request_ref |
| `generation_events` | generation_id, seq, type, payload_json, created_at; unique(generation_id,seq) |
| `usage_records` | id, generation_id, model_id, input_tokens, output_tokens, cost_estimate, usage_source |
| `audit_logs` | actor_id, org_id, action, target_type, target_id, created_at, metadata_sanitized |

`content_json` wird anhand versionierter Pydantic-Union-Schemas validiert, z. B. `{ "version": 1, "parts": [{ "type": "text", "text": "..." }] }`. Keine rohen Provider-Responses ungeprüft als universelles Chat-Format speichern. Rollen: `user`, `assistant`, `tool` (Tool-Nachrichten erst mit späteren Tools aktivieren).

### Unveränderlichkeit und Verzweigungen

1. Jede Nachricht hat höchstens **einen** Parent und gehört genau zu einem Gespräch.
2. Die Parent-Kette darf keinen Zyklus enthalten; Parent und Kind gehören derselben Organisation und demselben Gespräch.
3. Früheres Editieren erzeugt eine **neue** `user`-Nachricht mit demselben Parent wie das Original und `edited_from_message_id` als Herkunft. Original bleibt erhalten.
4. Regenerieren erzeugt eine neue `assistant`-Nachricht als Geschwister der bisherigen Antwort, d. h. gleicher vorheriger User-Parent.
5. Der aktuell sichtbare Pfad ergibt sich aus `conversations.active_leaf_message_id` und seiner Parent-Kette; ein expliziter Wechsel der Variante aktualisiert das aktive Blatt atomar.
6. Beim Editieren einer alten Frage dürfen die späteren Antworten des alten Zweigs nicht automatisch an den neuen Zweig angehängt werden.
7. Neue Generierungen verweisen auf ein unveränderliches `input_message_id` und ein ausgewähltes Modell.
8. Für eine Generation darf es nur eine zugeordnete Antwortnachricht geben; partielle Ausgaben bleiben markiert.
9. Providerinterne Konversationsobjekte sind **nicht** der verbindliche Zustand: Die an das Modell übergebene Historie wird aus dem aktiven Nachrichtenpfad aufgebaut.

### Transaktions- und Rechtevorgaben

- Nachrichtenoperationen prüfen Berechtigung und Organisation **vor** Mutation.
- Jede Antwortvariante wird transaktional angelegt und erhält eigene Generation.
- Optimistische Konkurrenzkontrolle (z. B. `version` in Conversation) verhindert versehentliches Überschreiben der aktiven Blattwahl durch parallele Tabs.
- Löschen berücksichtigt Retention/Audit und physische Bereinigung; `deleted_at` allein ist keine vollständige DSGVO-Löschung.
- RLS wird für mandantengebundene Tabellen aktiviert und mit **Negativtests** für fremde Organisationen überprüft. DB-Benutzer der Anwendung dürfen RLS nicht umgehen.

## 5. API-Verträge (v1)

Alle Fehler verwenden ein einheitliches Schema, z. B. `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`. Zeitangaben als ISO-8601 UTC. Cursor-Pagination für Listen. Jede mutierende Anfrage bekommt bei Bedarf einen `Idempotency-Key`.

### Identität und Organisation

```http
GET    /api/v1/auth/me
GET    /api/v1/auth/oidc/login
GET    /api/v1/auth/oidc/callback
POST   /api/v1/auth/logout
GET    /api/v1/organizations
```

Login erfolgt über OIDC Authorization Code + PKCE, serverseitige Validierung von Issuer, Audience, State und Nonce. Cookie `HttpOnly`, `Secure`, `SameSite` passend zur Deployment-Topologie; CSRF-Schutz für zustandsändernde Requests.

### Gespräche und Verzweigungen

```http
GET    /api/v1/conversations?cursor=...&query=...
POST   /api/v1/conversations
GET    /api/v1/conversations/{conversation_id}
PATCH  /api/v1/conversations/{conversation_id}
DELETE /api/v1/conversations/{conversation_id}
GET    /api/v1/conversations/{conversation_id}/messages?branch=active
POST   /api/v1/conversations/{conversation_id}/messages
POST   /api/v1/messages/{message_id}/edit
POST   /api/v1/conversations/{conversation_id}/select-leaf
GET    /api/v1/messages/{message_id}/alternatives
```

`POST .../messages`: User-Nachricht mit Parent und Client-Idempotenzkennung anlegen. `POST .../edit`: neue Nachricht als Alternative anlegen, nicht in-place überschreiben. `select-leaf` nimmt die neue Blatt-ID plus erwartete Conversation-Version entgegen.

### Generierungen

```http
POST   /api/v1/conversations/{conversation_id}/responses
GET    /api/v1/responses/{generation_id}
GET    /api/v1/responses/{generation_id}/events
POST   /api/v1/responses/{generation_id}/cancel
POST   /api/v1/messages/{assistant_message_id}/regenerate
GET    /api/v1/models
```

`POST .../responses` nimmt mindestens `input_message_id`, `model_id` und Idempotency-Key entgegen und gibt direkt den SSE-Stream zurück. Regenerieren verwendet den **gleichen User-Parent** wie die ursprüngliche Antwort und legt eine neue Generation an.

### Beispiel: Generation starten

```json
{
  "input_message_id": "00000000-0000-0000-0000-000000000001",
  "model_id": "00000000-0000-0000-0000-000000000002"
}
```

Vor dem Provideraufruf müssen Organisation, Zugriffsrecht, Model-Freigabe, gültiger Nachrichtenpfad und Budget geprüft werden. Die endgültige Historie ist eine Projektion des gewählten Pfades und enthält keine Nachrichten aus anderen Zweigen.

## 6. SSE-Protokoll, Stoppen und Recovery

SSE: `text/event-stream`, `id: <monotonic_seq>`, `event: <name>`, `data: <JSON>`, Leerzeile. Die ID identifiziert Ereignisse **pro Generation**, Sequenzen steigen monoton. Das Backend speichert Stream-Ereignisse oder mindestens genügend rekonstruierbaren Zustand, um bei erneutem Abruf nicht inkonsistent zu werden.

### V1-Ereignisse

```text
event: response.started
data: {"generation_id":"...","message_id":"..."}

event: response.output_text.delta
data: {"delta":"Hallo"}

event: response.usage.updated
data: {"input_tokens":20,"output_tokens":12}

event: response.completed
data: {"status":"completed"}
```

Weitere terminale Ereignisse: `response.cancelled`, `response.failed`. Zusätzlich möglich: `response.snapshot`, `response.heartbeat`. Das Frontend verarbeitet Events idempotent und erkennt Lücken.

### Zustandsmaschine

```text
pending -> running -> completed
                  \-> cancelling -> cancelled
                  \-> failed
pending -> cancelled
```

Terminalzustände sind final; ein verspätetes Provider-Delta darf sie nicht mehr ändern. Bei Stop setzt der Server den Abbruchwunsch, signalisiert den laufenden Provider-Task und speichert danach den tatsächlichen Endzustand. Ein Klick ist erst dann als abgeschlossen sichtbar, wenn die serverseitige Bestätigung eingegangen ist.

### Reconnect und Doppelsendungen

- `GET /responses/{id}/events?after=<seq>` liefert fehlende Ereignisse bzw. einen konsistenten Snapshot und neue Events.
- Auth und Rechte werden bei jeder Wiederverbindung erneut geprüft.
- Bei Verbindungsabbruch ist festgelegt, ob Generierung weiterläuft (V1: serverseitig weiter, bis Limit/Stop) und wie lange Events aufbewahrt werden.
- Erneute POSTs mit demselben Idempotency-Key starten keine zweite Generation.
- Der Browser darf unbestätigte Token-Teile nicht dauerhaft als endgültige Nachricht behandeln.
- Wenn der Anbieter kein Cancel unterstützt, schließt das Backend den Lauf geordnet und dokumentiert, ob die Upstream-Abrechnung ggf. weitergeht.

## 7. Modellabstraktion / Pydantic AI

Öffentlicher Vertrag der internen Gateway-Schicht, sinngemäß:

```python
class ModelGateway(Protocol):
    async def stream_response(
        self,
        *,
        model: ModelConfig,
        messages: list[CanonicalMessage],
        cancellation: CancellationToken,
    ) -> AsyncIterator[CanonicalEvent]: ...
```

Pydantic AI dient der Orchestrierung; Gateway und Domain-Schema bleiben providerunabhängig. Fähigkeiten je Modell in der Registry: `supports_streaming`, `supports_tools`, `supports_vision`, `supports_reasoning`, `context_window`, `max_output_tokens`. Backend lehnt nicht unterstützte Wünsche explizit ab, statt sie stillschweigend zu ignorieren.

**Provider-Konfiguration:** Keys nur aus Secret-Store/Umgebung, nie im DB-Export oder Frontend. Ein Fake-Provider für deterministische Integrationstests muss Streaming-Deltas, Verzögerung, Fehler und Cancel simulieren können.

**Kontextaufbau:** Nur aktiver Branch, serverseitige System-/Workspace-Instruktionen und genehmigte Inhalte; Tokenbudget vor dem Aufruf prüfen. In V1 keine stille semantische Kürzung. Bei Kontextüberschreitung eindeutige Fehlermeldung oder dokumentierte regelbasierte Strategie.

**Sensible Informationen:** Kein ungefragtes Mitsenden anderer Chats, Projekte oder Unternehmensdaten. Logs enthalten standardmäßig keine Klartextprompts oder Antworttexte.

## 8. Frontend-UX-Vertrag

### Bildschirmzustände

- **Leerer Chat:** Überschrift, mittig platziertes Prompt-Feld; nach erster Nachricht Layoutwechsel ans untere Ende.
- **Laufender Chat:** Antwort wächst schrittweise, Eingabe- und Stop-Zustand eindeutig, Token-Layout stabil.
- **Abgebrochen:** bis dahin generierter Inhalt bleibt sichtbar und als unvollständig markiert.
- **Fehlgeschlagen:** vorhandene Teilantwort bleibt; Fehler mit Retry-Möglichkeit.
- **Alternative Antworten:** Variante `2 / 3` und Pfeile, Auswahl ändert sichtbaren Pfad ohne Datenverlust.
- **Editierte Frage:** Ursprungsfrage bleibt als Geschwistervariante abrufbar.

### Scroll-Verhalten (Abnahmekriterium, kein Schönheitsdetail)

- Automatisch nach unten scrollen nur, wenn der Nutzer vor neuem Inhalt nahe dem unteren Ende war.
- Beim aktiven Scrollen nach oben kein erzwungenes Nachziehen.
- Bei Rückkehr nach unten darf Autoscroll wieder einsetzen.
- Beim Wechsel zwischen Varianten bleibt sichtbarer Kontext möglichst stabil; keine unerwarteten Sprünge.
- Composer-Resize, Codeblöcke und nachladende Inhalte dürfen den Viewport nicht unkontrolliert verschieben.

### Accessibility und Responsive

- Funktional ab schmalen Mobilansichten; Sidebar als zugänglicher Drawer.
- Sichtbarer Tastaturfokus, semantische Rollen, verständliche Labels, Escape für Dialoge.
- Streaming wird nicht als permanente Screenreader-Live-Region vorgelesen; maßvoller Statushinweis.
- Reduzierte Animation bei `prefers-reduced-motion`.
- Fokus bleibt nach Senden/Stoppen an sinnvoller Position.

### Frontend-State

- Serverdaten über dedizierte API-Schicht; lokaler State nur für UI, laufende Deltas und noch nicht bestätigte Entwürfe.
- Entwürfe pro Gespräch lokal speichern; keine sensiblen Prompts in unnötige Analytics senden.
- Generierungsstatus und ausgewählter Branch mit Server synchronisieren.
- Kein unkontrolliertes Rendern von HTML aus Markdown; Sanitizing/XSS-Tests erforderlich.

## 9. Security, Privacy und Betrieb

### Unverzichtbar

1. OIDC Issuer/Audience/Nonce/State/PKCE prüfen; Session-Rotation und Logout.
2. CSRF-Schutz, Secure/HttpOnly-Cookies, Content Security Policy und sichere CORS-/Proxy-Konfiguration.
3. Jede Resource-Operation filtert nach berechtigter Organisation; Cross-Tenant-Integrationstests für **alle** Endpunkte, inklusive SSE.
4. PostgreSQL RLS als zusätzliche Grenze und klare Session-Context-Verwaltung für Connection-Pooling.
5. Modellfreigaben, Token-/Rate-Limits und Concurrency-Limits pro Organisation/Benutzer.
6. Secrets nie im Code, in Responses, Logs oder Client-Bundles.
7. Audit: Logins, Rollenwechsel, Löschungen, Modellkonfigurationsänderungen; keine Inhaltsprotokollierung ohne explizite Vorgabe.
8. Data Retention, Export/Löschung und Backup-Restore-Prozesse dokumentieren.
9. Eingabe-/Ausgabegrenzen, Timeouts, Backpressure, Abbruch und Fehlerbehandlung.
10. Keine Tool-Ausführung ohne späteres eigenständiges Rechte- und Approval-Modell.

### Observability

Request-ID, Generation-ID, Organisation-ID pseudonymisiert, Latenz bis zum ersten Token, Tokens/s, Fehlerrate, Cancel-Rate, Provider-Latenz, DB-Pool-Metriken; strukturierte Logs und getrennte Health-/Readiness-Endpunkte.

### Deployment

- Docker Compose mit Frontend, Backend, PostgreSQL, Reverse Proxy; Datenbank nicht öffentlich exponieren.
- Versionierte Migrationen als kontrollierter Deploy-Schritt (kein stilles Auto-Migrate in jedem Replica).
- Dev-, Test- und Prod-Konfiguration strikt getrennt.
- Backup und **Restore-Test** vor Produktivfreigabe.
- TLS, Security-Header, Ressourcenlimits, Rolling-/Restart-Strategie dokumentieren.

## 10. Qualitätssicherung

| Ebene | Werkzeuge | Pflichtumfang |
|---|---|---|
| Python Unit | pytest | Branching, Validierung, Zustandsmaschine, Budgets |
| Python Integration | pytest + Test-PostgreSQL | Transaktionen, Migrationen, RLS, Isolation |
| Provider Contract | Fake und Mock HTTP | Streaming, Timeouts, Cancel, fehlerhafte Deltas |
| Frontend Unit | Vitest | Composer, SSE-Reducer, Varianten-Navigation |
| End-to-End | Playwright | Desktop/Mobile, Auth, Chat, Scroll, Reconnect |
| Static Analysis | Ruff, Pyright, ESLint, vue-tsc | Typen, Stil, Sicherheits-Basics |
| API Contract | OpenAPI + Client-Generierung | Schema-Drift verhindert |

### Kritische Testfälle

1. Start → erste Frage → SSE-Deltas → Abschluss → Reload: Verlauf identisch.
2. Während Streaming nach oben scrollen: Position bleibt; „Nach unten“-Aktion funktioniert.
3. Stoppen: keine weiteren neuen Deltas nach finalem Cancel; partielle Antwort erhalten.
4. Frühere Frage editieren: neuer Branch; Original-Branch weiter auswählbar.
5. Antwort regenerieren: zweite Assistentenantwort am gleichen Parent, beide Varianten sichtbar.
6. Zwei parallele Tabs: Konflikt bei aktiver Branch-Wahl klar behandelt.
7. Browser offline und zurück: keine doppelten Nachrichten; Resume/Snapshot konsistent.
8. POST-Retry mit gleichem Idempotency-Key: genau eine Generation.
9. Benutzer aus Org A darf weder Metadaten noch Inhalte/Streams aus Org B abrufen.
10. Markdown mit gefährlichem HTML/Links: kein XSS.
11. Lange Codeblöcke und mobile Tastatur: Composer und Scroll bleiben bedienbar.
12. Provider-Timeout, 429 und ungeordnetes Ende: stabile Fehleranzeige und keine hängenden Generierungen.

## 11. Umsetzung in Etappen

**Regel:** Codex implementiert immer **nur die ausdrücklich freigegebene Etappe**. Jede Etappe endet mit Testnachweis, Dokumentation und einer klaren Liste offener Punkte. Keine stillen Erweiterungen des Umfangs.

### Etappe 0 – Foundation

**Implementieren:** Monorepo-Struktur, Nuxt-4-App, FastAPI-App, uv-/Node-Lockfiles, PostgreSQL Compose, `.env.example`, Lint/Tests, Health/Readiness, GitHub Actions, OpenAPI-Client-Generierung, README mit Startbefehlen.

**Akzeptanz:** Frischer Checkout startet reproduzierbar; FE↔BE-Health funktioniert; DB-Verbindung testbar; Migration-Baseline ausführbar; CI grün; keine Secrets committed.

### Etappe 1 – UI-Prototyp mit Fake-Provider

**Implementieren:** Sidebar, Chat-Start/Verlauf, responsiver Composer, Theme, Markdown/Code, SSE-Simulator, Stop-Button, Scroll-Logik, Fake-Varianten, Fehlerzustände, Tastatursteuerung.

**Akzeptanz:** Desktop- und Mobile-E2E für Send/Stop/Scroll/Regenerate/Edit mit Fake-Daten grün; visuelle Referenz-Screenshots vorhanden.

### Etappe 2 – Domain, DB und Auth

**Implementieren:** SQLAlchemy-Modelle, Migrationen, Sessions, OIDC, Organisationen, RLS, Chat-CRUD, Nachrichtenbaum, Branch-Auswahl, API-Verträge, Zugriffstests.

**Akzeptanz:** Reload persistiert korrekte Daten; Parent-Invarianten sind erzwungen; Cross-Tenant-Zugriffe scheitern; OIDC-Login funktioniert in einer Testumgebung.

### Etappe 3 – Echte Pydantic-AI-Integration

**Implementieren:** Model Gateway, Registry, noris-Provider, SSE-Eventlog, Resume, Cancel, Idempotenz, Usage, Kontextbudget, Fehlerbehandlung.

**Akzeptanz:** Live-Modell antwortet, Stop ist verlässlich, Reconnect erzeugt keine Dopplungen, Fehlerszenarien sind automatisiert geprüft. Echte Provider-Zugangsdaten sind nie im Browser.

### Etappe 4 – Produktionsreife

**Implementieren:** Security-Hardening, Monitoring, Rate-Limits, Backup/Restore, Retention, Browser-/Mobiltests, Load-/Soak-Tests, dokumentiertes Deployment und Runbook.

**Akzeptanz:** Kritische E2E-/Security-Tests grün; Backups wurden testweise wiederhergestellt; klare Rollback-Prozedur; Produktiv-Freigabecheckliste abgeschlossen.

## 12. Definition of Done je Änderung

- Architektur und Zielverhalten aus `PLAN.md` eingehalten; Abweichungen als ADR dokumentiert.
- Migrationen auf frischer und bestehender Datenbank getestet.
- Neue Endpunkte in OpenAPI dokumentiert und Frontend-Typen aktualisiert.
- Erfolgs-, Fehler-, Rechte- und Abbruchfälle getestet.
- UX nicht nur visuell, sondern mit Tastatur und Mobile überprüft.
- Logging enthält keine unnötigen personenbezogenen Chat-Inhalte.
- Reproduzierbare Testbefehle und Ergebnisse im PR dokumentiert.

## 13. Offene Punkte vor Integration / Produktion

- [ ] Konkrete noris-AI-API-URL, Protokoll, Authentifizierung, unterstützte Modelle/Capabilities und Streaming-Semantik klären.
- [ ] OIDC-Identity-Provider, erlaubte Domains/Gruppen und Rollen-Mapping abstimmen.
- [ ] Organisatorische Regeln für Speicherung, Löschung, Backups und Modell-Datenverarbeitung definieren.
- [ ] Anforderungen an Deployment-Ziel, TLS, Logging, Skalierung und Ausfallsicherheit festlegen.
- [ ] Endgültige noris-AI-Branding-Vorgaben (Logo, Typografie, Farbpalette) erhalten.

Diese Punkte blockieren **nicht** Etappe 0 und den Fake-Provider-UI-Prototyp.

## 14. Codex-Startprompt

> Lies `PLAN.md` vollständig und behandle sie als verbindliche technische Spezifikation. Implementiere **ausschließlich Etappe 0 – Foundation**. Nutze stabile Versionen des vereinbarten Stacks und dokumentiere die gewählten Versionen in Lockfiles. Erstelle Monorepo, Nuxt-4-Frontend, FastAPI-Backend, PostgreSQL mit Docker Compose, initiale Alembic-Migration, gemeinsame API-Verträge, Linting, Tests und GitHub Actions. Halte Secrets aus dem Repository. Führe die verfügbaren Checks aus und dokumentiere exakt, welche erfolgreich waren und welche ggf. nicht laufen konnten. Prüfe deine Änderungen auf Widersprüche zu den Architekturentscheidungen. Beginne keine spätere Etappe ohne Freigabe.

---

**Leitprinzip:** PostgreSQL verwaltet den verbindlichen Gesprächszustand; Pydantic AI liefert Modell-Orchestrierung; Nuxt 4 sorgt für das Chat-Erlebnis. Änderungen früherer Fragen und erneutes Generieren erzeugen echte, persistente Alternativen statt destruktiver Überschreibungen.
