# Kompakter Composer

Der bestehende `ChatComposer.vue` verwendet weiterhin `UChatPrompt`, dessen Textarea und IME-Behandlung sowie `UChatPromptSubmit`. Enter, Shift+Enter, Slash-Menü, Dateiupload, Modellwahl, Denkaufwand und Websuche verwenden ihre bisherigen Anwendungsgrenzen.

## Struktur und Maße

- Einzeilige Desktop-Eingabe: 60–70 px Mindesthöhe, proportionaler Pillenradius und 16–22 px Eingabeschrift. Bei 1920 × 975 entsprechen 70 px Höhe, 35 px Radius und 48 px große Hauptaktionen der bereitgestellten Referenz. Die sichtbaren Glyphen von Plus, Mikrofon und Sendepfeil sind separat dimensioniert. Die unnötige zusätzliche Websuche-Zeile entfällt. Die Höhe bleibt inhaltlich bestimmt; der mehrzeilige Composer verwendet 28 px Radius.
- Unterhalb von 560 px tatsächlicher Composer-Breite stehen die Aktionen dauerhaft unter der Eingabe. Das verhindert eine verdeckte Eingabe und einen Zeilenwechsel der Aktionen beim Aktivieren der Websuche. Alle Hauptaktionen behalten mindestens 44 px große Bedienflächen.
- Die Websuche steht als blaues Globus-/Text-/Entfernen-Element im vorhandenen Textarea-Slot. Sie erzeugt keinen Header. Der Datenschutzhinweis ist über den Titel des Elements und die zugängliche Beschreibung der Eingabe verfügbar.
- Der bestehende Autosize-Mechanismus misst auch die Breite des Websuche-Elements und des Mikrofons. Mehrzeiliger Text wächst nach oben bis zur vorhandenen, vom Viewport begrenzten Scrollhöhe. Das Löschen stellt das kompakte Layout wieder her; die Textarea bleibt dieselbe DOM-Instanz. Auch die Höhenmessung erfolgt in der vorhandenen unsichtbaren Mess-Textarea. Das verhindert einen kurzzeitigen Höhenabfall des sichtbaren Felds, der den Verlauf automatisch nach oben klemmen und dessen Nachführmodus unterbrechen würde.
- Modellnamen werden bei Bedarf gekürzt; Menü und vollständiger Titel bleiben verfügbar. Lernmodus und Anhänge behalten ihren vorhandenen Header.
- Der Composer sitzt auch im leeren Chat unten. Safe-Area-Abstände und die bestehende VisualViewport-Behandlung bleiben erhalten.
- Das Mikrofon verwendet optional Browser-Diktat. Ohne Web-Speech-Unterstützung ist die Aktion deaktiviert und erklärt dies im Titel. Fehler werden angezeigt; Senden, Gesprächswechsel, Verlassen des Composers und Unmount beenden die Aufnahme und verwerfen späte Ergebnisse.

## Visuelle Quellen und Aussagegrenze

Die nachgereichte lokale Referenz heißt `ChatGPT-Bild 15. Okt. 2026, 17_59_01.png`, ist 1920 × 975 px groß und hat SHA-256 `fc8ca1e345f206febf6fcb90c4cd42f8f37fab7561c9e120752e7337acf983b9`. Das persönliche Original und daraus erzeugte lokale Ausschnitte werden nicht ins Repository übernommen. Verglichen werden die sichtbare Composer-Geometrie und die synthetischen Browser-Screenshots.

| Merkmal bei 1920 × 975 | Referenz, Bildpixel | Noris, CSS-Pixel bei DPR 1 |
| --- | --- | --- |
| Composer-Breite | ca. 1003 | 1000, vorhandener Design-Token |
| Composer-Höhe | ca. 70 | 70 |
| Unterkante / unterer Abstand | ca. 946 / 29 | 946 / 29 |
| Pillenradius | ca. 35 | 35 |
| Sendekreis | ca. 48 | 48 |
| Eingabeschrift | ca. 22 | 22 |

Die bestehende sichtbare Tastatur-Fokusmarkierung bleibt erhalten. Die zusätzlich geforderte Entfernen-Aktion und die Noris-Modellwahl bleiben erhalten; ihre Inhalte unterscheiden sich deshalb von der Referenz. Die originale Schrift, der Browserzoom und DPR der Aufnahme sind unbekannt. Ein zweiter separater Screenshot wurde nicht angegeben. Hell/Dunkel, mobile Zustände und das Wachstumsverhalten werden entsprechend den Aufgabenanforderungen separat geprüft.

## Prüfungen

`frontend/tests/websocket/compact-composer.spec.ts` prüft mit der bestehenden lokalen Websuche-Fixture die Breiten 1920, 1440, 768, 390 und 320 px in Hell und Dunkel; 390 px zusätzlich mit Touch-Emulation. Die Screenshots zeigen leere und einzeilige Eingabe, Websuche, mehrzeiligen Text mit und ohne Websuche, Scrollgrenze und das Schrumpfen mit und ohne Websuche. Geometrieprüfungen sichern feste Aktionspositionen, unveränderte Unterkante, freien Eingaberaum und ausbleibenden horizontalen Überlauf.

Die bestehenden Composer-, Tastatur-, Modell-, Lernmodus-, Upload- und Websuche-Tests bleiben Teil der Regression. Die neuen Unit-Tests prüfen außerdem Entfernen der Websuche, den bestehenden Recherche-Sendeguard und das Diktat inklusive verspäteter Ergebnisse und Aufräumen.

Die Baselines verwenden das im Lockfile festgelegte Playwright 1.64.0 mit Chromium 1248.

Erfolgreiche lokale Prüfungen:

- Vollständige Mock-Browsersuite: 308 bestanden, 33 gemäß Projekt-Auswahl ausgelassen.
- Vergleich ohne Baseline-Aktualisierung: alle 96 neuen Composer-Screenshots bestanden (12 Testfälle; 8 Projekt-/Viewport-Kombinationen werden bewusst nur einmal geprüft).
- Finale Websocket-Bildaktualisierung nach der Höhenkorrektur: 36 bestanden, 30 gemäß Projekt-Auswahl ausgelassen.
- 20 gezielte Autosize-/Streaming-/Bildschirmtastatur-Regressionen nach der Korrektur der Höhenmessung bestanden.
- 557 Unit-Tests in 42 Dateien.
- ESLint ohne verbleibende Meldungen.
- Nuxt-Anwendungstypprüfung und strenge Typprüfung einschließlich Testdateien. Die installierte Nuxt-/Vue-Router-Kombination meldet dabei einen bereits vorhandenen Hinweis zum fehlenden Volar-Plugin `vue-router/volar/sfc-route-blocks`; beide Prüfungen enden erfolgreich.
- Modell-/Denkaufwand-Suite: 37 bestanden, 13 gemäß Projekt-Auswahl ausgelassen.
- Betroffene Websocket-Suite: 90 bestanden, 30 gemäß Projekt-/Viewport-Auswahl ausgelassen. Sie umfasst Websuche, Uploads, Plusmenü, Lernmodus, Neuer-Chat-Lebenszyklus und die neue Composer-Matrix.

Für die lokalen Websocket-Läufe wurde ausschließlich eine neu angelegte Datenbank `noris_composer_test` auf einer eigenen Loopback-PostgreSQL-Instanz verwendet. Die normale Projektkonfiguration bleibt unverändert; lokale Wrapper für freie Ports und die Python-3.14-Testumgebung werden nicht versioniert.
