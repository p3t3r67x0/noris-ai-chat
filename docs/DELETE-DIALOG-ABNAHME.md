# Löschdialog: Implementierung und Abnahme

Stand: 2026-10-09. Branch: `feat/delete-dialog-fidelity`.

## Bestand und Abhängigkeiten

Review-Basis ist der offene UI-PR #18 (`feat/chatgpt-ui-fidelity`), zuletzt geprüft
bei `b9cf41c54c6b1ed4b8379ff860bfd3c1ce214326`. Die Dialogarbeit begann auf
`6a81a48a272d919afd894654f26d50751b3fc5e3`. Während der Abnahme wurde der
Dialog-Branch extern aktualisiert und übernahm die bereinigten Referenz-Fixtures
samt synthetischem Golden aus PR #18. Die Dialogimplementierung blieb dabei
identisch. Dieser UI-Stand enthält das bestehende
Sidebar-Kontextmenü, Archiv und die lokale Konversationsverwaltung und basiert
auf PR #17, dahinter #16, #15 und #14. PR #19 mit der LLM-Anbindung ist unabhängig.
Dieser Branch verändert weder Provider noch Nachrichtenmodell, Persistenzformat,
Composer, Scroll-System oder globale Design-Tokens. Kein Merge auf `main`.

Geänderte Dateien: `DeleteConversationDialog.vue` enthält Modal-UX und ausschließlich
dialogbezogene Styles; `ChatSidebar.vue` setzt Ziel und Rückgabefokus;
`ChatWorkspace.vue` reicht die bestehende Löschaktion durch und sperrt seine
Hintergrund-Shortcuts während des Dialogs. `tests/unit/delete-dialog.spec.ts` und
`tests/e2e/delete-dialog.spec.ts` ergänzen die Abnahme. Im vorhandenen
`chat-fidelity.spec.ts` ändert sich nur der Buttonname von „Löschen“ zu „Chat löschen“.
Hinzu kommen vier synthetische PNG-Baselines und dieses Dokument, insgesamt elf Dateien.
Im GitHub-PR-Diff erscheint zusätzlich das bereits in PR #18 bereinigte
`reference-reference-light.png`; sein Inhalt ist identisch mit der Datei in der
aktuellen Review-Basis. Dieses Bild stammt aus der parallelen Referenzbereinigung,
nicht aus dem fehlenden Löschdialog-Original. Ein vorgeschlagener lokaler
Branch-Merge wurde von der automatischen Freigabeprüfung unter Bezug auf
„Keine eigenmächtigen Merges“ abgelehnt und nicht ausgeführt.

Vorher öffnete `ChatSidebar` ein generisches `UModal`, zeigte den Chatnamen in
einem separaten Body und emittierte `delete`. `ChatWorkspace` leitete das Ereignis
an `chat.remove(id)` weiter. Das synchrone Vue-Ereignis konnte kein Löschresultat
an den Dialog zurückgeben.

Jetzt kapselt `DeleteConversationDialog.vue` genau dieses Nuxt-UI-Modal.
`ChatSidebar` verwaltet weiterhin das ausgewählte Conversation-Objekt und den
Open-State. Der interne Anschluss wechselt von `@delete` zum Callback-Prop
`removeConversation: (id: string) => void | Promise<void>`; `ChatWorkspace` reicht
dieselbe bestehende Aktion `chat.remove` durch. Es gibt keinen zweiten Store und
keine zweite Modal-Infrastruktur. Bei einer späteren asynchronen Löschaktion wird
deren Promise abgewartet; bei einem Fehler bleibt der Dialog offen.

**Mögliche Merge-Konflikte:** ausschließlich die Dialog-/Trigger-Zeilen in
`ChatSidebar.vue` und die Sidebar-Bindung in `ChatWorkspace.vue`. Beim Zusammenführen
mit PR #19 dessen Transport-/Modellinitialisierung erhalten und lediglich
`@delete="chat.remove"` durch `:remove-conversation="chat.remove"` ersetzen.

## Nuxt UI und Accessibility

Verwendet werden `UModal` und `UButton` aus der vorhandenen Version **4.11.3**.
Der offizielle [Nuxt-UI-MCP-Server](https://ui.nuxt.com/docs/getting-started/ai/mcp)
wurde am 2026-10-09 per HTTP-MCP initialisiert; `get-component-metadata(Modal)`
und `get-component(Modal, usage/theme)` wurden erfolgreich abgerufen.
Der Rückgabevertrag wurde zusätzlich mit den installierten Komponentenquellen
und TypeScript-Typen abgeglichen.

Verifiziert: `v-model:open`/`update:open`, Portal, Overlay, Transition,
`dismissible`, `content` mit `onOpenAutoFocus`/`onCloseAutoFocus`, Footer-`close`,
Close-Slot innerhalb des vorhandenen `DialogClose` und die Slot-Class-Funktionen
von `ui`. Die Beschreibung wird als Text interpoliert. Nuxt UI erzeugt `role=dialog`
und die Titel-/Beschreibungs-IDs; das von dieser Version nicht automatisch
ausgegebene `aria-modal=true` wird am Content ergänzt.

Initialfokus: **Abbrechen**. Reka/Nuxt UI übernimmt Fokusfalle, Tab/Shift+Tab,
Escape, Outside Click und Sperre des Hintergrunds. Kein globaler Enter-Handler
für die Löschung. Die bestehenden Workspace-Shortcuts für neuen Chat/Suche
pausieren während dieses Dialogs, damit sie den gesperrten Hintergrund nicht
verändern. X verwendet den Namen **Dialog schließen** und weiterhin den
Nuxt-UI-Close-Vertrag. Nach Abbruch kehrt der Fokus zum ursprünglichen Menübutton
zurück, sofern er noch vorhanden und nicht inert ist; ansonsten zu `#chat-main`.
Das betrifft besonders geschlossene mobile Drawer und gelöschte/archivierte Zeilen.

Während einer ausstehenden Löschung sind die Buttons deaktiviert, der
Bestätigungsbutton zeigt seinen Nuxt-UI-Ladezustand und Escape/Outside Click sind
gesperrt. Ein synchroner Guard verhindert doppelte Aufrufe. Fehler erscheinen als
generisches `role=alert` ohne interne Fehlerdetails; Retry bleibt möglich.

## Layout und visuelle Referenz

**BLOCKED: exakter Originalvergleich.** Für diesen Auftrag wurde kein
Löschdialog-Screenshot mit 1701 × 863 Pixeln angehängt oder als Dateipfad benannt.
Die vorhandene lokale Referenz zeigt eine andere allgemeine Chatansicht bei
1920 × 975 Pixeln ohne Löschdialog. Sie wurde nicht kopiert oder veröffentlicht.
Die Werte unten stammen aus den schriftlichen Vorgaben, nicht aus behaupteten
Messungen des fehlenden Originals. Pixel-Abweichungen zu dessen Overlay, Schatten,
Farben, Rundungen und Typografie sind deshalb noch nicht quantifizierbar.

| Eigenschaft | Umsetzung |
| --- | --- |
| Desktop-Viewport | 1701 × 863 CSS-Pixel, Screenshot in identischer Auflösung |
| Desktopbreite | 485 px |
| Mobile-Viewport / Breite | 390 × 844 / 358 px |
| Position | horizontal und vertikal zentriert |
| Außenabstand | mindestens 16 px, zusätzliche Safe-Area-Abstände |
| Padding / Radius | 24 px / 26 px |
| Höhe | natürliche Inhaltshöhe, kein `min-height` |
| Synthetischer Baseline-Chatname | Desktop 238 px hoch, Mobile 264 px hoch |
| Titel | 24 px, 30 px Zeilenhöhe, Gewicht 600 |
| Beschreibung | 18 px, 26 px Zeilenhöhe, `overflow-wrap:anywhere` |
| Abstand Titel → Beschreibung | 14 px |
| Abstand Beschreibung → Footer | 24 px |
| Buttons | mindestens 44 px hoch, 14 px Text, Pill-Radius, 8 px Abstand |
| Schatten | `0 8px 32px #00000014`, kein Rahmen |
| Overlay | neutrales Schwarz mit 35 % Deckkraft, keine Unschärfe |
| Stacking | Overlay 60, Dialog 70, Portal über dem gesamten Workspace |
| Light | weiße Fläche; Abbrechen `#f4f4f4`; Löschen `#fce8e8` / `#c52222`; Hover `#fae0e0` |
| Dark | Fläche `#303030`; Abbrechen `#3d3d3d`; Löschen `#512c2c` / `#ffaaaa` |

Die roten Textfarben wurden für lesbaren Kontrast gewählt. Hover und Active
werden zusätzlich im echten Browser in beiden Themes auf mindestens 4,5:1
Textkontrast geprüft, einschließlich des Active-Brightness-Filters. Der helle
Hoverton ist deshalb `#fae0e0`. Alle zusätzlichen
Farbtokens gelten ausschließlich für `.delete-dialog`. Vorhandene zentrale
Text-/Border-Tokens werden weiterverwendet. Die Struktur bleibt in beiden Themes
gleich. Footer-Buttons dürfen auf sehr kleinen Viewports umbrechen. Bewegungen
werden bei `prefers-reduced-motion` weggelassen.

Vier neue, ausschließlich synthetische Baselines liegen unter
`frontend/tests/e2e/__screenshots__/linux/{desktop,mobile}/delete-dialog-{light,dark}.png`.
Sie zeigen bewusst den sichtbaren Tastaturfokus auf Abbrechen. Bestehende
Screenshot-Baselines und die Toleranz von 0,001 bleiben unverändert.

## Lösch- und Persistenzvertrag

`chat.remove` bleibt unverändert: Es stoppt gegebenenfalls die Generierung dieser
Unterhaltung, entfernt nur deren Nachrichten/Entwurf, bereinigt deren Branch-Verweise
und ruft `conversations.remove` auf. Beim Löschen der aktiven Unterhaltung wird
`activeId=null`; eine inaktive Löschung erhält die bisherige aktive ID.
Abbrechen verändert weder Auswahl, Verlauf noch Entwürfe.

Erfolg bedeutet das definierte Ergebnis der bestehenden lokalen Store-Aktion.
Der bisherige debouncte LocalStorage-Writer meldet Speichermangel separat über
`storageWarning`; er liefert kein Promise an `chat.remove`. Der Dialog behauptet
daher keine neue transaktionale Zusicherung für Datenträgerfehler. Ein künftig
persistenter API-Callback muss bei Fehler ablehnen, damit die vorhandene
Dialog-Fehlerbehandlung greift.

## Prüfstatus

Unit-Tests prüfen die Dialog-Anwendungsgrenze mit UI-Stubs; Playwright prüft die
tatsächlich installierten Nuxt-UI-Komponenten. Der vollständige reguläre
GitHub-CI-Lauf für `2767771` ist bestanden:
[Run 37897054297](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37897054297),
Jobs `checks` und `compose-smoke`. Nach der abschließenden Ergänzung der
Hintergrund-Shortcut-Sperre sind die aktuellen [PR-20-Checks](https://github.com/p3t3r67x0/noris-ai-chat/pull/20/checks)
für den finalen Branchstand maßgeblich. Der finale Produktionsbuild ist zusätzlich
lokal mit allen 20 Dialog-Browserfällen geprüft, einschließlich der beiden neuen
Kontrastfälle. Die reguläre Browser-Suite umfasst damit 111 Fälle.

- **PASS:** Nuxt-UI-MCP-Abfrage und Abgleich mit 4.11.3.
- **PASS:** 83 Frontend-Unit-Tests, darunter neun neue Dialogfälle.
- **PASS:** auf dem aktualisierten Branch insgesamt 85 Frontend-Unit-Tests;
  zwei weitere Fälle stammen aus der parallelen synthetischen Referenzbereinigung.
- **PASS:** 38 Backend-Unit-/Contract-Tests; drei DB-Integrationstests separat.
- **PASS:** elf bestehende Prüfungen des Referenz-Bereinigungstools, synthetische Fixtures.
- **PASS:** 20 neue Playwright-Fälle auf dem Produktionsbuild, einschließlich
  vier Screenshot-Baselines, Desktop/Mobile und Light/Dark; unveränderte Toleranz.
- **PASS:** vollständige reguläre CI-Browser-Suite, 109 Fälle, sowie drei
  PostgreSQL-Integrationstests, Migrationen und Docker-Smoke im genannten Lauf.
- **PASS:** Frontend-ESLint, strenge Vue-/Test-Typprüfung, Backend-Ruff,
  Tools-Typecheck, API-Drift-Check, Produktionsbuild und Compose-Konfigurationsprüfung.
- **FAIL, bestehende Produktions-Baselineabweichung:** Die zusätzliche lokale
  vollständige Browser-Suite gegen den Produktionsbuild ergibt **107 PASS / 2 FAIL**.
  Betroffen sind ausschließlich `reference mobile drawer light/dark`, mit
  545 beziehungsweise 446 abweichenden Pixeln an Textkanten im Sidebar-Footer.
  Beide Fehler wurden mit denselben Pixelzahlen auf dem unveränderten PR-18-Stand
  `6a81a48` als Produktionsbuild reproduziert. Die neuen Dialog-Screenshots bestehen.
  Es wurden weder Sidebar-Styles noch die bestehenden Baselines/Toleranzen geändert.
  Der reguläre CI-Testmodus verwendet weiterhin den vorhandenen Nuxt-Dev-Server;
  dessen Ergebnis wird separat ausgewiesen.
- **BLOCKED:** Vergleich mit der nicht verfügbaren Löschdialog-Originalreferenz.
- **NOT TESTED:** manuelle Screenreader-Abnahme und physische Geräte mit Notch.

Reproduktion mit den vorhandenen Repository-Befehlen: `make lint`,
`make typecheck`, `make test-unit`, `make test-e2e`, `make check-api`, `make build`.
Gezielt: `pnpm --dir frontend exec vitest run tests/unit/delete-dialog.spec.ts`
und `pnpm --dir frontend exec playwright test delete-dialog.spec.ts`.
Kein Noris-Key und keine echten LLM-Aufrufe sind für diese Tests erforderlich.
