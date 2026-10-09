# Löschdialog: Implementierung und Abnahme

## Aktuelle Finalisierung: 2026-10-09

**Technische Abnahme: PASS. Vollständige Referenz-/Datenschutzabnahme: BLOCKED.**
Die älteren Abschnitte unten dokumentieren frühere Stände; für den aktuellen
Auftrag sind die folgenden Ergebnisse maßgeblich.

### Tatsächliche GitHub-Abhängigkeiten und PR-Status

Die benötigten Änderungen sind auf `main` vorhanden: PR #18 als
`458c828315b2302fd2541679b0443817b7a9abb7`, PR #19 als
`019617581258dac1ed9f028638ee4f5f702ca973`. PR #20 wurde auf `main` umgestellt.

GitHub meldet PR #20 seit **2026-10-09, 09:06:55 UTC als MERGED**, durch
`p3t3r67x0`, Merge-Commit `d10a1d5a4a914a900eae24349aedf6a79bb15a2f`.
Dieser Merge erfolgte während der Prüfung extern. Die Finalisierungsrunde hat
keinen PR-Merge ausgelöst. Der aktuelle Auftrag verlangte ausdrücklich keinen
Merge und keine neue Merge-Freigabe wird aus früheren Integrationsnotizen abgeleitet.
Ein geschlossener PR kann nicht mehr Ready for Review werden; der separate
Berichts-Folge-PR bleibt Draft. Kein weiterer Merge ohne ausdrückliche Freigabe.

### Visueller Vergleich

**BLOCKED:** Der Auftraggeber meldet die Originalreferenz als verfügbar; in
dieser Sitzung fehlen weiterhin deren lokaler Dateipfad beziehungsweise die
tatsächliche Bildanlage. Der Pfad wurde abgefragt. Die überprüfte neuere lokale
ChatGPT-Abbildung zeigt Einstellungen und keinen Löschdialog. Sie wurde nicht
kopiert oder veröffentlicht und nicht als Löschdialogreferenz verwendet.

Die Implementierungsmaße aus der Tabelle unten sind im aktuellen Produktionsbuild
mit synthetischen Daten geprüft: 1701 × 863 Desktop-Viewport, 485 px Dialogbreite,
26 px Radius, 24 px Padding, zentrierte Position, neutrale 35-Prozent-Abdunklung,
24/30-px-Titel, 18/26-px-Beschreibung, rechte Pill-Buttons und weicher Schatten.
Mobile bei 390 × 844: 358 px Breite; auch 320 px und lange HTML-artige Namen
erzeugen keinen horizontalen Überlauf. Light/Dark und alle vier vorhandenen
synthetischen Dialog-Goldens bestehen. Diese Prüfung ersetzt keinen Originalvergleich.

### Mobile Sidebar: Ursache und behobene Abweichung

**PASS: keine von PR #20 verursachte Regression.** Der unveränderte Basisstand
`458c828` und PR #20 vor der Footer-Korrektur (`5b5b7d1`) wurden getrennt mit
ihren gesperrten Abhängigkeiten gebaut. Ihre beiden mobilen Produktionsaufnahmen
sind untereinander pixelgleich: **0 unterschiedliche Pixel** in beiden Themes.
Gegen die bestehenden Goldens unterscheiden sich jeweils **545 / 446 Pixel**.
Der Fehler besteht damit bereits im Basisstand.

Das minifizierte CSS rundet die dimensionslosen Zeilenhöhen auf `1.42857` und
`1.33333`. Dadurch entstehen andere Textpositionen/Rasterungen im Footer als bei
den exakten Entwicklungswerten. Commit `0e04099` verwendet für Avatar/Kontolabel
und Caption explizite zentrale Zeilenhöhen **20 / 16 px** bei den vorhandenen
Schriftgrößen **14 / 12 px**. Die vorhandene Darstellung bleibt erhalten.
**Keine Baseline, Assertion, Testauswahl oder Toleranz wurde geändert.**

Lokal bestehen danach alle 20 Dialogfälle und beide vormals fehlerhaften
Drawer-Goldens: **22/22**. Die vollständige Compose-Produktionssuite besteht
**111/111**. Die früheren beiden FAIL-Ergebnisse bleiben historische Befunde;
der neue Lauf belegt die Korrektur.

### Vollständige Tests

Geprüfter Laufzeitstand: `0e0409960f2a2414b8d49c2f5a959021e2c3b9c5`.
[CI 37908234299](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37908234299)
ist mit beiden Jobs `checks` und `compose-smoke` erfolgreich. Die Zahlen stammen
aus den Jobprotokollen. Der Berichts-Folgecommit verändert nur dieses Dokument.

| Prüfung | Ergebnis |
| --- | --- |
| Frontend-Unit | **PASS**, 108 Tests |
| Backend-Unit, Contracts und simulierte HTTP-Integration | **PASS**, 102 Tests |
| PostgreSQL-Integration / Migrationen | **PASS**, 3 Tests und Migration |
| Reguläre Desktop-/Mobile-Playwright-Suite | **PASS**, 111 Tests |
| RealTransport mit lokalem LLM-Simulator | **PASS**, 6 Browserfälle |
| Vollständige Playwright-/Screenshot-Suite über Compose/Caddy-Produktion | **PASS**, 111 Tests |
| Dialog/Drawer zusätzlich am isolierten lokalen Produktionsbuild | **PASS**, 22 Tests |
| Ruff, Formatprüfung und ESLint | **PASS** |
| Python-, Vue-, Test- und Tools-Typecheck | **PASS** |
| API-Drift | **PASS**, Verträge aktuell |
| Backend-Paket und Nuxt-Produktionsbuild | **PASS** |
| Docker-Smoke, Same-Origin-Routing und DB-Berechtigungen | **PASS** |
| Originalvergleich des Löschdialogs | **BLOCKED**, Referenzpfad fehlt |
| Manuelle Screenreader-/Notch-Geräte-Abnahme | **NOT TESTED** |
| Neue echte kostenpflichtige Provider-Aufrufe | **NOT TESTED**, für diese UI-Prüfung nicht erforderlich |

330 reguläre CI-Testausführungen und 111 zusätzliche Produktionsausführungen
werden getrennt ausgewiesen; die 22 lokalen Fälle sind zusätzliche Wiederholungen.
Mock-Tests bleiben erhalten. Die aktuelle Reproduktion umfasst zusätzlich
`make python-typecheck` und nach Start eines isolierten Mock-Compose-Stacks
`make test-e2e-production`. Alle Testdaten und Fixture-Zugangsdaten sind synthetisch.

### Datenschutz und verbleibende Einschränkungen

**BLOCKED, bestätigter Altbestand:** Der in
[HISTORIENBEREINIGUNG.md](ui-reference/HISTORIENBEREINIGUNG.md) beschriebene alte
private Referenz-Blob antwortet auch bei einer anonymen HTTP-HEAD-Prüfung weiterhin
mit **200**. Dabei wurden keine Bilddaten heruntergeladen. Die Bereinigung der
aktuellen Dateien ersetzt nicht den offenen GitHub-Support-Takedown des Altbestands.

Diese Runde hat keine privaten Originale committet, keine privaten Vergleichsbilder
veröffentlicht, keine History-Rewrites ausgeführt und keinen Support-Kontakt
versendet. Die Originalreferenz muss lokal benannt und bei identischer Auflösung
geprüft werden; ein abgeschlossener Support-Takedown benötigt einen eigenen Nachweis.
Die frühere Integrationsfreigabe bei offenem Originalvergleich ersetzt nicht die
Pflichtprüfungen des aktuellen Finalisierungsauftrags.

## Historischer Implementierungsbericht

Stand: 2026-10-09. Branch: `feat/delete-dialog-fidelity`.

## Bestand und Abhängigkeiten

Review-Basis ist der offene UI-PR #18 (`feat/chatgpt-ui-fidelity`), zuletzt geprüft
bei `526a706917ecf72026dfa9c2e75fb542c40958eb`. Die Dialogarbeit begann auf
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
Zwischenzeitlich erschien im GitHub-PR-Diff zusätzlich das bereits in PR #18
bereinigte `reference-reference-light.png`. Nach der externen Integration der
aktuellen Review-Basis zeigt der PR ausschließlich die elf Dialog-Dateien.
Die dabei übernommenen Abhängigkeits- und Referenzänderungen stammen aus der
parallelen Basisarbeit; die Dialogimplementierung blieb identisch.
Ein vorgeschlagener lokaler
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

**NOT TESTED: exakter Originalvergleich.** Für diesen Auftrag wurde kein
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
GitHub-CI-Lauf für `a9941e6c14c5965db317f63cefb8413c85c8d8c7` ist bestanden:
[Run 37901418428](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37901418428),
Jobs `checks` und `compose-smoke`. Er prüft die Hintergrund-Shortcut-Sperre,
die Hover-Kontrastkorrektur und den korrigierten Testablauf nach dem Theme-Reload:
Vor der Sidebar-Interaktion werden Hydrierung und tatsächlich gesetztes Theme
abgewartet. Die aktuellen [PR-20-Checks](https://github.com/p3t3r67x0/noris-ai-chat/pull/20/checks)
bleiben für spätere Branchänderungen maßgeblich. Der finale Produktionsbuild ist zusätzlich
lokal mit allen 20 Dialog-Browserfällen geprüft, einschließlich der beiden neuen
Kontrastfälle. Die reguläre Browser-Suite umfasst damit 111 Fälle.

- **PASS:** Nuxt-UI-MCP-Abfrage und Abgleich mit 4.11.3.
- **PASS:** insgesamt 85 Frontend-Unit-Tests, darunter neun neue Dialogfälle;
  zwei weitere Fälle stammen aus der parallelen synthetischen Referenzbereinigung.
- **PASS:** 38 Backend-Unit-/Contract-Tests; drei DB-Integrationstests separat.
- **PASS:** elf bestehende Prüfungen des Referenz-Bereinigungstools, synthetische Fixtures.
- **PASS:** 20 neue Playwright-Fälle auf dem Produktionsbuild, einschließlich
  vier Screenshot-Baselines, Desktop/Mobile und Light/Dark; unveränderte Toleranz.
- **PASS:** vollständige reguläre CI-Browser-Suite, 111 Fälle, sowie drei
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
- **FAIL, lokaler Dev-Testaufbau:** Ein zusätzlicher lokaler Lauf der zwei
  Kontrastfälle mit verlinktem Dependency-Verzeichnis erreichte bereits beim
  initialen Start `data-ready=true` nicht innerhalb der bestehenden Testfrist.
  Die reguläre CI besteht beide Fälle; die abschließende Wiederholung am lokalen
  Produktionsserver besteht ebenfalls (2/2). Keine Wartefrist wurde erhöht.
- **NOT TESTED:** Vergleich mit der nicht verfügbaren Löschdialog-Originalreferenz. Der Auftraggeber hat die Integration nach grünen aktuellen Funktions- und synthetischen Screenshot-Tests ausdrücklich freigegeben; dieser Originalvergleich bleibt offen.
- **NOT TESTED:** manuelle Screenreader-Abnahme und physische Geräte mit Notch.

Reproduktion mit den vorhandenen Repository-Befehlen: `make lint`,
`make typecheck`, `make test-unit`, `make test-e2e`, `make check-api`, `make build`.
Gezielt: `pnpm --dir frontend exec vitest run tests/unit/delete-dialog.spec.ts`
und `pnpm --dir frontend exec playwright test delete-dialog.spec.ts`.
Kein Noris-Key und keine echten LLM-Aufrufe sind für diese Tests erforderlich.

## Erweiterte Integrationsfreigabe (2026-10-09)

Der Auftraggeber hat ausdrücklich entschieden: „Nach grünen Tests integrieren; Originalvergleich bleibt offen“. Die fehlende Originalreferenz ist damit eine ausstehende manuelle Abnahme (**NOT TESTED**), kein eigenständig aufzuhebender Merge-Blocker. Vor der Integration müssen die aktuellen kombinierten Checks bestehen. Die frühere Draft-/Merge-Sperre in diesem Bericht beschreibt den Stand vor dieser Freigabe. Die Transport-/Modellinitialisierung aus PR #19 und die aktuellen Design-, Scroll- und Referenzänderungen aus PR #18 bleiben bei der Integration erhalten. Eine bestandene Pixel-Abnahme des fehlenden Originals wird weiterhin nicht behauptet.

Die kombinierte Basis enthält die aktuellen Versionen aus main sowie PR #19. Der normale Branch-Merge erhält dessen `initializeChatTransport()` und Modellinitialisierung. Der anschließende Diff zur Transportbasis betrifft weiterhin ausschließlich Dialog-Implementierung, Dialogtests, vier synthetische Baselines und dieses Dokument; die zusätzliche Freigabedokumentation verändert kein Laufzeitverhalten.

## Zusätzliche integrierte Produktionsprüfung

`make test-e2e-production` prüft die vollständige vorhandene UI-Suite über den frisch gebauten Compose-/Caddy-Produktionsstack. Assertions, Screenshot-Goldens und Toleranz bleiben identisch zum regulären Lauf. Die beiden früheren lokalen Drawer-Baselinefehler werden damit unabhängig von der lokalen verlinkten Entwicklungsumgebung erneut geprüft. Ergebnisse werden anhand der aktuellen `compose-smoke`-CI ausgewertet; dieses Dokument erklärt einen ausstehenden Lauf nicht als bestanden.

## Produktionsintegration: stabile Footer-Zeilenhöhen

Der zusätzliche Compose-Produktionslauf [37906351675](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37906351675) reproduziert die früheren Drawer-Abweichungen: 109 PASS / 2 FAIL, 545 beziehungsweise 446 Pixel. Der Trace belegt im minifizierten Stylesheet `--text-sm--line-height:1.42857` und `--text-xs--line-height:1.33333`. Die daraus berechneten Zeilenhöhen unterscheiden sich geringfügig vom Entwicklungs-CSS und ändern Textposition und Rasterung im zentrierten Footer.

Avatar, Kontolabel und Caption verwenden nun zentrale Schriftgrößen von 0.875rem beziehungsweise 0.75rem und explizite Zeilenhöhen von 1.25rem beziehungsweise 1rem. Die vier `--noris-account-*`-Tokens vermeiden die gerundeten dimensionslosen Quotienten und erhalten die Darstellung aus der bestehenden Baseline. Die Avatar-Klassenanbindung wurde über den offiziellen Nuxt-UI-MCP-Server (Avatar-Metadaten und API/Theme) sowie die installierte 4.11.3-Komponente geprüft. Keine Baseline, Assertion, Testauswahl oder Screenshot-Toleranz wird geändert. Neue vollständige Entwicklungs- und Produktions-CI ist für diesen Fix erforderlich; der vorherige Fehler bleibt als historischer Befund dokumentiert.
