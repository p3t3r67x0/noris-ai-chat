# Adaptiver Chat-Composer

## CI-Nachprüfung vom 2026-10-11

Der abgeschlossene [Compose-Browserjob 114435754381](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/38127803240/job/114435754381?pr=43) meldete 16 Suchdialog-Screenshotabweichungen bei 257 erfolgreichen Tests. Die bisherigen Baselines enthielten noch den alten Composer und den Hinweis unterhalb des Composers. Die synthetischen Expected/Actual/Diff-Artefakte wurden lokal verglichen: Die relevante Geometrieänderung liegt im Hintergrund-Composer; Suchfeld, Dialoggeometrie und Trefferlayout bleiben erhalten. In acht Bildern unterscheidet sich zusätzlich die Rasterung eines einzelnen Zeichens im unveränderten synthetischen Treffernamen. Alle Actual-Bilder stimmen pixelgenau mit dem jeweiligen CI-Retry überein. Nur diese 16 synthetischen Baselines wurden aus den bereits vorhandenen CI-Aufnahmen übernommen; Toleranzen und Assertions bleiben bestehen.

Zwei mobile Settings-Navigationstests scheiterten zunächst und bestanden beim Retry. Der Helper wartet jetzt nach jeder Kategorieauswahl auf die neue Seitenüberschrift und beim Öffnen der mobilen Navigation auf `aria-expanded=true`. Dadurch kann die noch laufende vorherige Route die gerade wieder geöffnete Navigation nicht schließen. Auf ausdrücklichen Nutzerwunsch wurden keine weiteren Tests oder Docker-Läufe gestartet und keine CI-Ergebnisse abgewartet.

Der anschließend vom Nutzer verlinkte abgeschlossene [Job 114437614648](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/38128449260/job/114437614648?pr=43) bestand Lint/Typprüfung, 286 Backend- und 266 Frontend-Unit-Tests, 30 Integrationstests und 275 Mock-Browserfälle. Im SSE-Browserlauf bestanden 51 Fälle; vier Screenshotfälle scheiterten jeweils beim ersten Modell. Die vier vorhandenen synthetischen Light-/Dark-Aufnahmen für Desktop/Mobile wurden einzeln geprüft: Die alten Bilder zeigen den Composer in der Seitenmitte, die Actual-Aufnahmen den beauftragten unteren Dock und den Hinweis darüber. Nur diese vier geprüften Modell-0-Baselines wurden übernommen. Die übrigen 20 Modell-/Mehrzeilen-/Streamingbilder wurden wegen des ersten Fehlers nicht aufgenommen und bleiben unverändert, bis tatsächliche neue Aufnahmen vorliegen.

Die bestehenden Screenshotzustände sind jetzt unabhängige Testfälle, damit eine Abweichung die weiteren Aufnahmen nicht verhindert. Sämtliche Geometrie-, Text-, Modelllabel-, Overflow- und Stop-Assertions sowie die Screenshotnamen und Toleranzen bleiben erhalten. Stop wird auch nach einer fehlschlagenden Streamingaufnahme geprüft. Ein neuer lokaler Testlauf wurde nicht ausgeführt.

Der bestehende `ChatComposer.vue` verwendet weiterhin eine einzige `UChatPrompt`-Instanz und deren native Textarea, Enter-/Shift+Enter- und IME-Behandlung. Das CSS-Grid wechselt zwischen einer gemeinsamen Zeile und Texteingabe über der unteren Aktionszeile. Es gibt keine zweite Composer-Instanz und keinen Remount beim Layoutwechsel.

## Referenz und Geometrie

Die beiden am 11. Oktober 2026 lokal bereitgestellten Referenzen zeigen bei 1920 × 975 eine etwa 1003 px breite Chatspalte. Der kompakte Composer ist ungefähr 70 px hoch, seine Unterkante liegt bei etwa y=946. Die Referenz mit Anhang zeigt dieselbe Unterkante und eine nach oben vergrößerte Außenkontur. Die Pillenform entspricht ungefähr 35 px Radius. Bildpixel, CSS-Pixel, Browserzoom und Geräteskalierung sind ohne zusätzliche Aufnahmeinformationen nicht gleichzusetzen.

Noris behält seine bestehende Chatspalte und Design-Tokens. Die kompakte Höhe beträgt 60–70 CSS-Pixel, bei 1701 px Breite etwa 62 px. Die Steuerelemente haben mindestens 44 px große Touch-Ziele. Die Modellbezeichnung bleibt einzeilig und wird bei begrenzter Breite gekürzt; das Menü und der zugängliche Titel enthalten den vollständigen Namen. Es werden ausschließlich vorhandene, funktionierende Aktionen angezeigt. Eine Mikrofonattrappe wird entsprechend der Nutzerentscheidung nicht hinzugefügt.

Die privaten Referenzen und sämtliche daraus abgeleiteten Vergleiche bleiben außerhalb des Git-Bestands und Docker-Build-Kontexts. Neue öffentliche Screenshots enthalten ausschließlich synthetische Gespräche und Dateien. Historische Referenzdokumente sind keine neuen Freigaben für private Bildinhalte.

## Messung und Layoutwechsel

`useComposerAutosize` misst den Platzbedarf mit einer unsichtbaren Mess-Textarea bei der hypothetischen kompakten Eingabebreite. Die Breite berücksichtigt Innenabstände, Buttons und Grid-Abstände; Schriftmetriken werden von der tatsächlichen Textarea übernommen. Dadurch wird auch ein langer Satz ohne explizite Zeilenumbrüche erkannt. Im erweiterten Zustand sorgt eine 8-px-Hysterese für einen stabilen Rückwechsel, statt die breitere erweiterte Textarea als Umschaltschwelle zu verwenden.

Die echte Textarea wird anhand ihrer `scrollHeight` vergrößert und beim Löschen wieder verkleinert. Ihre maximale Höhe beträgt das Minimum aus 160 px und 30 % der verfügbaren Viewport-/Containerhöhe. Anhänge begrenzen den Texteingabebereich zusätzlich zugunsten sichtbarer Bedienelemente. Oberhalb der Grenze scrollt ausschließlich die Textarea; längere Dateilisten haben einen eigenen begrenzten Vorschau-Bereich innerhalb des Composers. Leerer oder wieder einzeiliger Text ohne Anhänge kehrt in die kompakte Zeile zurück.

Ein `ResizeObserver` berücksichtigt Breitenänderungen; Fenster-, VisualViewport- und Schriftladeereignisse lösen eine erneute Messung aus. Die vorhandene Viewport-Behandlung berücksichtigt Bildschirmtastatur und Safe-Area. Eingabe, Cursor und Fokus bleiben auf derselben nativen Textarea. Uploadstatusmeldungen und Dateinamen sind zugänglich.

## Scrollen

Der Composer-Dock bleibt am unteren Rand des flexiblen Chatbereichs. Zusätzlich benötigte Höhe wird dem Nachrichtenbereich entzogen. `useChatScroll` beobachtet weiterhin dessen Größe und den Nachrichteninhalt. Beim Lesen älterer Nachrichten bleibt die Scrollposition erhalten; nur aktiv folgendes Lesen wird bei Streaming oder Größenänderungen am Ende gehalten.

Der runde Scrollpfeil bleibt horizontal über dem Composer zentriert. Er erscheint bei mehr als 96 px Abstand und verschwindet erst bei höchstens 32 px Abstand. Der Klick aktiviert das automatische Folgen wieder. Diese Hysterese verhindert Flackern an der Sichtbarkeitsschwelle.

## Prüfung

Playwright prüft die sieben angeforderten Viewports, Light/Dark, Enter, Shift+Enter, IME, Streaming/Stop, manuelles Lesen, Wachstum und Schrumpfen. Die zusätzliche Zustandsmatrix bei 1701 × 863, 1440 × 900 und 390 × 844 misst Unterkante und Button-Achse, prüft dieselbe DOM-Instanz und den Fokus und erstellt synthetische Compact-/Expanded-/Maximized-Screenshots. Lange Sätze, 2/5/10 Zeilen, große Texte und Zoom werden ausdrücklich geprüft.

Die mobile Tastatur wird über VisualViewport-Ereignisse simuliert. Eine reale Betriebssystemtastatur und sämtliche Browser-Zoom-Implementierungen erfordern zusätzlich manuelle Geräteprüfung; CSS-Zoom im automatisierten Chromium-Test deckt die Größenänderung, Umbrüche und Cursorerhaltung ab.
