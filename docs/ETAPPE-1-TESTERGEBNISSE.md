# Etappe 1: Testnachweise

Stand: 2026-10-09. Die Implementierung beginnt mit `feat/chat-shell` auf dem gemergten Etappe-0-Stand `2d5e5458da190c9439663749a4a74dddd53fcb2e`. Ergebnisse werden erst nach tatsächlicher Ausführung ergänzt.

## Umgebung

Der lokale Git-Metadatenbereich ist für den Agenten schreibgeschützt. Veröffentlichung und Remote-Prüfungen verwenden die autorisierte GitHub-Anbindung; ein isolierter Git-Checkout dient zur Prüfung der Historie. Die Quellen werden weiterhin im bestehenden Workspace bearbeitet.

`npm view @nuxt/ui` konnte die Registry wegen `ENOTFOUND registry.npmjs.org` nicht erreichen. Nuxt UI 4.11.3 und seine APIs wurden anhand des offiziellen, versionierten GitHub-Releases und Quellcodes verifiziert. Die normale Lockfile-Auflösung erfolgt einmalig in GitHub Actions. Der dafür angelegte temporäre Workflow wird vor dem fertigen Shell-PR entfernt.

## PR 1: Shell

**Bestanden:** [CI 37875571609](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37875571609) auf `ad19dcb`: ESLint, striktes TypeScript/Pyright, API-Drift, 18 Frontend-Unit-, 38 Backend-Unit-/Contract-, 3 PostgreSQL-Integrations- und 14 Playwright-Tests. Nuxt-Produktionsbuild, Backend-Paketbuild, Compose-Validierung und frischer Compose-Smoke-Test ebenfalls erfolgreich. PR: [#14](https://github.com/p3t3r67x0/noris-ai-chat/pull/14).

Die acht Shell-Browserfälle ergänzen die sechs erhaltenen Foundation-Fälle. Erste Läufe erkannten frühe Klicks vor Hydration und einen vom mobilen Drawer überlagerten Archivdialog. Die Korrekturen sichern den Startzustand und schließen den Drawer vor Dialogen. Ein aus dem Trace extrahierter Desktop-Screenshot wurde visuell geprüft.

Die anfängliche lokale Paketsperre ist inzwischen aufgehoben: Nuxt UI, Markdown und Shiki sind nun lokal verfügbar. Frühere BLOCKED-Ergebnisse werden durch neue tatsächliche Läufe ersetzt, nicht rückwirkend als erfolgreich bezeichnet.

## PR 2: Composer und Transport

**Bestanden:** [CI 37876762996](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37876762996) auf `8674302`: ESLint, striktes TypeScript/Pyright, API-Drift, 43 Frontend-Unit-, 38 Backend-Unit-/Contract-, 3 PostgreSQL-Integrations- und 22 Playwright-Tests ohne Retry. Beide Produktionsbuilds, Compose-Validierung und frischer Compose-Smoke-Test bestanden. PR: [#15](https://github.com/p3t3r67x0/noris-ai-chat/pull/15). Lokal sind ESLint, striktes Nuxt-/Vue-TypeScript, Vitest und Nuxt-Produktionsbuild ebenfalls erfolgreich.

Browser-Traces zeigten einen Entwicklungs-Reload beim ersten dynamischen Shiki-Import; die gezielte Voroptimierung verhindert diesen Verlust. Der kurze Retry-Zustand wird mit der kontrollierten Browser-Uhr deterministisch geprüft.

Lokales Playwright: **BLOCKED**, da der Sandbox-Prozess nicht an `127.0.0.1:8000` binden kann. Lokale PostgreSQL-Integration: **BLOCKED**, da keine separate `NORIS_TEST_DATABASE_URL` mit `_test` bereitgestellt ist; die drei Fixtures brechen ohne Datenbankmutation ab. Die CI führt beide Prüfungen mit eigener Testdatenbank aus.

## PR 3: Verzweigungen und Entwürfe

**Bestanden:** [CI 37877634130](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37877634130) auf `74b6478`: ESLint, striktes TypeScript/Pyright, API-Drift, 60 Frontend-Unit-, 38 Backend-Unit-/Contract-, 3 PostgreSQL-Integrations- und 28 Playwright-Tests. Beide Produktionsbuilds, Compose-Validierung und frischer Compose-Smoke-Test bestanden. PR: [#16](https://github.com/p3t3r67x0/noris-ai-chat/pull/16).

Zusätzliche Unit-Fälle prüfen unveränderliches Editieren, Transporthistorien, Isolation, alte Fortsetzungen, Entwürfe, Abbruch beim Reload und beschädigte, zyklische oder fremde Parent-Referenzen. Drei Browserfälle laufen auf beiden Viewports. Der erste Lauf erkannte einen Test, der auf Desktop den nur bei geschlossener Sidebar sichtbaren Header-Button suchte; er bedient jetzt zuerst den sichtbaren Sidebar-Schalter.

## PR 4: UX und visuelle Nachweise

PR: [#17](https://github.com/p3t3r67x0/noris-ai-chat/pull/17), abhängig von PR 3. Lokal bestanden: 66 Frontend-Unit-Tests, 38 Backend-Unit-/Contract-Tests, ESLint, Ruff/Format, striktes Nuxt-/Vue-TypeScript, Pyright (0 Fehler), API-Drift und Nuxt-Produktionsbuild. Pyright lokal 1.1.409; die CI verwendet die bestehende gepinnte Version 1.1.408. Lokale Browser-/DB-Sperren bleiben wie oben dokumentiert.

Der erste Remote-Lauf prüfte bereits Send-Anker, Fokus, Shortcuts und Gesprächspositionen. Er erkannte eine nachlaufende Scroll-Aktualisierung bei der kontrollierten Uhr; der Post-Render-Watch ergänzt jetzt den ResizeObserver. Außerdem wurde eine Messung im Hintergrund eines geöffneten mobilen Drawers auf einen stabilen DOM-Locator umgestellt. Vier zunächst fehlende Referenzbilder führten bewusst zu fehlgeschlagenen Visual-Tests; sie wurden erzeugt und visuell geprüft. Der abschließende Lauf wird nach tatsächlicher Ausführung ergänzt.

**Zwischenstand:** [CI 37878303592](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37878303592) auf `d6fd1c9` bestand 38 von 40 Playwright-Fällen einschließlich aller vier Referenzvergleiche. Die beiden Scrollfälle bestanden ihre Positions-/Follow-/Lesepause-Assertions, suchten aber erst nach Ende des zeitgesteuerten Mocks den Stop-Button. Das Zeitfenster wurde auf 7,55 s begrenzt und der Streaming-Zustand vor Stop explizit geprüft. Kein Test wurde deaktiviert.

**PASS, nachträglich verifiziert:** [CI37879178881](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37879178881) auf `2d258f1` besteht66 Frontend-,38 Backend-,3 PostgreSQL- und40 Playwright-Fälle, alle bestehenden Screenshotvergleiche, Typen/Lint/API, beide Builds, Compose-Validierung und Smoke. Auch der Push-Lauf37879175457 ist grün. Die aktuellen acht Browser-Artefakte wurden geprüft. Damit sind die beiden früheren Stop-Timing-Fälle und der geänderte Kontrast tatsächlich verifiziert; die historischen Zwischenstände bleiben oben nachvollziehbar. Die nachgereichte Referenztreue wird separat in PR18 geprüft.

Ein zusätzlicher lokaler Chromium-Start ohne Serverport war ebenfalls **BLOCKED** (`sandbox_host_linux`, `Operation not permitted`). Auch ein Unix-Socket-Server darf hier nicht binden (`EPERM`). Diese alternativen Versuche ändern keine Anwendungskonfiguration und liefern keinen erfolgreichen Browsernachweis.

## Screenshots

| Zustand | Desktop | Mobile |
| --- | --- | --- |
| Light, leer | [Referenz](../frontend/tests/e2e/__screenshots__/linux/desktop/workspace-light.png) | [Referenz](../frontend/tests/e2e/__screenshots__/linux/mobile/workspace-light.png) |
| Dark, leer | [Referenz](../frontend/tests/e2e/__screenshots__/linux/desktop/workspace-dark.png) | [Referenz](../frontend/tests/e2e/__screenshots__/linux/mobile/workspace-dark.png) |
| Aktives Gespräch | [Screenshot](screenshots/etappe-1/desktop-active.png) | [Screenshot](screenshots/etappe-1/mobile-active.png) |
| Laufender Stream | [Screenshot](screenshots/etappe-1/desktop-streaming.png) | [Screenshot](screenshots/etappe-1/mobile-streaming.png) |

Die Referenzbilder werden unter Linux mit gepinntem Chromium erzeugt. Die Browser-Uhr hält den Gruppierungstag konstant. Caret und Animationen sind für den Vergleich ausgeblendet. Die mobile Emulation prüft 412 × 839 CSS-Pixel; Desktop 1280 × 720. Dokumentationsbilder sind dauerhafte Repo-Artefakte, Reports/Traces bleiben zusätzlich sieben Tage in Actions verfügbar.

## Grenzen und Abnahme

- Mock-Antworten und lokale Browser-Persistenz; keine echten Provider, Benutzerkonten, Dateiübertragung oder serverseitige Chat-Speicherung.
- Ein aktiver Stream pro Workspace. Entwürfe anderer Gespräche bleiben währenddessen bearbeitbar; inkompatible Generierungen sind gesperrt.
- Gleichzeitige Änderungen in mehreren Tabs stoppen weitere lokale Schreibvorgänge und zeigen einen Reload-Hinweis. Keine automatische Zusammenführung.
- Die automatische Prüfung verwendet Chromium auf Desktop und einem mobilen Viewport. Eine verkleinerte Visual-Viewport-Höhe prüft den Composer; reale iOS-/Android-Tastaturen, VoiceOver/TalkBack und weitere Browserengines benötigen manuelle Abnahme.
- Scrollpositionen überleben Gesprächswechsel innerhalb des Workspace; ein Reload öffnet den Verlauf am Ende.
- Etappe 2 wurde nicht begonnen. Die vier PRs sind in Reihenfolge zu prüfen; Merge nur durch den Repository-Verantwortlichen.


## Referenz-Folge-PR #18

[PR #18](https://github.com/p3t3r67x0/noris-ai-chat/pull/18), `feat/chatgpt-ui-fidelity`, Basis `feat/chat-ux-polish`. Die ursprünglichen vier PRs bleiben als Stack erhalten. #17 ist nach Prüfung seines grünen Heads für Review freigegeben; kein PR wurde gemergt.

### Lokal ausgeführte Prüfungen

**PASS:** 74 Frontend-Unit-Tests in zwölf Dateien, 38 Backend-Unit-/Contract-Tests; ESLint, striktes Nuxt-/Vue-TypeScript einschließlich Tests, Ruff/Format (24 Dateien), Pyright (0 Fehler/Warnungen), API-Drift, Nuxt-Produktionsbuild (3,98 MB Serverartefakte, 908 kB gzip), Backend-Wheel/sdist. Beide Compose-Konfigurationen sind über den bestehenden Wrapper erfolgreich validiert.

**BLOCKED lokal:** Playwright-Testserver kann nicht an `127.0.0.1:8000` binden (EPERM), Chromium-Sandboxstart ebenfalls untersagt. Der direkte Docker-Aufruf hat kein Compose-Plugin; der Wrapper findet die vorhandene standalone-v2-Version. Der lokale Smoke benötigt zusätzlich Zugriff auf den Docker-Daemon, der hier verweigert wird. Für lokale DB-Integration fehlt eine separate `NORIS_TEST_DATABASE_URL` mit `_test`; die Fixtures brechen ohne Mutation ab. Nuxt/UI-MCPs sind in dieser Sitzung nicht exponiert (`unknown MCP server`); auch der direkte MCP-Verbindungsversuch scheitert an DNS. Installierte, versionierte Komponenten und offizielle Quellen wurden als API-Ersatz geprüft. Das ist kein erfolgreicher MCP-Aufruf.

### Tatsächliche Browserläufe und Korrekturen

| Head / CI | Ergebnis | Konsequenz |
| --- | --- | --- |
| `58d57b2` / [37881075409](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37881075409) | 58/87 Browserfälle PASS; 27 Bildvergleiche FAIL, zwei neue Locator-Fälle FAIL | Exakter Locator für „Gedanken 1“; Schrift und Absatzabstände nach Bildvergleich korrigiert |
| `dba475b` / [37881928538](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37881928538) | 62/89 Browserfälle PASS; ausschließlich 27 Bildvergleiche FAIL | H1-Umbruch auf 32px bei 42px Zeilenhöhe angepasst; Entwurfsbeobachtung getrennt |
| `a1e4557` / [37882833762](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37882833762) | 64/91 Browserfälle PASS; ausschließlich 27 Bildvergleiche FAIL | Alle Edit-/Fokusfälle bestätigt; Variantenindex gegen wiederholte Gesamtsuche eingeführt |
| `eb0ca33` / [37883323319](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37883323319) | 64/91 Browserfälle PASS; ausschließlich 27 Bildvergleiche FAIL; 74/38/3 Unit-/DB-Fälle und Compose-Smoke PASS | 23 neue und vier geänderte Goldens aus echtem Chromium nach visueller Prüfung übernehmen |

Die 27 Bildfehler sind 23 fehlende und vier absichtlich geänderte Baselines. Auch der vom Auftraggeber gemeldete [Push-Job 113667689980](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37883319472/job/113667689980?pr=18) wurde direkt gelesen und hat dieselbe Ursache. Alle 27 Bilder werden nach tatsächlicher visueller Prüfung als reguläre Baselines committet. Bis der nächste normale Lauf sie bestätigt, bleiben diese Bildvergleiche FAIL. Builds/Compose-Validierung im Checks-Job wurden nach diesen Browserfehlern übersprungen; lokale Builds und der unabhängige Compose-Smoke haben eigene tatsächliche Nachweise. Keine Assertions, Pixelgrenzen oder Tests wurden abgeschwächt, deaktiviert oder als Skip versteckt.

Die neue Matrix enthält 22 permanente Zustands-/Theme-Szenen und eine zusätzliche Referenzszene bei 1920 × 975 / DPR 1. Die vier bisherigen leeren Baselines bleiben als Tests erhalten und werden sichtbar begründet aktualisiert. Zusätzliche Größen pro Theme: 1920 × 1080, 1440 × 900, 1280 × 800, 768 × 1024, 390 × 844, 360 × 800. Neue Browserfälle prüfen Send-Anker, denselben Composer-Knoten, Stop-Fokus, simuliertes VisualViewport-Resize, Stream-/Gesprächswechsel, Tastatur-Löschen/Suche, Sidebarpräferenz, Reload, große Codeblöcke/Tabellen/URLs, Editierdialog-Fokus sowie 100/500 Nachrichten mit zehn inaktiven Varianten. Die früheren PR-17-Scroll-/Stop-Timing-Fälle bestehen unverändert.

Die tatsächlichen Referenzszenen prüfen vor jeder Aufnahme Konsolen-/Hydrationfehler, horizontales Overflow, window-Scroll, berechneten Textkontrast (mindestens 4,5:1) und benannte Touch-Kontrollen (mindestens 44 × 44). Kurze Phasenmeldungen statt Token-Announcements bleiben erhalten. Das belegt ausgewählte Accessibility-Eigenschaften, keine vollständige WCAG-Konformität.

### Geometrie und Bildnachweise

Bei 1920 × 975 misst Chromium: Leiste 68,0px, Sidebar 375,984px, Hauptbereich 1476,016px, Inhalt/Composer 999,984px bei x=682,0px, Composer y=876/h=70/Unterabstand=29, Header 68. Mobile bei 390 × 844: Composer x=12, Breite 366, Höhe 60, Unterabstand 29. Kein äußeres Scrollen oder horizontales Seitenoverflow. Messwerte und Unterschiede stehen in [VISUAL-COMPARISON](ui-reference/VISUAL-COMPARISON.md).

Das Original bleibt unverändert lokal und im aktuellen Git-Baum ausgeschlossen, SHA256 `47403b9bd1291b403e0f9e61f609a659eda5b3f624b5ed6834d13a21c24cb0e9`. Die zuerst veröffentlichte Kopie wurde aus dem aktuellen Baum entfernt; frühere Git-Objekte werden damit nicht als gelöscht behauptet. Für die Veröffentlichung vorbereitete Vergleichsansichten maskieren nur persönliche Sidebar-Titel/Kontobuchstaben, mit expliziten Rechtecken in `comparison.json`. **BLOCKED:** Die automatische Freigabeprüfung lehnt den Upload der zusätzlichen Vergleichs-PNGs wegen möglicherweise privater, nicht ausreichend verifizierter Screenshotdaten ab. Diese fünf Bilder bleiben unter `docs/ui-reference/local-comparison/public/` lokal; sie werden nicht über einen alternativen Uploadweg veröffentlicht. Die reinen Noris-Testbaselines verwenden kontrollierte Mock-Daten. Kein geometrisches Element wird zur Verbesserung einer Pixelquote angepasst oder maskiert.

### Performancebeobachtung

Messungen aus den tatsächlichen Chromium-Reports, jeweils ein kalter Dev-Server-Durchlauf mit 100/500 sichtbaren Nachrichten, einem langen Codeblock und zehn inaktiven Varianten. `inputLatencyMs` misst Eingabe bis zum nächsten Frame; `scrollLatencyMs` die Scrollaktion bis zum Frame, kein vollständiges FPS-Profil. Werte sind Beobachtungen, keine Benchmarkgarantie.

| Zustand / Lauf | Nachrichten | Eingabe ms | Scroll ms | JS-Heap MB | DOM-Knoten |
| --- | --- | --- | --- | --- | --- |
| Desktop vor Variantenindex, `dba475b` | 500 | 646,2 | 692,2 | 225 | 7704 |
| Mobile-Emulation vor Variantenindex, `dba475b` | 500 | 713,2 | 793,6 | 225 | 7706 |
| Desktop nach Variantenindex, `eb0ca33` | 100 | 6,6 | 41,8 | 109 | 2304 |
| Desktop nach Variantenindex, `eb0ca33` | 500 | 31,9 | 163,9 | 188 | 7704 |
| Mobile-Emulation nach Variantenindex, `eb0ca33` | 100 | 8,3 | 85,8 | 109 | 2306 |
| Mobile-Emulation nach Variantenindex, `eb0ca33` | 500 | 12,0 | 145,3 | 212 | 7706 |

Der persistierte Entwurfs-Watch ist vom Nachrichten-Watch getrennt; eine computed Sibling-Metadatenkarte vermeidet Gesamtsuche pro Nachricht auf jedem Token. Der bestehende Nachrichtengraph bleibt erhalten. DOM-Identität wird geprüft, aber kein vollständiges Vue-Profiler-/Langzeit-Leak-Ergebnis behauptet. Die Scrollzeiten bei 500 Nachrichten lassen weitere Performanceabnahme offen; Virtualisierung wurde wegen Scroll-/Accessibility-Risiken ohne ausreichenden Nachweis nicht ergänzt.

### Verbleibende Abnahme

**NOT TESTED:** reale iOS-/Android-Tastaturen und Browserchrome, VoiceOver/TalkBack, Firefox/WebKit, High Contrast/Zoom, manuelle Referenzbestätigung durch den Auftraggeber. Dark/Mobile/Leerzustand sind getestete Noris-Varianten; die einzige gelieferte Referenz zeigt diese Zustände nicht. DPR, Zoom und Originalfont bleiben unbekannt. Kein Pixel-Perfect- oder ChatGPT-Funktionsparitätsversprechen. Keine Etappe 2, kein automatisches Merge.
