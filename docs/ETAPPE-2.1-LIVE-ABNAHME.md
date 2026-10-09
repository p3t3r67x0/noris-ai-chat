# Etappe 2.1: Live-Abnahme am 2026-10-09

Branch: `feat/noris-ai-integration`. PR: [#19](https://github.com/p3t3r67x0/noris-ai-chat/pull/19). Die bestehende Kette `RealTransport → FastAPI LLMGateway → OpenAICompatibleProvider → Noris` wurde tatsächlich im Browser verwendet. Keine neue Provider-Architektur und keine Änderungen an Layout, Sidebar, Composer oder Scrollcode.

## Konfiguration und Zugang

- Provider: `openai-compatible`, Basis `https://ai.noris.de/v1`, Host-Allowlist `["ai.noris.de"]`.
- Genau ein konfiguriertes Modell: `vllm/release/gpt-oss-120b`, Anzeigename `GPT-OSS 120B`. Die ID ist [von Noris dokumentiert](https://noris.cloud/nai/models/gpt-oss-120b/).
- Authentifiziertes `GET /v1/models`: **PASS**, HTTP 200, Modell im Account-Katalog gelistet. Die spätere erfolgreiche Generierung bestätigt zusätzlich die Nutzbarkeit.
- Frontend: `NUXT_PUBLIC_CHAT_TRANSPORT=real`; Same-Origin-Proxy auf das bestehende Backend. Isolierte lokale Ports 8594/8595.
- Provider-Key ausschließlich im Backend aus `NORIS_LLM_API_KEY` der vorhandenen gitignorierten `.env` gelesen. Keine Kopie in Frontend, Playwright, Git oder Berichte.
- Separate, zufällig erzeugte HTTP-Basic-Anwendungszugangsdaten. Nur diese erhält Playwright über eine private Datei mit Modus 0600. Die Datei wird beim Beenden des Testservers entfernt.
- Ein Backend-Worker, eine gleichzeitige Generierung, 256 maximale Ausgabetokens pro Request, 8192 lokales Kontextlimit, bestehende Byte-/Timeout-/Raten-/Budgetgrenzen. Keine automatischen Retries.
- Ursprüngliche ausdrückliche Freigabe: drei Aufrufe; anschließend zwei weitere ausdrücklich freigegeben. **Genau fünf Upstream-Generierungen** ausgeführt. Der Testzähler bleibt bei Serverneustarts erhalten.

## Gefundene und korrigierte Kompatibilität

Noris lässt `choices[0].finish_reason` in Zwischen-Chunks weg. Die ersten zwei Versuche ergaben deshalb `INVALID_RESPONSE`, obwohl HTTPS, Bearer-Anmeldung, Modellzugriff und SSE mit HTTP 200 funktionierten. Die Diagnose speichert ausschließlich feste Feldpfade und Validierungsfehlerarten, keine Provider-Inhalte oder Eingabewerte.

Der bestehende Adapter akzeptiert jetzt ein fehlendes `finish_reason` als Zwischen-Chunk. Ein gültiger terminaler Finish und `[DONE]` bleiben verpflichtend. Regressionstests prüfen sowohl erfolgreiche Noris-Chunks als auch weiterhin abgelehnte Streams ohne Abschluss. Der öffentliche Chat-/SSE-Vertrag bleibt unverändert.

Ein weiterer MCP-Versuch erreichte mit dem Provider-Standard das 256-Token-Limit bereits im Reasoning (`finish_reason=length`). Das wurde korrekt als `OUTPUT_LIMIT` gemeldet. Für kurze Smoke-Tests wird daher `NORIS_LLM_REASONING_EFFORT=low` verwendet. Diese optionale Einstellung sendet `reasoning_effort` nur serverseitig; ohne Einstellung bleibt der Provider-Standard erhalten. [Noris dokumentiert Reasoning-Stufen und deren Kosten](https://noris.cloud/nai/concepts/reasoning/); die [vLLM-Harmony-Implementierung](https://github.com/vllm-project/vllm/blob/main/vllm/entrypoints/openai/parser/harmony_utils.py) unterstützt low/medium/high. Die Noris-Annahme von `low` wurde durch den letzten Live-Aufruf geprüft. Reasoning wird nicht als Antworttext oder Konversationskontext übernommen.

## Tatsächliche Live-Aufrufe

MCP-Testfrage: „Erkläre in zwei Sätzen, was ein MCP-Server ist.“ Für Stop wurde eine laufende Aufzählung von 1 bis 100 angefordert. Jede Anfrage verwendete `max_tokens=256`.

| Nr. | Prüfung / Einstellung | Ergebnis | Messung am Provider-Adapter |
| --- | --- | --- | --- |
| 1 | Eigenständige HTTP-Probe, ursprünglicher Adapter | **FAIL**: `INVALID_RESPONSE` | HTTP 200/SSE; 316 ms; kein Text |
| 2 | Browser-Probe, ursprünglicher Adapter | **FAIL**: fehlendes Zwischen-Chunk-Feld | HTTP 200/SSE; 220 ms; kein Text |
| 3 | Browser-Stop, korrigierter Adapter, Provider-Standard | **PASS** | Erstes Textdelta 689 ms; Abbruch nach 859 ms; HTTP und Socket geschlossen |
| 4 | Eigenständige HTTP-Probe, korrigierter Adapter, Provider-Standard | **FAIL**: `OUTPUT_LIMIT` | HTTP 200/SSE; 1477 ms; Reasoning erreicht Tokenlimit |
| 5 | Browser-MCP-Test, korrigierter Adapter, `low` | **PASS** | Erstes Textdelta 212 ms; Stream vollständig nach 511 ms; 81 Textdeltas, 395 Zeichen |

Der letzte Browser-Test erhielt HTTP 200 von FastAPI und Noris, gültiges SSE/UTF-8, `finish_reason=stop`, `[DONE]` und den bestehenden `response.completed`-Abschluss. Die dargestellte Antwort enthält MCP; der Test speichert nur diesen Prüfbefund und die Zeichenanzahl. Senden bis dargestelltem Abschluss dauerte 1001 ms. Die Gesamtlaufzeit des Playwright-Falls einschließlich Anmeldung, Navigation und Fehlerprüfung betrug 19 Sekunden; sie ist keine reine Modelllatenz.

Modellwahl, sichtbarer Streaming-Status, Eingabefokus, Nachrichtenanker unter dem Header und fehlender Viewport-Overflow: **PASS**. Eine anschließend absichtlich zu große Eingabe zeigt den vorhandenen Fehler-/Retry-Zustand. Der Provider-Zähler bleibt unverändert: **PASS**, kein zusätzlicher kostenpflichtiger Aufruf.

Die eigenständige HTTP-Probe wurde nach Einstellung von `low` nicht erneut ausgeführt: **NOT TESTED** für diese Kombination. Der vollständige HTTP-/SSE-Pfad mit dieser Einstellung ist durch Browser-Aufruf 5 nachgewiesen; die Fehlschläge der eigenständigen Proben bleiben oben als **FAIL** dokumentiert. Der frühere Zugangsdaten-Blocker ist behoben.

## Abbruch und Grenzen

| Aussage | Status | Nachweis |
| --- | --- | --- |
| Browser-Fetch abgebrochen | **PASS** | Tatsächliches AbortSignal im Browser beobachtet |
| FastAPI beendet Provider-Iteration | **PASS** | Cancellation am bestehenden Adapter beobachtet |
| Upstream-HTTP-Abbruch | **PASS** | HTTPX-Response geschlossen, tatsächlicher Socket mit `fileno() == -1` |
| Teilantwort erhalten; keine weiteren sichtbaren Chunks | **PASS** | 38 Zeichen im Browser erhalten; Text und Delta-Zähler nach einer Sekunde unverändert |
| Noris-GPU-Abbruch | **NOT TESTED** | Keine Provider-Telemetrie oder belegte Cancel-API |
| Noris-Abrechnungsstopp | **NOT TESTED** | Keine Abrechnungs-/Job-Telemetrie |

Die lokale App-Anmeldung verwendete Loopback-HTTP; der Provider-Zugriff verwendete HTTPS. Dies ist eine Live-Funktionsabnahme, keine Abnahme eines öffentlichen TLS-/Ingress-Deployments. Account-Quotas, Lastverhalten, Multi-Worker-Budgets und weitere Modelle sind **NOT TESTED**. Die 256-Token-Grenze kann bei anderen Fragen auch mit `low` erreicht werden; dann ist `OUTPUT_LIMIT` das erwartete Ergebnis.

## Automatisierte Prüfung und Reproduktion

Lokale Backend-/Contract-/HTTP-, Frontend-Unit-, Simulator-Browser-, Lint-, Typecheck-, API-Drift-, Produktionsbuild- und Compose-Konfigurationsprüfungen werden auf dem finalen Stand durchgeführt. Die vollständige Foundation-CI führt zusätzlich die bisherigen 40 Mock-/UI-Browserfälle, PostgreSQL-Integration und einen frischen Docker-Stack aus. Verbindlicher Nachweis für den finalen Commit: [Checks von PR #19](https://github.com/p3t3r67x0/noris-ai-chat/pull/19/checks); detaillierte Prüfliste: [Etappe-2-Testergebnisse](ETAPPE-2-TESTERGEBNISSE.md).

Das lokale Hilfsmodul `noris_ai.llm.live_acceptance` wird niemals von der Produktionsanwendung importiert. Es verwendet den vorhandenen Adapter und Gateway, beobachtet nur Status/Zeiten/Zähler und begrenzt kostenpflichtige Requests. Unit- und TCP-Tests prüfen Opt-in, private Dateien, erhaltenen Aufrufzähler und Socket-Schließung. Der zusätzliche Startschritt `GET /v1/models` führt keine Textgenerierung aus.

Nur nach ausdrücklicher Kostenfreigabe, mit vorhandener serverseitiger Key-Konfiguration:

```sh
# Terminal 1; Session-Verzeichnis außerhalb von Git, vorhandene serverseitige .env.
NORIS_RUN_LIVE_LLM_SMOKE=1 PYTHONPATH=backend/src \
uv run --project backend --locked python -m noris_ai.llm.live_acceptance server \
  --session /tmp/noris-live-acceptance --env-file .env \
  --allow-paid-calls 3 --reasoning-effort low

# Terminal 2; Nuxt erhält keinen Provider-Key.
env -u NORIS_LLM_API_KEY NORIS_DEV_API_TARGET=http://127.0.0.1:8594 \
  NUXT_PUBLIC_CHAT_TRANSPORT=real pnpm --dir frontend dev --host 127.0.0.1 --port 8595

# Terminal 3; ein HTTP-Aufruf, danach zwei Browser-Aufrufe (MCP und Stop).
env -u NORIS_LLM_API_KEY NORIS_RUN_LIVE_LLM_SMOKE=1 PYTHONPATH=backend/src \
uv run --project backend --locked python -m noris_ai.llm.live_acceptance http \
  --session /tmp/noris-live-acceptance --allow-paid-calls 3

env -u NORIS_LLM_API_KEY NORIS_RUN_LIVE_LLM_SMOKE=1 NORIS_LIVE_TEST_STOP=1 \
  NORIS_LIVE_APP_ORIGIN=http://127.0.0.1:8595 NORIS_LIVE_SESSION=/tmp/noris-live-acceptance \
  pnpm --dir frontend test:e2e:live
```

Ein neues Session-Verzeichnis bedeutet einen neuen Zähler und benötigt eine entsprechende Kostenfreigabe. Eine Erhöhung auf fünf erfolgt ebenfalls nur nach neuer ausdrücklicher Freigabe. Playwright verwendet keine Retries, Screenshots, Videos oder Traces. Ohne `NORIS_RUN_LIVE_LLM_SMOKE=1` werden beide Live-Tests vor Browser-/Netzwerkstart übersprungen.

Die abschließende Browser-Vorprüfung verlangt außerdem ein Kataloglimit von genau 256 Ausgabetokens, bevor eine Nachricht gesendet wird. Gegen den Simulator bestehen beide Live-Testfälle; ein auf 1024 gesetzter Katalog wird bereits vor der Generierung abgelehnt, mit unverändertem Upstream-Zähler. Ohne Opt-in wird auch bei einem nicht mehr existierenden Session-Zugangspfad keine Zugangsdaten-Datei gelesen.

## Merge und Parallelentwicklung

Die Basis bleibt PR #17 (`feat/chat-ux-polish`), mit den Vertragsabhängigkeiten #14 → #15 → #16 → #17. PR #18 ist unabhängig und wird durch diese Arbeit nicht verändert. Die isolierte Arbeitskopie verhindert Eingriffe in dessen laufenden Workspace. Etappe 2.1 ändert gemeinsame Backend-Konfiguration und genau eine Compose-Variable; keine zusätzlichen UI-Schnittstellen. Kein Merge nach `main`. Eine Merge-Freigabe setzt grüne Checks des aktuellen PR-Heads und Betreiberabnahme voraus.
