# Noris AI: Chat-Shell vom 17. Oktober 2026

Basis: `b48ce93`, Feature-Branch `feat/chatgpt-shell-ui-fidelity`.
Der [vorab erstellte Audit](CHATGPT-2026-10-17-GAP-ANALYSIS.md) enthält
Ausgangsbefunde mit Zeilennummern und die Unterscheidung von Bildmessung,
Auftragsvorgabe, visueller Schätzung und unverifizierter Referenzeigenschaft.

## Ausgangszustand und Änderungen

Die bisherige Shell skalierte Rail und Sidebar mit der Viewportbreite. Bei
1701 × 863 betrugen sie 60,234375 und 333,109375 px. Der leere Chat stand unten;
Datumsgruppen und größere Zeilen bestimmten die Sidebar.

Die bestehende Shell verwendet jetzt feste Desktopmaße von 52/288/340 px.
Der Header enthält weiterhin Noris AI, Suche und Sidebar-Toggle; Neuer Chat
steht direkt darunter. Normale Gespräche erscheinen kompakt unter „Letzte“.
Dieser Abschnitt lässt sich mit einem beschrifteten Button einklappen. Die
Pin-Gruppe, ihre eigenen Cursor und ihre Nachladeaktionen bleiben separat.
Hover und aktive Auswahl verwenden unterschiedliche neutrale Flächen.

Der leere Chat zeigt „Wie kann ich dir helfen?“ mit dem vorhandenen Composer
als gemeinsame, erhöhte Einheit. Der Composer ist maximal 888 px breit und
kompakt 62 px hoch; auf Mobile bleiben Eingabe und untere Aktionszeile sichtbar.
Die deutsche Eingabeaufforderung lautet „Noris AI fragen“; Englisch verwendet
die bestehende Lokalisierung. Die neue Desktopbegrüßung misst 30 px, mobil
22–26 px, damit sie auch bei 320 px Breite einzeilig bleibt.

## Geänderte Dateien und wiederverwendete Architektur

Produktive Änderungen betreffen ausschließlich:

- `frontend/app/assets/css/main.css`
- `frontend/app/components/chat/ChatRail.vue`
- `frontend/app/components/chat/ChatSidebar.vue`
- `frontend/app/components/chat/ChatSidebarSection.vue` (kleiner Abschnittsrahmen mit eigener ARIA-ID pro gerenderter Instanz)
- `frontend/app/components/chat/ChatWorkspace.vue`
- `frontend/app/components/chat/ProfileMenu.vue` (Tooltip am vorhandenen Trigger)
- `frontend/app/lib/settings/messages.ts`

Die vollständige Liste einschließlich Tests, Dokumentation, Messdaten und
synthetischer Bilder steht in [CHANGED-FILES.txt](october-2026/CHANGED-FILES.txt).
Kein Backendmodul, API-Vertrag, Lockfile oder produktiver Transport wurde geändert.

Belegte Einstiegspunkte im finalen Code: Tokens in
`frontend/app/assets/css/main.css:6`, Desktoprail in derselben Datei bei Zeile 334,
Empty-Docking bei Zeile 183 und die Tastaturanpassungen bei Zeile 359;
Gruppendarstellung in `frontend/app/components/chat/ChatSidebar.vue:21`,
Abschnitts-ARIA in `frontend/app/components/chat/ChatSidebarSection.vue:8`,
Profiltooltip in `frontend/app/components/chat/ProfileMenu.vue:84` und die
unverändert einzelne Composerinstanz in
`frontend/app/components/chat/ChatWorkspace.vue:229`.

Wiederverwendet werden `ChatHeader`, `EmptyChatState`, `ChatComposer`,
`ChatTimeline`, `ConversationTitle`, `ChatSearchDialog`, `ChatModelMenu`,
`ChatReasoningMenu`, `ChatCommandMenu`, `ProfileMenu`, `USidebar`,
`UDropdownMenu`, `UChatPrompt` und `UChatPromptSubmit`. Die vorhandenen
Composables für Chat, Backend, Conversations, Drafts, Scroll, Viewport,
Sidebarpräferenz, Autosize, Uploads, Slash-Kommandos und Diktat bleiben erhalten.

## Tokens

Geändert: `--noris-rail-width` (Desktop 52 px), `--noris-sidebar-width` (288 px),
`--noris-chat-max-width` (888 px), `--noris-composer-height` (62 px),
`--noris-composer-control-size` (44 px), `--noris-composer-model-width` (128 px),
Sidebartext (16 px), Sidebartitel (20 px), Composertext (18 px),
Light-Sekundärtext (#5d5d5d), Hover-/Active-Abstufungen. Der vorhandene
Composer-Maxbreitenalias, proportionale Radius und Schatten bleiben erhalten.

Neu: `--noris-shell-navigation-width`, `--noris-navigation-row-height`
(44 px), `--noris-sidebar-section-gap` (32 px), `--noris-submit-background`
und `--noris-submit-foreground`. Die Submitfarben sind zentral in Light und
Dark definiert. Die bislang isolierten Light-Farben des Submitbuttons entfallen.
Es gibt keine Skalierungstransforms.

## Composer-Zustandsmodell und Docking

Es gibt weiterhin **einen** produktiven Editor. Das vorhandene unsichtbare
Messfeld von `useComposerAutosize` ist kein zweiter Editor. Keine Editor- oder
Chatkomponente wurde dupliziert. Der bestehende Zustandsautomat entscheidet
anhand der tatsächlichen Breite einschließlich Modell-/Reasoning-/Werkzeug-
Controls, Zeilenhöhe und Schriftmetriken:

| Zustand | Verhalten |
| --- | --- |
| Compact | Eine Eingabezeile, Plus links, Modell/Reasoning/Mikrofon/Submit rechts |
| Expanded | Mehrzeilige Eingabe oberhalb derselben Werkzeugleiste |
| Maximized | Begrenzte Höhe, interner Editor-Scroll, erreichbare Controls |
| Attachments / Lernmodus | Vorhandener Header über derselben Textarea |
| Streaming / Stop | Bestehende Generation, Stop und Cancellation-Logik |
| Disabled / Error | Bestehende Sende-, Upload-, Modell- und Fehlerguards |

Der hypothetische Compact-Platz bestimmt weiterhin den Rückwechsel; es gibt
keinen Zeichenanzahl-Breakpoint. Der bestehende 560-px-Breitenwechsel erhält
auf schmalen Composern die permanente untere Werkzeugzeile. Anhänge, Slash-
Popover, IME und Diktat behalten ihre bisherigen Ereignisse und Verknüpfungen.

Im Empty State reserviert ein flexibler Bereich unter dem Dock ungefähr die
untere Hälfte des Workspace. Wachstum verbraucht zuerst den Platz über dem
Dock. Das Eingabelimit ist dort `min(160px,18cqh)`, bei Anhangheadern weiterhin
enger. In aktiven Chats begrenzt weiterhin das bestehende Limit die Eingabe;
die Timeline bekommt den verbleibenden Platz und behält ihren Scrollcontainer.

## Navigation, Sidebar und New Chat

Die Rail bleibt außerhalb des Chatlisten-Scrollbereichs und zeigt nur echte
Noris-Funktionen: Home/Neuer Chat, Suche, Archiv und das bestehende Profilmenü.
Routenabhängiges `aria-current` kennzeichnet Home bzw. Archiv. Alle Railbuttons
verwenden das vorhandene zentrierte 44-px-Raster, reguläre Icons sind 20 px groß.
Tooltips decken auch das bestehende Profil ab.

`USidebar` behält Header, eigenen scrollenden Body und Footer. Die neue
„Letzte“-Darstellung fasst ausschließlich vorhandene Datumsgruppen zusammen;
Comparatoren, serverseitige Sortierung, begrenzte Fenster und Cursor bleiben
unverändert. Der Abschnittszustand ist lokaler UI-Zustand in derselben
Komponente. Einklappen blendet Zeilen aus, ohne ihre Instanzen zu zerstören;
Titelupdates werden beim Aufklappen sichtbar. Es gibt keine zweite Persistenz.
`useSidebarPreference` verwaltet weiterhin ausschließlich die Desktoppräferenz.

Der Browsercheck zeigte anfangs zwei gleiche Ziel-IDs: Nuxt UI rendert denselben
Inhalt für Desktop und Drawer. `ChatSidebarSection` kapselt deshalb ausschließlich
Überschrift und Inhaltsrahmen; jede Instanz erhält über Vue `useId` ihre eigene
ID. Es gibt weiterhin nur eine Sidebarverwaltung und einen gemeinsamen
Abschnittszustand. Unit- und Browsertests prüfen, dass das Drawer-Control genau
ein sichtbares ARIA-Ziel adressiert.

New Chat ruft unverändert `chat.newChat()` auf und fokussiert den vorhandenen
Composer. Neue leere Chats erzeugen weiterhin keinen POST/Sidebar-Eintrag.
Vorbereitete Upload-/Einstellungsentwürfe bleiben mit ihrer Conversation-ID
verbunden. Pin/Unpin, Umbenennen, Suche, Archiv, Löschen, Portalmenüs,
Fokusrückgabe und versionierte Live-Updates verwenden ihre bisherigen Pfade.

Ein produktives Projektmodell fehlt. Die Sektion entfällt bewusst. Auch
Work-Tabs, Plugins und Echtzeit-Voice werden nicht als fiktive Funktionen ergänzt.

## Responsive Verhalten und Accessibility

Geprüfte Zielmatrix: 1701×863, 1440×900, 1280×800, 1024×768, 768×1024,
390×844, jeweils Light/Dark. Die vorhandenen Tests ergänzen 1920, 360 und
320 px sowie Pixel-7-Touch-Emulation. Ab 1024 px: Rail und Sidebar nebeneinander.
Darunter: bestehender Slideover auf Chatrouten; die Einstellungen behalten ihre
vorhandene mobile Navigation. Der Chat bleibt im freien
Hauptbereich zentriert; das Schließen der Sidebar ändert weder Chat noch Editor.

`useChatViewport`, `visualViewport.height/offsetTop`, Safe-Area und die
vorhandenen Containerabfragen bleiben aktiv. Unter 500 px sichtbarer Höhe
entfällt der große Empty-State-Abstand; Begrüßung und Controls bleiben sichtbar.
Aktive Entwürfe begrenzen den Editor dort auf 18 % der sichtbaren Höhe.
Timeline-Padding sinkt auf 8 px; der letzte Nachrichtenabstand entfällt, damit
der kleinere Lesebereich tatsächlichen Antworttext statt Leerraum zeigt.
Unter 300 px entfallen außerdem der minimale obere Spacer und Dock-Innenabstand;
die Anhangliste wird auf 15 % der sichtbaren Höhe begrenzt. So bleiben auch
bei 250 px sichtbarer Höhe die bestehende Eingabe und ihre Controls erreichbar.
Der Chatheader verwendet dann weiterhin 44-px-Bedienflächen bei 44 px Höhe;
der Hinweistext pausiert bis zum Schließen der Tastatur und der Dock-Unterrand
verwendet 4 px oder den größeren Safe-Area-Inset. Eigene Tastaturtests prüfen
mindestens 80 px Nachrichtenbereich und 24 px sichtbaren Antworttext,
unveränderten Entwurf/Fokus und die Rückkehr zur normalen Höhe in beiden Themes.
Pinch-Zoom wird weiterhin nicht durch die Tastaturanpassung überschrieben.

Die Abschnittsüberschrift enthält einen nativen Button mit `aria-expanded`
und `aria-controls`. Unsichtbare Zeilen sind nicht fokussierbar. Rail und
Conversation-Navigation behalten ihre benannten Landmarks. Sichtbarer Fokus,
Escape/Fokusrückgabe, Pfeiltasten, Enter, Shift+Enter und IME werden durch
bestehende und neue Tests geprüft. Touchaktionen bleiben dauerhaft erreichbar.
Die Hauptcontrols und Chatzeilen sind mindestens 44 px hoch; Desktop-
Kontextaktionen bleiben 28 px groß und erfüllen damit die 24-px-Untergrenze.
Die bestehende globale Reduced-Motion-Regel bleibt erhalten; Titel haben
keine Marquee-Animation. Kontrastmessungen erfolgen in den Referenz-/Visualtests.
Das ist eine automatisierte Prüfung betroffener Kriterien, keine umfassende
WCAG-Zertifizierung oder Screenreader-Geräteabnahme.

## Visueller Vergleich und Geometrie

Die folgenden Dateien enthalten ausschließlich synthetische Noris-Inhalte:

| Vorher | Nachher | Differenz |
| --- | --- | --- |
| [before.png](october-2026/before.png) | [after.png](october-2026/after.png) | [diff.png](october-2026/diff.png) |
| [390 Light vorher](october-2026/before-390-light.png) | [390 Light nachher](october-2026/after-390-light.png) | [390 Light Diff](october-2026/diff-390-light.png) |
| [1701 Dark vorher](october-2026/before-1701-dark.png) | [1701 Dark nachher](october-2026/after-1701-dark.png) | [1701 Dark Diff](october-2026/diff-1701-dark.png) |

Alle sechs Größen und beide Themes liegen im selben Evidenzordner. Weitere
Zustände stehen unter `frontend/tests/e2e/__screenshots__/linux/desktop/october-*`
und `frontend/tests/websocket/__screenshots__/linux/desktop/october-*`.
Die Pixeldifferenz ist eine Änderungsdarstellung zwischen Noris-Versionen,
kein Pixelgleichheitsnachweis gegenüber der privaten Referenz.

Die Zustandsaufnahmen verwenden jeweils `light` und `dark`. Dateinamen ohne
Pfadangabe liegen in `frontend/tests/e2e/__screenshots__/linux/desktop/`;
WebSocketbilder liegen im entsprechenden `tests/websocket`-Verzeichnis.

| Angeforderter Zustand | Aufnahme / funktionaler Nachweis |
| --- | --- |
| Empty Chat | `october-{width}-{theme}-empty.png`, alle sechs Größen |
| Empty / Sidebar geschlossen | `october-{width}-{theme}-closed.png`, Desktopgrößen |
| Eine / zwei / fünf Zeilen | `october-{theme}-{single,two,five}.png` |
| Sehr langer Text | `october-{theme}-long.png`, interner Scroll und Schrumpfen geprüft |
| Upload / ein / zwei Anhänge | WebSocket: `october-{uploading,attachment,two-attachments}-{1701,390}-{theme}.png` |
| Streaming | `october-{theme}-streaming.png` |
| Stop angefordert | WebSocket: `october-pending-stop-{theme}.png`, genau ein zurückgehaltenes echtes Cancel-Frame |
| Antwort gestoppt | `october-{theme}-stopped.png` |
| Rail Hover / Active | `october-{theme}-rail.png`, Suchhover und aktive Home-Fläche |
| Sidebar / Chataktionen Hover | `october-{theme}-row-hover.png` |
| Letzte / angepinnter Chat | `october-{theme}-pinned.png`, eigene Pin-Gruppe |
| Aktionsmenü geöffnet | `october-{theme}-menu.png`, Escape und Fokusrückgabe geprüft |
| Neuer Chat | WebSocket-Lifecycle plus `docs/screenshots/new-chat/after/` |
| Sidebar geschlossen | `october-{width}-{theme}-closed.png`, Editor/Draft erhalten |
| Mobiler Drawer | `october-{768,390}-{theme}-drawer.png`, eindeutige sichtbare ARIA-Ziele |
| Aktiver langer Entwurf mit Tastatur | `active-keyboard-{360,250}-{theme}.png`, zusätzlich Touchprojekt |

| Maß bei 1701×863 / DPR 1 | Soll | Ist | Absolute / relative Abweichung | Sicherheit |
| --- | ---: | ---: | --- | --- |
| Rail | 52 | 52 | 0 px / 0 % | Markupangabe im Auftrag; HTML nicht bereitgestellt |
| Sidebar | 288 | 288 | 0 px / 0 % | aus Auftragsangaben abgeleitet |
| Navigation gesamt | 340 | 340 | 0 px / 0 % | Markupangabe im Auftrag |
| Composerbreite | ≈888 | 888 | 0 px / 0 % zum Schätzwert | visuelle Schätzung |
| Compact-Höhe | ≈62 | 62 | 0 px / 0 % zum Schätzwert | visuelle Schätzung |
| Chatzeile | ≈42,5 | 44 | 1,5 px / 3,53 % | Schätzung; größere Bedienfläche bewusst gewählt |
| Greeting-Schrift | ≈30 | 30 | 0 px / 0 % zum Schätzwert | visuelle Schätzung |

Die Greeting-Linebox liegt bei y=291,375 und ist 37,5 px hoch, der Composer
bei y=364,875. Der gemessene Abstand beträgt **36 px**. Die gemeinsame
horizontale Mitte ist x=1020,5. Vollständige DOMRects einschließlich Header,
Neuer Chat, Abschnitt, Zeile, Textarea und Controls sowie Vergleichssicherheit
stehen in [geometry-1701-light.json](october-2026/geometry-1701-light.json)
und den entsprechenden Dateien der übrigen Größen/Themes.

## Reproduktion

Die vorhandene Playwright-Konfiguration startet den Produktionsbuild und die
lokale API. WebSockettests verwenden den lokalen Provider-Simulator und eine
explizite, migrierte Wegwerfdatenbank mit Suffix `_test`. Keine Produktivdatenbank
wurde für die Browserprüfungen verwendet. Für diesen Lauf wurden eigene Loopback-Ports
und ein isoliertes Uploadverzeichnis verwendet.

Beim Vorbereiten einer Testdatenbank sowohl `NORIS_DATABASE_URL` als auch
`NORIS_MIGRATION_DATABASE_URL` auf dieselbe isolierte Datenbank setzen; eine
bereits vorhandene Migrations-URL hat sonst Vorrang.

```sh
pnpm --dir frontend exec playwright test
pnpm --dir frontend exec playwright test --config playwright.websocket.config.ts \
  october-attachments.spec.ts attachments.spec.ts new-chat.spec.ts \
  persistent-chat.spec.ts sidebar-pinning.spec.ts compact-composer.spec.ts \
  composer-plus-menu.spec.ts slash-commands.spec.ts learning-mode.spec.ts \
  conversation-titles.spec.ts
pnpm --dir frontend exec playwright test --config playwright.llm.config.ts \
  composer-layout.spec.ts reasoning-selection.spec.ts
```

Für die neutralen Vorher-/Nachher-Paare einen lokalen Mock-Build des jeweiligen
Commits starten und das Aufnahmeskript aus diesem Branch verwenden:

```sh
NORIS_SHELL_URL=http://127.0.0.1:3000 node frontend/scripts/capture-chat-shell.mjs after
python3 docs/ui-reference/compare_shell.py
```

Vorher wurde am Ausgangscommit aufgenommen; für dessen Reproduktion `before`
als Argument verwenden. Der lokale Browser benötigt das zu Playwright 1.64.0
passende Chromium 1248. Keine private Referenzdatei wird von diesen Skripten
gelesen. Die bestehenden Pixeltoleranzen bleiben **0,001**.

## Prüfergebnisse

Aufnahmeläufe mit Snapshot-Aktualisierung und Vergleiche ohne Aktualisierung
sind getrennt ausgewiesen. Fehler aus dem Gesamtlauf bleiben sichtbar; gezielte
Nachprüfungen ersetzen keinen behaupteten fehlerfreien Gesamtlauf.

| Prüfung | Ergebnis |
| --- | --- |
| Frontend ESLint | bestanden |
| Nuxt-Anwendungstypprüfung | bestanden; vorhandener optionaler Volar-Pluginhinweis |
| Vue-/Test-Typecheck | bestanden; derselbe vorhandene optionale Volar-Pluginhinweis |
| Tool-TypeScript | bestanden |
| Frontend Unit, vollständig | 572 bestanden in 43 Dateien |
| Gezielte Profil-/Sidebar-Unit-Regression | 11 bestanden nach der Tooltip-Anbindung |
| Nuxt Production Build | bestanden |
| API-Drift | bestanden; Verträge unverändert |
| Vorhandene Composer-Geometrie | 16 bestanden vor der neuen Matrix |
| Neue Produktionsmatrix | 14 bestanden, einschließlich aller Zielviewports und beider Themes |
| Gezielte finale Keyboard-/Upload-/Stop-Prüfung | 10 bestanden, 10 doppelte Mobile-Matrixfälle laut bestehender Projektauswahl ausgelassen |
| Finale aktive Keyboard-Prüfung | 8 bestanden: 360/250 px, abgeschlossen/streamend, Light/Dark und Desktop/Touch; mindestens 80 px Verlauf und 24 px Antworttext |
| Finale gezielte Accessibility-Prüfung | 4 bestanden, 2 doppelte Matrixfälle ausgelassen; Desktop-/Mobile-Profilkeyboard, Drawer-ID, sichtbarer Tooltip und berechnete Beschreibung |
| Profilmenü, vollständige Desktop-/Touch-Suite | 11 bestanden, 3 geräteabhängige Fälle ausgelassen; erneuter Klick, Keyboard, Submenüs und Fokusrückgabe |
| Mock-Browser-Gesamtsuite, ohne Snapshot-Aktualisierung | 346 bestanden, 4 fehlgeschlagen, 59 projektspezifisch ausgelassen; die vier Fehler betrafen den bei 250 px absichtlich versteckten Hinweistext |
| Mock: vollständige Settings-Nachprüfung | 8 bestanden nach fachlicher Anpassung der Hinweistext-Erwartung; Composergrenzen und Rückkehr des Hinweises werden zusätzlich geprüft |
| WebSocket-Gesamtlauf der betroffenen Dateien, ohne Snapshot-Aktualisierung | 107 bestanden, 1 fehlgeschlagen, 36 projektspezifisch ausgelassen; Katalog-Fixture-Refresh während Enter im Fortsetzungstest |
| WebSocket: vollständige Persistenz-Nachprüfung | 14 bestanden nach Verwendung der bestehenden stabilen Katalog-Fixture ausschließlich im Fortsetzungstest |
| SSE Modell-/Reasoning-Aufnahme | 37 bestanden, 13 doppelte Matrixfälle ausgelassen |
| SSE Modell-/Reasoning-Bildvergleich ohne Aktualisierung | 37 bestanden, 13 doppelte Matrixfälle ausgelassen |
| Screenshotvergleich ohne Aktualisierung | Alle ausgeführten Bildassertionen in Mock, WebSocket und SSE bestanden; die fünf oben genannten Fehler waren funktionale Testvorbereitungen/Erwartungen |
| Nicht ausgeführt | Externe Live-Provider-Suites, Backend-Unit-Suite (Backend unverändert), reale iOS-/Android-Geräte und Screenreader-Geräteabnahme |

Damit wurden **350 Mock-, 108 WebSocket- und 37 SSE-Fälle** unter dem finalen
Produktcode erfolgreich geprüft: die Vereinigung aus Gesamtlauf und vollständig
nachgeprüften betroffenen Testdateien. Wiederholte Fälle werden dabei nicht
doppelt gezählt. Ein weiterer ununterbrochener Gesamtlauf nach den letzten
beiden ausschließlich testseitigen Anpassungen wurde lokal nicht wiederholt.
Die maschinenlesbaren Ergebnisse stehen in
[TEST-RESULTS.json](october-2026/TEST-RESULTS.json).

Umgebungsbefunde: Der erste Build endete mit Exit 137. Der erfolgreiche
Wiederholungslauf begrenzte den Node-Heap auf 2048 MB und umging den verwaisten
Nuxt-Build-Lock. Ein paralleler Entwicklungsbrowserlauf konnte während der
Typgenerierung nicht hydratisieren und wurde zugunsten des Produktionsbuilds
abgebrochen. Das /tmp-Schreibkontingent erforderte das Verlegen temporärer
Testdateien in den ignorierten Testordner; der eigene abgebrochene Browserdownload
wurde entfernt. Die erste Wegwerfdatenbank hatte systemseitig SQL_ASCII;
WebSockettests verwenden eine neu angelegte UTF-8-Datenbank mit `_test`-Suffix.
Ein SSE-Vorlauf fand eine noch nicht migrierte eigene Datenbank vor: Der erste
Migrationsaufruf übernahm die vorhandene Migrations-URL und führte dort laut
Migrationslog keine Schemaänderung aus. Danach wurden beide URLs explizit auf
die neue Testdatenbank gesetzt und deren Migrationen vollständig ausgeführt.
Ein belegter Port wurde durch eigene freie Ports ersetzt. Diese Vorläufe werden
nicht als erfolgreiche Tests gezählt.

Der installierte Node 22.22.1 liegt unter der deklarierten Mindestversion
22.22.3. Die Prüfungen verwenden die vorhandenen Node-Entrypoints, weil der
pnpm-Managerstore in der Sandbox schreibgeschützt ist. Keine Paketversion wurde
geändert. Die bekannten Buildwarnungen zu es2019/BigInt und `modelModifiers`
bleiben bestehen.

Ein breiter Aufnahmelauf erreichte 341 bestandene Mock-Fälle und einen
rein testseitigen Clock-Fehler: Zwischen `Date.now()` und `clock.pauseAt(now+100)`
war der geplante Zeitpunkt unter Last bereits vergangen. Die Vorbereitung
vor einer Generation verwendet jetzt einen gemeinsamen aktuellen Zeitursprung
und einen vorab bestimmten zukünftigen Haltepunkt. Ein historischer Zeitursprung
nach dem Mount wurde verworfen: Vue schützt Ereignisse anhand ihrer Zeitstempel
und ignoriert solche rückwärts datierten Eingaben. Der gezielte Wiederholungslauf
bestand alle sechs Tastatur-/Chatwechsel-Fälle. Alle Streaming-Intervalle,
Assertions, Timeouts und Bildtoleranzen bleiben unverändert. Der WebSocket-
Aufnahmelauf erreichte 100 bestandene Fälle; acht New-Chat-Fälle enthielten noch
die alte Erwartung eines unten stehenden Empty State und prüfen jetzt dessen
neue Position mit einer exakten Geometrieassertion.

Ein weiterer vorhandener New-Chat-Test las zeitweise den Abschlussstatus der
vorherigen Antwort, bevor der neue Sendebefehl bestätigt war. Er wartet jetzt
zusätzlich auf den Empty State und den konkret neu gesendeten Nutzertext.
Die unveränderte Zwei-Conversation-Assertion wird erst anschließend geprüft.
Eine eigene Browserprüfung mit echter Zeit zeigte außerdem, dass die bisherigen
Timeline-Endabstände bei geöffnetem Keyboard den Lesebereich mit Leerraum
füllten. Die gezielte CSS-Anpassung und stärkere Textsichtbarkeitsassertion
prüfen diesen Befund. Keyboardbilder verwenden abgeschlossene synthetische
Texte; aktive Streams werden mit denselben Geometrie-/Fokusassertionen geprüft,
ohne wechselnden Streamtext als instabile Bildbaseline zu verwenden.

Im letzten Gesamtlauf bestanden 346 Mock-Fälle; vier ältere Assertions erwarteten
den Hinweistext auch bei 250 px sichtbarer Höhe. Die angepasste vollständige
Settings-Datei bestand anschließend mit acht Fällen. Der WebSocket-Gesamtlauf
bestand 107 Fälle; im Fortsetzungstest überlappte laut Trace die Enter-Ausführung
(562081–562116 ms) mit einem Katalog-Refresh (562092 ms). Die bestehende
`stableModelCatalog`-Fixture verändert nur den lokalen Ablauf-Timer, nicht
Verfügbarkeit, Berechtigungen oder Serverchecks. Die vollständige
Persistenzdatei bestand anschließend mit 14 Fällen. Assertion-Timeouts und
Pixeltoleranzen blieben unverändert.

Im ersten breiten Browserlauf bestanden vor dem Neustart 202 Mock-Fälle und
19 WebSocketfälle. Die festgestellten Abweichungen betrafen alte Text-/Geometrie-/
Farberwartungen, den anhand des Traces bestätigten Profiltest vor Hydrierung,
einen unter Last abgelaufenen Sidebar-Test sowie die korrigierten 250-px- und
320-px-Randfälle. Die Läufe wurden für den finalen Build beendet; nicht erreichte
Fälle und unterbrochene Tests werden nicht als bestanden gezählt.

## CI-Nachprüfung zu PR #88

Der [CI-Job 117411213241](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/39037862011/job/117411213241?pr=88)
bestand die komplette Mock-Suite mit **350 Fällen / 59 ausgelassen**. Auch der
Compose-Smoke-Job bestand. Die gesamte SSE-Suite führte dagegen **82 erfolgreiche,
13 ausgelassene und einen fehlgeschlagenen Fall** aus. Der Fehler lag in einem
SSE-Titeltest, der im früheren lokalen Teilumfang nicht enthalten war.

`frontend/tests/llm/conversation-titles.spec.ts:70` erwartete bei 1280 px weiterhin
den ungekürzten Titel „Docker DNS Troubleshooting Guide“. Die frühere Geometrie
verwendete hier 14 px Sidebartext, die neue 16 px. Die Beschriftung hat jetzt
255 px verfügbaren Platz; der vollständige Titel misst lokal in Chromium
254,640625 px. Wegen der bereits vorhandenen 1-px-Reserve in
`frontend/app/components/chat/ConversationTitle.vue:26` beträgt das Nutzungsbudget
254 px. Die mittlere semantische Variante ist deshalb korrekt.

Der unveränderte Test wurde lokal mit **einem Fehler / einem erfolgreichen
Touchfall** reproduziert. Die korrigierte Desktop-/Touchprüfung bestand mit
**zwei Fällen**. Sie prüft zusätzlich gemessene Textbreite, unveränderte Zeilenhöhe,
erreichbare Aktionen bei Hover und Tastaturfokus, fehlende Überlagerung,
unveränderten gespeicherten Volltitel und genau einen Titelrequest auch nach
Reload. Geometrie wird als JSON an den Browserreport angehängt. Produktcode,
Snapshot-Toleranzen, Assertion-Timeouts und Baselines bleiben unverändert.

Nach der Korrektur bestanden lokal auch die **vollständigen** Transportsuiten:
SSE **83 erfolgreich / 13 ausgelassen**, WebSocket **208 erfolgreich / 36
ausgelassen**, jeweils ohne Snapshot-Aktualisierung. Damit sind auch die zuvor
nicht lokal ausgeführten Recherche-, Quellen-, Pagination- und Toolfälle erfasst.

Beim folgenden CI-Lauf auf `5418737` bestand der Compose-Push-Job. Der parallele
[Compose-PR-Job 117416543849](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/39039720672/job/117416543849)
zeigte zusätzlich einen Initialisierungswettlauf in
`frontend/tests/websocket/web-search-ui.spec.ts`: Der mobile Chatwechseltest
füllte bereits das serverseitige Textfeld, während `.chat-workspace` noch
`data-ready="false"` und `inert` trug. Dies belegen die DOM-Snapshots unmittelbar
vor und nach `fill` im Playwright-Trace. Die Hydrierung setzte die Eingabe zurück;
`click` wartete anschließend bis zum Testende auf den deaktivierten Sendebutton.
Der eigentliche Chatwechsel wurde noch nicht erreicht.

Die Recherche-UI-Tests warten nun nach jeder ersten Navigation auf das bestehende
`data-ready="true"`-Signal von `ChatWorkspace.vue:198`, entsprechend dem bereits
verwendeten Muster anderer Tests. Es wurde keine neue Produktzustandslogik
hinzugefügt und kein Timeout erhöht. Die vollständige Recherche-UI-Datei bestand
anschließend lokal mit **16 Fällen** (Desktop und Mobile); ESLint und der
Test-Typecheck bestanden ebenfalls.

Die Zahlen der ursprünglichen lokalen Teilprüfungen oben bleiben historische
Nachweise. Aktuelle vollständige CI-Ergebnisse sind über die Checks des
[Pull Requests #88](https://github.com/p3t3r67x0/noris-ai-chat/pull/88) nachvollziehbar.

## Restabweichungen und Folgearbeiten

- Das PNG misst 1920×975; die zugehörige CSS-Pixel-Skalierung und das erwähnte
  Original-HTML fehlen. Die festen Auftragswerte werden umgesetzt, ohne die
  Bildnavigation von etwa 68/376 Bildpixeln als 52/288 CSS-Pixel auszugeben.
- Schriftfamilie, exakte Schatten und Rundungen der Quelle bleiben teilweise
  Schätzungen. Dark Mode und Mobile sind Noris-Ausprägungen, im Bild unbelegt.
- Noris behält seine vorhandene Modellwahl im Header, Themeauswahl, realen
  Modell-/Reasoningmenüs und einen deaktivierten Sendepfeil bei leerer Eingabe.
  Eine nicht vorhandene Echtzeit-Voice-Funktion wird nicht vorgetäuscht.
- Projekte und zusätzliche ChatGPT-Appbereiche fehlen bewusst mangels Noris-
  Produktmodell. Ihre Einführung wäre ein separater Produktauftrag.
- Reale iOS-/Android-Tastaturen, Browserzoom und Screenreader auf echten
  Geräten benötigen eine manuelle Abnahme. Automatisiert werden Chromium,
  Touch-Emulation, Kontrast, Keyboard und VisualViewport geprüft.
- Nächster Schritt ist das Review des Pull Requests und der verlinkten Bilder.
  Kein automatischer Merge.

## Abnahmekriterien und Nachweise

| Kriterium | Nachweis |
| --- | --- |
| AC-01 Rail 52 px | DOMRect-JSON und October-Shell-Matrix |
| AC-02 Navigation 340 px | Sidebar 288 px, Hauptbereich beginnt bei x=340 |
| AC-03 Header | Noris AI, Suche und Toggle in vorhandener Sidebar |
| AC-04 Neuer Chat | Geometrieprüfung direkt unter Header, mindestens 44 px hoch |
| AC-05 Letzte | Lokalisierte aufklappbare Abschnittsüberschrift |
| AC-06 Zeilen | Einheitlich 44 px, Hover/Active getrennt, synthetische Bilder |
| AC-07 Chataktionen | Bestehende Desktop-/Touch-/Keyboard-Sidebartests |
| AC-08 Empty State | Gemeinsame erhöhte Einheit, zentriert im freien Hauptbereich |
| AC-09 Compact | 888×62 px bei 1701×863, mindestens 44-px-Controls |
| AC-10 Wachstum | Konstante Unterkante bei 2/5/40 Zeilen in der Zielmatrix |
| AC-11 Schrumpfen | Rückkehr zur Ausgangshöhe und unveränderte Textarea |
| AC-12 Controls | Geometrie, Keyboard und funktionale Modell-/Upload-/Stoptests |
| AC-13 Ein Composer | Retained-DOM-Marker durch Wachstum und erstes Senden |
| AC-14 Upload | Reale API, zwei Anhänge, Progress, Retry, Reload und Senden |
| AC-15 Leere Chats | Bestehende WebSocket-New-Chat-Lifecycle-Tests |
| AC-16 Persistenz/Sync | Bestehende Persistenz-, Titel-, Pin- und Reconnectfälle |
| AC-17 Responsive | Alle sechs Zielviewports plus vorhandene Zusatzgrößen |
| AC-18 Themes | Light-/Dark-Matrix, Kontrast- und Theme-Persistenztests |
| AC-19 Accessibility | Keyboard, Fokus, Touch und ARIA; manuelle Geräteabnahme offen |
| AC-20 Evidenz | Versionierte synthetische Bilder, JSON-Messungen und Pixel-Diffs |
