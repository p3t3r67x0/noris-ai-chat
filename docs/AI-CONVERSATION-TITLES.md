# Automatische Gesprächstitel

Neue Gespräche zeigen zunächst ein lokal erkanntes Thema, etwa **Automatische Chat-Titel**, oder **Neuer Chat**, wenn kein verlässliches Thema erkennbar ist. Es werden keine Frageanfänge oder abgeschnittenen Wörter übernommen. Nach Beginn des vorhandenen Chat-Streams startet unabhängig davon genau ein automatischer Titelversuch. Ein gültiger Titel ersetzt den Fallback in der vorhandenen Sidebar und wird im bestehenden lokalen Chat-Snapshot gespeichert. Nachrichten, Varianten und Scrollverhalten verwenden weiterhin dieselben Komponenten und denselben Streaming-Vertrag.

## API und Provider

`POST /api/v1/llm/conversation-title` verlangt dieselbe Basic-Anmeldung und Origin-Freigabe wie `/api/v1/llm/chat`. Der JSON-Body enthält ausschließlich `conversationId`, `inputMessageId`, `modelId` und `firstMessage` (höchstens 1024 Unicode-Zeichen). Die Antwort enthält beide IDs und `title` mit höchstens 40 Zeichen. OpenAPI und die generierten TypeScript-Typen enthalten diesen Vertrag.

Der vorhandene `LLMGateway` reserviert dieselben globalen Slots, Raten- und Tagesbudgets. Der vorhandene `OpenAICompatibleProvider` verwendet denselben HTTP-Client. Nur dieser serverseitige Vorgang fügt eine vertrauenswürdige Titel-Systemanweisung hinzu. Öffentliche Chat-Nachrichten akzeptieren weiterhin ausschließlich user/assistant; Chatantworten erhalten keine Titelanweisung. Die erste Nutzernachricht ist untrusted Quelltext und darf die Titelregeln nicht ersetzen.

Ziel sind 2–5 Wörter als Themenphrase in der Gesprächssprache, bevorzugt höchstens 30 und niemals mehr als 40 Unicode-Zeichen. Technische Namen wie **Rust vs. C++** bleiben erhalten. Äußere Anführungszeichen und ein abschließender Punkt werden entfernt; Ellipsis, Steuerzeichen, Frageanfänge, Floskeln und generische KI-Ausgaben werden verworfen. Bekannte redundante Zusätze können lokal entfernt werden: **Automatisierte Chat-Titel Implementierung** wird zu **Automatische Chat-Titel**. Es werden immer ganze Begriffe erhalten, niemals Zeichen abgeschnitten oder Punkte angehängt. Bei ungeeigneten Ausgaben bleibt der lokale Fallback; weder Chattext noch Chat-Fehlerzustand ändern sich. Es gibt keine automatischen Retries.

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

Snapshot v1 verwendet weiterhin `titleSource` (`fallback`, `generated`, `manual`) und `titleGenerationAttempted`. `fallback` kennzeichnet lokale Themen/Platzhalter, `generated` ein validiertes KI-Ergebnis einschließlich lokaler Verkürzung, `manual` einen Benutzernamen. Fehlende Felder älterer Snapshots werden konservativ zu `manual` und `true` migriert: Ein historischer Nachrichtenausschnitt lässt sich ohne Herkunftskennzeichnung nicht sicher von einem manuellen Namen unterscheiden und bleibt deshalb erhalten. Bekannte automatische Titel werden beim Laden lokal normalisiert; IDs, Nachrichten, aktive Verzweigungen und Entwürfe bleiben erhalten. Es gibt keine rückwirkenden Provider-Anfragen. Der Versuch wird vor der ersten Chat-Anfrage markiert. Reload, Wechsel, Folgefragen, Edit und Retry starten keine weitere Titelgenerierung. Scheitert die Hauptanfrage vor Streaming, bleibt ebenfalls der Fallback ohne erneuten automatischen Versuch.

Manuelles Umbenennen setzt sofort `manual`. Ergebnisse werden nur bei passenden Gesprächs-/Nachrichten-IDs, derselben vorhandenen Conversation-Instanz und `fallback` angewendet. Späte Titel können umbenannte oder gelöschte Chats nicht überschreiben oder wiederherstellen. Wechsel und Archivieren verändern die Zuordnung nicht. Stop der Chatantwort ist unabhängig vom Titel. Löschen, Hydrate, pagehide und Unmount brechen ausstehende Titel ab. Fremde Storage-Änderungen beenden ebenfalls Titelanfragen und erhalten die vorhandene Warnung.

Titel erscheinen als normaler Text. `ConversationTitle` misst mögliche Themenformen mit einem unsichtbaren DOM-Element in der tatsächlichen Schrift des vorhandenen Titelbereichs. Padding, Menübutton und Abstände sind dadurch bereits von der verfügbaren Breite abgezogen. Messungen erfolgen bei Titeländerungen, ResizeObserver-/Fensteränderungen und nach dem Laden von Fonts. Eine passende Themenform wird über den vorhandenen Store persistent gespeichert; veraltete Messungen oder manuelle Namen werden nicht angewendet. Automatische Titel bleiben einzeilig und verwenden keine Ellipsis. Die Sidebar behält Breite und Zeilenhöhe. Lange manuelle Namen behalten Ellipsis, ihr bestehendes 120-Zeichen-Limit, den vollständigen zugänglichen Button-Namen und den nativen Tooltip.

Bei 1920 × 975 beträgt die gemessene Titelbreite rund 289 px (20-px-Schrift), bei 1440 × 900 rund 195 px und bei 1280 × 800 rund 185 px. Ein Titel unter 30 Zeichen kann also trotzdem zu breit sein. Beispielsweise passt **Sicherheitskonzept planen** auf schmaleren Desktops. Unbekannte, unbrauchbare Themenformen fallen auf **Neuer Chat** zurück. Diese konservative lokale Erkennung deckt bekannte technische Themen ab; sie ist keine allgemeine Sprachzusammenfassung.

## Datenschutz und Prüfung

Die zusätzliche Anfrage überträgt nur den Anfang der ersten Nachricht, keinen Verlauf. Ist eine erste Frage unklar, kann ein bekannter Themenbegriff aus der abgeschlossenen Antwort oder beim Laden aus dem vorhandenen aktiven Gesprächspfad den unbekannten lokalen Fallback ersetzen. Dieser Kontext bleibt ausschließlich im Browser; dafür entsteht keine weitere LLM-Anfrage. Offensichtliche Zugangsdaten, E-Mail-Adressen, URLs, UUIDs und JWTs werden vor dem Provider-Aufruf ersetzt. Die Titelanweisung verlangt breite Themen statt unnötiger sensibler Details. Diese Minimierung erkennt nicht sämtliche personenbezogenen Angaben. Diagnose-Logs enthalten nur feste Fehlercodes, keine Nachrichten, Titel, IDs, Provider-Texte oder Secrets. Screenshots und Fixtures verwenden ausschließlich synthetische Texte.

MockTransport erzeugt deterministische lokale Titel ohne Backend-/Provider-Aufruf. Die bestehenden Ziele `make lint`, `make typecheck`, `make check-api`, `make test-unit`, `make test-integration`, `make test-e2e`, `make test-e2e-production` und `make build` prüfen die Erweiterung mit. Titeltests decken zwei Sprachen, technische Namen, gemeinsame Budgets, Streaming, IDs, Umbenennen, Löschen, Archivieren, Reload, alte Snapshots, Fehler und Sidebar-Geometrie ab.

Playwright prüft zusätzlich die tatsächliche DOM-Textbreite, einheitliche Eintragshöhen, Einzeiligkeit, fehlende Ellipsis und die Menübedienung bei 1920 × 975, 1440 × 900, 1280 × 800 und 390 × 844. Die Abnahme-Nachricht zur automatischen Chat-Titelgenerierung ergibt **Automatische Chat-Titel** im Mock-Modus und über den bestehenden Backend-/Provider-Vertrag mit einer lokalen Fixture. Titelaufnahmen und `title-widths.json` enthalten ausschließlich synthetische Inhalte und bleiben in den Testartefakten. Bestehende Screenshot-Baselines und Toleranzen werden unverändert geprüft. Die CI führt außerdem die gesamte Suite am Entwicklungsserver und am frischen Compose-Produktionsstack aus.
