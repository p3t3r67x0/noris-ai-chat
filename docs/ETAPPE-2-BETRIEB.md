# Etappe 2: Konfiguration und Betrieb

Der Real-Transport verwendet die bestehende Nuxt-Oberfläche und eine Same-Origin-FastAPI-API. Nur das Backend kennt Provider-URL und Provider-Key. Es gibt keine neue Datenbank, keinen zusätzlichen Compose-Dienst und keinen zusätzlichen Reverse-Proxy.

## Mock-Modus

`.env.example` aktiviert `NORIS_LLM_PROVIDER=disabled` und `NUXT_PUBLIC_CHAT_TRANSPORT=mock`. `make dev-up` oder die Host-Entwicklung aus README bleiben ohne Provider-Zugangsdaten möglich. Demo-Modelle und `/lang`-/`/fehler`-Fixtures sind ausschließlich im Mock-Modus verfügbar. LLM-Endpunkte antworten bei deaktiviertem Provider mit 503; Healthchecks und die übrige Anwendung bleiben funktionsfähig.

## Real-Modus

Die Noris-Dokumentation nennt `https://ai.noris.de/v1`, Bearer-Authentifizierung und OpenAI-kompatible Chat Completions. Der Betreiber muss die tatsächlich nutzbaren Modell-IDs und Account-Quotas selbst freischalten. Die ID `vllm/release/gpt-oss-120b` ist [dokumentiert](https://noris.cloud/nai/models/gpt-oss-120b/) und wurde für den bereitgestellten Account live geprüft; siehe [Etappe-2.1-Abnahme](ETAPPE-2.1-LIVE-ABNAHME.md). Diese Prüfung überträgt sich nicht automatisch auf andere Accounts oder Modelle.

In der gitignorierten `.env` bzw. über serverseitige Secret-Injektion konfigurieren:

```dotenv
NORIS_LLM_PROVIDER=openai-compatible
NUXT_PUBLIC_CHAT_TRANSPORT=real
NORIS_LLM_BASE_URL=https://ai.noris.de/v1
NORIS_LLM_ALLOWED_HOSTS=["ai.noris.de"]
NORIS_LLM_ACCESS_USERNAME=<separater-anwendungsbenutzer>
NORIS_LLM_ALLOWED_ORIGINS=["https://<anwendungs-host>"]
NORIS_LLM_MODELS=[{"id":"vllm/release/gpt-oss-120b","name":"GPT-OSS 120B","available":true,"streaming":true,"context_window":8192,"max_output_tokens":1024}]
NORIS_LLM_DEFAULT_MODEL=vllm/release/gpt-oss-120b
```

Zusätzlich `NORIS_LLM_API_KEY` und ein **separates** `NORIS_LLM_ACCESS_PASSWORD` mit mindestens 32 Zeichen injizieren. Anwendungszugangsdaten müssen druckbare ASCII-Zeichen verwenden; der Benutzername darf keinen Doppelpunkt enthalten. Header-Steuerzeichen sind auch im Provider-Key unzulässig. Keine echten Werte in Git, PRs, Screenshots oder Logs ablegen. Anwendungspasswort und Provider-Key dürfen nicht identisch sein. Keine Secrets in `NUXT_PUBLIC_*` setzen. Lokal exakte HTTP-Origins wie `http://127.0.0.1:8080` und bei Host-Nuxt `http://127.0.0.1:3000` freigeben; `localhost` und `127.0.0.1` sind unterschiedliche Origins.

Backend und Frontend nach Konfigurationsänderungen neu starten; Compose liest nur explizit weitergereichte Variablen. Das Frontend-Runtime-Setting funktioniert auch mit dem vorhandenen Produktionsimage. `NORIS_ENVIRONMENT=production` verlangt HTTPS-Origins und einen HTTPS-Provider. Vor öffentlicher Nutzung TLS am vorhandenen Caddy bzw. am vorhandenen Deployment-Ingress konfigurieren; die lokale HTTP-Compose-Vorlage ist dafür allein nicht ausreichend.

Alle LLM-Endpunkte verlangen HTTP Basic mit den **Anwendungszugangsdaten**, niemals dem Provider-Key. Für den vorhandenen Browser-Flow einmal `https://<anwendungs-host>/api/v1/llm/models` öffnen, im nativen Browserdialog anmelden und danach zur Chatseite zurückkehren. Anschließend lädt die Modellauswahl den Katalog. Keine zusätzliche Login-Komponente oder Speicherung von Passwörtern in Browser-Storage. Basic ist eine Zugangsschranke für diese Integration; individuelle OIDC-Konten und Mandantentrennung sind eine spätere Aufgabe.

Der bestehende Proxy leitet `/api/*` zum Backend und hat bereits `flush_interval -1`. Keine zusätzliche CORS-Freigabe nötig. Für Host-Entwicklung bleibt `NORIS_DEV_API_TARGET` die lokale FastAPI-Adresse; es darf nicht auf den privaten Provider zeigen.

## Variablen und Grenzen

Alle Backend-Werte tragen das bestehende Präfix `NORIS_`. JSON-Listen müssen gültiges JSON sein.

| Variable | Standard / Bedeutung |
| --- | --- |
| `NORIS_LLM_PROVIDER` | `disabled`; alternativ `openai-compatible` |
| `NUXT_PUBLIC_CHAT_TRANSPORT` | `mock`; alternativ `real`; einzige öffentliche LLM-Einstellung |
| `NORIS_LLM_BASE_URL` | Kein Standardziel; API-Basis inklusive `/v1` |
| `NORIS_LLM_ALLOWED_HOSTS` | `[]`; exakte erlaubte Hostnamen, keine Wildcards |
| `NORIS_LLM_API_KEY` | Kein Standard; ausschließlich serverseitiger Bearer-Key |
| `NORIS_LLM_ACCESS_USERNAME` | Kein Standard; separater HTTP-Basic-Benutzer |
| `NORIS_LLM_ACCESS_PASSWORD` | Kein Standard; mindestens 32 Zeichen, vom Provider-Key verschieden |
| `NORIS_LLM_ALLOWED_ORIGINS` | `[]`; exakte Browser-Origins ohne abschließenden Slash |
| `NORIS_LLM_MODELS` | `[]`; IDs, Namen, availability/streaming, context_window und max_output_tokens |
| `NORIS_LLM_DEFAULT_MODEL` | Kein Standard; muss nutzbares konfiguriertes Modell sein |
| `NORIS_LLM_TOKEN_LIMIT_PARAMETER` | `max_tokens`; alternativ `max_completion_tokens` für passende Provider |
| `NORIS_LLM_REASONING_EFFORT` | Unset/leer: Provider-Standard; optional `low`, `medium`, `high` ausschließlich serverseitig für kompatible Modelle |
| `NORIS_LLM_CONNECT_TIMEOUT_SECONDS` | `5`; auch Write-/Pool-Timeout |
| `NORIS_LLM_READ_TIMEOUT_SECONDS` | `120`; maximale Stille zwischen Netzwerkdaten |
| `NORIS_LLM_TOTAL_TIMEOUT_SECONDS` | `1800`; gesamte Generierung, höchstens 3600 |
| `NORIS_LLM_TITLE_TIMEOUT_SECONDS` | `6`; eigener Titel-Timeout, höchstens 30 |
| `NORIS_LLM_TITLE_MAX_OUTPUT_TOKENS` | `96`; Titel-Ausgabe, höchstens 256 und höchstens Modelllimit |
| `NORIS_LLM_MAX_CONCURRENT` | `4`; aktive Anfragen und HTTP-Verbindungen, höchstens 32 |
| `NORIS_LLM_REQUESTS_PER_MINUTE` | `20`; gemeinsame Anfragefrequenz pro Backend-Prozess |
| `NORIS_LLM_DAILY_TOKEN_BUDGET` | `100000`; konservative Input-/Outputreservation, UTC-Tageswechsel |
| `NORIS_LLM_MAX_REQUEST_BYTES` | `1048576`; vollständiger JSON-Body, höchstens 8 MiB |
| `NORIS_LLM_MAX_UPSTREAM_BYTES` | `16777216`; SSE-Daten einschließlich Metadaten, höchstens 64 MiB |

Weitere feste Grenzen: Body-Empfang 10 Sekunden; 100 Nachrichten; 64 KiB pro SSE-Zeile/Event. Zeichen-, Stream- und Timeoutgrenzen sind jetzt konfigurierbar und werden über den Modellkatalog mit dem Browser abgestimmt. Details, Provider-Nachweis und ein bedingtes 32768/131072-Profil stehen in [LLM-OUTPUT-LIMITS.md](LLM-OUTPUT-LIMITS.md). Keine automatischen Modell-Retries und keine automatische Kontextkürzung.

Das Kontextmanagement prüft den aktiven Gesprächspfad mit UTF-8-Bytes plus Nachrichten- und Outputreserve gegen das **lokale** Modelllimit. Das Beispiel setzt absichtlich 8192 statt des dokumentierten 128K-Fensters. Eine Überschreitung wird vor Provider-Aufruf abgelehnt. Ungewählte Antwortvarianten und privilegierte System-/Developer-Rollen gelangen nicht in den Request. Der Backend-Vertrag akzeptiert nur abwechselnde user-/assistant-Nachrichten mit abschließender User-Nachricht.

Raten-/Tagesbudgets gelten für einen Prozess und bleiben bei Fehler/Stop reserviert. Sie überleben keinen Neustart. Deshalb **einen Backend-Worker** betreiben und zusätzliche Account-Kostenlimits beim Provider setzen. Für mehrere Replikate ist vor Skalierung ein gemeinsamer Quota-Speicher erforderlich; diese Etappe behauptet keine verteilte Kostenkontrolle.

Die Provider-Adresse wird ausschließlich durch Betreiber konfiguriert, HTTPS und Host-Allowlist geprüft, Redirects und Umgebungs-Proxys sind deaktiviert. Loopback-HTTP ist nur für development/test zulässig. Eine vertrauenswürdige Host-Allowlist und Netzwerk-Egress-Regeln bleiben Betreiberaufgaben; die Anwendung ist kein beliebiger URL-Proxy. Bei fehlender/ungültiger Real-Konfiguration scheitert der Start kontrolliert, ohne Requests an ein Standardziel. Eine später nicht erreichbare Provider-Instanz führt zu einem Request-Fehler und beendet nicht die Anwendung.

## Healthchecks und Fehlersuche

Automatische [Gesprächstitel](AI-CONVERSATION-TITLES.md) verwenden `POST /api/v1/llm/conversation-title`, dieselbe Anmeldung und dieselben Budgets. Nur dieser Prozess fügt eine serverseitige Titelanweisung hinzu. Chat-Nutzerdaten können weiterhin keine privilegierten Rollen senden. Titel-Fehler kommen als JSON zurück und lassen den Platzhalter bestehen; bei `TITLE_ALREADY_ATTEMPTED` (409) wird keine weitere Provider-Anfrage gestartet. Provider-/Antwortfehler verwenden 502, der Titel-Gesamttimeout 504, gemeinsame Raten-/Budgetlimits 429. Kein automatischer Retry.

`GET /api/v1/health/live` prüft den API-Prozess. `GET /api/v1/health/ready` prüft wie zuvor PostgreSQL und Baseline. Beide rufen keinen Provider auf. `GET /api/v1/llm/models` prüft Anmeldung und statische Freigabe, **nicht** tatsächliche Provider-Liveness.

Vor Beginn des Streams verwendet die API `{error:{code,message,request_id}}`. Nach Beginn kommt `response.failed` im SSE-Stream; HTTP bleibt 200 und bereits empfangener Text erhalten. Request-IDs dienen zur Diagnose, ohne Prompt oder Konfiguration zu loggen. Provider-Response-Bodies und interne Ausnahmen werden nicht an den Browser weitergereicht.

| Fehler | Prüfung |
| --- | --- |
| `LLM_DISABLED` | Backend-Schalter und vollständige Serverkonfiguration |
| `ACCESS_DENIED` | Native Anmeldung über `/api/v1/llm/models`, Anwendungszugangsdaten |
| `ORIGIN_DENIED` | Exakte Origin einschließlich Schema/Port und zulässiger Browserzugriff |
| `MODEL_UNAVAILABLE` | Modell-Allowlist, availability/streaming und echte Account-Berechtigung |
| `CONTEXT_LIMIT`, `REQUEST_TOO_LARGE`, `VALIDATION_ERROR` | Aktiver Pfad, Längen, Rollenfolge und lokal gesetzte Limits |
| `RATE_LIMIT`, `BUDGET_LIMIT` | Prozessgrenzen bzw. Provider-Quota; Retry bewusst auslösen |
| `PROVIDER_AUTH_FAILED` | Serverseitigen Provider-Key prüfen, niemals im Browser eingeben |
| `PROVIDER_UNREACHABLE` | DNS, HTTPS, Egress und konfigurierte Basisadresse |
| `TIMEOUT` | Connect-/Read-/Gesamtlimit und Provider-Verhalten |
| `STREAM_INTERRUPTED`, `INVALID_RESPONSE` | SSE-/UTF-8-Vertrag, Finish und `[DONE]`, Proxy-Pufferung |
| `OUTPUT_LIMIT`, `CONTENT_FILTERED` | Token-/Bytegrenzen bzw. Provider-Filter; Teilantwort bleibt erhalten |
| `INTERNAL_ERROR` | Request-ID und serverseitige Diagnose ohne Secrets |

Stop schließt Browser-Fetch, FastAPI-Stream und Provider-HTTP-Verbindung auch während Provider-Stille. Das wurde gegen einen lokalen HTTP-Server und in Etappe 2.1 gegen Noris geprüft, einschließlich tatsächlicher Socket-Schließung. GPU-Abbruch und Abrechnungsstopp bleiben getrennt **NOT TESTED**; keine dedizierte Noris-Cancel-API ist belegt.

## Deterministische Tests und optionaler Live-Test

```sh
make lint
make typecheck
make check-api
make test-unit
make test-llm-integration
pnpm --dir frontend test:e2e:llm
make build
```

Die HTTP-/Browser-Integration startet ausschließlich lokale simulierte Provider. Browser-Tests verwenden isolierte Ports 8591–8593, Desktop und Mobile und eigene `test-results/llm`; keine Zugangsdaten oder kostenpflichtigen Calls erforderlich. Die bestehenden CI-Ziele `make test-unit` und `make test-e2e` führen auch die neuen HTTP-/Browserprüfungen aus; die Workflow-Datei bleibt unverändert. Mock-, DB- und UI-Browserprüfungen bleiben in CI aktiv.

Für eine lokale Abnahme den [begrenzten Live-Testserver](ETAPPE-2.1-LIVE-ABNAHME.md#automatisierte-prüfung-und-reproduktion) verwenden: vorhandener Provider/Gateway, Modellzugriff vorab prüfen, separate private Anwendungszugangsdaten erzeugen und drei freigegebene Requests mit je maximal 256 Ausgabetokens erlauben. Bei GPT-OSS für diesen kurzen Test `NORIS_LLM_REASONING_EFFORT=low` setzen. Reasoning-Tokens verbrauchen ebenfalls das Outputlimit; bei Erreichen der Grenze bleibt `OUTPUT_LIMIT` das korrekte Ergebnis.

Der Browser-Test kann auch eine bereits konfigurierte Real-Anwendung prüfen. Für diesen Test muss deren Katalog ausschließlich GPT-OSS 120B enthalten und das serverseitige Outputlimit auf 256 gesetzt sein. Nach ausdrücklicher Kostenfreigabe nur die getrennten Anwendungszugangsdaten injizieren:

```sh
export NORIS_RUN_LIVE_LLM_SMOKE=1
export NORIS_LIVE_APP_ORIGIN=https://<anwendungs-host>
# NORIS_LLM_ACCESS_USERNAME und NORIS_LLM_ACCESS_PASSWORD extern injizieren.
pnpm --dir frontend test:e2e:live
```

Dieser Test sendet die MCP-Frage durch Browser und Backend und kann Kosten verursachen. Ohne Opt-in werden beide Fälle vor Browser-/Netzwerkstart übersprungen. Der zusätzliche Stop-Test verlangt `NORIS_LIVE_TEST_STOP=1`, einen weiteren freigegebenen Aufruf und `NORIS_LIVE_SESSION` mit lokalen HTTP-Beobachtungen. Screenshots, Videos, Traces und automatische Retries sind deaktiviert. Playwright benötigt keinen Provider-Key. Der tatsächliche erfolgreiche Noris-Lauf und die vorherigen Fehlschläge sind im [Etappe-2.1-Abnahmebericht](ETAPPE-2.1-LIVE-ABNAHME.md) dokumentiert. Andere Accounts/Konfigurationen bleiben bis zu eigener Prüfung unverifiziert.
