# Provider-native Modellfähigkeiten

Stand: 2026-10-10. Katalogangaben sind Providerberichte, keine erfolgreichen Generierungsproben. Zwei reine GET-Prüfungen über die validierte Serverkonfiguration bestätigten Schema 2.4, Modellmetadaten und Feldstrukturen. Keine Generierung wurde für diese Änderung gegen Noris ausgeführt. Die Referenzpreise unten sind historische USD-Katalogangaben; der Browser zeigt jeweils den aktuellen **Abrufzeitpunkt** seines Backend-Katalogs. Readiness und Zugriff gelten höchstens für dessen Cache-TTL.

## Bestandsaufnahme auf main

Ausgangspunkt: `11bdf28`. `discover_models()` lieferte IDs, filterte explizites `is_ready=false` und tolerierte fehlende Bereitschaft. Modalitäten, Preise und Schema-Version wurden verworfen. Die exakte Registry führte fünf reale Chatmodelle plus optionalen Smart Router; DeepSeek V4.1 Flash und Qwen3.8 fehlten. Gemma/Qwen3.6 behaupteten Vision und 262144 Kontexttokens, während Schema 2.4 aktuell nur Texteingabe und 131072 Kontexttokens meldet. GLM 5.2 war mit 1000000 statt 1048576 erfasst. Statische, teils große Kontextwerte waren zugleich Anwendungsgrenzen. Der bisherige `ModelCost` enthielt ausschließlich unbelegte Punktefelder. `provider_max_output_tokens` hatte einen Default von 8192 und eine strukturelle Obergrenze von 131072; das konnte Providerberichte mit einer Million Ausgabetokens nicht ausdrücken.

Bereits vorhanden und erhalten: serverseitige Bearer-Authentifizierung, validierte URL/Host-Allowlist, HTTP Basic für die Anwendung, lazy Discovery, Single-Flight-Cache, Fehler-Cooldown, gemeinsame Freigabe für Chat und Titel, reservierte Tokenbudgets, Parallelitäts-/Raten-/Größenlimits und begrenzte Timeouts. Eine laufende Generierung behält das bei Admission gespeicherte Modell. PostgreSQL-Tabellen, Migrationen, Chat-Persistenz und WebSocket-v1-Protokoll bleiben unverändert. Der SSE-Kompatibilitätsmodus und die bestehende Provider-SSE-Decodierung bleiben erhalten.

## Providervertrag und Mapping

`ProviderModel` und seine verschachtelten Pydantic-Modelle lesen `data[]` mit `schema_version`, `id`, `name`, Modalitäten, `hugging_face_id`, `created`, `is_ready`, `is_free`, `discount_to_user`, Datacenter-Ländercodes sowie den tatsächlich beobachteten Compliance-Feldern `zdr` und `hipaa`. Zusätzliche Felder werden auf jeder typisierten Ebene ignoriert. Unbenutzte unterstützte Parameter bleiben intern erhalten; sie werden nicht ungeprüft zum Browser durchgereicht. Tatsächlich verwendete Tokenparameter werden zusätzlich typisiert validiert.

IDs, Bereitschaft, Streaming, Tokenzahlen und verwendete Preise werden validiert. Fehlende Fakten bleiben null/UNKNOWN. Eine ungültige Modellzeile wird ausgeschlossen; ein ungültiger Envelope erzeugt `INVALID_RESPONSE`. Doppelte IDs werden vollständig ausgeschlossen, weil ein widersprüchlicher Vertrag keine Freigabe tragen kann. Negative, unendliche, NaN- oder ungültige Preise werden abgelehnt und niemals als null USD interpretiert.

Schema 2.4 sowie kompatible Versionen innerhalb von Major 2 werden strukturell gelesen. Fehlende Versionsangaben bleiben bei vollständig gültigem Vertrag kompatibel. Andere Major-Versionen werden gelesen, aber nicht zur Generierung freigegeben. Zusätzliche Modalitäten oder Einheiten verleihen keine Fähigkeiten. Ein fehlendes `is_ready` autorisiert auch ältere Antworten **nicht** mehr.

| Providerfakt | Wirkung |
| --- | --- |
| Texteingabe + Textausgabe + explizites Streaming | Chat-Kandidat; erfordert zusätzlich lokale Chat-Endpunktfreigabe |
| Ausgabe `embeddings` | EMBEDDING; aus Chat ausgeschlossen |
| Ausgabe `rerank` | RERANKING; aus Chat ausgeschlossen |
| Eingabe `image` | Visionfähigkeit; der vorhandene Chat sendet weiterhin Text |
| Unterstütztes `reasoning_effort` oder dokumentierter Modellvertrag | Reasoningfähigkeit; keine ID-/Namensheuristik |
| `supported_inputs.max_context_length.value`, `unit=token` | Gemeldetes Kontextfenster |
| Tokenparameter `.max` und/oder `max_length.value`, `unit=token` | Kleinste anwendbare gemeldete Ausgabekapazität |
| `created` | Providerdatum; Bedeutung als Modellrelease nicht bestätigt, getrennt vom Katalogabruf |

Textausgabe allein bestätigt keinen Chat-Completions-Vertrag. Die Registry enthält weiterhin exakte lokale Freigaben, UI-Namen, Beschreibungen, Reasoning-Wiring und Sicherheits-/Timeoutpolicy. Die sieben vom Auftrag bestätigten IDs sind freigegeben. Neu entdeckte, unbekannte Chat-Kandidaten werden automatisch verarbeitet, bleiben aber bis zu einer gezielten dokumentierten Betreiberfreigabe gesperrt. Embeddings/Reranker können auch durch Overrides nicht zu Chatmodellen werden. Smart Router wird ausschließlich bei tatsächlicher Listung mit validen Text-/Streaming-Metadaten und `is_ready=true` angeboten.

## Gemeldete und effektive Limits

Die folgenden Defaults gelten ohne Betreiber-Overrides und bei den am 2026-10-10 gemeldeten Providerfakten:

| Anzeigename / vollständige ID | Providerkontext | Providerausgabe | Lokaler Kontext | Lokale Ausgabe |
| --- | ---: | ---: | ---: | ---: |
| DeepSeek V4.1 Flash · `vllm/qsu/deepseek-v41-flash` | 1048576 | 1048576 | 8192 | 4096 |
| GLM 5.3 Flash · `vllm/qsu/glm-5-3-flash` | 1048576 | 1048576 | 16384 | 8192 |
| Qwen3.8 27B · `vllm/qsu/qwen3.8-27b` | 131072 | 131072 | 8192 | 4096 |
| Gemma 4 31B · `vllm/release/gemma-4-31b-it` | 131072 | 131072 | 8192 | 2048 |
| GLM 5.2 · `vllm/release/glm-5-2` | 1048576 | 1048576 | 16384 | 8192 |
| GPT-OSS 120B · `vllm/release/gpt-oss-120b` | 131072 | 131072 | 8192 | 4096 |
| Qwen3.6 27B · `vllm/release/qwen3.6-27b` | 131072 | 8192 | 8192 | 4096 |

`provider_context_window` und `provider_max_output_tokens` sind dynamische Meldungen. `verified_max_output_tokens` ist eine explizit vom Betreiber dokumentierte Generierungsprüfgrenze; standardmäßig null. `effective_context_window`/`effective_max_output_tokens` sind die tatsächlich verwendeten Grenzen. Die bisherigen `context_window`/`max_output_tokens` bleiben als identische effektive Werte erhalten. `documented_context_window`/`supported_output_tokens` bleiben kompatible Aliasse für die gemeldeten Werte; `provenance` kennzeichnet die Herkunft. Ein Providerbericht erhält PROVIDER und DOCUMENTED, niemals automatisch LIVE_TEST/VERIFIED.

Die effektive Ausgabe ist das Minimum aus Modellpolicy, globalem `NORIS_LLM_MAX_OUTPUT_TOKENS`, gemeldeten Kapazitäten, gegebenenfalls Betreiber-/Live-Prüfgrenzen sowie Kontext nach Reasoning-, System- und Sicherheitsreserve. Ein Kontext von einer Million Tokens erhöht niemals die Ausgabe. Unbekannte Tokenunits liefern kein gemeldetes Maximum und erlauben keine automatische Erweiterung; konservative Rückfallgrenzen sind höchstens 8192 Kontext und 1024 Ausgabe. Ungültige/conflicting Konfigurationen bleiben gesperrt.

Pro Anfrage sendet der Provider exakt das durch Admission gebundene `max_output_tokens`, Titel höchstens `NORIS_LLM_TITLE_MAX_OUTPUT_TOKENS` (Default 96). Der Client kann kein größeres Tokenlimit übergeben. Die bestehenden UTF-16-, Byte-, Tokenbudget-, Parallelitäts-, Raten- und Timeoutgrenzen gelten zusätzlich.

## Betreiberkonfiguration und Herkunft

`NORIS_LLM_MODELS` bleibt die bestehende serverseitige Override-Konfiguration. Exakte IDs mit `available=false` sperren Modelle. `context_window`, `max_output_tokens`, Reserven und Timeouts sind lokale Policies. Legacy-Konfigurationsfelder `provider_context_window` und `provider_max_output_tokens` mit `provider_limit_evidence` werden als **zusätzliche Betreibergrenzen** behandelt; sie überschreiben niemals Providerfakten. Eine neue Live-Prüfgrenze wird explizit mit `verified_max_output_tokens` plus `verified_output_evidence` (oder Legacy-`provider_limit_evidence`) mit nicht geheimem Prüfverweis/Datum gesetzt. Höhere Ausgabe erfordert zusätzlich eine bewusste Erhöhung des globalen Outputceilings, verifizierte Kapazitätsangaben und genügend Kontext. Tagesbudgets werden dabei nicht geändert.

Beispiel einer bewussten, weiter konservativen Kontextanhebung:

```dotenv
NORIS_LLM_MODELS=[{"id":"vllm/qsu/deepseek-v41-flash","name":"DeepSeek V4.1 Flash","context_window":32768,"provider_context_window":32768,"provider_limit_evidence":"Betreiberfreigabe 2026-10-10, Schema 2.4 geprüft","max_output_tokens":4096}]
```

Für eine unbekannte tatsächlich geprüfte ID zusätzlich `category=CHAT`, `streaming=true`, den belegten `token_limit_parameter`, Quellen und Evidence für category/streaming/token_limit_parameter setzen; siehe Betriebsdokumentation. Kein Override kann Readiness, Modalitäten oder dynamische Preise herstellen. `provenance` trennt PROVIDER, LOCAL_POLICY, DOCUMENTATION, LIVE_TEST und UNKNOWN. Das LLMModel-Konfigurationsformat bleibt aus Kompatibilitätsgründen erhalten, dient aber ausschließlich lokaler Policy.

GPT-OSS sendet nur bei expliziter Einstellung `reasoning_effort` low/medium/high. GLM 5.2 verwendet dokumentiert `chat_template_kwargs.reasoning_effort` high/max. DeepSeek V4.1 Flash, GLM 5.3 Flash und Qwen3.8 erhalten ohne Parameterbeleg kein erfundenes Reasoning-Wiring. Legacy-`NORIS_LLM_REASONING_EFFORT` gilt ausschließlich für GPT-OSS. Titel wählen low nur bei bestätigter Unterstützung.

## Kosten

`pricing[].cost_usd` wird als Decimal eingelesen. Nur `unit=token` wird auf eine Million Tokens skaliert: `cost_usd × 1000000`. Unterstützt sind prompt, cached_prompt und completion an den jeweiligen Textmodalitäten. Unbekannte Units, fehlende oder widersprüchliche Preise bleiben UNKNOWN/null; sie werden nicht zu Gratispreisen. Decimal-Werte werden im JSON-Vertrag als Strings serialisiert. Die bisherigen Punktefelder bleiben kompatibel vorhanden, aber null; keine USD/Punkte-Umrechnung.

| Modell | Input USD/Mio. | Cache-Input USD/Mio. | Output USD/Mio. |
| --- | ---: | ---: | ---: |
| DeepSeek V4.1 Flash | 10 | 2 | 30 |
| GLM 5.3 Flash | 10 | 3 | 18 |
| Qwen3.8 27B | 12 | 3 | 100 |
| Gemma 4 31B | 6 | 1 | 17 |
| GLM 5.2 | 20 | 4 | 200 |
| GPT-OSS 120B | 6 | 1 | 25 |
| Qwen3.6 27B | 15 | 3 | 100 |

Historischer GET-Stand 2026-10-10; keine Zusage für zukünftige Preise oder Rechnung. `is_free=true` wird ausdrücklich als Provider-Gratismeldung gekennzeichnet. `discount_to_user` bleibt getrennt erhalten, weil die Einheit und Anwendung nicht durch den Katalogvertrag gesichert sind. Rabatte werden nicht eigenmächtig in USD-Preise eingerechnet. Die UI zeigt gegebenenfalls „Rabatt gemeldet; Abrechnung unbestätigt“.

Vor Admission berechnet das Gateway bei belastbaren Preisen eine konservative Schätzung mit seinem bestehenden Tokenzähler plus voller Output-/Reasoningreserve. Cachetreffer werden nicht vorausgesetzt. `estimated_max_cost_usd` zeigt in der Modellauswahl eine Katalogobergrenze aus den lokalen Tokenlimits; sie ist keine gemessene Nutzung oder Rechnung. Beispiel: DeepSeek mit 1000 Input- und 2000 Outputtokens kostet nach obigen ungekürzten Katalogpreisen geschätzt 0,07 USD. Bei unbekannten Preisen wird keine Zahl gezeigt. Es gibt keinen neuen kostenpflichtigen Probeaufruf, automatischen Ersatz oder erhöhtes Tagesbudget.

## Cache, Verfügbarkeit und Fehler

Default-TTL 300 Sekunden, Discovery-Gesamttimeout 10 Sekunden, Fehler-Cooldown 10 Sekunden. Parallele Aktualisierungen teilen einen GET. Erfolgreiche leere Listen ersetzen den alten Katalog. Nach TTL-Ablauf muss Admission erneut prüfen. Stale-Display ist standardmäßig aus; optional veraltete Einträge sind deaktiviert, haben kein Defaultmodell und `expires_in_seconds=0`. Preise behalten ihren alten Abrufzeitpunkt und die UI kennzeichnet sie als veraltet. Auth-/Modellfehler invalidieren den Cache. `is_ready=true` garantiert keine konkrete erfolgreiche Generierung oder Quota.

Modellfehler liefern die bestehenden verständlichen, bereinigten Fehlercodes. Teilantwort, Chat und Entwurf bleiben erhalten. Die UI bietet manuelle Auswahl; sie startet keinen automatischen Ersatzrequest. Browserauthentifizierung, Schlüsselhaltung und Proxy-Routing bleiben unverändert. GET/POST verwenden ausschließlich die validierte Server-URL; keine Browser-URL und keine Keys im Frontend.

## Tests und bekannte Unsicherheiten

Die Fixture `backend/tests/fixtures/noris-models-2.4.json` enthält beobachtete Struktur und historische Modellquotes, aber synthetisches Readiness/Datum. Accountdiscount, private Accountdaten, Schlüssel und Screenshots sind ausgeschlossen. Weitere Simulator-Facts sind ausdrücklich synthetisch. Unit-/Contract-/HTTP-/Browsertests verwenden ausschließlich lokale Provider. Sie prüfen Schema, neue IDs, Modalitäten, unbekannte Einheiten, Preise, Readiness, Freigaben, Cache/Entzug/Ausfall, Tokenlimits, verschiedene Reasoningparameter und beide Streamingtransporte. OpenAPI und generierte TypeScript-Typen werden zusammen geprüft.

Die Modellmaxima sind Providerberichte. Ein tatsächliches Live-Ausgabemaximum für diese Änderung bleibt NOT TESTED. Die Rabattsemantik sowie tatsächliche Rechnung, Cachetreffer, Accountquotas und GPU-Abrechnung nach Stop bleiben unbestätigt. Ein Freigabevertrag für eine bisher unbekannte ID erfordert weitere Dokumentation oder ausdrücklich autorisierte Einzelprüfung. Die vorhandenen Prozessbudgets sind weiterhin pro Backend-Worker; Neustarts setzen sie zurück. Alle Modellpolicies und Accountquotas müssen deshalb weiterhin vom Betreiber bewusst gewählt werden.

## Abnahme dieser Änderung

Prüfung am 2026-10-10, ausschließlich synthetische Generierungen. Die vorhandenen Screenshot-Toleranzen und Testaktivierungen wurden beibehalten.

| Gate | Status | Ergebnis |
| --- | --- | --- |
| `make lint` | PASS | Ruff, Format und ESLint; Frontend nach Decimal-Exponentenfix erneut geprüft |
| `make typecheck` | PASS | Python strict, Nuxt/Vue und Tools-TypeScript |
| `make check-api` | PASS | OpenAPI und TypeScript ohne Drift; WebSocket-Vertrag unverändert |
| `make test-unit` | PASS | 286 Backendtests; Frontend zuletzt 228 Tests, einschließlich Decimal-Null-/Exponentenquote |
| `make test-integration` | PASS | 30 Tests auf eigener wegwerfbarer PostgreSQL-Instanz |
| `make test-e2e` | PASS | 167 Mock/UI- und 51 SSE-/Modellkatalogtests, Desktop und Mobile |
| `make test-e2e-websocket` | PASS | 18 Tests gegen gebaute Compose-Container, Caddy und PostgreSQL |
| `make build` | PASS | Python sdist/wheel und Nuxt-Produktion |
| Compose-Konfiguration | PASS | Basis-, Entwicklungs- und Testkonfiguration validiert |
| Compose-Laufzeit mit isolierten Hostports | PASS | Separater Stack gesund, Same-Origin-Katalog und Readiness geprüft |
| Zusätzliche Docker-Bridge auf diesem Host | BLOCKED | Host-Firewall blockiert neue Bridges; sudo-Authentifizierung fehlt. Temporäres Hostnetz-Override verwendete ausschließlich freie lokale Ports |
| Kostenpflichtige Live-Generierung / maximales Provideroutput | NOT TESTED | Keine Freigabe, kein kostenpflichtiger Aufruf |
| Abschließende Gates mit FAIL | Keine | Ein durch vollen Datenträger unterbrochener Integrationslauf wurde nach gezielter Bereinigung eigener Build-Caches erfolgreich wiederholt |

Die E2E-Suites enthalten weiterhin ihre 19 bereits bestehenden Projekt-/Viewportskips (14 Mock, 5 SSE). Es wurden keine Tests deaktiviert oder Toleranzen abgeschwächt. Compose wurde als eigener Projektname mit getrennten Datenvolumes gestartet; für das Firewallhindernis wurde nur ein temporäres, nicht committetes Testoverride verwendet. Die volle Partition wurde durch gezieltes Entfernen eigener unbenutzter Testbuild-Caches entlastet. Eigene Testcontainer und -volumes wurden danach entfernt; bestehende Dienste und Nutzerdaten wurden nicht verändert.

Änderungsbereiche: Backend-Providervertrag/-Schemas, Catalog-Service, lokale Registry, Modell-/Kostenvertrag und Gateway-Schätzung; synchronisierte OpenAPI-/TypeScript-Dateien; Modellauswahl-Metadatenformatierung; bereinigte Fixture und Unit-/Contract-/HTTP-/WebSocket-/Browsertests; README, Betriebsdokumentation und `.env.example`. Kein neues Providerframework, keine DB-Migration und keine Änderung an Chat-Layout oder WebSocket-v1-Nachrichten.
