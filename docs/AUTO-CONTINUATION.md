# Automatische Fortsetzung im persistenten Chat

Bei `finish_reason=length` erzeugt der bestehende Providerpfad ein
`response.incomplete` mit `reason=output_limit`. `GenerationManager` wartet,
bis das Gateway den Aufruf geschlossen und freigegeben hat, und lässt die
Fortsetzung erneut durch `LLMGateway.reserve` zu. `continuation_messages`
ergänzt die bestehende serverseitige Anweisung und die bisherige Antwort.
Das Modell bleibt gleich. Es gibt keine zusätzliche User-/Assistant-Nachricht
und keine zusätzliche Datenbank-Generierung innerhalb dieser automatischen Kette.

Die Provideraufrufe erhalten getrennte interne Admission-IDs, damit bestehende
Duplikatsperren erhalten bleiben. Browser und PostgreSQL verwenden durchgehend
dieselbe Generierungs-ID und denselben Assistant-Knoten. Text und Sequenz werden
weiter vor Auslieferung gemeinsam mit dem Replay-Event committed.

## Konfiguration und Kosten

```dotenv
NORIS_CHAT_AUTO_CONTINUE_MAX=8
```

`Settings.chat_auto_continue_max` folgt dem vorhandenen `NORIS_`-Präfix;
`.env.example` und Compose reichen den Wert an das Backend weiter. Er gilt pro
Generierung, einschließlich einer manuell gestarteten Fortsetzung. Zulässig sind
0 bis 20; 0 deaktiviert automatische Fortsetzungen. Ein Standardlauf enthält
höchstens den ursprünglichen Aufruf und acht automatische Folgeaufrufe.

`NORIS_LLM_MAX_CONTINUATIONS` bleibt die zusätzliche Gesamtgrenze für die
Antwortlinie (Standard 8, maximal 20). Automatische und manuelle Fortsetzungen
erhöhen gemeinsam den persistenten `continuationCount`. Bei den beiden
Standardwerten 8 bleibt nach acht automatischen Fortsetzungen kein weiterer
manueller Schritt verfügbar. Ist die automatische Grenze kleiner als die
Gesamtgrenze, bleibt „Weiterschreiben“ verfügbar, soweit Größe und bestehende
Fehlerregeln dies erlauben. Eine manuelle Fortsetzung bewahrt weiterhin die
ursprüngliche Antwort als unveränderte Variante. Regeneration startet eine
neue Variante mit Zähler 0.

Jeder Folgeaufruf prüft unverändert Modellfreigabe, Kontext einschließlich
System-/Reasoning-/Ausgabereserven, Parallelität, Requests pro Minute, Tagesbudget
und Größenlimits. Das Tagesbudget reserviert konservativ den gesamten neuen
Prompt und die zulässige Ausgabe; alte Antwortteile werden im Folgeprompt erneut
gezählt. Reservationskosten werden weiterhin nicht rückerstattet. Antwortgröße
gilt für den gesamten angehängten Text; Upstream-/Streambytegrenzen und
Providerzeitlimits gelten weiterhin je Aufruf. Die Begrenzung der Aufrufzahl
begrenzt die gesamte Kette zusätzlich. Admission und Budget bleiben wie bisher
prozesslokal; der Betrieb setzt einen Backend-Worker voraus.

## Streaming, Stop und Endzustände

Es wird genau ein `chat.generation.started` gesendet. Der Assistant bleibt
`streaming`, der Worker `running`; Markdown, Scrollverhalten und Stop bleiben
aktiv. Zwischen den Aufrufen erscheinen weder Abschlussmeldung noch neue
Antwortvariante. Ein leeres Delta überträgt den zugelassenen Fortsetzungszähler,
ohne den Text oder Renderingzustand zu verändern.

Die bestehende `ContinuationFilter` entfernt exakte Überschneidungen ab 64
Zeichen über Chunkgrenzen hinweg; der Prüfbereich bleibt auf 4096 Zeichen
begrenzt. Kürzere Wiederholungen bleiben erhalten, weil sie in Code und Markdown
beabsichtigt sein können. Whitespace, offene Codeblöcke, Tabellen und Listen
werden unverändert weitergeführt. Fehlender neuer Nicht-Whitespace-Text sowie
erkannte vollständige Wiederholungen beenden die Kette mit
`DUPLICATE_CONTINUATION`.

| Ergebnis | Persistenz und Oberfläche |
| --- | --- |
| Provider endet regulär mit `stop` | `completed`; keine Ausgabelimitmeldung. |
| Automatische Grenze erreicht | `incomplete`, `AUTO_CONTINUATION_LIMIT`; vollständiger Text und verständliche Meldung bleiben erhalten. |
| Gesamtgrenze erreicht | `incomplete`, `CONTINUATION_LIMIT`; kein weiterer manueller Schritt. |
| Kontext, Budget, Rate Limit, Zeit-/Größenlimit, Filter oder sonstiger Fehler | `failed` mit dem vorhandenen präzisen Fehlercode; kein automatischer Wiederholungsversuch. |
| Nutzer drückt Stop | Aktueller Stream wird geschlossen; `cancelled`, vollständiger bis dahin übernommener Text, keine weitere Fortsetzung. |
| Disconnect-Frist oder Serverneustart | Bestehendes `interrupted`-Verhalten und gespeicherter Text bleiben erhalten. |

Stop setzt weiterhin ein vom Worker beobachtetes Abbruchsignal, sodass ein
laufender Datenbank-Commit nicht unterbrochen wird. Der Worker prüft das Signal
vor und nach Admission sowie zwischen Streamereignissen. Der Browser übernimmt
beim Terminalereignis den vollständigen Datenbankstand, auch wenn nach Stop noch
Deltas unterwegs waren. Reload und Reconnect verwenden denselben Job, Replay
oder atomare Snapshots; `continuationCount` und Fehler-/Limitmeldungen werden
ebenfalls wiederhergestellt.

## Tests

Die Tests verwenden ausschließlich lokale Simulationen und wegwerfbare
PostgreSQL-Datenbanken; es sind keine kostenpflichtigen Provideraufrufe nötig.

- `backend/tests/unit/test_auto_continuation.py`: `length`, `stop`, mehrere
  Fortsetzungen bis zum Standardlimit, beide Grenzen, Kontext-/Tagesbudget-/RPM-
  und Größenprüfung, Providerfehler ohne Retry, fehlender Fortschritt,
  Überschneidungen, Markdown und Abbruch bei ruhendem Provider.
- `backend/tests/integration/test_chat_websocket.py`: PostgreSQL-Snapshots,
  ein Nachrichtenknoten, Streamingstatus und Sequenzen, Idempotenz, Reconnect,
  Stop, Regeneration/Varianten, gespeicherte Limitmeldung und manuelles Fortsetzen.
- `frontend/tests/unit/websocket-transport.spec.ts`: durchgehender Streamingstatus,
  vollständiger Stop-Text und Metadaten aus Reconnect-Snapshots.
- `frontend/tests/websocket/auto-continuation.spec.ts`: Desktop/Mobil, lange
  Markdown-Antworten ohne Duplikate, Reload und tatsächlicher WebSocket-Reconnect
  während der Fortsetzung sowie Stop und anschließender Reload.
- `frontend/tests/websocket/persistent-chat.spec.ts`: automatisches Limit und
  manuelle Fortsetzung mit unveränderter Ausgangsvariante.

Die WebSocket-Browserkonfiguration und `compose.test.yaml` setzen ausschließlich
für Tests das automatische Limit auf 2, um mehrere Fortsetzungen und den
manuellen Fallback unter der unveränderten Gesamtgrenze von 8 zu prüfen.
