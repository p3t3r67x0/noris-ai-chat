# Automatische Titel im WebSocket-Chat

## Befund und Beweisgrenze

Ein `completed` der ersten Assistentenantwort bestätigt ausschließlich den Antwort-Commit. Der Titel wird danach in einem separaten Gateway-Aufruf erzeugt. `errorCode=null` der Antwort schließt einen Titelfehler deshalb nicht aus. Die bisherigen WebSocket-Titelfehler wurden durch `except (LLMError, ChatError): pass` verschluckt; Datenbankfehler endeten ohne Titelkontext im allgemeinen Task-Fehlerlog. Ohne damalige Titeldiagnose lässt sich der konkret gemeldete produktive Fehler keiner einzelnen Ursache sicher zuordnen. Es wurden weder Produktionsdaten noch Produktionsserver geändert und keine echten Provider-Completions angefordert.

Der Code begrenzte Titel auf sechs Sekunden und 96 **gesamte** Ausgabetokens. Der OpenAI-kompatible Adapter liefert ausschließlich sichtbares `delta.content`; `reasoning_content`/`reasoning` werden nicht als Titel behandelt. `finish_reason=length` führt zu `OUTPUT_LIMIT`, auch wenn noch kein sichtbarer Titel existiert. Die Noris-Dokumentation beschreibt zusätzliche Reasoning-Tokens, Kosten und Latenz: [Reasoning](https://noris.cloud/nai/concepts/reasoning/). Für DeepSeek V4.1 Flash bestätigt der bestehende Katalog keine unterstützte Reasoning-Steuerung. Deshalb werden keine spekulativen `enable_thinking`-/`thinking`-Parameter gesendet. GPT-OSS verwendet das verifizierte `reasoning_effort=low` für Titel. Lokale HTTP-Fixtures reproduzieren Reasoning ohne sichtbaren Output beim alten Limit und einen gültigen sichtbaren Titel beim neuen Limit für beide konkreten Modell-IDs; sie belegen keine Live-Latenz oder Live-Titelqualität.

## Ablauf und Korrekturen

1. Nach abgeschlossener erster Antwort (einschließlich erfolgreichem Retry/Continuation) prüft der Server persistierte Herkunft und Claim. Folgefragen sind ausgeschlossen; Quelle ist ausschließlich der Anfang der gespeicherten ersten Nutzernachricht.
2. Gateway-Admission prüft Modellverfügbarkeit, Kontext, gemeinsame parallele Slots, Minutenrate und Tagesbudget. Kein automatischer Provider-Retry oder Wechsel zu einem anderen Modell. Titel bekommen standardmäßig 20 Sekunden und 1024 gesamte Ausgabetokens, weiterhin begrenzt durch das Modelllimit. Die produktiven Compose-Defaults werden ebenfalls auf 20/1024 angehoben; reine Python-Defaults würden dort weiterhin von 6/96 überschrieben. Explizit konfigurierte engere Limits bleiben wirksam.
3. Migration `0009_title_claim` ermöglicht einen dauerhaften atomaren Claim nach Admission und vor dem Provideraufruf. Es gibt keinen prozesslokalen 10000-Titel-Stopp für persistierte Chats. Bereits beanspruchte, manuelle, generierte und gelöschte Unterhaltungen starten keinen zweiten Titelaufruf.
4. Der sichtbare Titel muss weiterhin 2–5 Wörter und höchstens 40 Zeichen enthalten und die bestehenden Datenschutz-/Formatregeln erfüllen. Leerer/ungültiger Output, Timeout, Budget- und Ratefehler bleiben diagnostiziert, ohne den abgeschlossenen Antwortstatus zu verändern.
5. Speicherung sperrt die Gesprächszeile und wechselt ausschließlich `fallback` auf `generated`, erhöht die Version und committet vor dem Broadcast. Bei `OperationalError` gibt es maximal drei idempotente Schreibversuche mit dem vorhandenen Ergebnis. Permanente SQL-Fehler werden nicht wiederholt. Manuelle Umbenennung gewinnt auch während eines Provideraufrufs; REST-Umbenennungen verteilen zusätzlich die gespeicherten versionierten Metadaten an alle verbundenen Tabs.
6. Alle verbundenen Tabs erhalten Titel- und Gesprächsereignisse. Neue Gesprächsmetadaten gelangen automatisch in die Sidebar. Der Browser liest nach `chat.connected` verpasste Metadaten nach und verbindet sich auch ohne laufende Antwort begrenzt wieder. Reload liest denselben gespeicherten Titel über REST. Veraltete Versionsstände können manuelle Titel nicht zurücksetzen.

## Diagnose

JSON-Serverlogs unter `uvicorn.error.noris_ai.title` haben ausschließlich diese Felder: `event`, `conversation_id`, `model_id`, `phase`, `error_code`, `duration_ms`, `outcome`. Phasen: `eligibility`, `admission`, `claim`, `generation`, `validation`, `persistence`, `broadcast`. Ergebnisse: `started`, `success`, `failure`, `skipped`, `retry`. Fehlertexte, Stacktraces, SQL, API-Schlüssel, Prompts, Reasoning und Titelinhalte werden hier nicht geloggt. Die Conversation-ID ermöglicht gezielte Korrelation; Dauer ist die seit Beginn des jeweiligen Gateway-/Lebenszyklusaufrufs verstrichene Zeit.

## Begrenzte Wiederholung und verbleibende Grenzen

Ein bereits gestarteter fehlgeschlagener Provideraufruf kann abgerechnet worden sein. Er wird deshalb weder bei Regeneration noch Reload/Reconnect automatisch wiederholt. Ein Prozessabbruch nach Claim oder drei erfolglose Datenbankschreibversuche kann weiterhin einen Fallback hinterlassen; das wird diagnostiziert. Eine dauerhafte Retry-Outbox für Titelresultate ist nicht Teil dieser Korrektur. Automatische Erfolgsgarantien bei dauerhaft nicht verfügbarem Provider oder PostgreSQL sind damit ausdrücklich ausgeschlossen. Bestehende historische Fallbacks werden nicht heimlich kostenpflichtig nachgeneriert.

Der vorhandene Server unterstützt einen Worker. Titelclaims sind zwar dauerhaft/atomar; Gateway-Quotas und Peer-Broadcast bleiben wie bisher prozesslokal. Mehrere Browser-Tabs gegen diesen Worker werden getestet. Betrieb mehrerer Backend-Replikate benötigt weiterhin verteilte Quotas und Ereignisverteilung.

## Regressionen

`test_persisted_titles.py`: beide nativen Modell-IDs, Reasoning und sichtbarer Output, altes/neues Tokenlimit, Timeout mit geschlossenem Stream, feste Fehlercodes, Datenschutz der Logs, Datenbankfehler vor Provideraufruf, begrenzte Schreibwiederholung und parallele Tasks. Bestehende Titeltests prüfen ungültige Ausgabe einschließlich Wortzahl und echte Gateway-Budget-/Rate-Admission.

`test_conversation_titles.py`: PostgreSQL und reale FastAPI-WebSockets, erfolgreiche Titelpersistenz, zwei Peers, Reconnect, Regeneration ohne zweiten Titelaufruf, Fehlerisolierung, manuelle Umbenennung während Titelgenerierung, atomare Claims zwischen Repository-Instanzen und idempotenter Commit.

Frontend-Unit-Tests prüfen Reconnect eines untätigen Tabs und Autoritäts-/Versionsschutz bei alleinstehendem Titelereignis. Desktop-/Mobile-WebSocket-Browsertests prüfen DeepSeek und GPT-OSS, automatische Sidebar-Aktualisierung in zwei Tabs, unterbrochene Verbindung, manuellen Titel, Seitenreload und Regeneration; alle Completions sind lokale synthetische Fixtures.

## Lokale Prüfung

- Vollständige Backend-Unit-, Vertrags- und lokale HTTP-Provider-Suite: 419 bestanden.
- Vollständige PostgreSQL-/WebSocket-/Proxy-Integrationssuite auf dem finalen Backend-Stand: 90 bestanden, einschließlich des zusätzlichen Zwei-Tab-Tests für manuelles REST-Umbenennen.
- Vollständige Frontend-Unit-Suite: 287 bestanden; die gezielt wiederholten Titel-/WebSocket-Unit-Tests sind ebenfalls grün.
- Vollständige Desktop-/Mobile-WebSocket-Browsersuite: 100 bestanden, 14 planmäßig übersprungen (die Bildschirmbreiten-Screenshot-Matrix läuft bereits im Desktop-Projekt).
- Ruff-Lint und Formatprüfung, ESLint, strikte Python-/Vue-/Test-/Tool-Typprüfung, OpenAPI-/WebSocket-Vertragsprüfung und Compose-Konfigurationsprüfung bestanden.

Die WebSocket-Composer-Screenshot-Prüfung wartet auf den unabhängig gespeicherten Titel und den bereiten Composer. Eine alte Referenz für 1700 px zeigte noch den Fallback und einen vorübergehend deaktivierten Senden-Button; sie wurde auf den fertigen Zustand aktualisiert. Die Toleranzen bleiben unverändert. Der bestehende Textreferenz-/Bearbeitungstest wartet jetzt auf die neue abgeschlossene Antwortvariante und die gespeicherte Bearbeitung, statt eine ältere abgeschlossene Antwort als Erfolg zu werten; er besteht zusätzlich dreimal auf Desktop und dreimal auf Mobile.

Der [GitHub-CI-Lauf 38237123791](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/38237123791) zeigte zwei weitere Test-Races: Der Reconnect-Unit-Test sendete sein simuliertes Serverereignis vor dem Öffnen des Mock-WebSockets und der Listener-Registrierung. Er wartet jetzt auf die geöffnete Verbindung. Im Bildvorschau-Browsertest deaktivierte die nach einer Sekunde fällige Katalogaktualisierung den Senden-Button zwischen Playwrights Bereitschaftsprüfung und dem eigentlichen Mausklick. Dieser Test verifiziert zunächst den realen Vision-Katalog und hält dessen Gültigkeit im Browser anschließend für 60 Sekunden stabil; die Katalogaktualisierung hat eigene Tests. Assertions, Testzeitlimits und die produktive Katalogvalidierung bleiben unverändert. Nach diesen Korrekturen bestehen alle 287 Frontend-Unit-Tests sowie zehn Wiederholungen des Bildvorschau-Tests je auf Desktop und Mobile (20 insgesamt).

Die Testdatenbanken und HTTP-Provider liegen ausschließlich lokal. Der Produktionsserver wurde weder geprüft noch verändert. Die Migration ist vor dem Start des aktualisierten Backends einzuspielen; es gibt keinen automatischen Daten-Backfill oder Provider-Retry.
