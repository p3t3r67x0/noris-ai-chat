# Chat-Shell: Audit vom 17. Oktober 2026

Vor Implementierung erstellt. Ausgangspunkt: `main`, `b48ce93`, sauberer Arbeitsbaum;
Feature-Branch: `feat/chatgpt-shell-ui-fidelity`. Zeilenangaben beziehen sich auf
diesen Ausgangscommit. Keine AGENTS.md im Projekt oder seinen Eltern gefunden.

## Quellen und Referenzsicherheit

Das bereitgestellte PNG misst **1920 × 975 Bildpixel**, ohne DPI-/Zoom-Metadaten.
Ein Original-HTML wurde in dieser Sitzung nicht bereitgestellt. Die im Auftrag
als Markupwerte genannten **52 px Rail, 340 px Gesamtnavigation, 288 px Sidebar**
sind verbindliche Zielvorgaben, aber hier **nicht aus Markup verifiziert**.
1701 × 863 wird als CSS-Testviewport verwendet; eine 1:1-Abbildung des PNG auf
diesen Viewport ist widerlegt durch die unterschiedlichen Bildabmessungen.
Auch eine einheitliche Skalierung ist nicht nachgewiesen: Bildnavigation
444 / 340 = 1,306, Bildbreite 1920 / 1701 = 1,129.

| Merkmal | Quelle / Wert | Sicherheit |
| --- | --- | --- |
| PNG-Abmessungen | Pillow: 1920 × 975 | gemessen |
| Rail / Sidebar-Ende | sichtbare Kanten bei x≈68 / x≈444 | Bildmessung ±1 px |
| Composer | x≈680–1683, y≈409–479; ≈1003 × 70 | Bildmessung ±3 px |
| Begrüßung | sichtbare Glyphen y≈334–357; Mittelpunkt x≈1182 | Bildmessung ±3 px |
| Abstand Glyphen–Composer | ≈52 Bildpixel | Bildmessung; kein CSS-Linebox-Abstand |
| Chatzeilen | ≈48 Bildpixel Abstand | Bildmessung ±2 px |
| Schrift / Radius | ≈30 CSS-px / 31 CSS-px laut Auftrag | visuelle Schätzung |
| Composer bei 1701 | ≈888 × 62 CSS-px laut Auftrag | visuelle Schätzung, Ziel |
| Light-Flächen | häufigste RGB: Rail #f9f9f9, Sidebar/Canvas #fcfcfc, Composer #fff | gemessen mit Pillow |
| Primär-/Sekundärtext | #0d0d0d / #5d5d5d laut Auftrag | Zielvorgabe; Sekundärfarbe kein belegter Rasterwert |
| Dark / Mobile / Interaktion | im Bild nicht sichtbar | unbestätigte Referenzeigenschaften |

Das persönliche Original und fremdes HTML werden nicht versioniert. Vorher/
Nachher-Bilder verwenden ausschließlich synthetische Noris-Daten.

## Ist-Zustand und bestätigte Codebefunde

| Befund | Quelle im Ausgangscommit | Konsequenz |
| --- | --- | --- |
| Nuxt 4.6.1, Vue 3.5.43, Nuxt UI 4.11.3; kein Frontend-Versionsfeld | `frontend/package.json:1` | Installierte Komponenten weiterverwenden; README nennt teils ältere Versionen |
| Rail skaliert 56–68 px, Sidebar 272–376 px | `frontend/app/assets/css/main.css:12`, `:321` | 1701: ≈60,24 + 333,11 statt 52 + 288 |
| Composerbreite folgt Chatspalte (768–1000 px); Höhe 60–70 px | `frontend/app/assets/css/main.css:13`, `:16` | bei 1701 bereits ≈886 × 62; auf 1440 bleibt Breite bei 768 |
| Rail hat Home, Suche, Archiv und bestehendes Profil | `frontend/app/components/chat/ChatRail.vue:11` | Keine erfundenen Appbereiche ergänzen |
| Zentriertes 44-px-Buttonraster, 20-px-Icons vorhanden | `frontend/app/assets/css/main.css:108` | erhalten |
| Header mit Noris AI, Suche, Toggle, Neuer Chat vorhanden | `frontend/app/components/chat/ChatSidebar.vue:171` | Geometrie vereinheitlichen, Such-/Togglebeziehungen ergänzen |
| USidebar / Slideover, eigener Body-Scrollcontainer | `frontend/app/components/chat/ChatSidebar.vue:160` | keine neue Drawer- oder Scrollverwaltung |
| Datumsgruppen statt „Letzte“, 48-px-Zeilen + 2-px-Gap | `frontend/app/components/chat/ChatSidebar.vue:189`, `frontend/app/assets/css/main.css:295` | lokale Darstellung zu Letzte bündeln; Pins separat erhalten |
| Aktionen bereits bei Hover/Fokus, Touch dauerhaft; Portal/Fokusrückgabe vorhanden | `frontend/app/assets/css/main.css:300`, `:309`; `frontend/app/components/chat/ChatSidebar.vue:69` | bestehendes UDropdownMenu erhalten |
| ConversationTitle passt generierte Titel durch DOM-Messung an, kein Marquee | `frontend/app/components/chat/ConversationTitle.vue:12` | keine neue Animation nötig |
| New Chat wählt vorbereiteten Chat oder null, erzeugt keinen Datensatz | `frontend/app/composables/useChat.ts:195` | Lifecycle unverändert lassen |
| Ein ChatComposer im Dock, Begrüßung direkt davor | `frontend/app/components/chat/ChatWorkspace.vue:221` | Einheit positionieren ohne Remount |
| Empty State wird an Unterkante gedrückt | `frontend/app/assets/css/main.css:172` | flexibler Abstand ober-/unterhalb für erhöhte Mitte fehlt |
| Native Textarea mit unsichtbarem Messfeld; tatsächliche Toolbarbreite, 560-px-Schwelle | `frontend/app/composables/useComposerAutosize.ts:13`, `:39`, `:63` | Messlogik weiterverwenden |
| Compact/Expanded/Maximized, Uploadheader, Slash, Diktat, Send/Stop vorhanden | `frontend/app/components/chat/ChatComposer.vue:132`, `:145`, `:186`, `:203` | keine zweite Editorinstanz |
| Uploads per bestehendem Backend, MIME-Limits, Progress, Reload und Retry | `frontend/app/composables/useChatAttachments.ts:30`, `:65`, `:93` | keine API-/Backendänderung nötig |
| Diktat optional, verwirft späte Ergebnisse | `frontend/app/composables/useComposerDictation.ts:18` | keine Echtzeit-Voice-Attrappe |
| Getrennte Pin-/Normal-Cursor und Fenster bis 500; Versionsguard | `frontend/app/composables/useChatBackend.ts:81`, `:247`, `:279`, `:545` | keine Pagination oder Datensynchronisation ersetzen |
| Desktoppräferenz; mobile Änderungen nicht persistiert | `frontend/app/composables/useSidebarPreference.ts:5` | unverändert verwenden |
| VisualViewport resize/scroll, Safe-Area im CSS | `frontend/app/composables/useChatViewport.ts:3`; `frontend/app/assets/css/main.css:251` | bestehende Tastaturanpassung erhalten |
| Keine Projektroute oder Projektressource in App/API | `frontend/app/pages/index.vue:1`; `docs/api/openapi.json:1` (Suche nach Projektressourcen negativ) | Projekte bewusst weglassen |

## Dokumentations- und Testaudit

Gelesen: README, ADAPTIVE-COMPOSER, CHAT-COMPOSER-LAYOUT, NEW-CHAT-LIFECYCLE,
COMPOSER-PLUS-MENU, sidebar/README, DESIGN-TOKENS, composer/IMPLEMENTATION,
REFERENCE-ANALYSIS und RESPONSIVE-SPECIFICATION. Ältere Berichte beschreiben
68/376 px und teilweise einen unten platzierten Empty State; dieser Auftrag
ersetzt diese Layoutvorgaben. Bestehende Screenshots liegen unter
`frontend/tests/{e2e,llm,websocket}/__screenshots__` und `docs/ui-reference`.

`frontend/playwright.config.ts:16` definiert Desktop/Pixel-7-Projekte und
unverändert 0,001 maximale Pixeldifferenz. Die Suite baut eine lokale
Produktionsfixture, startet API/Nuxt und nutzt synthetische Daten.
`frontend/tests/e2e/composer-layout.spec.ts:37`, `:55` und
`reference-desktop.spec.ts:22` prüfen noch die bisherige Geometrie. Diese
Erwartungswerte müssen fachlich aktualisiert werden; Toleranzen bleiben gleich.
Vitest (`frontend/vitest.config.ts:10`) deckt die bestehenden Composables und
Komponenten ab. WebSockettests erfordern eine migrierte Wegwerfdatenbank
(`frontend/playwright.websocket.config.ts:4`). CI: `.github/workflows/ci.yml:67`.

Umgebung: Node 22.22.1 liegt knapp unter engines >=22.22.3. pnpm meldet eine
schreibgeschützte Manager-Store-Sperre, installierte Node-Entrypoints sind vorhanden.
Lokale Listener benötigen Sandbox-Freigabe; der Nuxt-Start wird so geprüft.

## Fehlende Funktionalität und Implementierungsstrategie

1. Zentrale feste Desktopnavigation 52/288/340, semantische Zeilenhöhe und
   Abstände; Composer 888/62 mit mindestens 44-px-Controls. Bestehende Tokens
   erhalten bzw. genau einmal ersetzen, keine Skalierungstransforms.
2. Vorhandenen Header und Rail ausrichten; reale Ziele und ProfileMenu erhalten.
3. Sichtbare Datumsgruppen ausschließlich in der Sidebar zu „Letzte“ bündeln,
   vorhandene Comparatoren und eigene Pin-Gruppe erhalten. Auf-/Zuklappen als
   lokaler UI-Zustand; keine zweite Persistenz. Paging mit der Liste einklappen.
4. Begrüßung und vorhandenen Dock als Einheit oberhalb der Mitte positionieren.
   Wachsende leere Entwürfe behalten eine stabile Unterkante; aktive Timeline
   bleibt im bestehenden Flex-Scrollbereich.
5. Themefarben zentral, Active von Hover unterscheiden, ARIA, Tooltip und
   Tastaturbeziehungen ergänzen. Mobile/Keyboard über bestehende Composables.
6. Reproduzierbare Light-/Dark-Matrix, DOMRect-JSON und synthetisches
   before/after/diff. Kein Pixelgleichheitsanspruch gegenüber der privaten Quelle.

## Risiken und Teststrategie

- Geänderte Navigation zentriert sämtliche Inhalte neu: betroffene Goldens nach
  Browserprüfung aktualisieren; keine Tests löschen und keine Toleranzen lockern.
- Empty-State-Wachstum darf den Dock nicht nach unten bewegen; DOM-Identität,
  Fokus, Draft und Anhangverknüpfung beim ersten Senden ausdrücklich prüfen.
- Lange Modellnamen/Reasoning und mobile Touchbuttons begrenzen Eingabebreite:
  vorhandene reale Breitenmessung und Maximalhöhe beibehalten.
- Keine neuen Backendfunktionen; Serverpagination und Versionen bleiben
  autoritativ. Bestehende Unit-/WebSocketfälle für Reconnect, Titel, Uploads
  und New Chat ausführen, soweit die isolierte Infrastruktur verfügbar ist.
- Viewports 1701×863, 1440×900, 1280×800, 1024×768, 768×1024, 390×844 in
  beiden Themes; zusätzlich vorhandene 1920-/360-/320-Prüfungen erhalten.
- ESLint, beide Typechecks, vollständiges Vitest, Production Build und
  vorhandene Playwrights tatsächlich ausführen. Umgebungsfehler separat
  dokumentieren; API-Drift nur bei geänderten Verträgen erforderlich.
- WCAG-relevante Tastatur-, Focus-, Touch-, Reduced-Motion- und Landmarkchecks
  automatisieren; reale OS-Tastatur und Assistenztechnik bleiben manuelle Abnahme.
