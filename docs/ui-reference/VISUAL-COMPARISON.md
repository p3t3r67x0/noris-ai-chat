# Visueller Vergleich und Abnahme

## Ausgangszustand

PR17-Head2d258f1 wurde anhand seiner tatsächlichen Browser-Artefakte aus [CI37879178881](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37879178881) visuell gelesen. Desktop1280×720 und Mobile412×839 stimmen mit ihren bestehenden Baselines überein, aber nicht mit der neuen1920×975-Referenz: zweiteilige Navigation,272px Sidebar,768px Spalte,≈132px Composer,16px Text, graue User-Blase und Teal-Senden. Diese Abweichungen sind das konkrete Änderungsziel.

## Vergleichsmethode

Neue deterministische Noris-Referenzszene bei1920×975/DPR1/Light. Vergleichsinhalte orientieren sich an den sichtbaren Absätzen; fremde Kontodaten/Funktionen werden nicht zur Produktfunktion. Original unverändert, SHA256 wird mit dem Vergleich festgehalten. Side-by-side zeigt vollständige unskalierte Bilder; Overlay50% und absolute RGB-Differenz sind zusätzliche Diagnose. Keine automatische Pixelquote erklärt die UI für gleichwertig; anderer Text, eigene Icons und Brand verursachen erwartete Differenzen.

Navigation, Sidebar, Spaltenkanten, Bubble, Typografie, Composer, Farben und Abstände werden getrennt anhand Browsergeometrie und Bildartefakten bewertet. Geänderte Goldens werden nur aus tatsächlichem Chromium-Output übernommen und visuell geprüft; der normale Testlauf bleibt strikt. Fehlende Baselines sind FAIL, nicht PASS.

## Abnahmegrenzen

Dark/Mobile/leer/hover/focus können gegenüber dem einzigen Light-Desktopbild nicht als referenzgleich angenommen werden. Der unbekannte DPR und die unbekannte Schrift verhindern eine pixelgenaue Zusage. MCP-Nutzung ist derzeit BLOCKED. Lokales Playwright/Compose/DB hängt an den dokumentierten Umgebungsrechten; Remote-Nachweise werden mit konkretem Head und Lauf ergänzt. Reale Mobile-Tastaturen bleiben manuell offen.

Konkrete Folge-PR-Ergebnisse und Bildlinks werden nach der Ausführung ergänzt. Kein automatisches Merge; Reihenfolge14→15→16→17→Folge-PR.
