# Abweichungen vor der Korrektur des Plus-Menüs

Stand: 2026-10-12. Die Vorher-Bilder unter `before/` wurden aus der bereits vorhandenen Umsetzung mit synthetischen Chatdaten erzeugt. Sie sind nicht die vom Auftrag erwähnten Ist-/Referenz-Anhänge: Diese beiden Bilder wurden im Gespräch bisher nicht übermittelt.

Die folgende Liste beruht auf den gemessenen Vorher-Screenshots, dem vorhandenen CSS und den ausdrücklich genannten Sollwerten. Eine vollständige bildbasierte Gegenüberstellung bleibt bis zum Eingang der beiden Referenzbilder offen.

| Merkmal | Nachgewiesener Ist-Zustand vor der Korrektur | Verbindliches Soll / Korrektur |
| --- | --- | --- |
| Desktopbreite | 544 px bei 1440 und 1700 px Viewport | 700–880 px bei ausreichend Platz; responsiv begrenzen. |
| Desktopschrift der Beschreibung | 12 px | 14 px; die Beschreibung soll deutlich lesbar rechts neben dem Titel stehen. |
| Desktopschrift des Titels | 14 px, normales Gewicht | 14–15 px; beim Verbreitern auf 15 px vereinheitlichen. |
| Beschreibungsspalte | Flex-Umbruch direkt nach unterschiedlich langen Titeln | Einheitliche Titel-/Beschreibungsspalten bei ausreichend Platz. |
| Rechte Statushinweise | Fünf Hinweise „Noch nicht verfügbar“, 10 px, teils zweizeilig | Vollständig aus der Darstellung entfernen; fehlende Funktionen über `disabled`/`aria-disabled` und fehlende Handler behandeln. |
| Desktopzeilenhöhe / Menühöhe | 44 px / 274 px | Weniger gedrängte Einträge; 48 px mit 8 px Außenpolster ergeben 306 px. Die genaue Referenzhöhe kann ohne Bild nicht gemessen werden. |
| Mobilezeilen | Mindestens 56 px, Beschreibungen darunter; Statushinweise beanspruchen zusätzliche Breite | Touchhöhe erhalten, volle Breite für Titel/Beschreibung nutzen, keine rechten Hinweise. |
| Beschreibungen | „Echtzeitinformationen“, „Detaillierte Recherche“ | „Echtzeitinformationen suchen“, „Detaillierten Bericht erstellen“. |
| Icons | Sechs einheitliche 20-px-Lucide-Icons sind nach der bereits erfolgten Bundle-Ergänzung vorhanden | Alle sechs Icons in der finalen Darstellung und per Browsertest prüfen. |
| Position / Layout-Shift | Oberhalb des Composers, am Plus ausgerichtet; bei 390 px auf 12 px Randabstand verschoben; kein Layout-Shift | Verhalten erhalten und zusätzlich bei Tabletbreite sowie während Größenänderungen prüfen. |
| Hintergrund / Rahmen / Rundung / Schatten | Light/Dark-Tokens, 1-px-Rahmen, 16-px-Radius, Nuxt-UI-Schatten | Beibehalten, bis die Referenz eine konkrete abweichende Messung erlaubt. Derzeit ist kein Pixelvergleich möglich. |
| Hover / Tastaturfokus | Hover-/Highlight-Hintergrund; keine eigens definierte sichtbare Fokusoutline | Einheitlichen Hover für verfügbare Aktionen erhalten und sichtbaren Tastaturfokus ergänzen. Nicht implementierte Aktionen bleiben deaktiviert. |
| Plus-Button geschlossen | Generische Nuxt-UI-Ghost-Fläche mit komponentenseitiger Rundung; keine gezielte Kreisgestaltung | Transparenter Grundzustand, subtiler kreisförmiger Hover, vorhandene Klickfläche und Iconposition erhalten. |
| Plus-Button geöffnet | `data-state="open"` vorhanden, aber ohne dauerhaftes Active-Styling | 44-px-Kreis aus vorhandenen Light-/Dark-Tokens ausschließlich über diesen Open-State; ohne Rahmen, Schatten, Scale oder Layout-Shift. |
| Plus-Button Animation / Fokus | Allgemeine Fokus- und Reduced-Motion-Regeln vorhanden | Sichtbare 2-px-Fokusoutline und 100-ms-Hintergrundtransition; vorhandene Reduced-Motion-Regel anwenden. |

## Nachgewiesene Funktionsursachen

1. Die Upload-Freigabe hängt an Backend-Verfügbarkeit und geladenen Attachment-Limits, nicht an einer vom Benutzer manuell anzulegenden Unterhaltung. `useChatAttachments.add` und `ChatBackend.ensure` legen einen neuen Chat bereits automatisch an.
2. Die bisherige Erklärung „Upload benötigt eine gespeicherte WebSocket-Unterhaltung“ ist irreführend, wenn der konfigurierte WebSocket-Modus wegen eines Backend-Fehlers noch nicht bereit ist. Die Erklärung muss zwischen Demo-Modus, laufendem Laden und einem tatsächlichen Backend-/Uploadfehler unterscheiden.
3. In den lokalen Container-Logs zu `http://localhost:8080/` ist `GET /api/v1/conversations/{id}/active-path?limit=50` mit HTTP 500 nachgewiesen. SQLAlchemy meldet `psycopg.errors.UndefinedColumn`: `chat_attachment.pdf_sections` fehlt. Der generische Backend-Handler liefert `INTERNAL_ERROR` / „An internal error occurred“; `responseError` übernimmt die bereinigte Servermeldung und `useChatBackend` zeigt sie als Ladefehler. Die Initialisierung bleibt dadurch unvollständig und der Upload gesperrt.
4. Die vorhandene additive Migration `0008_pdf_sections` ergänzt `pdf_sections` und `pdf_page_count`. Diese Betriebsursache wird in der isolierten Docker-Testdatenbank reproduziert und mit derselben vorhandenen Migration behoben. Die laufende Datenbank auf Port 8080 wird im Rahmen dieses Auftrags nicht migriert oder verändert.
5. Die vorher bereits gefundene Entwurfsübernahme beim ersten Attachment sowie die Behandlung leerer/abgebrochener Dateiauswahlen bleiben erhalten.

Nachtrag zur Verifikation: Der isolierte Integrationstest bestätigt HTTP 500 auf Schema 0007 und HTTP 200/201 nach der vorhandenen Migration 0008. Die späteren reinen GET-Nachtests auf `localhost:8080` liefern für Readiness, Unterhaltungsliste, neuesten Active Path und Attachment-Limits jeweils HTTP 200; die Log-Ursache ist damit historisch belegt, aber bei diesen aktuellen Aufrufen nicht mehr reproduzierbar.

## Grenzen der visuellen Abnahme

Ohne die beiden Bildanhänge kann diese Liste keine unbekannten Referenzmaße für Padding, Höhe, Farben, Schatten, Rundungen, Hover und Fokus behaupten. Die Umsetzung kann gegen die expliziten Zahlen und Interaktionsanforderungen geprüft werden; die geforderte Bildabnahme bleibt offen.
