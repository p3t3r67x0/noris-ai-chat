# Automatische Gesprächstitel

Neue Gespräche zeigen zunächst **Neuer Chat**. Nach Beginn des vorhandenen Chat-Streams startet unabhängig davon genau ein automatischer Titelversuch. Ein gültiger Titel ersetzt den Platzhalter in der vorhandenen Sidebar und wird im bestehenden lokalen Chat-Snapshot gespeichert. Nachrichten, Varianten und Scrollverhalten verwenden weiterhin dieselben Komponenten und denselben Streaming-Vertrag.

## API und Provider

`POST /api/v1/llm/conversation-title` verlangt dieselbe Basic-Anmeldung und Origin-Freigabe wie `/api/v1/llm/chat`. Der JSON-Body enthält ausschließlich `conversationId`, `inputMessageId`, `modelId` und `firstMessage` (höchstens 1024 Unicode-Zeichen). Die Antwort enthält beide IDs und `title` mit höchstens 50 Zeichen. OpenAPI und die generierten TypeScript-Typen enthalten diesen Vertrag.

Der vorhandene `LLMGateway` reserviert dieselben globalen Slots, Raten- und Tagesbudgets. Der vorhandene `OpenAICompatibleProvider` verwendet denselben HTTP-Client. Nur dieser serverseitige Vorgang fügt eine vertrauenswürdige Titel-Systemanweisung hinzu. Öffentliche Chat-Nachrichten akzeptieren weiterhin ausschließlich user/assistant; Chatantworten erhalten keine Titelanweisung. Die erste Nutzernachricht ist untrusted Quelltext und darf die Titelregeln nicht ersetzen.

Ziel sind 3–6 Wörter als Themenphrase in der Gesprächssprache; kurze technische Titel wie **Rust vs. C++** bleiben zulässig. Äußere Anführungszeichen und abschließende Punkte werden entfernt. Leere, zu lange, mehrzeilige, generische oder offensichtlich ungeeignete Ausgaben werden verworfen. Bei Fehlern bleibt der Platzhalter; weder Chattext noch Chat-Fehlerzustand ändern sich. Es gibt keine automatischen Retries.

## Grenzen und Kosten

| Grenze | Standard |
| --- | --- |
| `NORIS_LLM_TITLE_MAX_OUTPUT_TOKENS` | 96; höchstens 256 und höchstens Modelllimit |
| `NORIS_LLM_TITLE_TIMEOUT_SECONDS` | 6 Sekunden; höchstens 30 |
| Browser-Timeout | 8 Sekunden, unabhängig vom Chat-Timeout |
| Hintergrundanfragen im Browser | Höchstens zwei gleichzeitig; keine Warteschlange |
| Automatische Versuche | Ein gespeicherter Versuch pro neuem Gespräch |

Der Browser beginnt nach `response.started`, damit die Hauptantwort zuerst einen Gateway-Slot erhält. Reichen gemeinsame Limits nicht für den Titel, bleibt der Platzhalter. Der Server verhindert zusätzlich wiederholte zugelassene Titelanfragen für dieselbe Gesprächs-ID. Seine Duplikatmenge ist auf 10000 IDs pro Prozesslebensdauer begrenzt; danach werden weitere Titelanfragen mit `RATE_LIMIT` abgelehnt, ohne alte IDs zu verdrängen. Wie die bestehenden Quotas ist dieser Schutz prozesslokal und überlebt keinen Neustart. Weiterhin einen Backend-Worker betreiben; mehrere Replikate benötigen gemeinsamen Quota-Speicher. Fehler und Abbrüche behalten ihre Budgetreservierung.

Bei gesetztem `NORIS_LLM_REASONING_EFFORT` verwenden Titel `low`; Chatantworten behalten den konfigurierten Wert. Ohne Einstellung bleibt der Provider-Standard erhalten. Reasoning kann das Outputbudget verbrauchen; ein unzureichendes Limit führt zum Platzhalter. Titelqualität und Tokenlimit wurden gegen lokale Fixtures geprüft, ohne zusätzliche kostenpflichtige Noris-Aufrufe.

## Persistenz und Rennen

Snapshot v1 erhält `titleSource` (`fallback`, `generated`, `manual`) und `titleGenerationAttempted`. Fehlende Felder älterer Snapshots werden konservativ zu `manual` und `true` migriert. Bestehende Namen bleiben erhalten; es gibt keine rückwirkende Massengenerierung. Der Versuch wird vor der ersten Chat-Anfrage markiert. Reload, Wechsel, Folgefragen, Edit und Retry starten keine weitere Titelgenerierung. Scheitert die Hauptanfrage vor Streaming, bleibt ebenfalls der Platzhalter ohne erneuten automatischen Versuch.

Manuelles Umbenennen setzt sofort `manual`. Ergebnisse werden nur bei passenden Gesprächs-/Nachrichten-IDs, derselben vorhandenen Conversation-Instanz und `fallback` angewendet. Späte Titel können umbenannte oder gelöschte Chats nicht überschreiben oder wiederherstellen. Wechsel und Archivieren verändern die Zuordnung nicht. Stop der Chatantwort ist unabhängig vom Titel. Löschen, Hydrate, pagehide und Unmount brechen ausstehende Titel ab. Fremde Storage-Änderungen beenden ebenfalls Titelanfragen und erhalten die vorhandene Warnung.

Titel erscheinen als normaler Text. Die vorhandene Sidebar behält einzeilige Ellipsis, Breite und Zeilenhöhe; der vollständige Titel bleibt im Button-Tooltip verfügbar. Manuelle Namen behalten ihr vorhandenes 120-Zeichen-Limit.

## Datenschutz und Prüfung

Die zusätzliche Anfrage überträgt nur den Anfang der ersten Nachricht, keinen Verlauf. Offensichtliche Zugangsdaten, E-Mail-Adressen, URLs, UUIDs und JWTs werden vor dem Provider-Aufruf ersetzt. Die Titelanweisung verlangt breite Themen statt unnötiger sensibler Details. Diese Minimierung erkennt nicht sämtliche personenbezogenen Angaben. Diagnose-Logs enthalten nur feste Fehlercodes, keine Nachrichten, Titel, IDs, Provider-Texte oder Secrets. Screenshots und Fixtures verwenden ausschließlich synthetische Texte.

MockTransport erzeugt deterministische lokale Titel ohne Backend-/Provider-Aufruf. Die bestehenden Ziele `make lint`, `make typecheck`, `make check-api`, `make test-unit`, `make test-integration`, `make test-e2e`, `make test-e2e-production` und `make build` prüfen die Erweiterung mit. Titeltests decken zwei Sprachen, technische Namen, gemeinsame Budgets, Streaming, IDs, Umbenennen, Löschen, Archivieren, Reload, alte Snapshots, Fehler und Sidebar-Geometrie ab.

Lokal bestanden 138 Backend-Unit-/Contract-Tests, 9 lokale TCP-Integrationstests, 153 Frontend-Unit-Tests, 3 PostgreSQL-Tests, 137 UI-/Screenshot-Tests am isolierten Produktionsbuild, 18 simulierte LLM-Browsertests und 11 bestehende Datenschutzprüfungen. Lint, strikte Typprüfungen, API-Drift, beide Produktionsbuilds und beide Compose-Konfigurationen wurden ebenfalls geprüft. Desktop-/Mobile-Titelaufnahmen enthalten nur synthetische Inhalte und bleiben in den Testartefakten. Bestehende Screenshot-Baselines und Toleranzen sind unverändert. Der vollständige Compose-Lauf wird zusätzlich durch die bestehende CI geprüft.
