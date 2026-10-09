# Design-Tokens

Quelle: REFERENCE-ANALYSIS.md. Alle Produktwerte werden in `frontend/app/assets/css/main.css` zentral definiert. Geometrie wird bei1920×975 CSS-Pixeln/DPR1 gegen Bildpixel verglichen; Skalierung der Originalaufnahme ist unbekannt.

| Token | Referenzziel bei1920 | Status |
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
| `--noris-heading-font-size` | 30px | geschätzt |
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
| `--noris-text-secondary` | #676767 | #b4b4b4 | abweichend von≈#8f8f8f zugunsten4.5:1 |
| `--noris-border` | #e5e5e5 | #424242 | Kante geschätzt, Dark INFERRED |
| `--noris-hover-background` / `--noris-active-background` | #efefef | #2b2b2b | aktive Light-Fläche gemessen |
| `--noris-user-bubble-background` | #000000 | #303030 | Light beobachtet; Dark INFERRED |
| `--noris-user-bubble-foreground` | #ffffff | #ececec | Light beobachtet; Dark INFERRED |

Systemschrift (`ui-sans-serif`, `system-ui`, Apple/BlinkMac, Segoe UI, sans-serif) ist rechtmäßig lokal verfügbar; genaue Referenzschrift UNVERIFIED. Keine kopierten Fontdateien. Header, Sidebar, Body, Überschriften und Composer haben eigene zentral definierte Schriftmaße. Kleinere Viewports bekommen16px Nachrichtenschrift und entsprechend kleinere Geometrie, keine CSS-Transforms. Menüs/Fokus/Disabled sind eigene zugängliche Ausprägungen; ihre Referenzzustände sind nicht sichtbar.
