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

Folgt nach PR 3. Das gewünschte Positionieren der gesendeten Frage unter dem Header gehört zu dieser Etappe des Frontends.
