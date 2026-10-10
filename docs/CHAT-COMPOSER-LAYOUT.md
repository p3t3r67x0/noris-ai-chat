# Chat-Layout und Composer-Abnahme

Basis: `main` bei `447d6f9`, Branch `fix/chat-composer-layout-fidelity`.

Der Composer verwendet weiterhin `UChatPrompt`, `UChatPromptSubmit` und das dynamische `USelectMenu`. Dessen vorhandene Header-, Body- und Footer-Slots stehen in einer gemeinsamen CSS-Grid-Zeile: Plus, schrumpfende Textarea, Modellwahl und Send/Stop. Aktionsbuttons haben feste quadratische Maße; die Modellwahl besitzt eine begrenzte, vom Namen unabhängige Breite. Es gibt keine absolute Aktionsleiste und kein Textarea-Padding zur Freihaltung darüberliegender Buttons.

Modellnamen bleiben einzeilig. Auf schmalen Viewports kürzt der Trigger den Namen mit Ellipsis; Menü und `title` enthalten den vollständigen Katalognamen. Der Menü-Pfeil steht als eigenes Flex-Element neben dem Text und kann ihn nicht überlagern. Provider-IDs, Katalog, Tastaturbedienung und Generierungssteuerung bleiben erhalten. Die vorhandene Autosize-Funktion wächst bis acht Zeilen beziehungsweise zum CSS-Limit `min(13rem, 30dvh, 30cqh)`; danach scrollt die Textarea. Die Containerhöhe berücksichtigt auch den durch die Bildschirmtastatur verkleinerten Workspace. Die Buttons bleiben auch bei mehrzeiligem Text auf derselben horizontalen Achse.

Die bestehenden Surface-, Text-, Border- und Fokus-Tokens gelten für beide Themes. Der Hinweistext steht oberhalb des Composers. Nachrichten und Composer besitzen dieselbe maximale Breite und sind im verbleibenden Hauptbereich zentriert. Die Sidebar und der Nachrichtenverlauf behalten ihre unabhängigen Scrollcontainer; Composer, VisualViewport-Anpassung und Scroll-Following verwenden die vorhandenen Komponenten und Composables. Eine CSS-Containerabfrage berücksichtigt die tatsächliche Workspacehöhe nach VisualViewport-Resizing: Unter 500 px wird der Begrüßungstext im leeren Chat ausgeblendet und der Composer unten angeordnet, damit auch ein langer Entwurf über der Bildschirmtastatur erreichbar bleibt.

## Lokale Referenzmessung

Die private Referenz liegt ausschließlich außerhalb des Repositorys unter `~/noris-references/chatgpt-layout.png`. Sie wird von keinem Browser-/CI-Test gelesen. Das Original misst 1920 × 975 Bildpixel. Maßvergleich und Modell-Baselines verwenden DPR 1; die ergänzenden mobilen Interaktionstests verwenden die Pixel-7-Emulation. Zoom oder DPR der ursprünglichen Aufnahme lassen sich aus der Bilddatei nicht ermitteln.

| Bereich | 1920 × 975 | 1701 × 863 |
| --- | ---: | ---: |
| Icon-Leiste | 68 px | ca. 60 px |
| Konversations-Sidebar | 376 px | ca. 333 px |
| Linke Navigation insgesamt | 444 px | ca. 393 px |
| Hauptbereich | 1476 px | ca. 1308 px |
| Chat-/Composer-Spalte | 1000 px | ca. 886 px |
| Einzeiliger Composer | 70 px | 70 px |

Die vorhandenen skalierbaren Breitentokens entsprechen diesen Maßen. Unter 1024 px ersetzt der vorhandene Drawer die Desktopnavigation. Unter 640 px ist der Composer 60 px hoch, die Aktionsbuttons bleiben mindestens 44 × 44 px. Mobile und Dark Mode sind überprüfte Noris-Zustände; das bereitgestellte Bild zeigt ausschließlich Desktop Light.

## Browser- und Datenschutzprüfung

`tests/e2e/composer-layout.spec.ts` prüft in beiden Themes alle angeforderten Viewports: 1920 × 975, 1701 × 863, 1440 × 900, 1280 × 800, 768 × 1024, 390 × 844 und 360 × 800. Geprüft werden Navigationsbreiten, Hauptbereich, identische Außenkanten von Verlauf und Composer, Zentrierung der Buttons, Fokus, Drawer, unabhängiges Sidebar-Scrolling und begrenztes Textarea-Wachstum mit Rückkehr zur ursprünglichen Höhe. Der lange Entwurf bleibt auch bei simulierten VisualViewport-Höhen von 360 und 250 px sichtbar und fokussiert.

Die synthetische Chatliste verwendet eindeutige, absteigende Aktivitätszeitstempel. Zuvor identische Zeitstempel machten ihre Reihenfolge vom produktiven ID-Tiebreaker abhängig und führten bereits auf der aktuellen Basis zu einer Abweichung von den älteren Goldens. Die Produktionssortierung bleibt erhalten; die Fixture zeigt wieder die beabsichtigte, deterministische Beispielreihenfolge.

`tests/llm/composer-layout.spec.ts` verwendet einen vollständig synthetischen Katalog mit `Gemma 4 31B`, `GPT-OSS 120B`, `GLM 5.3 Flash` und einem besonders langen Testnamen. Die Auswahl verändert weder Composergröße noch Position. Die tatsächlichen Provider-IDs der Simulator-Fixture bleiben unverändert. Send/Stop läuft ausschließlich über den bereits vorhandenen lokalen HTTP-Simulator. Die Tests erzeugen Light-/Dark-Baselines für Desktop und Mobile, Modellnamen, mehrzeilige Eingabe und Streaming. Die bestehende Vergleichstoleranz von 0,001 bleibt unverändert.

Die vorhandenen Browserfälle prüfen zusätzlich Markdown, Tabellen, Syntaxfarben, Kopieren, Varianten, Retry, Fokus, Scroll-Following, manuelles Pausieren, Wiederaufnahme und VisualViewport-Keyboard-Resizing. WebSocket-Tests verwenden eine separate temporäre PostgreSQL-Datenbank und den lokalen Provider-Simulator. Es werden keine kostenpflichtigen Provider aufgerufen.

Alle 33 bestehenden synthetischen Bildzustände wurden mit den bisherigen Goldens verglichen. Die 31 vom Composer betroffenen Baselines wurden nach Sichtprüfung aktualisiert; die beiden Drawer-Baselines bleiben erhalten. Hinzu kommen 24 geprüfte Modell-/Composer-Bilder. Geprüft wurden insbesondere Außenkanten, Abstände, Hinweisposition, Menü-Pfeil, Textumbruch, Fokus und Send/Stop. Die endgültigen Browserläufe vergleichen diese Bilder ohne Snapshot-Aktualisierung.

Vor Commit werden `git status --short`, `git diff --cached --name-only`, sämtliche vorgesehenen Textdateien und PNGs kontrolliert. Vor Push werden Original-Bytes, dekodierte Bildpixel und der bekannte historische Original-Blob gegen die erreichbaren Branch-Objekte geprüft. Neue Bilder stammen ausschließlich aus synthetischen Browserzuständen; die private Referenz, ihre Bilddaten und private Gesprächsinhalte werden nicht übernommen. Vorbestehende, mit der Referenz überlappende Titelbeispiele in Tests wurden durch neutrale synthetische Titel ersetzt. Historische generische technische Titelvorlagen sind kein neu übernommener Referenzinhalt; der produktive Titelmechanismus bleibt unverändert.

## Abnahme

Alle Prüfungen wurden lokal gegen die fertige Implementierung ausgeführt:

| Prüfung | Ergebnis |
| --- | --- |
| `make lint`, `make typecheck`, `make check-api`, `make build` | bestanden |
| `make test-unit` | 241 Backend-/Vertragstests und 224 Frontendtests bestanden |
| PostgreSQL-Integration | 30 Tests bestanden |
| Playwright UI/Mock | 167 bestanden, 14 doppelte mobile Matrixfälle übersprungen |
| Playwright HTTP/SSE | 49 bestanden, 5 doppelte mobile Matrixfälle übersprungen |
| Playwright WebSocket/PostgreSQL | 18 bestanden |

Die abschließenden Browserläufe verwenden denselben fertigen Nuxt-Produktionsbuild mit den vorhandenen Transport-Fixtures. Sie vergleichen die geprüften Baselines ohne Aktualisierung. Build- und Serverbefehle der CI bleiben unverändert. Die Kontrolle vor Commit umfasst 69 Dateien, darunter ausschließlich 55 synthetische PNGs; die Kontrolle der erreichbaren Branch-Historie wird vor Push wiederholt.
