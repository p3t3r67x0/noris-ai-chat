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

**Ausstehend:** [CI 37878919360](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37878919360) prüft `80a08b4` mit korrigiertem Stop-Zeitfenster und erhöhtem Platzhalter-/Fehler-/Warnkontrast. Der Bericht wartet nicht auf diesen Lauf. Die vier visuell geprüften Referenzen stammen noch vom vorherigen Farbstand; nach dem Kontrastupdate sind mögliche Abweichungen zu prüfen und Referenzen gegebenenfalls aus tatsächlich gerenderten Bildern neu zu übernehmen. PR 4 bleibt bis dahin ein Entwurf; eine vollständige grüne Browserprüfung wird nicht behauptet.

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
