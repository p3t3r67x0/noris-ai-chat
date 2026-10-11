# Textauswahl und Textreferenzen

Eine abgeschlossene Auswahl im Text einer Benutzer- oder Assistentennachricht zeigt die schwebende Aktion **noris AI fragen**. Die Aktion übernimmt den exakten Browser-Auswahltext als Attachment in den vorhandenen Composer, fokussiert das Eingabefeld und erhält dessen Entwurf. Es wird keine Nachricht automatisch gesendet. Mehrere Referenzen sind möglich; jede lässt sich einzeln entfernen. Ein aufklappbarer Auszug macht den vollständigen Text auch auf kleinen Bildschirmen zugänglich.

## Wiederverwendete Komponenten und Abläufe

| Bestehender Bestandteil | Verwendung |
| --- | --- |
| `ChatMessage.vue`, `MarkdownContent`, `CodeBlock.vue` | Auswahlgrenzen in vorhandenen Nachrichten und gerendertem Markdown |
| `ChatTimeline.vue`, `useChatScroll` | Auswahl innerhalb des Nachrichten-Scrollcontainers |
| `ChatWorkspace.vue` | Übergabe zum bestehenden Attachment-State und Composer-Fokus |
| `ChatComposer.vue`, `UChatPrompt`, `useComposerAutosize` | Attachment-Header, Entfernen, Fokus, unveränderte Textarea- und Resize-Mechanik |
| `useChatAttachments` | Gemeinsame Slots, Status, Quoten, Retry, Entfernen und Wiederherstellung für Dateien und Textreferenzen |
| `ChatAttachment`, `AttachmentService`, `ChatRepository` | Besitzerprüfung, PostgreSQL-Speicherung, Nachrichtenzuordnung, Bereinigung |
| WebSocket v1, `GenerationManager`, `LLMGateway` | Vorhandener Nachrichtenpfad und unveränderte Kontext-, Token-, Byte- und Budgetprüfungen |

Neu ist ausschließlich die UI-Komponente `ChatTextSelection.vue` für die schwebende Aktion. `lib/chat/selection.ts` enthält Auswahlvalidierung und Positionierungsberechnung; `lib/chat/textReferences.ts` bereitet Referenzen für die bereits vorhandenen zustandslosen Transporte auf. Es gibt keinen zusätzlichen Composer, keine neue Chat-Architektur und keine zusätzliche UI-Abhängigkeit.

## Auswahl und Bedienung

Die Browser Selection API liefert den Text und eine Kopie des Range. Anfang und Ende müssen im selben auswählbaren Nachrichteninhalt liegen. Mehrere Absätze, Listen, Markdown-Formatierung und Code sind erlaubt. Composer, Steuerelemente, Sidebar, Dialoge, leere Auswahlen und Auswahlen über Nachrichtengrenzen werden ignoriert.

Während einer Maus-/Touch-Auswahl oder einer mit Shift gehaltenen Tastaturauswahl bleibt die Aktion verborgen. Pointer-Up bzw. Shift-Up zeigt sie; native Touch-Handle-Änderungen werden nach 160 ms stabiler Auswahl verarbeitet. `Range.getClientRects()` bestimmt die erste sichtbare Zeile. Die Position berücksichtigt Scrollclipping und den Visual Viewport; ohne Platz oberhalb weicht die Aktion nach unten aus. Scrollen und Größenänderungen aktualisieren ihre Position. Ein natives manuelles Popover in der Browser-Top-Layer verhindert Abschneiden oder Überlagern durch Chat-Komponenten. Seine feste Position verursacht keinen Layout-Shift.

Pointer-Down auf der Aktion verhindert, dass der Browser die Auswahl vor dem Klick löscht. Die Auswahlaktion stiehlt keinen Fokus. Tab aus dem Nachrichtenverlauf erreicht die Aktion, Enter/Space aktiviert sie, Escape schließt sie. Ein Klick außerhalb schließt sie ebenfalls. Fokusmarkierungen, zugängliche Beschriftungen und der vorhandene mindestens 44 px große Touchbereich bleiben nutzbar. Die Aktion verwendet keine Animation und benötigt damit keine Ausnahme für Reduced Motion.

## Datenmodell und Migration

Textreferenzen sind bestehende Attachments mit `mime_type = text/plain` und `status = ready`:

- `ChatAttachment.id` ist die Referenz-ID.
- `conversation_id` und `message_id` behalten die vorhandene Zielzuordnung.
- `extracted_text` speichert den exakten ausgewählten Text einschließlich Leerraum.
- Neu: nullable UUID-Spalten `source_message_id` und `source_conversation_id` speichern die Herkunft. Eine Check-Constraint fordert beide oder keine der beiden Angaben.
- Dateiname, Größe in UTF-8-Bytes, SHA-256 und Erstellungszeit verwenden die bestehenden Felder.

Migration `0007_text_references` ergänzt nur diese zwei Spalten und die Check-Constraint in `chat_attachment`. Sie ist notwendig, weil das vorhandene Modell keine Herkunftsmetadaten enthält. Vorhandene Datei- und Nachrichtenzeilen bleiben erhalten. Der Referenztext wird einmal im vorhandenen Textfeld gespeichert; es entsteht keine Referenztabelle und keine zusätzliche Datei auf dem Storage-Volume. Die Herkunft ist Snapshot-Metadatum und bewusst kein löschender Foreign Key: Eine gespeicherte Referenz kann die Löschung ihrer Quellkonversation überleben.

Vor Start des aktualisierten Backends wie üblich `make migrate` ausführen. Der Downgrade entfernt die Herkunftsfelder; der gespeicherte Attachment-Text bleibt erhalten.

## API-Vertrag

`POST /api/v1/chat/attachments/references` verwendet die vorhandene authentifizierte Attachment-API und deren Herkunftsprüfung für Requests:

```json
{
  "conversationId": "<Zielkonversation-UUID>",
  "sourceConversationId": "<Quellkonversation-UUID>",
  "sourceMessageId": "<Quellnachricht-UUID>",
  "text": "Exakter ausgewählter Text"
}
```

Die `201`-Antwort ist `AttachmentResponse` mit dem optionalen Feld `textReference: { sourceMessageId, sourceConversationId, text }`. Reguläre Dateien haben `textReference: null`. Die Grenzen-API ergänzt `maxReferenceChars` entsprechend `NORIS_CHAT_ATTACHMENT_MAX_TEXT_CHARS` (standardmäßig 16.000, maximal 32.000). Datei-/Speicher-/Anzahlgrenzen gelten gemeinsam für Dateien und Referenzen.

Liste, Löschen, Download und die Nachrichten-/Pfadantworten verwenden die vorhandenen Endpunkte. Ein Referenzdownload liefert den exakten UTF-8-Text mit den bestehenden privaten Download-Headern. Der WebSocket-Generate-Request verwendet weiterhin `attachmentIds`; es gibt kein neues Kommando und keinen Protokollversionswechsel. OpenAPI, WebSocket-JSON-Schema und generierte TypeScript-Verträge werden gemeinsam aktualisiert.

## Modellkontext, Reload und Zweige

Der Server prüft den Besitz der Zielkonversation und der Quellnachricht. Der Text ist eine vom Benutzer bereitgestellte Momentaufnahme des gerenderten Inhalts; die API behauptet keine serverseitige Übereinstimmung mit dem Markdown-Quelltext.

Beim Senden ordnet der vorhandene Generationstransaktionspfad die bestätigten Attachments der Benutzernachricht zu. `attachment_context` ergänzt Text und Herkunft als JSON unter **untrusted input** innerhalb derselben Benutzerrolle. Referenzen erzeugen keine privilegierten Systemnachrichten. Die vorhandenen Gateway-Limits zählen den vollständigen ergänzten Inhalt; zu große Anfragen werden abgelehnt. Es wird nichts still gekürzt.

Gesendete Referenzen werden aus PostgreSQL zusammen mit Nachrichten und Pfaden geladen. Ungesendete Referenzen werden durch die bestehende Attachment-Liste wiederhergestellt. Für den lokalen Demo-/SSE-Betrieb nutzt derselbe Attachment-State einen lokalen Attachment-Cache; gesendete Referenzen bleiben im vorhandenen Chat-Snapshot. Zustandslose Anfragen ergänzen Referenzen ebenfalls in Benutzerrollen.

Regeneration und Fortsetzung verwenden die gespeicherten Attachments des ursprünglichen Inputs. Beim Bearbeiten einer referenzierenden Benutzernachricht erhält der neue immutable Zweig eigene Textreferenz-Attachments. Die ursprünglichen Attachments bleiben am ursprünglichen Input. Das vorhandene `chat.message.created`-Event synchronisiert die kanonischen Attachment-IDs in den bestehenden Frontend-State. Attachment-Reihenfolge ist über Erstellungszeit und ID deterministisch, damit Regeneration denselben Kontext verwendet.

## Verifikation

Die neuen Unit-, PostgreSQL-/WebSocket-Integrations- und Playwright-Tests decken einfache und mehrzeilige Auswahl, Markdown/Code, Absätze, Viewportposition, reale Mausauswahl, Touch-Events, Tastaturbedienung, Auswahlabschluss, Entfernen, mehrere Referenzen, Entwurfserhalt, Versand, Modellkontext, Limits, Reload, Serverneustart, Regeneration und bearbeitete Zweige ab. Screenshot-Baselines für Aktion und Composer liegen für Desktop und Mobile unter `frontend/tests/e2e/__screenshots__/linux/`.

| Prüfung | Ergebnis |
| --- | --- |
| Frontend-Unit-Tests | 278 bestanden |
| Backend-Unit-, Vertrags- und lokale Provider-Integrationstests | 357 bestanden |
| Vollständige PostgreSQL-/Proxy-Integrationssuite | 63 bestanden |
| Erweiterte Referenz-Integrationssuite einschließlich Besitzer- und Kopierquotenprüfung | 10 bestanden |
| Bestehende Desktop-/Mobile-Browser-Regressionssuite einschließlich Referenztests | 288 bestanden, 19 gerätebedingt übersprungen |
| Abschließende Auswahl-/Referenz-Browserprüfung mit Screenshotvergleich | 15 bestanden, 1 mobiler Maus-Drag-Test übersprungen |
| WebSocket-Browserregression | 64 weitere Tests bestanden, 6 gerätebedingt übersprungen |
| Abschließende WebSocket-Persistenzsuite einschließlich korrigierter Referenztests | 14 bestanden, Desktop und Mobile |
| ESLint, Ruff und Ruff-Formatierung | erfolgreich |
| Nuxt-/Vue-/Test-TypeScript, Tool-TypeScript und striktes Pyright | erfolgreich |
| OpenAPI-/WebSocket-Vertragsdrift und Alembic-Schemadrift | keine Abweichung |

Die mobilen Maus-Drag-Tests werden bewusst übersprungen; mobile Auswahl wird über Touch-Events und die native Selection API geprüft. Der erste neue WebSocket-Test las den Entwurf zunächst über einen nur beschreibbaren Endpunkt und schlug damit auf beiden Geräten fehl. Nach Umstellung auf die vorhandene Entwurfsliste bestanden beide Referenztests und die gesamte Persistenz-Browsersuite.

## Offene Einschränkungen

- Der in der Aufgabe erwähnte ChatGPT-Screenshot war nicht als Datei verfügbar. Das Styling folgt dem beschriebenen Verhalten und den vorhandenen Designvariablen; ein pixelgenauer Referenzabgleich war nicht möglich.
- Mobile-Automation verwendet Chromium/Pixel-7-Emulation und native Selection API mit Touch-Events. Echte iOS-/Android-Auswahlhandles und Bildschirmtastaturen benötigen zusätzlich eine Prüfung auf Hardware.
- Auswahlen über mehrere Nachrichten werden abgelehnt, weil eine Referenz genau eine Quellnachricht hat.
- Die bestehende Attachment-Bereinigung entfernt ungesendete Referenzen nach der konfigurierten Orphan-Frist (standardmäßig 24 Stunden).
- Der bestehende Import lokaler Demo-Chats in PostgreSQL importiert weiterhin Nachrichtentext und Entwürfe; lokale Attachment-Metadaten werden dabei wie bisher nicht importiert.
