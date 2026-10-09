# Design-Tokens

Quelle: REFERENCE-ANALYSIS.md. Alle Produktwerte werden in `frontend/app/assets/css/main.css` zentral definiert. Geometrie wird bei 1920×975 CSS-Pixeln/DPR 1 gegen Bildpixel verglichen; Skalierung der Originalaufnahme ist unbekannt.

| Token | Referenzziel bei 1920 | Status |
| --- | --- | --- |
| `--noris-rail-width` | 68px | gemessene Kante |
| `--noris-sidebar-width` | 376px | gemessene Kante |
| `--noris-chat-max-width` / `--noris-composer-max-width` | 1000px | gerundete gemessene Spalte≈1003 |
| `--noris-header-height` | 68px | geschätzt |
| `--noris-composer-height` | 70px | gemessen±3 |
| `--noris-composer-radius` | 35px | geschätzt |
| `--noris-composer-bottom-gap` | 29px | gemessen±3, inklusive Noris-Hinweis |
| `--noris-message-font-size` | 22px | geschätzt |
| `--noris-message-line-height` | 1.545≈34px | geschätzt |
| `--noris-heading-font-size` | 32px | Schätzung nach überprüfter Umbruchbreite, 42px Zeilenhöhe |
| `--noris-sidebar-font-size` | 20px | geschätzt |
| `--noris-composer-font-size` | 22px | geschätzt |
| `--noris-user-bubble-radius` | 28px | geschätzt |

| Flächentoken | Light | Dark | Begründung |
| --- | --- | --- | --- |
| `--noris-background` | #fcfcfc | #212121 | Light gemessen; Dark INFERRED |
| `--noris-sidebar-background` | #fcfcfc | #181818 | Light gemessen; Dark INFERRED |
| `--noris-rail-background` | #f9f9f9 | #131313 | Light gemessen; Dark INFERRED |
| `--noris-composer-background` | #ffffff | #303030 | Light gemessen; Dark INFERRED |
| `--noris-text-primary` | #0d0d0d | #ececec | Light gemessen; Dark INFERRED |
| `--noris-text-secondary` | #676767 | #b4b4b4 | abweichend von≈#8f8f8f zugunsten 4.5:1 |
| `--noris-border` | #e5e5e5 | #424242 | Kante geschätzt, Dark INFERRED |
| `--noris-hover-background` / `--noris-active-background` | #efefef | #2b2b2b | aktive Light-Fläche gemessen |
| `--noris-user-bubble-background` | #000000 | #303030 | Light beobachtet; Dark INFERRED |
| `--noris-user-bubble-foreground` | #ffffff | #ececec | Light beobachtet; Dark INFERRED |

Schriftstack `Arial, Helvetica, sans-serif` ist rechtmäßig lokal verfügbar; Chromium/Linux nutzt den metrisch kompatiblen Liberation-Sans-Ersatz. Genaue Referenzschrift UNVERIFIED. Keine kopierten Fontdateien. Der erste Browservergleich zeigte zu breite Systemschrift: Die Referenzphrase „Ich würde“ misst ≈96 Bildpixel; Liberation Sans bei 22px misst 95,38px, DejaVu Sans bei 22px 107,61px. Diese Messung begründet die schmalere Auswahl. Header, Sidebar, Body, Überschriften und Composer haben eigene zentral definierte Schriftmaße. Kleinere Viewports bekommen 16px Nachrichtenschrift und entsprechend kleinere Geometrie, keine CSS-Transforms. Menüs/Fokus/Disabled sind eigene zugängliche Ausprägungen; ihre Referenzzustände sind nicht sichtbar.

## Produktionsintegration: stabile Footer-Zeilenhöhen

Der zusätzliche Compose-Produktionslauf [37906351675](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37906351675) reproduziert die früheren Drawer-Abweichungen: 109 PASS / 2 FAIL, 545 beziehungsweise 446 Pixel. Der Trace belegt im minifizierten Stylesheet `--text-sm--line-height:1.42857` und `--text-xs--line-height:1.33333`. Die daraus berechneten Zeilenhöhen unterscheiden sich geringfügig vom Entwicklungs-CSS und ändern Textposition und Rasterung im zentrierten Footer.

Avatar, Kontolabel und Caption verwenden nun zentrale Schriftgrößen von 0.875rem beziehungsweise 0.75rem und explizite Zeilenhöhen von 1.25rem beziehungsweise 1rem. Die vier `--noris-account-*`-Tokens vermeiden die gerundeten dimensionslosen Quotienten und erhalten die Darstellung aus der bestehenden Baseline. Die Avatar-Klassenanbindung wurde über den offiziellen Nuxt-UI-MCP-Server (Avatar-Metadaten und API/Theme) sowie die installierte 4.11.3-Komponente geprüft. Keine Baseline, Assertion, Testauswahl oder Screenshot-Toleranz wird geändert. Neue vollständige Entwicklungs- und Produktions-CI ist für diesen Fix erforderlich; der vorherige Fehler bleibt als historischer Befund dokumentiert.
