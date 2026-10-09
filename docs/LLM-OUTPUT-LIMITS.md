# Lange Antworten und Providerlimits

Stand der Prüfung: 9. Oktober 2026. Keine kostenpflichtige Generierung wurde zur Prüfung verwendet.

## Nachweis und verbleibende Unsicherheit

Die [Noris-Modellkarte](https://noris.cloud/en/nai/models/gpt-oss-120b/) nennt für `vllm/release/gpt-oss-120b` **128K Kontext**. Die Karte basiert auf den Daten des Modellherstellers. Die [API-Referenz](https://noris.cloud/en/nai/api/chat-completions/) beschreibt `max_tokens` als Obergrenze generierter Tokens, nennt aber keinen separaten Maximalwert. Die [Original-Modellkarte](https://arxiv.org/abs/2508.10925) spezifiziert 131072 Kontexttokens. Kontextkapazität belegt keine separat freigeschaltete Ausgabegröße des gehosteten Providers.

Ein authentifizierter, ausschließlich lesender `GET https://ai.noris.de/v1/models` lieferte HTTP 200 und die Modell-ID, aber keine Felder für Kontext- oder Ausgabelimits. `GET /openapi.json` lieferte HTTP 404. Damit ist insbesondere **32768 Ausgabe bei Noris nicht verifiziert**; aus den vorhandenen Daten lässt sich keine tatsächliche maximale Ausgabegröße bestimmen. Die alte 8192-Grenze war eine lokale Anwendungspolitik, kein belegtes Providermaximum.

Das Schema erlaubt nun bis zu 131072 Tokens als strukturelle Grenze. Das konkrete Ausgabelimit muss unter dem Kontextfenster bleiben und wird zusätzlich durch `provider_max_output_tokens` sowie `NORIS_LLM_MAX_OUTPUT_TOKENS` begrenzt. Beide bleiben standardmäßig auf 8192. Für größere Providerwerte ist ein nicht leerer `provider_limit_evidence` erforderlich, etwa eine datierte Noris-Auskunft mit Ticketnummer für Ausgabegröße, Kontextfenster und Einbeziehung der Reasoning-Tokens. Dieser Eintrag dokumentiert eine Betreiberprüfung; er ist keine automatische technische Verifikation. Erst nach einem solchen Nachweis darf das Profil unten aktiviert werden. Ein etwaiger kostenpflichtiger Akzeptanztest braucht weiterhin ausdrückliche Freigabe.

## Konfigurationsbeispiel nach Providerbestätigung

```dotenv
NORIS_LLM_MAX_OUTPUT_TOKENS=32768
NORIS_LLM_MODELS=[{"id":"vllm/release/gpt-oss-120b","name":"GPT-OSS 120B","context_window":131072,"max_output_tokens":32768,"provider_max_output_tokens":32768,"provider_limit_evidence":"HIER tatsächliche datierte Noris-Bestätigung eintragen","timeout_policy":{"read_seconds":120,"total_seconds":1800}}]
NORIS_LLM_DEFAULT_MODEL=vllm/release/gpt-oss-120b
NORIS_LLM_TOKEN_LIMIT_PARAMETER=max_tokens
NORIS_LLM_REASONING_EFFORT=low
NORIS_LLM_MAX_MESSAGE_CHARS=32000
NORIS_LLM_MAX_RESPONSE_CHARS=262144
NORIS_LLM_MAX_REQUEST_BYTES=1048576
NORIS_LLM_MAX_UPSTREAM_BYTES=16777216
NORIS_LLM_MAX_STREAM_BYTES=16777216
NORIS_LLM_CONNECT_TIMEOUT_SECONDS=5
NORIS_LLM_READ_TIMEOUT_SECONDS=120
NORIS_LLM_TOTAL_TIMEOUT_SECONDS=1800
NORIS_LLM_HEARTBEAT_SECONDS=10
NORIS_LLM_CONTEXT_SAFETY_TOKENS=512
NORIS_LLM_DAILY_TOKEN_BUDGET=100000
```

32768 ist die Obergrenze **aller generierten Tokens einschließlich Reasoning**, keine Garantie für 32768 sichtbare Texttokens. [Noris berechnet Reasoning-Tokens wie Ausgabetokens](https://noris.cloud/en/nai/concepts/reasoning/). `reasoning_content` und `reasoning` aus dem Stream werden nicht in die sichtbare Antwort übernommen; sie zählen aber zum begrenzten Upstream-Datenvolumen. `max_completion_tokens` bleibt für kompatible Provider konfigurierbar. Reasoning-Effort darf das konfigurierte Tokenlimit nicht erhöhen.

## Größen, Timeout und Kostenkontrolle

Benutzereingaben und Assistententext haben getrennte konfigurierbare UTF-16-Grenzen. Diese gelten im Backend auch für den erneut gesendeten Gesprächspfad. Die absoluten Schemagrenzen betragen jeweils 1048576 Zeichen; Request-, Upstream- und Browser-Streamvolumen bleiben separat begrenzt. SSE-Einzelzeilen und Events behalten ihre 64-KiB-Schutzgrenze. Der Gateway reserviert 512 Bytes seines Streamlimits für den terminalen Status. Die lokale Wiederherstellung prüft absolute Nachrichtengrenzen und behält die bestehende Gesamtgrenze von sechs Millionen UTF-16-Codeeinheiten sowie maximal 10000 Nachrichten; sie verwirft längere erlaubte Antworten nicht aufgrund des alten 32000-Limits. Browser-Speicherquoten können das Speichern weiterhin verhindern; dann zeigt die Anwendung die bestehende Speicherwarnung.

Der authentifizierte Modellkatalog liefert die wirksamen Zeichen- und Streamlimits sowie Browser-Timeouts. Der Browser übernimmt sie für Composer, Bearbeitung, Generierung und Übertragung. Die globale Obergrenze für den Backend-Gesamttimeout beträgt standardmäßig 1800 Sekunden, der Browser bekommt 15 Sekunden Zuschlag. Die globale Obergrenze für den Backend-Idle-Timeout beträgt 120 Sekunden. Die tatsächlich verwendeten Provider-Timeouts sind jeweils das Minimum aus der globalen Grenze und der modellbezogenen `timeout_policy` im dynamischen Katalog. Das bestätigte Langantwort-Profil setzt daher auch die Modell-Timeouts explizit; die konservativen Standardprofile des Modellkatalogs bleiben erhalten. SSE-Kommentare halten die Browserverbindung während stiller Reasoning-Phasen alle zehn Sekunden aktiv; sie heben weder den Upstream-Idle-Timeout noch die Gesamtdauer auf. Stop cancelt den ausstehenden Provider-Read und schließt den HTTP-Stream. Caddy streamt weiterhin mit `flush_interval -1`.

Die Reservierung ist `Summe UTF-8-Eingabebytes + 32 × Nachrichtenanzahl + 64 + Sicherheitsreserve + Systemreserve + max_output_tokens + reasoning_reserve_tokens`. Dies ist eine bewusst konservative Schätzung, keine exakte Tokenisierung. Bei 131072 Kontext und 32768 Ausgabe bleiben bei den Standardreserven höchstens 97536 Tokens für diese geschätzte Eingabe einschließlich Template-Overhead. Bei einer Nachricht sind daher höchstens 97440 UTF-8-Inhaltsbytes möglich; das separate Zeichenlimit kann früher greifen.

Das Tagesbudget bleibt 100000 Tokens, ebenso bleiben Parallelitäts- und Ratenlimits bestehen. Die ganze Reservierung wird auch nach Abbruch, Fehler oder `finish_reason=length` nicht erstattet: Unsichtbares Reasoning kann sonst die Kostenkontrolle umgehen. Jeder manuelle Retry reserviert erneut. Provider-Nutzungsstatistiken werden nicht benutzt, um Reservierungen anhand sichtbarer Textlänge zu reduzieren. Für größere Tagesbudgets braucht es eine ausdrückliche Betreiberkonfiguration; der Ausbau erhöht sie nicht automatisch. Die bestehende In-Memory-Kontrolle gilt für einen Backend-Worker und wird bei Prozessneustart zurückgesetzt; mehrere Worker benötigen eine gemeinsame Budgetverwaltung.

`finish_reason=length` erhält den bereits gestreamten Text und endet mit `response.incomplete` / `output_limit`. Die explizite Aktion „Weiterschreiben“ setzt dieselbe Assistentenantwort fort; jede Fortsetzung nutzt Modellfreigaben und Budgetreservierung erneut. Siehe [LONG-CONTEXT-RESPONSES.md](LONG-CONTEXT-RESPONSES.md). Die Antwort wird nicht als vollständig markiert. Manuelles Regenerieren erzeugt weiterhin eine neue Antwortvariante. Retry einer gescheiterten Fortsetzung erhält hingegen den vorhandenen Assistentenknoten und Text.

## Lokale Prüfung

Die Regressionstests simulieren 9000 Ausgabetokens plus Reasoning und mehr als 32000 UTF-16-Codeeinheiten, einschließlich normalem Abschluss und `length`, beiden Tokenlimit-Parametern, Budget- und Kontextablehnung, konfigurierbaren Größenlimits, langen Timeouts, SSE-Heartbeats, Stop, Retry und lokaler Wiederherstellung. HTTP- und Browserprüfungen verwenden ausschließlich Loopback-Simulatoren. Diese Tests belegen das Verhalten der Anwendung, nicht die Kapazität des Noris-Deployments.
