# Lernmodus: Umsetzung und Abnahme

Die [Bestandsanalyse](LEARNING-MODE-AUDIT.md) wurde vor der Umsetzung erstellt.
Der Branch verwendet den aktuellen `main` einschließlich des bestehenden
`composerMenuItems`-Builders. Plus und Slash öffnen dasselbe Nuxt-/Reka-Menü.
Es gibt weiterhin einen Composer, Nachrichtenbaum, GenerationManager und
Providerpfad.

## Verhalten und Persistenz

„Lernen“ schließt das Menü, erhält den Entwurf und fokussiert dasselbe Textfeld.
Die Aktivierung sendet keine Nachricht. Ein Slash-Befehl wird nur in seinem
auslösenden Bereich entfernt; Text davor und dahinter bleibt erhalten.
Der blaue Indikator steht links über der Eingabe und unter vorhandenen Anhängen.
Das X deaktiviert den Modus ausdrücklich. Textarea, Toolbar, Dateidialog,
Modellwahl, Autosizing und bestehende Antwortvarianten bleiben verwendbar.

Modus und optionale abstrakte Denkpräferenz gehören zum Gespräch. Die additive
Migration `0010_conversation_learning` folgt auf die bestehende
`0009_title_claim` und ergänzt genau zwei Spalten mit
Check-Constraints. Altgespräche erhalten `normal` und keine Denkpräferenz.
Nachrichten, IDs, aktive Blätter und Zweige werden nicht migriert. Speichern
verwendet die vorhandene Versionierung und Warteschlange. Ein fehlgeschlagener
Moduswechsel wird angezeigt und blockiert Senden bis zum erfolgreichen Retry.

Die gespeicherte WebSocket-Unterhaltung ist der Produktpfad. Im lokalen Mock
bleibt die Demo erkennbar; ihr Modus wird im vorhandenen lokalen Snapshot
gespeichert. Im alten, zustandslosen HTTP-Vorschaumodus ist Lernen deaktiviert,
weil dieser keinen serverseitig gespeicherten Gesprächsmodus besitzt.

## Serverseitiges Tutoring und Denkpräferenzen

Die Policy-Version `2026-10-12.1` wird ausschließlich aus einem vertrauenswürdigen
`PersistedChatRequest` ergänzt. Der GenerationManager erfasst den gespeicherten
Modus vor der Versionsprüfung; laufende Antworten behalten diesen Stand.
Policy, Fortsetzungsanweisung und aktive Gesprächshistorie werden bei Admission,
Token-/Byte-Prüfung und jedem Providersegment identisch berücksichtigt.

Die Policy steuert Sprache, Vorwissen, Lernziel, Schwierigkeit, kleine Schritte,
Verständnisprüfung, konstruktive Korrektur, Übungen und Zusammenfassungen.
Sie erlaubt höchstens eine Lernfrage gleichzeitig und fordert gemeinsame
Lösungsentwicklung bei Hausaufgaben. Browsernachrichten können keine System-
oder Entwicklerrolle erzeugen. Dateien und PDF-Auszüge bleiben Benutzerinhalt;
die Policy untersagt ihre Übernahme als privilegierte Anweisung und die
Offenlegung interner Instruktionen.

| Exaktes, belegtes Modellprofil | Nutzerpräferenz | Providerparameter |
| --- | --- | --- |
| GPT-OSS 120B | Sofort / Mittel / Hoch | `reasoning_effort`: `low` / `medium` / `high` |
| GLM 5.2 | Hoch / Sehr hoch | `chat_template_kwargs.reasoning_effort`: `high` / `max` |
| Andere oder unbelegte Modelle, virtuelle Router | Keine belegte Denkstufe | Modellstandard |
| Pro | Kein belegtes Profil | Deaktiviert |

Das Mapping verlangt passende Parameter, Modell-ID, Evidenz und unterstützte
Providerwerte. Ein Modellwechsel verändert keine Modell-ID automatisch und
erhält die gespeicherte Präferenz. Wenn sie im neuen Modell nicht verfügbar ist,
zeigt das Menü dies an und verwendet ausdrücklich den Modellstandard.
Nicht unterstützte direkt angeforderte Präferenzen werden serverseitig abgelehnt.
„Sofort“ bezeichnet den geringsten belegten Denkaufwand, keine garantierte Latenz.
Quellen: [GPT-OSS-Modellkarte](https://huggingface.co/openai/gpt-oss-120b),
[Noris GLM 5.2](https://noris.cloud/nai/models/glm-5-2/).

## Vergleich mit den vier verbindlichen Referenzen

Alle vier lokalen ChatGPT-Bilder vom 12.10.2026 wurden visuell gelesen. Die
Originale enthalten Benutzerinhalte und werden nicht eingecheckt. Alle neuen
Testbilder verwenden synthetische Daten.

| Referenz | Geprüftes Ergebnis |
| --- | --- |
| `10_56_35.png` | Composerbreites Menü direkt oberhalb des Textfelds; Lernen als zweite Aktion, Buch und „Lerne Neues“, Beschreibungen neben dem Titel |
| `10_56_42.png` | Zeigt einen Feedbackdialog; kein zusätzlicher Feedbackdialog gehört zum Lernmodus-Auftrag |
| `10_56_49.png` | Blauer kompakter Lernindikator, Anhänge darüber, ausgewählte Lernaktion mit Hintergrund und „Ausgewählt“ |
| `10_57_00.png` | Großes Denkstufenmenü mit Inline-Beschreibungen und markierter Auswahl; unbelegte Stufen bleiben sichtbar deaktiviert |

Bewusste Unterschiede: Die vorhandenen noris-Werkzeuge bleiben im Menü und
behalten ihre tatsächliche Verfügbarkeit. Ein Eintrag „Modellstandard“ ermöglicht
das Zurücksetzen der Denkpräferenz. Nicht belegte Stufen erhalten eine klare
Verfügbarkeitsbeschreibung. Es wird kein identischer Chatinhalt oder identischer
Menüumfang behauptet.

Die [24 Lernmodus-Goldens](../frontend/tests/e2e/__screenshots__/linux/desktop/)
decken Slash-Menü, aktive Lernanzeige, ausgewählte Aktion und Denkstufen für
1920 × 975, 768 × 1024 und 390 × 844 jeweils in Light und Dark Mode ab.
Zusätzlich zeigen echte lokale WebSocket-Aufrufe das
[Desktop-Denkmenü](../frontend/tests/websocket/__screenshots__/linux/desktop/learning-provider-reasoning.png)
und [Mobile-Denkmenü](../frontend/tests/websocket/__screenshots__/linux/mobile/learning-provider-reasoning.png)
mit belegten GPT-OSS-Fähigkeiten, gespeichertem Modus und echtem Dateianhang.
Die bestehenden Plus-Menü-Bilder werden an die neue Referenzgestaltung angepasst.

## Lokale Prüfungen

Die folgende Tabelle dokumentiert die Erstprüfung und die Fokuskorrektur vor der
Integration der anschließend gemergten Titeländerung auf `main`. Die erneuten
Prüfungen des zusammengeführten Stands sind weiter unten beschrieben.

Alle Dienste laufen auf eigenen Loopback-Ports. PostgreSQL-Datenbanken liegen
in einem eigens angelegten flüchtigen Testcluster; keine vorhandene Anwendung
oder Produktivdatenbank wird migriert. HTTP-/LLM-Tests verwenden den lokalen
Simulator. Sie prüfen den tatsächlichen Providerpayload und das Streaming,
keine stochastische Qualitätsgarantie eines live aufgerufenen Modells.

| Prüfung | Ergebnis |
| --- | --- |
| Ruff, Format, ESLint | Erfolgreich |
| Pyright, Nuxt/Vue und Tools-Typecheck | Erfolgreich, keine Fehler |
| Generierte REST-/WebSocket-Verträge | Aktuell, `api:check` erfolgreich |
| Backend Unit, Contract, lokale HTTP-Integration | 410 bestanden |
| Frontend Vitest | 291 bestanden |
| PostgreSQL-Integration einschließlich Nginx/Caddy | 83 bestanden |
| Playwright UI, Desktop und Mobile | 300 bestanden, 25 doppelte Screenshot-/eingabegerätespezifische Fälle übersprungen |
| Playwright HTTP, Desktop und Mobile | 75 bestanden, 5 gezielte Skip-Fälle |
| Playwright WebSocket, Desktop und Mobile | 100 bestanden (57 Desktop, 43 Mobile), 14 doppelte Screenshot-Fälle übersprungen |
| Nuxt-Produktionsbuild und Backend-Wheel/Source-Distribution | Erfolgreich |

Die vorhandenen Make-/pnpm-Aufrufe werden verwendet: `make lint typecheck
check-api`, `make test-unit`, `make test-integration`, `make test-e2e`,
`make test-e2e-websocket` und `make build`. Für Integrationstests muss
`NORIS_TEST_DATABASE_URL` auf eine wegwerfbare Datenbank mit Suffix `_test`
zeigen. WebSocket-Browsertests benötigen eine getrennte migrierte Testdatenbank
in `NORIS_DATABASE_URL`. Jeder parallel ausgeführte Browserlauf verwendet eigene
Provider-, Backend-, Frontend- und Nuxt-Ports. Persistente Desktop-/Mobile-Läufe
verwenden getrennte Datenbanken; Mock und zustandsloses HTTP benötigen die
Testdatenbank lediglich für die Bereitschaftsprüfung.

Aktivieren/Deaktivieren, Reload, Entwurferhalt, Slash-Bereich, Pfeile/Enter/Escape,
Touch, Fokuszustände, Modellwechsel, Anhänge, Zweige, Kontextlimits, serverseitige
Rollen, Capability-Grenzen und Reduced Motion werden durch bestehende und neue
Tests abgedeckt. Physische Mobilgeräte und ein echter Screenreader wurden nicht
verwendet; die Browserprüfungen kontrollieren Rollen, Beschriftungen und Fokus.

## CI-Regressionsprüfung: Dateiauswahl und Modellmenü

Die ersten GitHub-Actions-Läufe zeigten eine Fokus-Race: Die Schließanimation des
Plus-Menüs konnte erst nach dem Öffnen der Modellauswahl enden. Der ausstehende
Fokusrücksprung ins Textfeld schloss dann das neue Modellmenü. Der Composer prüft
nun vor dem Rücksprung, ob der Benutzer bereits ein anderes Steuerelement
fokussiert hat, und erhält dessen Fokus.

Ein neuer WebSocket-Regressionstest verlängert gezielt die native Schließanimation
und öffnet währenddessen die Modellauswahl. Er prüft, dass Auswahl, Entwurf und
Anhang erhalten bleiben. Der unveränderte Produktionsbuild scheitert daran auf
Desktop und Mobile; mit der Korrektur bestehen beide Fälle. Zusammen mit den
betroffenen Bildanhang-Tests bestanden 24 Prüfungen über drei Wiederholungen.
ESLint, Nuxt-/Vue-Typecheck, alle 291 Vitest-Tests und der Produktionsbuild wurden
für die Korrektur erneut erfolgreich ausgeführt.

Der zusätzliche isolierte lokale Compose-Aufbau baute die Images erfolgreich,
konnte aber PostgreSQL über das Docker-Testnetz nicht erreichen: DNS löste korrekt
auf, die TCP-Verbindung lief in einen Timeout. Nur dieses Testprojekt wurde
anschließend entfernt. Die Compose-Abnahme erfolgt im GitHub-Actions-Job
`compose-smoke`; der lokale WebSocket-Lauf verwendet den eigenen Testcluster.

## Integration des aktuellen main

Die Titeländerung aus `dd1ae84` bleibt einschließlich der dauerhaften
Titel-Claims, Diagnostik und Wiederherstellung nach Reconnect erhalten. Die noch
nicht veröffentlichte Lernmodus-Migration wurde als `0010_conversation_learning`
direkt hinter `0009_title_claim` eingeordnet; es gibt genau einen Alembic-Head.
Ein neuer Integrationstest prüft Upgrade und Downgrade aus dem bestehenden
main-Schema mit generiertem Titel, gespeichertem Claim, aktiver Nachricht und
Chatverlauf. Die Lernmodus-Integration wartet vor dem nächsten versionsgebundenen
Moduswechsel gezielt auf die unabhängige Titel-Speicherung.

Der zusammengeführte Stand besteht erneut 430 Backend-Unit-/Vertrags-/HTTP-Tests,
293 Frontend-Unit-Tests, 93 PostgreSQL-Integrationstests, die statischen Prüfungen,
die API-Vertragsprüfung und beide Produktionsbuilds. Die vollständigen Browser-
und Compose-Prüfungen werden zusätzlich auf dem aktuellen PR-Commit ausgeführt;
ihre Ergebnisse stehen in den
[Prüfungen von PR 52](https://github.com/p3t3r67x0/noris-ai-chat/pull/52/checks).

Die neuen Titel-Browsertests halten den tatsächlich abgefragten Modellkatalog
während ihrer Prüfung gültig und warten vor Enter auf die Sendebereitschaft.
Die separate Katalogaktualisierung bleibt anderweitig abgedeckt. Der Profiltest
liest die bekannte Playwright-Viewportgröße statt einer Seitenauswertung, die
eine noch laufende Navigation unterbrechen kann. 18 wiederholte Titel-/Persistenz-
prüfungen auf Desktop und Mobile und drei Desktop-Profilprüfungen bestanden mit
den unveränderten Testfristen; die drei mobilen Fälle sind gezielt übersprungen.
