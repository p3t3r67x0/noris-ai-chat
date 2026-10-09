# Etappe 2: Prüfnachweise

## Aktueller Stand Etappe 2.1

Am 2026-10-09 wurden tatsächliche Noris-Modellberechtigung, Browser-End-to-End-Streaming mit GPT-OSS 120B und Stop einschließlich Upstream-Socket-Schließung geprüft: **PASS**. Zwei anfängliche Chunk-Validierungsfehler und ein Outputlimit im Reasoning sind mit ihren **FAIL**-Ergebnissen im [Live-Abnahmebericht](ETAPPE-2.1-LIVE-ABNAHME.md) dokumentiert. Die erfolgreiche Konfiguration verwendet serverseitig `NORIS_LLM_REASONING_EFFORT=low` und höchstens 256 Ausgabetokens. GPU-Abbruch und Abrechnungsstopp bleiben jeweils **NOT TESTED**.

| Finale lokale Prüfung | Status | Nachweis |
| --- | --- | --- |
| Backend Unit-/Contract-/TCP-Integration | **PASS** | 102 Tests, davon 6 echte lokale HTTP-Tests |
| Frontend Unit-/Transport-/Branch-Kontext | **PASS** | 89 Tests in 11 Dateien |
| Bestehende RealTransport-Browserfälle | **PASS** | 6 Fälle, Desktop und Mobile, ausschließlich Simulator |
| Live-Playwright MCP und Stop | **PASS** | Getrennte erfolgreiche Live-Läufe nach ausdrücklicher Kostenfreigabe; 5 tatsächliche Generierungen einschließlich 3 Fehlschlägen |
| Live-Fehleranzeige ohne Mehrkosten | **PASS** | `CONTEXT_LIMIT`, Retry sichtbar, unveränderter Upstream-Zähler |
| API-Drift, ESLint, Ruff, strikte Typprüfungen | **PASS** | Bestehende Checkbefehle; öffentlicher API-/SSE-Vertrag unverändert |
| Backend-/Frontend-Produktionsbuild | **PASS** | Wheel/sdist und Nuxt/Nitro |
| Compose Basis/Entwicklungskonfiguration | **PASS** | Bestehendes Compose-v2-Wrapper-Skript, `.env.example`, jeweils `config --quiet` |
| Vollständige Mock-/UI-, DB- und Docker-Laufzeit-Suite lokal | **NOT TESTED** | Isoliert über [PR-Checks](https://github.com/p3t3r67x0/noris-ai-chat/pull/19/checks) prüfen; 40 bisherige Browserfälle, 3 PostgreSQL-Tests und frischer Compose-Stack |

Die bisherigen Etappe-2-Ergebnisse unten bleiben als historischer Stand erhalten. Deren fehlende Zugangsdaten sind kein aktueller Blocker mehr. Die eigenständige HTTP-Probe nach Umschaltung auf `low` ist **NOT TESTED**; der komplette HTTP-/SSE-Pfad dieser Konfiguration ist durch den erfolgreichen Browser-Lauf nachgewiesen. Öffentlicher TLS-/Ingress-Betrieb, Provider-Quotas und Lasttests sind **NOT TESTED**.

**Vollständige CI: PASS** auf Implementierungscommit `b0f7ad0ae75bac0426d636637544613ce8ccad3e`: [PR-Lauf](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37889407015), einschließlich `checks` und `compose-smoke`. 102 Backend-/Contract-/HTTP-, 89 Frontend-, 40 Mock-/UI-Browser-, 6 RealTransport-Browser- und 3 PostgreSQL-Tests: insgesamt 240 automatisierte Tests. Lint, strikte Typprüfung, API-Drift, Migrationen, Produktionsbuilds und frischer Docker-Smoke ebenfalls bestanden. Eine anschließend ergänzte Live-Vorprüfung des 256-Token-Kataloglimits und diese Nachweisdokumentation werden erneut durch die Checks des aktuellen PR-Heads geprüft.

## Ursprüngliche Etappe-2-Prüfung

Prüfdatum: 2026-10-09. Branch `feat/noris-ai-integration`, Basis PR #17 / `2d258f1b7c6312058c18047cc10ddb6df711181d`. Alle hier aufgeführten lokalen Modellaufrufe nutzen deterministische Fixtures; keine echten Provider-Zugangsdaten und keine kostenpflichtigen Calls. Die Tabelle beschreibt die lokalen Läufe. GitHub Actions führt auf dem PR zusätzlich die vollständigen Foundation-/Mock-Browser-, PostgreSQL- und Compose-Prüfungen aus; maßgeblich ist der aktuelle Check-Stand des PRs.

| Prüfung | Status | Tatsächlicher Nachweis |
| --- | --- | --- |
| Backend Unit-/OpenAPI-Contract-Tests | **PASS** | 89 Tests; `pytest backend/tests/unit backend/tests/contract` |
| Lokale HTTP-Integration | **PASS** | 5 Tests mit realen TCP-Verbindungen zu simuliertem HTTP-Provider und FastAPI |
| Frontend Unit-/Transport-/Kontext-Tests | **PASS** | 89 Tests in 11 Vitest-Dateien; Mock-/Real-Vertrag und unveränderte Zustandsmaschine |
| Browser-Integration Real-Transport | **PASS** | 6 Fälle: Streaming, Stop/Fortsetzung, Retry/Modellwechsel jeweils Desktop und Mobile |
| Ruff Lint und Format | **PASS** | Gesamtes Backend; 38 Python-Dateien |
| ESLint | **PASS** | Gesamtes Frontend einschließlich neuer Testkonfigurationen |
| Strikte Python-Typprüfung | **PASS** | Pyright 1.1.408; 0 Fehler/Warnings |
| Nuxt und Vue-/Test-Typprüfung | **PASS** | `nuxt typecheck` und `vue-tsc --noEmit --project tsconfig.tests.json` |
| Generierungsskripte typisiert | **PASS** | `tsc --project tsconfig.tools.json` |
| OpenAPI-/TS-Drift | **PASS** | `node scripts/generate-api.mjs --check` |
| Backend-Produktionsbuild | **PASS** | Wheel und sdist mit fixiertem Lockfile erstellt |
| Frontend-Produktionsbuild | **PASS** | Nuxt/Nitro-Produktionsbuild erfolgreich |
| Compose-Konfiguration | **PASS** | Basis und Entwicklungs-Overlay mit `.env.example` validiert |
| Live-Test ohne Opt-in | **PASS** | Ein Test wird vor Browser-/Netzwerkstart übersprungen; dies bestätigt nur den Opt-in-Schutz |
| Bestehende vollständige UI-/DB-/Docker-Laufzeit-Suite lokal | **NOT TESTED** | Getrennte laufende UI-Arbeitskopie wird nicht gestört; disposable DB und vollständiger Stack werden in CI geprüft |
| Echter Noris-End-to-End-Smoke | **BLOCKED** | Keine bereitgestellten Provider-Zugangsdaten/Anwendungsinstanz; nicht als PASS gewertet |
| Account-Modellberechtigung und aktuelle Noris-Liveness | **BLOCKED** | Dokumentierte Modell-ID und API sind kein Laufzeitnachweis |
| Noris-GPU-/Abrechnungsstopp bei Socket-Abbruch | **NOT TESTED** | Lokaler HTTP-Abbruch nachgewiesen; tatsächliche Provider-Wirkung ungeprüft |

## Abgedeckte Fälle

Provider-Tests prüfen korrektes Request-JSON, serverseitigen Bearer-Header und URL, fragmentierte UTF-8-Daten mit Netzwerkgrößen 1/2/7/8192, SSE-Kommentare/Multi-Line-Data, BOM und abschließende LF-/CRLF-/CR-Ereignisse an jeder Bytegrenze. Ungültiges JSON/UTF-8, falsche Datentypen, leere Antworten, unvollständiger Abschluss, fehlendes `[DONE]`, Outputgrenzen und Content-Filter enden nachvollziehbar mit Fehler. 401/403, 429, 404, 500, Redirects und Netzwerk-/Timeoutfehler werden ohne Provider-Inhalte übersetzt.

API-/Gateway-Tests prüfen anonyme Sperre auf beiden Endpunkten, deaktivierten Provider ohne Health-Ausfall, Modell-Allowlist, Kontext-, Body-, Rate-, Budget- und Duplikatgrenzen, Origin-Kontrolle, unzulässige privilegierte Rollen/Provider-URLs, leere User-Nachrichten und ungültige Unicode-Eingaben. Modelle wechseln tatsächlich im Provider-Aufruf. Teilantworten bleiben bei terminalem Fehler erhalten. Gesamttimeout gibt den aktiven Slot frei. Ein leerer Assistant-Knoten nach frühem Stop bleibt in der aktiven Kontextfolge zulässig.

Die fünf HTTP-Integrationstests verwenden Uvicorn auf dynamisch gebundenen Loopback-Ports statt nur In-Memory-Mocks. Sie prüfen erfolgreiche UTF-8-Weiterleitung, Rate Limit, Timeout, ungültige Daten und Client-Disconnect während Provider-Stille. Beim Disconnect wird das Ende des Upstream-Generators tatsächlich beobachtet.

Frontend-Contract-Tests speisen Mock und Real durch dieselbe `useChatStream`-Zustandsmaschine. Sie prüfen Fragmentierung, Sequenzfehler, abgebrochene/ungültige Streams, Proxy-Fehler ohne HTML-Leak, externe Abbrüche schon während der Headerphase, Browser-Timeout und SSE-Puffergrenzen. `createChatState`-Tests prüfen Edit, Antwortvarianten, ausgewählten Branch, Retry und Modellwechsel: Requests enthalten nur die User-/Assistant-Nachrichten des aktiven Parent-Pfads, keine ungewählten Schwesterantworten. Der konfigurierte Modellkatalog erhält die bestehende reaktive Array-Identität und übernimmt keine gespeicherten, nicht freigegebenen IDs.

Playwright startet simulierten Provider → echtes FastAPI → Nuxt und sendet aus der bestehenden Oberfläche. Desktop und Mobile erhalten den UTF-8-Text. Stop beendet den stillen Provider; eine anschließende Frage übernimmt den vollständigen aktiven Pfad einschließlich leerer gestoppter Antwort. Retry nach simuliertem 429 verwendet das neu ausgewählte Modell und nur die ursprüngliche User-Frage. Neue Browser-Artefakte liegen separat in `test-results/llm`; bestehende UI-Snapshots werden nicht verändert. Die alte Browser-Suite erzwingt explizit Mock/disabled, damit auch bei einer extern konfigurierten Entwicklungsumgebung keine echten Modellcalls entstehen.

## Grenzen und Abnahme

**PASS** gilt für implementierten Adapter, rückwärtskompatiblen Transport, lokales HTTP-Streaming, Stop, Retry, Modellwechsel, ausgewählten Kontext, Schutz der Provider-Keys und die oben tatsächlich ausgeführten Checks. Die übrigen bestehenden automatisierten Prüfungen werden zusätzlich durch CI nachgewiesen.

**BLOCKED** bleibt der ausdrücklich verlangte echte End-to-End-Test gegen Noris. Die gesamte Live-Anbindung wird deshalb noch nicht als vollständig verifiziert erklärt. **NOT TESTED** sind GPU-/Abrechnungsabbruch und reale Account-Quotas. Es ist kein noch offener Implementierungsfehler aus den lokalen finalen Prüfläufen bekannt (**FAIL**: keiner); ein später fehlschlagender CI-/Live-Lauf muss entsprechend ausgewiesen werden.

Konfiguration und reproduzierbare Befehle: [Betrieb](ETAPPE-2-BETRIEB.md). Schnittstellen, Sicherheits-/Budgetgrenzen und Merge-Abhängigkeiten: [Architektur](ETAPPE-2-ARCHITEKTUR.md). Kein Merge nach `main`; zuerst die offenen Basis-PRs #14 → #15 → #16 → #17 zusammenführen. Die parallele UI-Fidelity #18 ist unabhängig; gemeinsame Script-/Konfigurationsdateien gezielt integrieren.
