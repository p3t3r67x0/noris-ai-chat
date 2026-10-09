# Visueller Vergleich und Abnahme

## Ausgangszustand

PR17-Head2d258f1 wurde anhand seiner tatsächlichen Browser-Artefakte aus [CI37879178881](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37879178881) visuell gelesen. Desktop1280×720 und Mobile412×839 stimmen mit ihren bestehenden Baselines überein, aber nicht mit der neuen1920×975-Referenz: zweiteilige Navigation,272px Sidebar,768px Spalte,≈132px Composer,16px Text, graue User-Blase und Teal-Senden. Diese Abweichungen sind das konkrete Änderungsziel.

## Vergleichsmethode

Neue deterministische Noris-Referenzszene bei1920×975/DPR1/Light. Vergleichsinhalte orientieren sich an den sichtbaren Absätzen; fremde Kontodaten/Funktionen werden nicht zur Produktfunktion. Original unverändert, SHA256 wird mit dem Vergleich festgehalten. Side-by-side zeigt vollständige unskalierte Bilder; Overlay50% und absolute RGB-Differenz sind zusätzliche Diagnose. Keine automatische Pixelquote erklärt die UI für gleichwertig; anderer Text, eigene Icons und Brand verursachen erwartete Differenzen.

Navigation, Sidebar, Spaltenkanten, Bubble, Typografie, Composer, Farben und Abstände werden getrennt anhand Browsergeometrie und Bildartefakten bewertet. Geänderte Goldens werden nur aus tatsächlichem Chromium-Output übernommen und visuell geprüft; der normale Testlauf bleibt strikt. Fehlende Baselines sind FAIL, nicht PASS.

## Abnahmegrenzen

Dark/Mobile/leer/hover/focus können gegenüber dem einzigen Light-Desktopbild nicht als referenzgleich angenommen werden. Der unbekannte DPR und die unbekannte Schrift verhindern eine pixelgenaue Zusage. MCP-Nutzung ist derzeit BLOCKED. Lokales Playwright/Compose/DB hängt an den dokumentierten Umgebungsrechten; Remote-Nachweise werden mit konkretem Head und Lauf ergänzt. Reale Mobile-Tastaturen bleiben manuell offen.

## Tatsächlicher Vergleich

Die ursprüngliche Datei wurde mit Pillow gelesen und unverändert gelassen. [Pixelmessungen](evidence/reference-measurements.json) enthalten Originalauflösung, SHA256, Messrechtecke und dominante Farben. [Browsermessungen](evidence/browser-measurements.json) stammen aus den tatsächlichen Chromium-Artefakten von PR #18. Der unbekannte Screenshot-DPR wird ausdrücklich nicht als gemessen ausgegeben; Noris verwendet für den Vergleich DPR 1.

| Bereich | Referenz / Methode | Noris / Ergebnis | Bewertung |
| --- | --- | --- | --- |
| A Navigation | Pixelkanten: Leiste ≈68, gesamte Navigation ≈444 px | DOM: 68,0 + 375,984 px | Geometrie übernommen; eigene Icons und nur funktionierende Bereiche |
| B Sidebar | ≈376 px; aktive Zeile #efefef; Zeilenabstand ≈48 px | 375,984 px; gleiche aktive Fläche und kompakte Zeilen | Projekte entfallen, da nicht implementiert. Historie beginnt dadurch höher; bewusste Abweichung |
| C Inhalt | Spaltenkanten ≈682–1682 px | x=682,0; Breite 999,984 px | Zentrierung und Breite stimmen auf Messgenauigkeit überein |
| D Nachrichten | User rechts, schwarz/weiß, begrenzte Bubble; Assistant ohne Karte | Dieselbe Behandlung; sichere Markdown-Ausgabe und unveränderliche Varianten | Eigener Beispielinhalt. Der feste Header begrenzt den sichtbaren Verlauf; der Screenshot zeigt eine oben angeschnittene Bubble |
| E Typografie | Fließtext ≈22/34, H1 ≈32/42 px; Schrift unbekannt | 22/34 und 32/42; Arial/Helvetica, Linux Liberation Sans | H1-Umbruch nach Bildprüfung korrigiert. Ersatzfont, Rasterung und einzelne Zeilen bleiben abweichend |
| F Composer | ≈1000 × 70 px; y≈876; Unterabstand≈29; Radius≈35 | 999,984 × 70; y=876; Unterabstand=29; Radius=35 | Geometrie übernommen. Keine Mikrofonfunktion; eigene verfügbare Modellauswahl und offene Stop-Iconform |
| G Farben | Dominant: rail #f9f9f9, workspace/sidebar #fcfcfc, composer #fff, aktiv #efefef | Gleiche Flächen; sekundärer Text #676767 | Sekundärtext bewusst dunkler für ≥4,5:1 Kontrast; Dark Mode ist eine geprüfte eigene Variante |
| H Abstände | Text-/Composer-Ausrichtung und kompakte Navigation gemessen | Gemeinsame Spalte, 68 px Header, mobile 12 px Rand | Eigenes Modell im Header; Verlauf/Sidebar unterscheiden sich durch nicht implementierte Referenzfunktionen |

Bestehende Noris-Aufnahme: [1920 × 975, Light](../../frontend/tests/e2e/__screenshots__/linux/desktop/reference-reference-light.png). **Datenschutz-Nachprüfung:** Diese Referenzszene enthält übernommene Texte aus der privaten Vorlage und ist kein vollständig synthetisch bereinigter Veröffentlichungskandidat. Die fünf neu bereinigten, ausdrücklich freigegebenen Ansichten sind separat im [Bereinigungsbericht](BEREINIGUNGSBERICHT.md) benannt. Weitere permanente Szenen: [Desktop Light](../../frontend/tests/e2e/__screenshots__/linux/desktop/reference-active-light.png), [Desktop Dark](../../frontend/tests/e2e/__screenshots__/linux/desktop/reference-active-dark.png), [Mobile Light](../../frontend/tests/e2e/__screenshots__/linux/mobile/reference-active-light.png), [Mobile Dark](../../frontend/tests/e2e/__screenshots__/linux/mobile/reference-active-dark.png). Alle 27 neuen/geänderten Baselines wurden anhand der tatsächlichen Browserbilder visuell geprüft. Die bestehende Pixelgrenze bleibt unverändert bei 0,001; die Bilder werden nicht automatisch im CI erneuert.

## Vergleichsartefakte und Veröffentlichung

**Lokal vorhanden:** unveränderte private Vergleiche unter `local-comparison/final/`; die fünf früheren Kandidaten wurden wegen weiterhin lesbarer privater Gesprächsinhalte nach `local-comparison/quarantine/previous/` verschoben. Die frühere Sidebar-Maskierung genügte nicht. Auch die Aussage, die Referenz-Baseline enthalte ausschließlich frei erfundene Mock-Inhalte, wird hier korrigiert: Sie übernimmt Referenztexte aus der privaten Vorlage.

**Fünf vollständig bereinigte und freigegebene Bilder:** [Referenz](evidence/sanitized/reference-layout-redacted.png), [Noris](evidence/sanitized/noris-reference.png), [Side-by-side](evidence/sanitized/side-by-side.png), [Overlay](evidence/sanitized/overlay.png) und [Differenzbild](evidence/sanitized/difference.png) enthalten ein neu erfundenes Gespräch, neutrale Kontodaten und geprüfte statische UI-Ausschnitte. Das [Bereinigungsprotokoll](BEREINIGUNGSBERICHT.md) dokumentiert Ersetzungen, Hashes, elf lokale Prüfungen und den offenen historischen Git-Bestand. Alle ursprünglichen lokalen Bildverzeichnisse bleiben im Git ausgeschlossen. Die veröffentlichten Kopien sind bearbeitete synthetische Derivate, keine unveränderten Browseraufnahmen; sie ersetzen keinen ursprünglichen Pixelvergleich.

**Veröffentlichung freigegeben am 2026-10-09:** Erst nach vollständiger Bereinigung und abschließender Freigabe werden ausschließlich die fünf neuen Dateien mit den im [Manifest](evidence/sanitized/manifest.json) gebundenen Hashes veröffentlicht. Die frühere automatische Ablehnung betraf unzureichend bereinigte Bilder; diese bleiben in Quarantäne. [Frühere Vergleichsmetadaten](evidence/comparison.json) beschreiben die alte, unzureichende Maskierung und sind kein Nachweis der jetzigen Anonymisierung. Das Original bleibt unangetastet. Die bestehende Fixture/Baseline und der historische Originalbestand benötigen weiterhin einen eigenen Bereinigungsschritt.

Die mittlere absolute RGB-Differenz der maskierten Diagnoseansicht liegt bei etwa 22/255 je Kanal. Dieser Wert enthält Texte, Icons und Scrollkontext und ist kein Abnahmegrenzwert. Er belegt weder Pixelgleichheit noch funktionale Parität. Die direkte Betrachtung und getrennte Geometriemessung entscheiden über die dokumentierten Korrekturen.

## Status

**PASS:** programmatische Referenzanalyse, lokale Bildprüfung, elf Datenschutzprüfungen, Hash-Abgleich der fünf freigegebenen PNGs, gemessene Desktop-Geometrie, Kontrast-/Overflow-Prüfungen und alle 27 regulären Bildvergleiche im [vollständigen Push-Lauf 37887972615](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37887972615) auf `30d54e8` (91 Browserfälle bestanden). **FAIL historisch, behoben:** 23 fehlende und vier geänderte Baselines. **OFFEN Datenschutz:** historischer Originalbestand und übernommene Referenztexte in vorhandener Fixture/Baseline. **BLOCKED:** MCP-Verbindung. **NOT TESTED:** manuelle UX-Abnahme durch den Auftraggeber, reale mobile Tastaturen, Screenreader und nicht durch die Referenz belegte Dark-/Mobile-Fidelität. Die Bildveröffentlichungsfreigabe ist keine vollständige UX-Abnahme. Auch der separate [PR-Lauf 37887976895](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37887976895) auf demselben Code-Head ist vollständig grün; neue Dokumentations-Workflows sind separate Läufe.

Kein automatisches Merge; Reihenfolge #14 → #15 → #16 → #17 → #18. Etappe 2 bleibt außerhalb des Umfangs.
