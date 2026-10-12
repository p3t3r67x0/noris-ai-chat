# Plus-Menü im Chat-Composer

## Bestandsanalyse und Wiederverwendung

| Vorhandener Baustein | Verwendung |
| --- | --- |
| `ChatWorkspace.vue` | Ein bestehender Composer, Entwurf und Attachment-State pro Unterhaltung; verbindet weiterhin Upload, Entfernen und Wiederholen. |
| `ChatComposer.vue` / Nuxt UI `UChatPrompt` | Bestehendes Textfeld mit Enter, Shift+Enter, IME und Senden/Stoppen; unveränderte Attachment-Vorschau im Header. |
| `UButton` / `UDropdownMenu` | Bestehender Plus-Trigger und Menü, mit Reka-Portal, Fokusverwaltung, Tastaturbedienung und Floating-UI-Kollisionsbehandlung. |
| Natives `input[type=file]` | Bestehender Mehrfach-Dateidialog mit TXT, Markdown, PDF, PNG und JPEG; derselbe `files`-Event. |
| `useChatAttachments` | Bestehende MIME-/Größen-/Anzahlprüfung anhand der Server-Limits, XHR-Fortschritt, Uploadbestätigung, Fehler, Retry, Abbruch und gespeicherte Anhänge. |
| `useComposerAutosize` | Bestehendes kompaktes, mehrzeiliges und maximiertes Composer-Layout. |
| `useChatViewport` | Bestehende Anpassung des Workspace an `visualViewport` bei Bildschirmtastatur. |
| `ChatModelMenu` | Bestehende Modellauswahl und Bildkompatibilität. Bildanalyse vorhandener Anhänge bedeutet keine Bilderstellung. |
| Nuxt UI, Tailwind, Lucide, `useAppLocale` | Vorhandene Komponenten, Schatten und Klassen, Theme-Tokens, lokal gebündelte Icons und deutsche/englische Beschriftungen. |

Die Bestandsprüfung fand einen Upload-Eintrag, keine Dateibibliothek, Bilderstellung, Websuche, Deep-Research-Orchestrierung oder Zeichenoberfläche. Chat-Suche durchsucht Unterhaltungen und stellt keine Websuche dar. Das Backend und seine Upload-API werden unverändert weiterverwendet.

## Menüstruktur und verfügbare Funktionen

`frontend/app/lib/chat/composerMenu.ts` definiert Reihenfolge, stabile Aktions-IDs, Übersetzungsschlüssel, Beschreibungen und Lucide-Icons. `composerMenuItems` erhält die tatsächlich implementierten Handler und die Upload-Verfügbarkeit. Ohne Handler bleibt ein Eintrag deaktiviert und besitzt keine `onSelect`-Aktion. Eine spätere Integration registriert ihre echte Aktion unter der bestehenden ID.

| Eintrag | Status |
| --- | --- |
| Fotos und Dateien hinzufügen | Öffnet den bestehenden nativen Mehrfach-Dateidialog, sobald Backend und Attachment-Limits bereit sind. |
| Aus Bibliothek hinzufügen | Noch nicht verfügbar; deaktiviert. |
| Bild erstellen | Noch nicht verfügbar; deaktiviert. |
| Websuche | Noch nicht verfügbar; deaktiviert. |
| Deep Research | Noch nicht verfügbar; deaktiviert. |
| Skizzieren | Noch nicht verfügbar; deaktiviert. |

Das Plus-Menü ist auch im lokalen Demo-/SSE-Modus erreichbar. Dort erklärt der deaktivierte Upload-Eintrag, dass der Demo-Modus keine gespeicherten Uploads unterstützt. Bei laufender Initialisierung erscheint „Datei-Upload wird vorbereitet …“, bei einem Backend-Fehler dessen tatsächliche Meldung. Eine manuell angelegte Unterhaltung ist keine Voraussetzung. Die fünf nicht implementierten Funktionen besitzen `disabled`/`aria-disabled`, eine gedämpfte Darstellung und keine Aktion. Rechte „Noch nicht verfügbar“-Hinweise wurden entfernt. Ihre Implementierung bleibt eine separate Entscheidung; im Rahmen dieser Korrektur werden keine neuen Dienste oder Anwendungen gebaut.

## Layout, Positionierung und Interaktion

- Hintergrund, Text, Rahmen und Hover verwenden vorhandene `--noris-*`-Theme-Tokens; Nuxt UI liefert den dezenten Schatten. Ein einzelner dünner Rahmen und ein Radius von 1 rem ersetzen die generische Dropdown-Darstellung.
- Desktop/Tablet: Breite `clamp(700px, 51vw, 880px)`, zusätzlich auf den verfügbaren Viewport begrenzt. Bei 1440 px sind es rund 734 px, bei 1700 px 867 px, bei Tabletbreite 768 px 700 px. Mindestens 48 px hohe Einträge, 20 px große Icons, 15 px große Titel und 14 px große Beschreibungen in einheitlichen Spalten. Es gibt keine zusätzlichen Gruppentrenner oder rechten Statushinweise.
- Mobile: maximal Viewportbreite abzüglich 24 px und Safe-Area-Inset; mindestens 56 px hohe Einträge, Beschreibung unter dem Titel, Umbruch statt horizontalem Scrollen.
- Das bestehende Portal zeigt das Menü als Overlay. Eine virtuelle Reka-Referenz verwendet die linke Kante des Plus-Buttons und die obere/untere Kante des tatsächlichen Composers. Dadurch bleibt das Menü auch über einem mehrzeiligen Composer mit Anhängen und bei dessen Größenänderung frei von Überlappungen, soweit Platz vorhanden ist.
- Reka/Floating UI berücksichtigt den sichtbaren Viewport, 12 px Kollisionsabstand, automatische Verschiebung/Seitenwechsel und die verfügbare Höhe. Der vorhandene Menü-Viewport scrollt bei Platzmangel. Positionen werden während des Öffnens laufend nachgeführt.
- Klick auf Plus öffnet/schließt, Außenklick und Escape schließen. Die explizite Pointer-Freigabe des geöffneten Plus-Buttons erhält das erneute Anklicken auch im bestehenden modalen Reka-Menü.
- Geschlossen besitzt Plus eine transparente Fläche. `data-state="open"` des vorhandenen Dropdown-Triggers aktiviert ausschließlich einen 44-px-Kreis aus `--noris-active-background`; es gibt keinen zweiten Active-State. Eine zentrierte CSS-Pseudofläche erhält die bestehende Klickfläche, Button- und Iconposition auch bei größeren Composer-Control-Tokens. Rahmen und Schatten entfallen; Hover und 100-ms-Hintergrundtransition verwenden vorhandene Theme-Tokens. Tastaturfokus bleibt mit 2-px-Outline sichtbar; die bestehende Reduced-Motion-Regel reduziert die Transition.
- Enter, Leertaste und Pfeil nach unten öffnen per Tastatur. Pfeiltasten, Home und End navigieren durch verfügbare Einträge; deaktivierte Einträge werden übersprungen. Enter/Leertaste aktivieren den nativen Upload und schließen das Menü.
- Beim normalen Schließen stellt Reka den Fokus auf Plus wieder her. Nach Upload-Auswahl oder Abbruch geht er in das bestehende Textfeld zurück, ohne Scrollsprung.

Ein zusätzlich gefundener Bestandsfehler ist korrigiert: Beim ersten Anhang wurde eine neue Unterhaltung angelegt, ohne den Entwurf aus dem noch unzugeordneten Chat zu übernehmen. Der vorhandene Workspace überträgt den Text jetzt synchron in dieselbe Attachment-Unterhaltung und leert den vorherigen Entwurf. Eine leere Dateiauswahl emittiert keinen Upload-Event und legt keine Unterhaltung an.

## Ursache von „An internal error occurred“

Die untersuchten Backend-Logs zu `http://localhost:8080/` weisen `GET /api/v1/conversations/{id}/active-path?limit=50` mit HTTP 500 aus. SQLAlchemy/psycopg meldet die fehlende Spalte `chat_attachment.pdf_sections`. Der generische Backend-Handler liefert die bereinigte Meldung `INTERNAL_ERROR` / „An internal error occurred“. `realTransport.responseError` und `useChatBackend` zeigen diese Meldung weiterhin an; die Backend-Initialisierung und damit der Upload bleiben gesperrt. Der bisherige Hinweis auf eine „gespeicherte WebSocket-Unterhaltung“ erklärte diesen Fall falsch und wurde korrigiert.

Der neue Integrationstest `test_attachment_schema_readiness.py` reproduziert dieselbe HTTP-500-Antwort mit dem bestehenden Schema `0007_text_references`. Die bereits vorhandene additive Migration `0008_pdf_sections` stellt anschließend Readiness und Active Path mit HTTP 200 sowie den Upload mit HTTP 201 wieder her; die alte Nachricht bleibt erhalten. Eine neue Migration oder ein Ersatz für die Persistenz ist nicht erforderlich. Die Lösung wurde in der isolierten Docker-Testdatenbank nachgewiesen. Eine noch ausstehende Migration einer betroffenen Instanz ist eine Betriebsaufgabe und wird durch einen Frontend-PR allein nicht ausgeführt. Fehler werden nicht ausgeblendet.

Beim abschließenden, ausschließlich lesenden Nachtest auf `http://localhost:8080/` am 2026-10-12 liefern Readiness, Unterhaltungsliste, Active Path der neuesten Unterhaltung und Attachment-Limits jeweils HTTP 200. Der in den Logs nachgewiesene Fehler tritt bei diesen aktuellen Aufrufen nicht mehr auf. Nutzerinhalte und Zugangsdaten wurden weder in Testartefakte noch in diese Dokumentation übernommen.

## Visuelle Referenz und Screenshots

Die genannten ChatGPT- und Noris-Screenshots wurden in dieser Unterhaltung nicht angehängt. Die vorhandene Repository-Referenz `docs/ui-reference/evidence/sanitized/reference-layout-redacted.png` zeigt den Composer, aber kein geöffnetes Plus-Menü. Ein belastbarer Pixelvergleich mit dem Menü-Referenzbild ist deshalb nicht möglich. Das Menü folgt den ausdrücklichen Größen- und Interaktionsvorgaben. Die vor der Korrektur erstellte [Abweichungsliste](ui-reference/plus-menu/DEVIATIONS.md) trennt gemessene Werte von unbekannten Referenzmaßen. Der PR bleibt bis zum Bildvergleich ein Entwurf; eine visuelle Abnahme wird nicht behauptet.

Die sechs [Vorher-Bilder](ui-reference/plus-menu/before/) dokumentieren den lokalen Zwischenstand vor der angeforderten Verbreiterung und Active-State-Korrektur mit synthetischen Gesprächsdaten. Sie sind weder Benutzer-Bildanhänge noch ein Screenshot des unveränderten `main`-Branches.

Playwright erzeugt und prüft vollständige Seitenansichten mit synthetischen Gesprächsdaten unter `frontend/tests/websocket/__screenshots__/linux/desktop/`:

- `plus-menu-1440-light.png` / `plus-menu-1440-dark.png`
- `plus-menu-1700-light.png` / `plus-menu-1700-dark.png`
- `plus-menu-768-light.png` / `plus-menu-768-dark.png` (768 × 1024)
- `plus-menu-390-light.png` / `plus-menu-390-dark.png`

Für jede der vier Größen und beide Themes gibt es zusätzlich `plus-button-closed-{width}-{theme}.png`. Die geöffneten Menübilder zeigen den Active-Kreis. Desktop wird mit 1440/1700 × 900 und Mobile mit 390 × 844 aufgenommen. Alle 16 Nachher-Bilder werden nach ihrer Erzeugung nochmals gegen gespeicherte Vergleichsbilder geprüft; vorhandene Attachment- und Composer-Vergleichsbilder werden nicht aktualisiert.

Zusätzliche Geometrieprüfungen kontrollieren Ausrichtung am Plus-Button, Abstand zum kompakten und mehrzeiligen Composer, unveränderte Composer-/Button-/Icon-Abmessungen, gleiche Zeilenhöhen, vollständige Icons und fehlenden horizontalen Overflow. Prüfungen umfassen Toggle, Außenklick, Escape, Dateiauswahl, Active-State-Entfernung, Fokus, Pfeiltasten, Enter/Leertaste, Hover und Reduced Motion. Touch-Interaktion läuft zusätzlich im bestehenden Mobile-Projekt. Die Tastaturprüfung simuliert eine `visualViewport`-Höhe von 300 px; sie ersetzt keinen Test auf einem physischen Smartphone.

## Lokale Validierung

Die Prüfungen verwenden ausschließlich lokale Simulatoren und eine isolierte, flüchtige PostgreSQL-Datenbank in einem eigens gestarteten Docker-Container. Es wird keine lokale PostgreSQL-Instanz angelegt. Bestehende Anwendungscontainer und Produktivdienste werden nicht verändert; auf GitHub-CI wird nicht gewartet.

Ausgeführt werden die vorhandenen Skripte für ESLint, Nuxt/Vue-Typecheck, Vitest, relevante Playwright-Tests und Nuxt-Produktionsbuild über ihre lokalen Node-Einstiegspunkte. Der pnpm-Launcher benötigt in dieser Umgebung eine Schreibsperre außerhalb des Workspace; deshalb werden dieselben bereits installierten Programme direkt ausgeführt. Projektabhängigkeiten und Lockfiles bleiben unverändert; es wird keine UI-Bibliothek ergänzt. Backend-Prüfungen verwenden die bestehende virtuelle Umgebung, den vorgeschriebenen Pyright-Aufruf und `uv build`.

| Prüfung | Ergebnis am 2026-10-12 |
| --- | --- |
| Frontend ESLint | Erfolgreich. |
| Backend Ruff / Format | Erfolgreich; 104 Dateien bereits korrekt formatiert. |
| Nuxt-Typecheck, Vue-Test-Typecheck, Tool-Typecheck | Erfolgreich, Exit 0. |
| Backend Pyright 1.1.408 | 0 Fehler, 0 Warnungen. |
| Frontend Vitest | 32 Dateien, 285 Tests erfolgreich. |
| Backend Unit / Contract / lokale LLM-Simulatoren | 399 Tests erfolgreich. |
| Backend Attachment-/Referenz-/PDF-/Schema-Integration | 38 Tests erfolgreich in Docker-PostgreSQL. |
| Playwright WebSocket: Plus-Menü und Attachments | 46 erfolgreich, 14 absichtlich übersprungen; alle 16 neuen Bilder ohne Aktualisierung verglichen. |
| Playwright Demo: Plus-Menü, Chat-Composer, Layout, Autosize | 40 erfolgreich, 14 absichtlich übersprungen; bestehende Vergleichsbilder unverändert. |
| Nuxt-Produktionsbuild | Erfolgreich. |
| Backend-Produktionsbuild | Source-Distribution und Wheel erfolgreich gebaut. |

Die übersprungenen Browserfälle sind doppelte Geometrie-/Screenshot-Matrizen im Mobile-Projekt; die Touch-Interaktionen laufen dort trotzdem. Es wurde nicht auf CI gewartet. Der eigene flüchtige Docker-Testcontainer wurde nach den Prüfungen gestoppt und automatisch entfernt.

Bestehende Werkzeugmeldungen: Nuxt/Vue-Typecheck meldet das nicht auflösbare optionale Plugin `vue-router/volar/sfc-route-blocks`, endet aber mit Exit 0. Die Builds melden vorhandene Abhängigkeitswarnungen zu BigInt/es2019, `modelModifiers` und Kommentarannotationen. Es wurden keine Toolchain-/Abhängigkeitsrefactorings vorgenommen. Die visuelle Freigabe anhand der fehlenden Referenzbilder bleibt offen.
