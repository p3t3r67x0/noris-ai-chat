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

In Umsetzung. Lokal sind ESLint, striktes Nuxt-/Vue-TypeScript und der Nuxt-Produktionsbuild erfolgreich. Der PR ergänzt echte Nuxt-UI-Composer-Interaktionen sowie acht Desktop-/Mobilfälle für Send, Markdown, Clipboard, IME, Stop und Fehler/Retry. Unit-Ergebnisse werden nach dem fertigen Lauf ergänzt.

Lokales Playwright: **BLOCKED**, da der Sandbox-Prozess nicht an `127.0.0.1:8000` binden kann. Lokale PostgreSQL-Integration: **BLOCKED**, da keine separate `NORIS_TEST_DATABASE_URL` mit `_test` bereitgestellt ist; die drei Fixtures brechen ohne Datenbankmutation ab. Die CI führt beide Prüfungen mit eigener Testdatenbank aus.

## PR 3: Verzweigungen und Entwürfe

Implementiert: unveränderliches Editieren, Antwortvarianten, Wiederherstellung alter Fortsetzungen, Entwürfe und validierte gemeinsame lokale Persistenz. Zusätzliche Unit-Fälle prüfen Transporthistorien, Isolation, Abbruch beim Reload sowie beschädigte, zyklische und fremde Parent-Referenzen. Drei neue Browserfälle laufen auf Desktop und Mobilgerät. Remote-Nachweise werden nach dem tatsächlichen Lauf ergänzt.

## PR 4: UX und visuelle Nachweise

Folgt nach PR 3. Das gewünschte Positionieren der gesendeten Frage unter dem Header gehört zu dieser Etappe des Frontends.
