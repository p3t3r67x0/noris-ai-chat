# Lange Antworten und GPT-OSS-Kontext

## Verifikation am 9. Oktober 2026

Die [Noris-Modellkarte](https://noris.cloud/nai/models/gpt-oss-120b/) nennt
`vllm/release/gpt-oss-120b` und 128K Kontext. Die
[Originalkonfiguration](https://huggingface.co/openai/gpt-oss-120b/blob/main/config.json)
setzt `max_position_embeddings` auf **131072**. Das ist die Modellfähigkeit,
keine Messung des eingesetzten Noris-Servers.

Die [Noris-API-Dokumentation](https://noris.cloud/nai/api/chat-completions/)
beschreibt `max_tokens`, nennt jedoch weder dessen maximale Zahl noch eine
separate numerische maximale Ausgabe. Ein kostenloser, authentifizierter
`GET https://ai.noris.de/v1/models` bestätigte den Modellzugriff des vorhandenen
Kontos (HTTP 200). Der Modelleintag lieferte keine Kontext-/Ausgabegrenzen.
**Es wurden keine kostenpflichtigen Generierungen ausgeführt.** 131072 Kontext,
8192 oder größere Ausgaben sind durch diesen Metadatencheck nicht getestet.
Die bisherigen kleinen Live-Abnahmen in `ETAPPE-2.1-LIVE-ABNAHME.md` beweisen
keine größeren Grenzen. Neue Tests verwenden ausschließlich Simulationen.

[Noris-Quotas](https://noris.cloud/nai/concepts/rate-limits/) betreffen RPM, TPM
und optional AI-Punkte pro Virtual Key/Kunde. Konkrete Accountwerte sind nicht
öffentlich dokumentiert und wurden nicht geliefert. Sie müssen im Konto oder
mit Noris geklärt werden. Ein gelistetes Modell beweist keine bestimmte Quota.

## Bestandsaufnahme von main (`ce2ac9c`)

| Grenze vorher | Zweck und neue Behandlung |
|---|---|
| Modellkontext 8192 als Standard; Schema bis 2 Mio. | Lokale Kontextpolitik. 131072 nur mit expliziter Providergrenze und Nachweis. |
| Ausgabe standardmäßig 1024, Schema maximal 8192 Tokens | Pro-Aufruf-Kostenlimit. Globaler konfigurierbarer Deckel plus separate bestätigte Providergrenze. Standardausgabe bleibt 1024. |
| 32000 Zeichen in API, Provider, Gateway, Frontend und Persistenz | Speicher-/Renderinggrenze. Durch synchronisierte konfigurierbare Eingabe-/Antwortlimits ersetzt; Backend zählt UTF-16 wie JavaScript. |
| UTF-8-Bytes + 32/Nachricht + 64 + Antwortreserve | Konservative Kontext- und Tagesbudgetschätzung. Jetzt optional lokaler Modelltokenizer plus ausdrücklich reserviertes System-/Reasoning-/Sicherheitsbudget. |
| 100 Nachrichten, abwechselnd user/assistant | Begrenzter aktiver Pfad; unverändert. Fortsetzung endet mit bestehendem Assistant; vertrauenswürdige Fortsetzungsanweisung wird nur serverseitig ergänzt. |
| POST-Body 512 KiB; Empfang maximal 10 s | Schutz vor großen/langsamen Requests. Bytewert konfigurierbar, Empfangszeit unverändert. |
| Providerstream 1 MiB; SSE-Zeile/Event 64 KiB | Begrenzte Daten und Parserpuffer. Bytewert weiterhin konfigurierbar; Parsergrenze bleibt. Gateway teilt Text in höchstens 512 Zeichen pro Event. |
| Browserstream 4 MiB | Gesamte SSE-Daten einschließlich Metadaten begrenzt; jetzt aus Backendkatalog. |
| Connect 5 s, Read/Idle 30 s, insgesamt 120 s | Verbindungs-, Stillstands- und absolute Zeitgrenzen. Getrennte Werte; Konfigurationsprüfung verhindert Idle/Connect oberhalb der absoluten Zeit. |
| Frontend absolut 135 s | Kann erlaubte Backendläufe über 120 s abbrechen. Jetzt Backend-Gesamtzeit + Connect + 15 s, aus authentifiziertem Katalog. |
| 4 parallele Generierungen, 20 Requests/min, 100000 Tokens/Tag | Kosten-/Lastkontrolle; jede Fortsetzung und Titelanfrage nutzt dieselbe Admission. |
| Titel 6 s, 96 Ausgabetokens, 256 Zeichen, 1 Versuch/Chat | Separates kleines Titelbudget; unverändert. |
| Titelerzeugung im Browser 8 s; Quelle 1024 Unicode-Zeichen, serverseitig bereinigt | Begrenzter, separater Titelaufruf; beeinflusst weder Antworttext noch Gesprächskontext. |
| Titel höchstens 50 Zeichen generiert / 120 manuell; Metadatensnapshot 2 Mio. Zeichen | Begrenzte Navigation und Metadatenspeicherung; unverändert. |
| 10000 Titelversuche pro Prozess | Begrenzter Duplikatspeicher; unverändert. Zusätzlich maximal 10000 Fortsetzungs-IDs, ohne unsichere Verdrängung. |
| Snapshot 6 Mio. UTF-16-Zeichen; 10000 Nachrichten | Begrenzte lokale Speicherung; unverändert. Schreibseite prüft jetzt dieselbe Gesamtgrenze wie der Reader. |
| Syntaxhervorhebung nur bis 16000 Zeichen/Codeblock | Schützt vor teurem Highlighting; lange Codeblöcke bleiben vollständig als Text lesbar. |
| Eingabeentwurf bisher höchstens 64000 Zeichen, still gekürzt | Jetzt vollständiger Entwurf bis zur technischen Speichergrenze; darüber sichtbare Ablehnung. |

Composer und Bearbeitung verwenden das Eingabelimit. Modell-Header und Composer
reagieren auf den authentifizierten Katalog; unbekannte Modelle werden nicht
als Mockmodelle angeboten. Stop bricht den Fetch und den Upstream ab. Normales
Retry/Regenerieren bewahrt die alte Antwort als Variante; Retry einer Fortsetzung
verwendet denselben Assistant und seinen aktuellen Text. Der aktive Pfad schließt
ungewählte Branches aus. Caddy nutzt weiterhin `flush_interval -1`; das Backend
setzt `X-Accel-Buffering: no` und `Cache-Control: no-store, no-transform`.

## Bewusste Aktivierung

Standardwerte bleiben konservativ: 8192 Kontext, 1024 Ausgabetokens pro Modell,
8192 als **lokaler** maximaler Ausgabedeckel, 32000 Eingabezeichen, 128000
Antwortzeichen, 512 KiB Request, 1 MiB Upstream und 4 MiB Downstream. Die
Schemaobergrenzen sind technische Schutzgrenzen, keine Providerzusagen.

Für 128K müssen Betreiber den tatsächlich bereitgestellten Kontext bestätigen
(Provider-/Accountbestätigung oder ausdrücklich genehmigter Live-Test) und im
Modell `context_window=131072`, `provider_context_window=131072` sowie
`provider_limit_evidence` setzen. Der Nachweis darf keine Secrets oder privaten
Inhalte enthalten. Fehlender Nachweis oder überschrittene Providergrenzen führen
zu einem Konfigurationsfehler. Bestehende größere, bisher ungeprüfte lokale
Konfigurationen müssen daher ergänzt werden; die Anwendung hebt sie nicht selbst an.

Größere Ausgaben benötigen unabhängig davon eine bestätigte
`provider_max_output_tokens`, einen passenden Modellwert `max_output_tokens`
und einen bewusst erhöhten `NORIS_LLM_MAX_OUTPUT_TOKENS`. Oberhalb von 8192
muss ebenfalls ein Nachweis vorliegen. Da Noris keinen größeren Zahlenwert
veröffentlicht, enthält `.env.example` keine vorgetäuschte größere Providerkapazität.
Die bisherigen 8192 sind eine bestehende lokale Schutzpolitik, kein neuer Live-Nachweis.

Bei großem Kontext müssen `NORIS_LLM_MAX_MESSAGE_CHARS`,
`NORIS_LLM_MAX_REQUEST_BYTES` und das Tagesbudget genügend Platz bieten.
Antworten und Fortsetzungen müssen zusätzlich in `NORIS_LLM_MAX_RESPONSE_CHARS`
sowie beide Stream-Bytegrenzen passen. Die technischen Maxima sind 1048576
UTF-16-Einheiten pro Eingabe/Antwort, 8 MiB Request, 64 MiB je Stream,
131071 Ausgabetokens, 20 Fortsetzungen und 3600 s absolute Laufzeit.
Diese Maxima sind keine empfohlenen Einstellungen. Ein ausreichend großes
Tagesbudget ersetzt keine Providerquota.

## Kontext, Tokenizer und Reasoning

Admission prüft:

```text
geschätzter kompletter Providerprompt
  + max_output_tokens
  + reasoning_reserve_tokens
  <= context_window
```

Der Prompt enthält Systemanweisungen, den gesamten gewählten Gesprächspfad,
die aktuelle Usernachricht und bei Fortsetzung den **vollständigen** bisherigen
Assistanttext sowie die festen Fortsetzungsanweisungen. Es gibt keine stille
Kürzung. Stattdessen kommt `CONTEXT_LIMIT` vor dem Provideraufruf.

Optional lädt `NORIS_LLM_TOKENIZER_PATH` eine lokal bereitgestellte `tokenizer.json`
der tatsächlich eingesetzten GPT-OSS-Revision. `NORIS_LLM_TOKENIZER_MODEL_ID`
ordnet sie dem Modell zu. Der Betreiber prüft Revision und SHA-256 gegen die
[Originalartefakte](https://huggingface.co/openai/gpt-oss-120b/tree/main).
Es gibt keine Laufzeit-/CI-Downloads von Modellartefakten. Truncation und Padding
des Tokenizers werden ausgeschaltet. Eine unlesbare konfigurierte Datei blockiert
den Start. Für Docker wird sie mit einem lokalen Compose-Override read-only
gemountet; beide Variablen müssen dort explizit gesetzt werden.

Die lokal tokenisierte Inhaltstokenzahl wird mit 10 % Sicherheitsaufschlag angesetzt. Dazu kommen
32 Tokens pro Nachricht, 64 für die Vorlage, standardmäßig 256
`NORIS_LLM_CONTEXT_SAFETY_TOKENS` und 256 `NORIS_LLM_SYSTEM_RESERVED_TOKENS`.
Der Provider kann seine Chatvorlage/Systemvorgaben ändern; auch die lokale
Tokenizerzählung ist deshalb eine **Promptschätzung**, keine Provider-Usage.
Ohne passenden Tokenizer werden UTF-8-Bytes statt Inhaltstokens verwendet,
mit denselben zusätzlichen Reserven. Das ist für Byte-BPE konservativ und
nutzt bei normalem Text weniger vom theoretischen Kontextfenster.

[Reasoning-Tokens](https://noris.cloud/nai/concepts/tokens/) kosten bei Noris
zusätzlich Geld und Kontext. `reasoning_reserve_tokens` pro Modell reserviert
zusätzlichen Platz und Tagesbudget. Bei Aktivierung von GPT-OSS muss der Betreiber
diesen Wert und die Semantik des Tokenparameters mit Noris bestätigen; beispielsweise
sind 4096 zusätzliche Tokens eine bewusste Reserve, keine gemessene Usage.
Wenn `max_tokens`/`max_completion_tokens` Reasoning bereits mitzählt, ist diese
zusätzliche Reserve absichtlich konservativ. Die Antwort erhält dadurch keine
Garantie über eine Mindestzahl sichtbarer Tokens. `reasoning_effort` bleibt
serverseitig und optional. Verdeckte Reasoning-Deltas werden nicht als Antworttext
dargestellt; alle übertragenen Bytes zählen gegen das Upstreamlimit.

## Fortsetzungsoperation und Fehlermeldungen

`POST /api/v1/llm/chat` verwendet `operation="generate"` oder `"continue"`.
Fortsetzung übermittelt `assistantMessageId`, den ursprünglichen `inputMessageId`,
einen neuen `generationId`, `continuationCount` und den aktiven Pfad mit abschließendem
Assistanttext. Der Server fügt eine feste Systemanweisung und Useranweisung hinzu;
Clients können keine privilegierten Rollen einspeisen.

`finish_reason=stop` beendet erfolgreich. `finish_reason=length` führt zu
`response.incomplete` mit `reason="output_limit"`; weder `response.completed`
noch eine Erfolgsmeldung wird ausgegeben. Die UI zeigt „Ausgabelimit erreicht –
weiterschreiben“. „Weiterschreiben“ startet genau einen weiteren, sichtbaren
Provideraufruf am selben Knoten und verwendet das ursprüngliche Modell. Es gibt
**keine automatische Fortsetzung und keine automatischen Retries**.
Standardmäßig sind maximal acht manuelle Fortsetzungsversuche pro Antwort möglich.
Fehlgeschlagene Versuche zählen mit. Stop bleibt während jeder Fortsetzung verfügbar.

Der Client blockiert Doppelklicks durch seinen aktiven Generierungszustand. Das
Backend sperrt gleichzeitige Fortsetzungen desselben Conversation-/Assistant-Ziels
auch mit verschiedenen Generation-IDs. Bereits benutzte Fortsetzungs-IDs werden
abgelehnt. Diese Sperren sind pro Prozess; die bestehende Browserautorität für
Conversation-Branches wird nicht zu einer serverseitigen Gesprächsdatenbank erweitert.

Ein begrenzter Anfangspuffer erkennt exakte Wiederholungen des vorherigen Endes
(64–4096 Zeichen), entfernt diese und hängt nur neue Zeichen an. Ein erkennbarer
Neustart der ganzen Antwort oder eine Fortsetzung ohne Fortschritt endet mit
`DUPLICATE_CONTINUATION`. Der bestehende Text wird niemals gelöscht/umgeschrieben.
Whitespace, Tabellen und offene Codefences werden ohne zusätzliche Trennzeichen
fortgesetzt. Kurze oder semantisch umformulierte Wiederholungen lassen sich nicht
zuverlässig von legitimer Markdown-/Codewiederholung unterscheiden und werden
deshalb nicht heuristisch entfernt. Provider können trotz Anweisung inkonsistentes
Markdown erzeugen; die Anwendung garantiert den Erhalt des Originals.

`RESPONSE_SIZE_LIMIT` und `STREAM_SIZE_LIMIT` sind lokale Schutzgrenzen mit eigenen
Meldungen. `CONTEXT_LIMIT`, `BUDGET_LIMIT`, Netzwerkunterbrechung, Provider-Timeout,
Providerfehler und Benutzerabbruch bleiben getrennte Zustände. Fehlercodes und
bereinigte Meldungen werden pro Assistant persistiert. Stop zeigt die Teilantwort
mit „Antwort gestoppt.“. Netzwerk-Retry erhält die vorherige Teilantwort; während
einer Fortsetzung wird direkt am selben Knoten erneut versucht.

## Streaming, Darstellung und Persistenz

Connect/Write/Pool verwenden `NORIS_LLM_CONNECT_TIMEOUT_SECONDS`, der Upstream-
Idle-Timeout ist `NORIS_LLM_READ_TIMEOUT_SECONDS`, die absolute Generierungszeit
ist `NORIS_LLM_TOTAL_TIMEOUT_SECONDS`. Idle wird durch empfangene Providerbytes
zurückgesetzt, die absolute Frist niemals. Der Server sendet standardmäßig alle
10 Sekunden SSE-Kommentare während Reasoning/Stille. Diese halten den Browser-/Proxy-
Pfad aktiv, verlängern jedoch weder die Provider-Idle-Frist noch die absolute Zeit.
Der Browser erhält Gesamtfrist und separate Idle-Frist aus dem Katalog;
`createRealTransport` erlaubt explizite Overrides für Tests. Im regulären UI gibt
es keine kleinere, unabhängig konfigurierte Browserfrist. Keine unbegrenzten
offenen Verbindungen; Abbruch schließt auch einen stillen Upstream.

Markdown wird bei laufenden Antworten höchstens alle 50 ms neu gerendert;
bei einem terminalen Zustand wird sofort der letzte volle Inhalt angezeigt.
Der gespeicherte Rohtext bleibt stets aktuell. Scrollnachführung wird nach dem
tatsächlichen Markdown-DOM-Update abgeglichen und respektiert weiterhin manuelles Lesen.
Bestehende Zeilenumbrüche,
Tabellen-/Codeüberlaufregeln, sichere Link-/HTML-Behandlung und Scrollregeln bleiben
erhalten. Fortsetzung ändert keine Turn-ID und erzwingt keinen Scrollsprung.

Snapshots akzeptieren lange Antworten unabhängig vom aktuell ausgewählten Modell
bis zur technischen Obergrenze und behalten Branches, Modell, Status und Anzahl
Fortsetzungen. Reload eines laufenden Streams markiert ihn gestoppt und erhält
den gespeicherten Text. Snapshots werden weiterhin nach 120 ms sowie bei `pagehide`
atomar geschrieben. Bei Browserquota, 6-Mio.-Gesamtgrenze oder fremdem Tab wird
eine Speicherwarnung angezeigt; vorhandener Speicher wird nicht durch einen
unlesbaren Snapshot ersetzt. `localStorage` hat eine browserabhängige Quota;
es ist kein unbegrenzt haltbarer Speicher. Ein abruptes Beenden kann die letzten
noch nicht gespeicherten 120 ms betreffen.

Eingabeentwürfe werden nicht mehr bei 64000 Zeichen abgeschnitten. Sie bleiben bis
zur technischen Entwurfsgrenze (2097152 UTF-16-Einheiten) vollständig erhalten;
größere Ersetzungen werden mit einer sichtbaren Meldung abgelehnt und der bisherige
Entwurf bleibt erhalten. Senden und Bearbeiten prüfen das konfigurierte Eingabelimit,
ohne Browser-`maxlength` als stillschweigende Kürzung zu verwenden.

## Kosten und Sicherheitsgarantien

Jeder Aufruf reserviert den vollständigen geschätzten Prompt, maximale Ausgabe
und zusätzliche Reasoningreserve gegen das Tagesbudget. Reservierungen bleiben
auch bei Fehlern/Stop bestehen; keine Usage-Rückerstattung, kein versteckter Aufruf.
Die Reservierung ist eine Schätzung, **keine tatsächliche Provider-Tokennutzung
oder Euroabrechnung**. Provider-Usage wird derzeit nicht als tatsächlicher
Verbrauch angezeigt. Tatsächliche Tokens und AI-Punkte müssen aus dem Providerkonto
kommen; fehlende Usage wird niemals als null Verbrauch behandelt.

Allowlisten, Basic-Zugriff, Originprüfung, serverseitige Providersecrets, URL-/Host-
Validierung, keine Redirects, Request-/Parallelitäts-/RPM-/Tageslimits und bereinigte
Fehler bleiben wirksam. Budgets/Sperren gelten für einen Backend-Worker und werden
bei Neustart zurückgesetzt, wie zuvor. Kontenweite Quotas müssen beim Provider
gesetzt werden. Große Grenzen bewusst aktivieren und nicht mehrere Worker als
Umgehung der lokalen Budgetkontrolle betreiben.

## Deterministische Abnahme

Backendtests prüfen 131072-Konfiguration, Provider-/lokale Deckel, exakte
Kontextbudgetgrenze mit Output/Reasoningreserve, lokalen Tokenizer ohne Truncation,
lange Stop-/Length-Ausgabe, UTF-16-Grenze, Fortsetzung mit fragmentiertem Überlapp,
mehrere Schritte, Duplikate, geteilte Budgets, Heartbeats und Abbruch.
Frontendtests prüfen Status, gleiche Nachricht/Branch, Doppelklick, Stop, Retry,
Fehlerpersistenz, Reload, lange Markdown-Strukturen, Schritt-/Größenlimits und
getrennte Browserfristen. HTTP-/Browsertests verwenden einen Loopback-Provider;
Desktop und Mobil prüfen echte lange SSE-Übertragung, Reload, Fortsetzung und Stop.
Es gibt keine kostenpflichtigen LLM-Anfragen in CI.

`pnpm --dir frontend test:e2e:llm` baut den Produktionsclient und verwendet einen
Loopback-Proxy (`scripts/serve-browser-fixture.mjs`) mit ungepufferter Weiterleitung
und Abbruch des Upstreams beim Schließen der Verbindung. Das prüft den ausgelieferten
Client ohne Entwicklungsmodul-Ladezeiten. Die allgemeinen UI-/Screenshot-Assertions
und ihre Fristen bleiben unverändert; Referenzbilder enthalten nur Testdaten.
`NORIS_E2E_PROVIDER_PORT`, `NORIS_E2E_BACKEND_PORT`, `NORIS_E2E_FRONTEND_PORT` und
optional `NORIS_E2E_NUXT_PORT` erlauben kollisionsfreie lokale Testports.
