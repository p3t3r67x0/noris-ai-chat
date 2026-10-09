# Etappe 1: Testnachweise

Stand: 2026-10-09. Die Implementierung beginnt mit `feat/chat-shell` auf dem gemergten Etappe-0-Stand `2d5e5458da190c9439663749a4a74dddd53fcb2e`. Ergebnisse werden erst nach tatsächlicher Ausführung ergänzt.

## Umgebung

Der lokale Git-Metadatenbereich ist für den Agenten schreibgeschützt. Veröffentlichung und Remote-Prüfungen verwenden die autorisierte GitHub-Anbindung; ein isolierter Git-Checkout dient zur Prüfung der Historie. Die Quellen werden weiterhin im bestehenden Workspace bearbeitet.

`npm view @nuxt/ui` konnte die Registry wegen `ENOTFOUND registry.npmjs.org` nicht erreichen. Nuxt UI 4.11.3 und seine APIs wurden anhand des offiziellen, versionierten GitHub-Releases und Quellcodes verifiziert. Die normale Lockfile-Auflösung erfolgt einmalig in GitHub Actions. Der dafür angelegte temporäre Workflow wird vor dem fertigen Shell-PR entfernt.

## PR 1: Shell

Lokaler Vitest-Lauf: **18 Tests in drei Dateien bestanden**. Die vorhandenen Foundation-Tests bleiben erhalten; acht zusätzliche Desktop-/Mobilfälle prüfen Shell, Sidebar, Suche, Chat-Verwaltung und Theme. Lokale Nuxt-UI-Typ-, Build- und Browserprüfungen sind zunächst **BLOCKED**, da die neuen Pakete in der Sandbox nicht heruntergeladen werden können. Die vollständigen GitHub-Actions-Ergebnisse werden nach dem tatsächlichen Lauf ergänzt.

## PR 2–4

Noch nicht begonnen. Ergebnisse, Screenshot-Artefakte und offene Risiken folgen jeweils mit dem tatsächlich geprüften Stand.
