# Prüfstand: Composer und Dateianhänge

## Nachtrag: Bildanbindung und CI-Evidenz

Die nachfolgende Tabelle beschreibt den Stand **vor** der ergänzten Vision-Implementierung. Der Nutzer untersagte anschließend ausdrücklich weitere Tests und Docker-Läufe sowie das Warten auf CI. Die neue Bildanbindung wurde deshalb ausschließlich durch Quellen-/Codeprüfung bearbeitet; neue synthetische Unit-, PostgreSQL-/WebSocket- und Browserfälle wurden geschrieben, aber nicht ausgeführt. HTTP-/WebSocket-Verträge wurden als Codegenerierung aktualisiert. Keine tatsächliche Noris-Generierung fand statt. Zwei reine Modellkatalog-GETs bestätigten aktuelle Bildeingaben; die Payload folgt der offiziellen Noris-Dokumentation. Ein erfolgreicher Modellaufruf bleibt unbestätigt.

Für PR #43 wurden die bereits vorhandenen synthetischen Bilder des abgeschlossenen [CI-Jobs 114435754381](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/38127803240/job/114435754381?pr=43) geprüft. Die 16 Suchdialog-Baselines enthielten den vorherigen Hintergrund-Composer; die Actual-Bilder stimmen jeweils pixelgenau mit dem Retry überein. Die gezielte Übernahme und die mobile Settings-Navigationskorrektur sind in `ADAPTIVE-COMPOSER.md` dokumentiert. Kein Browserlauf wurde neu gestartet und keine privaten Referenzinhalte veröffentlicht.

Stand: 11. Oktober 2026. Die beiden abhängigen Änderungen basieren auf `main` einschließlich der Chatsuche aus PR #42. Die privaten ChatGPT-Referenzen bleiben lokal; neue veröffentlichte Browserbilder enthalten ausschließlich synthetische Gespräche und Dateien.

## Abgeschlossene lokale Prüfungen

| Prüfung | Ergebnis vor dem angeordneten Teststopp |
| --- | --- |
| `make lint` | erfolgreich, einschließlich Shutdown-Regression |
| `make typecheck` | Python-, Vue- und Werkzeugtypen erfolgreich |
| `make check-api` | generierte HTTP-/WebSocket-Verträge aktuell |
| `make test-unit` | 300 Backend- und 261 Frontend-Tests erfolgreich |
| `make test-integration` | vollständiger Lauf mit 45 erfolgreichen PostgreSQL-Tests |
| `make build` | Backend-Paket und Nuxt-Produktionsbuild erfolgreich; nochmals mit aktualisiertem `main` gebaut |
| Composer-Browsermatrix | Compact/Expanded/Maximized, Fokus, Cursor, Zoom, Unterkante und Toolbar geprüft; synthetische Referenzbilder manuell geprüft |
| Upload-Browserfälle | echte Mehrfachauswahl, Persistenz, Download, Wiederholung, Entfernen, Abbruch, Limits und fehlende Vision-Unterstützung auf Desktop/Mobile geprüft |

Die Provider-Aufrufe in diesen Prüfungen verwenden lokale Simulatoren und synthetische Zugangsdaten. Bestehende Datenbankvolumes wurden nicht gelöscht.

## Offene vollständige Browserabnahme

Der letzte vollständige Mock-Browserlauf vor Aktualisierung auf PR #42 hatte 218 erfolgreiche Fälle, 18 vorhandene projektabhängige Auslassungen und einen Fehler: Der Profiltest sendete vor abgeschlossener Hydrierung. Er wartet jetzt ausdrücklich auf `data-ready`; diese letzte Korrektur wurde nach der Nutzeranweisung nicht erneut ausgeführt.

Der letzte vollständige WebSocket-Browserlauf hatte 52 erfolgreiche Fälle, sechs Auslassungen für doppelte Screenshot-Projekte und zwei Fehler. Ein paralleler Mock-Lauf löschte das gemeinsame übergeordnete Artefaktverzeichnis; Mock-Artefakte verwenden jetzt ein eigenes Unterverzeichnis. Der zweite Fehler war eine noch streamende lange Simulatorantwort beim bestehenden 5-Sekunden-Statuscheck. Die Assertion und ihr Timeout bleiben unverändert.

Die Suchscreenshots mit dem geänderten Composer wurden anhand des oben verlinkten abgeschlossenen CI-Jobs visuell geprüft und gezielt übernommen. Ein neuer vollständiger Browserlauf nach dieser Korrektur wurde nicht gestartet. Der letzte gestartete Integrationstest wurde auf Nutzeranweisung beendet; die ergänzte MIME-Prüfung wurde dabei bereits in den Attachment-Fällen ausgeführt, der gesamte Lauf war beim Stopp noch nicht abgeschlossen. Die zusätzliche MIME-Bedingung im API-Feld `modelUsable` und die nachträgliche Vision-Anbindung wurden danach nicht getestet.

Auf ausdrücklichen Nutzerwunsch erfolgen keine weiteren Tests, Docker-Prüfungen oder Wartezeiten auf CI. Die Pull Requests sind deshalb Drafts. Es wurden keine Assertions abgeschwächt, Snapshot-Toleranzen erhöht oder Tests deaktiviert. Reale Softwaretastaturen und browserabhängiger Zoom bleiben zusätzlich manuell zu prüfen; automatisierte VisualViewport-/CSS-Zoom-Prüfungen ersetzen keine Geräteabnahme.
