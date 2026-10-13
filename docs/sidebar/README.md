# Sidebar: Rail-Zentrierung und persistente Chat-Fixierungen

## Bestandsanalyse

| Bestehender Baustein | Wiederverwendung |
| --- | --- |
| `ChatRail.vue`, `ProfileMenu.vue`, Layout in `ChatWorkspace.vue` | Bestehende Rail und Profil-Menüs; gemeinsame Geometrie ausschließlich über Rail-CSS. |
| `ChatSidebar.vue` / Nuxt UI `USidebar` | Desktop-Sidebar und mobiler Slideover bleiben erhalten. |
| Nuxt UI `UDropdownMenu` | Portal, Collision Detection, Menü-Tastatursteuerung und bestehende Umbenennen-/Archivieren-/Löschen-Aktionen. |
| `ConversationTitle.vue` | Vorhandene Titelanpassung ohne Änderung der gespeicherten Titel. |
| `groupConversations`, `useConversations` | Eine Chatverwaltung, ergänzt um Pin-Status und eine zusätzliche Gruppe. |
| `ChatSearchDialog`, `useConversationSearch` | Bestehende Suche inklusive serverseitiger Pagination; durchsucht weiterhin alle Chats. |
| `ChatBackend`, `useChatBackend` | Bestehende REST-Warteschlange, Versionsprüfung, Metadatenverwaltung und begrenzte Cache-Fenster. |
| `ChatService`, `ChatRepository`, Conversation-PATCH-API | Bestehende Owner-Prüfung und pessimistisch gesperrtes, optimistisch versioniertes Update. |
| `chat.conversation.updated` | Live-Verteilung von Pin- und Archivstatus an verbundene Tabs. |

Die tatsächliche Rail-Ursache liegt im Button-Inhalt, nicht im übergeordneten Container: `align-items: center` zentrierte bereits die Buttons. Nuxt UI verwendete jedoch unterschiedliche Slot-/Icon-Paddings und keine zentrierte Inhaltsausrichtung. Bei 1440 px lagen alle Button-Mitten bei **28 px**, aber die Inhalte bei **21,336 px** (Marke), **22 px** (Suche/Archiv) und **28 px** (Avatar). Marke und Profil hatten 48 px breite Buttons, Icon-Buttons 44 px.

Der Fix verwendet ein gemeinsames 44 × 44 px großes Flex-Raster mit `justify-content: center`, `align-items: center`, ohne horizontales Padding oder Gap. Die vorhandene responsive Rail-Breite und die breite Sidebar bleiben erhalten. Reguläre Rail-Icons verwenden 20 px; Marke und Avatar behalten ihre vorgesehenen Größen. Auf Tablet/Mobile bleibt die Chat-Rail gemäß bestehender Navigation ausgeblendet.

Die bereitgestellten lokalen PNG-/HTML-Referenzen wurden hinsichtlich Struktur, Interaktion und Geometrie geprüft. Aus ihnen wurden keine CSS-Bundles, Komponenten oder Icondateien übernommen. Die Evidenz enthält ausschließlich synthetische Chats.

## Verhalten

Desktop-Aktionen liegen rechts über der Chatzeile und sind im Normalzustand unsichtbar und nicht fokussierbar (`visibility: hidden`). Hover, Fokus innerhalb der Zeile und ein offenes Menü zeigen sie. Der Titel erhält nur während der Interaktion Platz für die Aktionen; Zeilenhöhe und Nachbarzeilen bleiben stabil. Auf Geräten ohne Hover oder mit grobem Pointer sind die Aktionen dauerhaft erreichbar und mindestens 44 × 44 CSS-Pixel groß.

Das Menü nutzt horizontale Lucide-Ellipsis sowie getrennte Pin-/Unpin-Icons mit 16 px. Die Chatzeile dient als Menüanker; auf Desktop öffnet das Menü vollständig rechts neben der Zeile. Im mobilen Drawer öffnet es darunter, damit der Trigger weiter direkt antippbar bleibt. Die vorhandene Kollisionserkennung priorisiert Viewport-Grenzen, und das Portal verhindert Abschneiden am Sidebar-Overflow. Escape, erneuter Trigger-Klick, Außenklick, Pfeiltasten und Enter bleiben Nuxt-UI-Menüfunktionen. Menüpunkte sind auf Touchgeräten ebenfalls mindestens 44 px hoch. Das Wiederherstellen des Fokus berücksichtigt versteckte Desktop-Aktionen und beim Wechsel zwischen Gruppen neu gerenderte Zeilen. Desktop-Inhalt und mobiler Drawer behalten jeweils ihren eigenen Dropdown-Zustand.

Pin-Aktionen werden erst nach bestätigtem Server-Update angezeigt. Doppelte gleichzeitige Anfragen sind deaktiviert; Erfolg oder Fehler wird über den bestehenden Statusbereich angekündigt. Aktive Conversation, Titel und Nachrichtenverlauf werden durch Pin/Unpin nicht verändert.

## Migration und API

`0013_conversation_pinning` ergänzt `chat_conversation.pinned_at TIMESTAMPTZ NULL` sowie einen partiellen Index auf `(owner_id, pinned_at DESC, id DESC)` für nicht gelöschte, nicht archivierte, fixierte Chats. Die Migration folgt auf `0012_conversation_visibility` aus `main`. Bestehende Daten und der Sichtbarkeitsstatus vorbereiteter Chats werden beim Upgrade und beim Rollback erhalten. Readiness erwartet die neue Migration.

Die bestehende PATCH-API akzeptiert genau eine Änderung zusammen mit der vorhandenen Version:

```json
{ "pinned": true, "version": 7 }
```

`pinned: false` löst die Fixierung. Wiederholungen mit aktueller Version ändern weder `pinned_at` noch die Revision, wenn der Status bereits stimmt. Veraltete Versionen erhalten weiterhin `409 VERSION_CONFLICT`; Owner-fremde oder gelöschte IDs bleiben `404`. Pin/Unpin verändert `updated_at` nicht und erhält damit die chronologische Position normaler Chats.

Jede Conversation-Antwort enthält `pinnedAt`. Der vorhandene lokale Chat-Import übernimmt das optionale Feld ebenfalls; wiederholter Import überschreibt keine inzwischen serverseitig geänderte Fixierung. OpenAPI, WebSocket-Schema und generierte TypeScript-Typen werden mit `scripts/generate-api.mjs` synchronisiert.

`GET /api/v1/conversations?pinned=true` paginiert unabhängig nach `(pinned_at, id)` absteigend und schließt Archive aus. `pinned=false` liefert die normale chronologische Liste ohne Pins. Ohne Filter bleibt das bisherige API-/Suchverhalten erhalten. Cursor sind an Owner, Pin-Filter, Archivfilter und Suchanfrage gebunden.

Die Sidebar lädt zunächst jeweils höchstens 50 Metadatensätze; weitere Pins werden über „Weitere fixierte Chats laden“ abgefragt. Auch Monate alte Chats erscheinen damit unabhängig von der normalen ersten Seite. Beide Sidebar-Fenster bleiben auf 500 IDs begrenzt und bieten bei einem verschobenen Fenster das Laden der neuesten Chats an. Nachrichten werden für diese Abfragen nicht geladen; vorhandene History-Cache-Grenzen bleiben erhalten.

Pin- und Archivänderungen senden `chat.conversation.updated`. Das ergänzte Ereignis `chat.conversation.deleted` enthält ID und Conversation-Version, damit gelöschte Pins auch in anderen Tabs verschwinden. Begrenzte Löschmarkierungen verhindern die Wiederaufnahme durch verspätete Metadaten; Reconnects gleichen bekannte IDs mit PostgreSQL ab und erkennen zusätzlich neu entstandene Pin-Seiten. Alte Pin-Events und verspätete Seitenantworten werden anhand der vorhandenen Conversation-Version verworfen.

## Visuelle Evidenz

Vorher-Bilder und Geometrie: `evidence/before-{Breite}-{light|dark}.png` beziehungsweise `-geometry.json`.

Nachher-Bilder: `evidence/after-{Breite}-{light|dark}-{Zustand}.png`; Zustände sind `normal`, `hover`, `menu`, `pin-hover`, `pinned` und auf Touchgrößen zusätzlich `mobile-sidebar`. Die Desktop-Geometrie wird ebenfalls als JSON gespeichert.

Getestete Viewports: **1700 × 900, 1440 × 900, 768 × 1024 und 390 × 844**, jeweils Light/Dark. Die Vorher-Aufnahmen zeigen eine reduzierte synthetische Liste; die Nachher-Aufnahmen eine synthetische Unterhaltung mit drei Chatzeilen. Der Rail-Vergleich erfolgt im identischen Viewport anhand der tatsächlichen DOM-Geometrie.

| Vergleich | Vorher | Nachher |
| --- | --- | --- |
| 1440 × 900 Light | [Vorher](evidence/before-1440-light.png) | [Normal](evidence/after-1440-light-normal.png) / [Menü](evidence/after-1440-light-menu.png) |
| 1440 × 900 Dark | [Vorher](evidence/before-1440-dark.png) | [Normal](evidence/after-1440-dark-normal.png) / [Menü](evidence/after-1440-dark-menu.png) |
| 1700 × 900 Light / Dark | [Light](evidence/before-1700-light.png) / [Dark](evidence/before-1700-dark.png) | [Light](evidence/after-1700-light-pinned.png) / [Dark](evidence/after-1700-dark-pinned.png) |
| 768 × 1024 Light / Dark | [Light](evidence/before-768-light.png) / [Dark](evidence/before-768-dark.png) | [Light](evidence/after-768-light-mobile-sidebar.png) / [Dark](evidence/after-768-dark-mobile-sidebar.png) |
| 390 × 844 Light / Dark | [Light](evidence/before-390-light.png) / [Dark](evidence/before-390-dark.png) | [Light](evidence/after-390-light-mobile-sidebar.png) / [Dark](evidence/after-390-dark-mobile-sidebar.png) |

## Validierung und Einschränkungen

Neue Tests decken direkte Aktionen, Gruppierung, Sortierung, Duplikate, Versionskonflikte, begrenzte Pin-Fenster, stale Events/Seitenantworten, Reconnect-Pagination, Migration, Owner-Prüfung, Idempotenz, Backend-Neustart, unabhängige Pagination, Archive und Löschung ab. Playwright misst die Icon-, Button- und Avatar-Mittelpunkte mit maximal 1 CSS-Pixel Toleranz und prüft Hover, Fokus, Menüs, Sidebar-Umschaltung, Touchziele sowie Persistenz und Synchronisation zwischen zwei Tabs. Die größte gemessene Abweichung zwischen den Icon-Mittelpunkten beträgt **0,0078125 CSS-Pixel**, gegenüber der Rail-Achse höchstens **0,015625 CSS-Pixel**.

| Lokale Prüfung | Ergebnis |
| --- | --- |
| ESLint / Ruff inkl. Formatprüfung | Bestanden |
| Nuxt / Vue-tsc / Tools-TypeScript / Pyright | Bestanden |
| API-Drift-Check | Bestanden |
| Backend Unit / Contract / lokale LLM-Integration | 516 bestanden |
| PostgreSQL-Integration, vollständige Suite | 124 bestanden, einschließlich aller Caddy-/nginx-Proxy-Tests |
| Frontend Unit, vollständige Suite | 468 bestanden |
| Gezielte Sidebar-/Import-Unit-Tests | 63 bestanden |
| Playwright Mock, zwei breitere Regressionstestläufe | 170 beziehungsweise 86 bestanden; teilweise überlappende Fälle |
| Finale Playwright-Geometrie-/Screenshot-Matrix | 8 bestanden |
| Finale Playwright-WebSocket-Pin-/Sidebar-Fälle | 6 bestanden |
| Finale Playwright-HTTP-Titeltests | 16 bestanden |
| Playwright Löschfehler / Retry / Benachrichtigung | 1 bestanden |
| Produktionsbuild Nuxt / Python-Paket | Bestanden |

Beim Abgleich mit `main` (`06c9301`) wurden die bisherigen Testkorrekturen für das aktuelle Benachrichtigungssystem übernommen. Vorbereitete Chats bleiben auch bei vorhandenem Pin-Metadatum unsichtbar, bis eine aktuelle Serverrevision sie freigibt; veraltete Events überschreiben diesen Zustand nicht. Der Touch-Geometrietest wartet auf das Ende der Drawer-/Menüanimation und berücksichtigt numerische Chromium-Rundungen mit 0,01 CSS-Pixel Toleranz. Ein Reload-Test wartet vor Enter auf den sendebereiten Composer.

In der lokalen Demo bleibt die vorhandene lokale Speicherung bestehen. Der WebSocket-/Produktionsmodus verwendet ausschließlich PostgreSQL für Fixierungen. Die Migration wurde nur in separat angelegten lokalen Testdatenbanken ausgeführt; es gibt keine Produktivserveränderung und keinen automatischen Merge.
