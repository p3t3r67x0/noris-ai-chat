# Native Slash-Kommandos

PR B baut auf PR A (#86) und dem bereits gemergten Composer aus PR #85 auf.
Die vorhandene `UChatPrompt`-/Textarea-Instanz bleibt bestehen. Die funktionale
Referenz ist die Werkzeug-/Modellbedienung im Composer; die deutschen Befehlsnamen
und Aliase sind Noris-spezifisch. Sie behaupten keine entsprechende ChatGPT-API.

| Befehl | Aliase | Aktion / Verfügbarkeit |
| --- | --- | --- |
| `/lernen` | `/learn`, `/study` | Gespeicherten Lernmodus aktivieren; verfügbare Gesprächspersistenz erforderlich |
| `/suche` | `/search`, `/web` | Websuche aktivieren; Betreiberfreigabe, aktuelles geeignetes Modell und Bereitschaft erforderlich |
| `/denken` | `/think`, `/reasoning` | Bestehendes Denkaufwand-Menü öffnen; nur belegte Optionen des gewählten Modells |
| `/modell` | `/model` | Vorhandene Modellwahl öffnen; mindestens ein verfügbares Modell erforderlich |
| `/bild` | `/image` | Für eine echte Bildgenerierungsanbindung reserviert; derzeit nicht verfügbar |
| `/datei` | `/file`, `/upload` | Native Dateiauswahl des vorhandenen Uploadsystems öffnen |
| `/hilfe` | `/help` | Lokal alle aktuell verfügbaren Befehle erklären |

`app/lib/chat/commands.ts` ist die zentrale, typisierte Registry mit stabiler ID,
Name, übersetztem Anzeigenamen und Beschreibung, Symbol, Aliasen,
Verfügbarkeitsprüfung und Ausführung. Ein neuer Befehl braucht einen Registry-
Eintrag und einen echten Handler plus Berechtigungs-/Fähigkeitsprüfung im
`CommandContext`. Bildeingabe bedeutet keine Bildgenerierungsfähigkeit: Ohne
Generierungsanbindung und Handler wird `/bild` nicht angeboten.

`useSlashCommands` erkennt einen Token am Cursor nach einem Leerzeichen oder am
Textanfang. Es unterstützt auch eine Einfügung mitten im Entwurf. URLs und Pfade
werden nicht als Befehlstoken erkannt. Während der Eingabe wird nach kanonischem
Namen und Alias gefiltert. Die Textarea behält den Fokus; `aria-controls` und
`aria-activedescendant` verknüpfen sie mit der Listbox. Pfeile wählen zyklisch,
Home/End wählen den ersten/letzten Eintrag. Enter oder Tab führt die Auswahl
aus; Escape schließt ohne Textverlust. Maus und Touch verwenden dieselbe Aktion.
IME-Komposition einschließlich Keycode 229 und der 50-ms-Abschlussphase löst
keine Befehlsausführung aus.

`ChatCommandMenu` verwendet das vorhandene Nuxt-UI-Popover und dessen
Kollisionserkennung. Das Menü erscheint bevorzugt über dem Composer und weicht
bei Platzmangel nach unten aus. Seine Höhe ist an den verfügbaren Platz gebunden;
es scrollt vertikal. Beschriftungen umbrechen auch bei 320 Pixeln. Das Plus-Menü
bleibt eine eigene Ansicht seiner bisherigen Aktionen; beide Ansichten rufen
dieselben Lernmodus-, Such- und Upload-Handler auf und schließen sich gegenseitig.

Vor **jeder** Übermittlung prüft der Composer bekannte führende Kommandos und
Kommandos am Cursor noch einmal, auch nach Escape, Paste, programmatischen Entwurfsänderungen oder einem
Klick auf Senden. Verfügbarkeit wird vor der Ausführung erneut geprüft. Ein
nicht verfügbarer bekannter Befehl bleibt als Entwurf erhalten und zeigt einen
lokalen Hinweis. Unbekannte Slash-Texte bleiben normale Chatnachrichten; damit
bleiben beispielsweise technische Fragen mit eigenen Slash-Begriffen sendbar.
Die Ausführung entfernt ausschließlich den ausgewählten Befehlstoken. Der
verbleibende Entwurf wird nicht automatisch versendet. Ein Modellwechsel setzt
den Lernmodus nicht zurück und übernimmt nur vorhandene Reasoning-Fähigkeiten.

Tests: Registry-/Composer-Unit-Tests; Playwright mit Mock- und echtem lokalen
WebSocket-/PostgreSQL-Stack. Die Matrix deckt 320, 390, 1440 und 1920 Pixel,
beide Themes, Tastatur, Touch, IME, Fokus, Cursorposition, Menü-Flipping sowie
die vorhandenen Composer-, Streaming-, Stop- und Retry-Grenzen ab. Die acht neuen
Command-Screenshots und aktualisierten Slash-Ansichten des Lernmodus enthalten
ausschließlich synthetische Testdaten.

Abnahme am 16.10.2026: 570 Frontend-Unit-Tests bestanden; vollständige Mock-
Browsertests 328 bestanden / 45 projektbedingt ausgelassen; betroffene WebSocket-
Browsertests 42 bestanden / 16 projektbedingt ausgelassen. ESLint, strenge
Anwendungs-/Test-Typprüfung und Produktionsbuild sind erfolgreich. Die abschließenden
Build-, Unit- und Mock-Läufe wurden wegen des verfügbaren Arbeitsspeichers
nacheinander ausgeführt: Node-Heap 1536 MB, Vitest und Mock-Browser je zwei Worker,
WebSocket-Browser ein Worker. Die bestehenden Composer-Screenshots wurden ohne
Aktualisierung verglichen; nur die Slash-Ansichten erhielten neue Referenzen.
