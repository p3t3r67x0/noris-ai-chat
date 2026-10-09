# UI-Referenz: Analyse und Abweichungsplan

Stand: 2026-10-09. Verbindliche visuelle Quelle ist der vom Auftraggeber bereitgestellte Screenshot die lokale Desktopreferenz (1920 × 975). Das Original bleibt unverändert als lokale persönliche Referenz; die bestehende Git-Ausschlussregel wird respektiert. Öffentliche Vergleichsansichten maskieren ausschließlich persönliche Chat-Titel/Kontobuchstaben, keine Flächenkanten oder Maße. Keine private Sitzung wurde aufgerufen. Die nachträgliche pixelorientierte Aufgabenstellung konkretisiert das frühere allgemeine UX-Ziel der PLAN.md; Etappe 2 bleibt ausgeschlossen.

## Methode und Aussagegrenzen

**OBSERVED** bezeichnet Sichtbares im Original, **DOCUMENTED** eine veröffentlichte Primärquelle, **INFERRED** eine eigene oder vom Auftraggeber verlangte Interaktionsentscheidung, **UNVERIFIED** nicht beobachtbare Referenzeigenschaften. Pillow liest Abmessungen und häufigste RGB-Werte in definierten Rechtecken. Kanten/Positionen werden an unveränderten Bildpixeln abgelesen; Rundungen und Schriftgrößen sind Schätzungen. Bildpixel sind nicht automatisch CSS-Pixel: DPR, Browserzoom, Betriebssystem und Schrift fehlen. Der Vergleich verwendet deshalb dokumentiert DPR 1, ohne dessen Übereinstimmung zu behaupten.

| Merkmal | Original, Bildpixel | Evidenz |
| --- | --- | --- |
| Bild | 1920 × 975 | OBSERVED, Dateimetadaten |
| Icon-Leiste | x 0–67, Breite 68 | OBSERVED, Kante ±1 px |
| Gesprächssidebar | x 68–443, Breite 376 | OBSERVED, Kante ±1 px |
| Gesamtnavigation | 444 | OBSERVED |
| Inhalts-/Composer-Spalte | x ≈680–1683, Breite ≈1003 | OBSERVED, Kanten ±3 px |
| Hauptbereich | x 444–1919, Breite 1476 | OBSERVED |
| Composer | x ≈680, y ≈876, Breite ≈1003, Höhe ≈70 | OBSERVED, Kanten ±3 px |
| Composer-Unterkante | ≈946, Abstand nach unten ≈29 | OBSERVED |
| Composer-Radius | ≈35 | INFERRED aus Pillenform |
| Stop | ≈48 × 48, Mittelpunkt ≈1649/911 | OBSERVED ±2 px |
| Header | Bedienelemente um y34, angenommene Höhe 68 | OBSERVED Mitte; INFERRED Höhe |
| Chatlistenzeile | ≈48 hoch, aktive Fläche x76–436 | OBSERVED |
| Nutzernachricht | rechts, x≈982–1682, schwarz/weiß, Radius ≈28 | OBSERVED; obere Kante abgeschnitten |
| Fließtext | ≈22, Zeilenabstand ≈34 | INFERRED aus Raster/Glyphen |
| H1 | ≈32, Zeilenabstand ≈42, fett | INFERRED; nach Glyphen-/Umbruchvergleich korrigiert |
| Sidebartext / Composertext | ≈20 / ≈22 | INFERRED |

RGB-Häufigkeiten in unverdeckten Flächen: Leiste `(0,0,68,975)` → **#f9f9f9**, Sidebar `(68,0,443,975)` → **#fcfcfc**, Arbeitsfläche `(445,65,1919,875)` → **#fcfcfc**, Composer `(690,890,1600,930)` → **#ffffff**. Sichtbarer Haupttext **#0d0d0d**, Sidebartext **#313131**, aktive Fläche **#efefef**; sekundärer Text **#8f8f8f** ist gemessen, wird aus Kontrastgründen für lesbare UI-Texte dunkler umgesetzt. Weitere Farben siehe DESIGN-TOKENS.md.

Nicht aus diesem Bild ableitbar: Dark Mode, Mobile, leerer Chat, Hover/Fokus, Animationen, Tastatur, zeitlicher Scrollverlauf, genaue Schriftfamilie, komplette User-Blase. Diese Eigenschaften bleiben UNVERIFIED als Referenz; ihre Noris-Implementierung wird separat geprüft. Die sichtbaren Projekte, Benachrichtigungen, Quellen, Sprach-/Sharingfunktionen und Denkzeit sind keine Etappe-1-Funktionen und werden nicht als funktionierende Elemente nachgebildet.

## Bestehender Zustand und konkreter Plan

Auditiert: README, PLAN, Etappe-0/1-Berichte, Nuxt-Konfiguration, Paketmanifest, alle Chat-Komponenten/Composables und Unit-/E2E-Tests, Foundation-Workflow. PRs #14 → #15 → #16 → #17 sind offen, konfliktfrei, ohne eingereichte Reviews. #17 ist zunächst Draft. Sein Head `2d258f1` besteht [CI 37879178881](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/37879178881): 66 Frontend-, 38 Backend-, 3 PostgreSQL- und 40 Browsertests, Builds, Compose. Browser-Artefakte dieses Heads wurden geprüft. Der Zugriff auf klassische Branch-Protection-Details liefert 403; das ist keine Merge-Freigabe.

| Lücke | Priorität | Umsetzung / Nachweis |
| --- | --- | --- |
| Zweiteilige Navigation, Sidebar 272 statt insgesamt 444 | hoch | Funktionsfähige eigene Icon-Leiste + vorhandene Sidebar; 68/376 bei Referenzbreite |
| Textspalte 768 statt ≈1000, Text 16 statt ≈22 | hoch | Zentrale responsive Maße; gleiche Außenkanten für Verlauf/Composer |
| Composer ≈132 statt70, Toolbar zweite Zeile | hoch | Derselbe UChatPrompt mit einer Anfangszeile und inline angeordneten Kontrollen; Autosize/IME behalten |
| Graue User-Blase, Teal-Button, cremefarbene Flächen | hoch | Gemessene neutrale Light-Tokens, separat begründete Dark-Tokens |
| Stop-Klick fokussiert Button, Sidebarpräferenz flüchtig | mittel | Fokus ohne Browserscroll zurückgeben; Desktoppräferenz getrennt von mobilem Drawer speichern |
| Scroll-Mindesthöhe enthält feste56px | mittel | Tatsächliche Timeline-Innenabstände messen; RAF/ResizeObserver/Nutzerabsicht behalten |
| Vier leere Screenshot-Baselines, kein Vergleich1920×975 | hoch | Zustands-/Theme-Matrix, Referenzszene, Overlay/Differenz, Browsergeometrie |
| Kein100/500-Nachrichtenprofil | mittel | Deterministische Fixtures und Browser-Performance-Artefakt |

Reihenfolge: (1) Tokens/Layout, (2) Sidebar/Header, (3) Composer/Typografie, (4) Fokus/Scroll, (5) Browser/visuelle Nachweise, (6) Korrektur und Dokumentation. Dedizierter Folge-PR `feat/chatgpt-ui-fidelity` auf `feat/chat-ux-polish`; keine Umverteilung auf die ursprünglichen PRs und kein automatisches Merge. PR #17 wurde nach Prüfung seines grünen Heads und der Browserbilder für Review freigegeben; er bleibt ungemergt. Die neue Referenzabnahme liegt in PR #18.

## APIs und Primärquellen

Nuxt4.5.2/UI4.11.3 bleiben gepinnt. Nuxt-MCP ist in `codex mcp list` registriert, aber in dieser Sitzung nicht exponiert; `nuxt-ui` und `nuxt` melden bei MCP-Abfragen „unknown MCP server“. MCP-Nutzung: **BLOCKED**. Kein erfundener Tool-Nachweis. Ersatzprüfung vor Änderungen: installierte `@nuxt/ui/dist/runtime/components/{ChatPrompt,ChatPromptSubmit,Sidebar,SelectMenu,Button}.vue` und generierte UI-Slots, strikte Typprüfung. `ChatPrompt`: rows/maxrows, footer/body/base, textareaRef, IME-Guard; `ChatPromptSubmit`: streaming/submittedColor/Variant und stop; `Sidebar`: gap/container/inner/header/body/footer, offcanvas/slideover und eigener1023px-Breakpoint.

Offizielle Quellen: [Nuxt4 app-Verzeichnis](https://nuxt.com/docs/4.x/directory-structure/app), [ChatPrompt4.11.3](https://github.com/nuxt/ui/blob/v4.11.3/src/runtime/components/ChatPrompt.vue), [ChatPromptSubmit4.11.3](https://github.com/nuxt/ui/blob/v4.11.3/src/runtime/components/ChatPromptSubmit.vue), [Sidebar4.11.3](https://github.com/nuxt/ui/blob/v4.11.3/src/runtime/components/Sidebar.vue), [ChatGPT Release Notes](https://help.openai.com/en/articles/6825453-chatgpt-release-notes). Letztere belegen keine exakten Screenshotmaße und keine beobachtete Scrollparität.
