# Datenschutzbereinigung der Integrationsbranches

Stand: 2026-10-09. Der Auftraggeber hat die gezielte Historienbereinigung von PR #18 und PR #20 sowie die Löschung von exakt 17 alten Browserartefakten separat genehmigt. Anschließend wurde die Integration der bereinigten PRs #18 und #19 bei erfolgreicher aktueller CI ausdrücklich freigegeben. Der GitHub-Support-Takedown bleibt ein offener Datenschutzpunkt.

## Ersetzte Inhalte und erhaltene Architektur

- Das private Originalbild wurde aus allen sieben neu aufgebauten PR-18-Commits entfernt.
- Die aus der privaten Vorlage kopierten Benutzer- und Assistant-Texte in `referenceChat()` wurden vollständig durch einen frei erfundenen Tagesplan ersetzt. Referenztitel heißen ausschließlich „Fiktiver Tagesplan“ oder „Beispiel N“; der einzige Link verwendet example.com.
- Der persönliche Screenshot-Dateiname wurde in den betroffenen Dokumentversionen durch eine neutrale Referenzbezeichnung ersetzt.
- Die private Referenz-Golden wurde aus allen sieben Commits entfernt. Eine neue Golden stammt aus dem tatsächlich ausgeführten Chromium-Test mit synthetischer Fixture und wurde bei 1920 × 975 visuell geprüft.
- Die zuvor freigegebenen fünf vollständig bereinigten Vergleichsbilder bleiben byteidentisch. Unbereinigte Originale und alte lokale Vergleiche werden nicht erneut veröffentlicht.
- PR #20 wurde separat auf die bereinigte Basis umgestellt. Seine elf Dialogänderungen und der später ergänzte Shortcut-Fix blieben erhalten. Spätere normale Dialog-/Kontraständerungen werden getrennt geprüft.

Die Vorher-/Nachher-Diffs der sieben bereinigten Commits betreffen ausschließlich vier Datenschutzpfade. UI-Komponenten, Design-Tokens, Transport, Nachrichtenmodell, Persistenz und Scrollarchitektur blieben dabei byteidentisch. Die sieben logischen Commitgrenzen und Änderungsbeschreibungen bleiben erhalten; GitHub vergab neue Commit-IDs und neue Commit-Metadaten. Es wird keine unveränderte Remote-Autor-/Zeitstempelidentität behauptet.

## Veröffentlichte neue Referenz-Golden

Datei: `frontend/tests/e2e/__screenshots__/linux/desktop/reference-reference-light.png`.

- Auflösung: 1920 × 975.
- SHA256: `53f1131465080523a3ce46e09577483063916f0e5007d0a16bbb1dd1f2915fb8`.
- Git-Blob: `5e9c721ca73cc0f7aae4b11ebbde055f4efa8706`.
- PNG-Prüfung: gültige CRCs, ausschließlich IHDR/IDAT/IEND, keine angehängten Daten.
- Alle übrigen vorhandenen Referenz-Goldens, Assertions, Testauswahl und Screenshot-Toleranzen blieben unverändert.

Der erste bereinigte CI-Lauf bestand 90 Browserfälle und scheiterte ausschließlich an der bewusst entfernten Golden. Dieser Zwischenlauf ist **FAIL**, kein erfolgreicher Abnahmenachweis. Nach Sichtprüfung und regulärer Übernahme der synthetischen Aufnahme bestehen die vollständigen [PR-18-Prüfungen auf d7fa33b](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37900051593): 76 Frontend-, 38 Backend-, 3 PostgreSQL- und 91 Browserfälle, außerdem Lint, Typen, API-Vertrag, Builds und Compose-Smoke.

Die zusätzliche kombinierte UI-/RealTransport-Validierung auf `cd303eb` besteht [CI 37898524480](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37898524480): 99 Frontend-, 102 Backend-/Contract-/HTTP-, 3 PostgreSQL-, 91 UI-Browser- und 6 RealTransport-Browserfälle, insgesamt 301. Die 27 visuellen Fälle sind Teil der 91 UI-Browserfälle und werden nicht doppelt gezählt. Dies ist ein Integrationsbranch-Nachweis, keine Behauptung über einen späteren main-Commit.

## Alte Browserartefakte

**PASS:** Alle 14 genehmigten alten PR-18-Artefakte und alle drei zusätzlich genehmigten alten PR-20-Artefakte sind unwiderruflich gelöscht. Eine unabhängige anschließende Abfrage der jeweiligen Runs findet keines dieser Artefakte mehr.

Der isolierte Actions-Workflow prüfte vor dem Löschen Artefakt-ID, Namen, Run-ID und alten Head-Commit gegen die genaue Allowlist. Der Workflow wurde nicht nach main übernommen.

- PR #18: [Bereinigungslauf 37898455609](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37898455609), erfolgreich. Artefakt-IDs: 11599270387, 11598144290, 11597870092, 11597935262, 11597540612, 11597237665, 11595600994, 11595506119, 11594488639, 11595153734, 11594813022, 11594977664, 11594596126, 11594174769.
- PR #20: [Bereinigungslauf 37898984136](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37898984136), erfolgreich. Artefakt-IDs: 11600996282 (Run 37897054297), 11600882094 (Run 37897048367), 11601342578 (Run 37897858356).

Neue Artefakte der bereinigten Branches verwenden synthetische Referenzinhalte.

## Historienprüfung und verbleibender Support-Takedown

**PASS im geprüften Umfang:** Die lokalen bereinigten UI-, kombinierten UI-/Transport- und ursprünglichen Transport-Historien wurden anhand der bekannten privaten Inhalte, betroffenen Bild-Blobs und gängigen Secret-Muster geprüft. 254 / 321 / 247 historische Text-Blobs ergaben jeweils null Funde. Die neuen PR-18-/PR-20-Branch-Vorfahren übernehmen die private Originaldatei und private Referenz-Golden nicht. Der Mustervergleich ersetzt kein vollständiges externes Security-Audit.

**BLOCKED, serverseitiger Altbestand:** GitHub liefert das Original weiterhin über den alten Commit `58d57b217b31c9dc749de65603bd49d1c6c96b8c` aus, obwohl dieser nicht zur bereinigten Branch-Historie gehört. Der Blob `3d50917c0d895af92dceffcc8cda7c9c64819e5f` bleibt unter dieser alten Adresse erreichbar. Der Auftraggeber wurde informiert und genehmigte anschließend ausdrücklich den Merge ausschließlich bereinigter Dateien und Historien; die Support-Bereinigung bleibt offen.

Eine Support-Anfrage wurde lokal vorbereitet, aber nicht versendet. GitHub Support muss alte PR-Referenzen und zwischengespeicherte Ansichten gegebenenfalls entfernen und die serverseitige Bereinigung bestätigen. Fremde Clones oder Forks lassen sich durch einen Branch-Force-Push nicht weltweit löschen. Es wird keine vollständige weltweite Löschung behauptet.

Quelle: [GitHub-Dokumentation zur Entfernung vertraulicher Daten](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository).
