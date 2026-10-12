# Dateibibliothek: vorhandene Attachments wiederverwenden

Status: geplant; kein zweiter Dateispeicher. Stand: 2026-10-12.

Übergreifende Regeln: [Tool-Architektur](TOOL-ARCHITECTURE.md); Umsetzung: [Roadmap](FEATURE-ROADMAP.md).

## 1. Bestandsaufnahme

`AttachmentService` und `/chat/attachments` speichern bereits TXT, Markdown, PDF, PNG und JPEG mit owner, conversation, SHA-256, MIME, Quota, privatem `storage_key`, Text-/PDFextraktion und sicherem Download. `useChatAttachments` hält Uploads je Unterhaltung, lädt pending Attachments wieder und übergibt ausschließlich bestätigte IDs an den vorhandenen Chatpfad. Textreferenzen sind eigenständige unveränderliche DBsnapshots; sie haben einen zufälligen storage_key, aber keine physische Datei.

Die heutige GET-Liste verlangt `conversationId`, begrenzt auf 200 und ist kein globaler Bibliotheksindex. Ein Attachment gehört über `conversation_id` und `message_id` höchstens einer Nachricht. `begin_generation` weist Attachments anderer Chats oder bereits anderer Nachrichten ab. `remove` verweigert gebundene Attachments; `cleanup` entfernt ungebundene alte Attachments und Dateien gelöschter Chats. `get` setzt heute einen nicht gelöschten Ursprungschat voraus. Diese Invarianten verhindern eine Bibliothek allein durch einen neuen Picker.

## 2. Fehlende Komponenten

Nötig sind ownerbezogene paginierte Bibliotheksabfragen, ein Picker, eine persistente Viele-zu-viele-Bindung an bestehende Nachrichten/Entwürfe, optionales Pinning und eine gemeinsame Retention-/Quotalogik. Upload, Extraktion, PDFseiten, Bildvorbereitung, sichere Dateiauslieferung, Attachment-IDs und physisches Volume bleiben dieselben.

Entscheidung: `ChatAttachment` bleibt **die canonical Ressource**. Neue Bindungen referenzieren dieselbe ID und dieselben Bytes. Keine Kopie per Browserdownload/reupload, keine zweite Blobtabelle mit eigenem Pfad, kein weiteres Volume und keine neue S3speicherung. Die bestehende unique-storage-key-Constraint bleibt.

## 3. Datenmodell und Migrationsstrategie

| Modell | Felder / Constraints |
| --- | --- |
| `ChatAttachment` | bestehende Felder unverändert erhalten; additive originKind (`upload/text_reference/generated_image/sketch`) und optionale Ergebnisprovenienz. `conversation_id`/`message_id` zunächst Legacy-Ursprungsprojektion, nicht mehr alleinige Mitgliedschaft. |
| `chat_attachment_link` | id, attachment_id, owner_id, conversation_id, nullable message_id, purpose=`input/output`, created_at, expires_at für pending Links, deleted_at; zusammengesetzte Message-/Conversation-FK; unique active `(attachment_id,message_id,purpose)` und partieller unique Pendinglink je `(attachment_id,conversation_id,purpose)`. |
| `chat_library_item` | attachment_id + owner_id, pinned_at, hidden_at; optionaler Bibliothekszustand ohne Dateibytes. Fehlender Datensatz bedeutet normale Sichtbarkeit aktiver Ressourcen. |
| `chat_resource_action` | gemeinsames idempotentes Nutzeraktionsrecord aus der Tool-Architektur; bei library.attach zusammen mit allen Links committen. Wiederholung liest dieselbe gespeicherte Responseprojektion. |

Ein Originattachment darf mehreren Inputnachrichten, Bildoutputs und pending Entwürfen gehören. Link-Owner muss dem canonical Owner entsprechen; composite unique/FK oder gleichwertige DBconstraint plus Repositoryprüfung, keine bloße UIbehauptung. Attachments dürfen nie nach Ownerwechsel „übernommen“ werden.

Expand/backfill/validate:

1. Additive Tabellen/Indizes anlegen. Bestehende nicht gelöschte Attachments in genau einen originbezogenen Link backfillen; message_id-null bedeutet pending. Textreferenzen ohne Dateibytes bleiben korrekt.
2. Zentralen Attachmentreader auf Linkprojektionen umstellen. `ChatMessage.attachments`, `message_response`, `attachment_context`, `pdf_request` und `_image_request` erhalten weiterhin canonical Attachmentdaten; Membership und Kontextconversation kommen aus dem Link. Keine Neuauswertung/Neu-Extraktion bestehender PDFs.
3. Upload und Referenzcreation schreiben canonical Ressource und initialen Link atomar; der alte Responsevertrag bleibt nach conversation/message projiziert. `AttachmentResponse.id` bleibt canonical ID, `conversationId/messageId` bezeichnen die ausgewählte Bindung.
4. `begin_generation` bewegt nur target-pending Links auf die Inputnachricht oder bestätigt bestehende idempotente Links. Wiederverwendung aus einem anderen Chat erfordert zuvor authentifiziertes `library.attach`; bloße fremde IDs im Generatecommand werden weiter abgewiesen.
5. Legacy- und Linkreader vergleichen, Migration wiederholt prüfen, anschließend neue Membershipreader verpflichtend aktivieren. Die alten Spalten nicht in derselben PR entfernen. Flags schalten nur Bibliotheksaktionen aus; nach Mehrfachbindungen niemals auf einen verlustbehafteten Legacyreader zurückrollen.

Upload/Textreferenzen bleiben über dieselbe public API nutzbar. Regenerierung verwendet dieselbe Inputbindung. Editierte Nachrichten erhalten neue Links auf unveränderte Dateien; bestehende spezielle Textreferenzsnapshot-Vererbung muss erhalten bleiben und getestet werden. Eine spätere Vereinheitlichung dieser Referenzkopien ist keine Voraussetzung.

### Quota, Entfernen und Lebensdauer

Dateibytes zählen **einmal je canonical Attachment**, auch bei mehreren Links. Bestehende Defaultquota: 10 MiB je Datei, 100 MiB je Owner, 5 pending Dateien je Nachricht; aktuelle globale Ressourcenzahlgrenze 200 beibehalten. Linkzahl zusätzlich begrenzen, Vorschlag 2.000 aktive Links pro Owner; keine unbeschränkte Quotaumgehung durch Metadaten.

Alle aktiven Attachments mit aktiver Chatbindung werden im Picker entdeckt. Pin hält eine Ressource unabhängig von ihrer Ursprungconversation; hiding entfernt nur den Bibliothekseintrag aus der Liste. Textreferenzen werden zunächst nicht automatisch als „Datei“ in der Bibliothek angezeigt, bleiben aber bestehende Chatattachments. Scanned PDFs ohne extrahierbaren Text sind downloadbar; Modelanalyse ist weiterhin nicht behauptet.

Pendinglinkentfernung, Verbergen in der Bibliothek und endgültige Dateilöschung sind verschiedene Operationen. Ein Link wird nie durch Entfernen eines anderen Chats gelöscht. Soft Delete eines Chats macht dessen Links sofort unzugänglich; Dateien bleiben bei anderen aktiven Links oder gültigem Pin verfügbar. Archivierung erlaubt Lesen/Quelle auswählen, verbietet neue Zielbindungen in das Archiv.

Cleanup wird **vor** Freigabe neuer Links umgestellt: Pendinglinks nach bestehender Orphanfrist verfallen lassen; canonical Datei erst löschen, wenn keine aktive Nachricht, kein gültiger pending Link, kein Pin und kein noch finalisierender Toolresultatbezug vorliegt. Librarylisting allein pinnt nichts. Snapshotreferenzen bleiben entsprechend ihrer eigenen Bindungen erhalten. Generationresultate schützen nur bis zur atomaren Outputbindung, kein unbegrenztes verstecktes Pinning.

`AttachmentService.get/image_input` prüft Owner und angeforderte aktive Bindung/Pin anstelle der bisherigen alleinigen Ursprungsjoinprüfung. Vorschau des gleichen canonical Bilds in mehreren Chats lädt weiter dieselben geprüften Bytes. Contentzugriff auf origin-gelöschte, aber legitim anderweitig gebundene Ressourcen muss möglich bleiben; komplett gelöschte Ressourcen weiterhin 404.

## 4. API-Verträge

Neue Routen unter `/api/v1`, alle mit bestehendem `ChatAccess` und Originprüfung bei Writes:

| Route | Eingabe / Ausgabe |
| --- | --- |
| GET `/chat/library` | `q` ≤200 Zeichen, erlaubte MIMEgruppen, `cursor`, `limit` 1–50 → `{items:[LibraryItem],nextCursor,hasMore}`. Keine owner_id akzeptieren. |
| POST `/chat/library/attach` | `{requestId,conversationId,attachmentIds:[UUID]}` → `{attachments:AttachmentResponse[]}` nach atomarem Targetcheck. Maximal verbleibende Nachrichtenslots. |
| DELETE `/chat/attachments/{id}/links/{conversationId}` | Entfernt nur pending Inputlink dieser Conversation; gebundene Nachrichtenlinks 409. Wiederholter Remove idempotent. |
| PATCH `/chat/library/{id}` | `{pinned:boolean}` → autoritativer LibraryItem; Quota/Owner/Status prüfen. |
| DELETE `/chat/library/{id}` | Verbergen und Pin lösen; aktive Chatlinks und Bytes unverändert bis regelkonformem Cleanup. UI nennt die Operation „Aus Bibliothek entfernen“. |

`LibraryItem`: canonical attachmentId, originalFilename, mimeType, sizeBytes, originKind, createdAt, hasText, modelUsable, pinned, safe Sourceconversationlabel. Keine storage_keys, Serverpfade oder extracted_text in globalen Suchlisten. Keysetcursor bindet Sortierung/Filter und Owner an bestehendes Cursorpattern; default `created_at DESC,id DESC`, Dateinamenssuche, keine Suche in vertraulichem Volltext.

Ein Bibliotheksattach wird über `library.attach.v1` in der gemeinsamen Registry validiert, ist aber eine kurze authentifizierte Ressourcenmutation ohne kostenpflichtigen Hintergrundlauf. Idempotenzrecord bindet requestId an Owner, Ziel und sortierte Attachment-IDs; Wiederholung liefert identischen Linkzustand, andere Argumente 409. Es benötigt keinen künstlichen Assistantknoten oder eigene Generierung.

Bestehendes POST Upload bleibt Rawbody, kein Multipartwechsel. GET chatbezogene Attachmentliste liefert Linkprojektionen mit genau einem pending Eintrag je Datei. Bestehendes DELETE `/chat/attachments/{id}` bleibt für alte ausschließlich origin-pending Uploads gültig; es löst nur diese Legacybindung und löscht canonical Bytes nur bei null verbleibenden Retentionbezügen. Der neue Picker verwendet immer die eindeutige Linkroute.

Fehler: `ATTACHMENT_NOT_FOUND` 404 für fremd/gelöscht, `ATTACHMENT_QUOTA` 413, `ATTACHMENT_IN_USE` 409 für unzulässiges Entfernen, `VERSION_CONFLICT`/Idempotenzkonflikt 409, `ATTACHMENT_INCOMPATIBLE` 422 beim Versand. Zielprüfung und Slotreservation atomar unter derselben Quotalockreihenfolge wie Upload. Kein partielle Erfolgsliste bei unzulässiger Mehrfachauswahl.

## 5. WebSocket-Ereignisse

Picker und Linkmutation verwenden REST; die erfolgreiche Antwort reicht für denselben Composerstate. **Keine erfundene generationId** für eine reine Bibliotheksauswahl. Ein Reload liest pending Links aus dem bestehenden Attachmentendpoint. Tabübergreifende sofortige Draftsync ist zunächst nicht erforderlich und darf später einen eigenen resource-event-Vertrag bekommen.

Beim normalen Versand enthält bestehendes `chat.message.created` die Attachmentprojektion; neue Dateibeziehungen werden mit derselben Generation atomar aufgenommen. Danach bleiben `chat.generation.*` unverändert fachlich zuständig. Tool-/Researchverwendung referenziert dieselben Attachment-IDs; Bildoutputs verwenden v2 `chat.attachment.created`. V1-Nutzer können gewöhnliche neue Attachmentbindungen weiterhin als normale Text-/Visioneingabe verwenden.

## 6. Frontend-UX

Plus → „Aus Bibliothek hinzufügen“ öffnet einen Nuxt-UI-Dialog, Desktop mit Suchfeld, MIMEfilter, paginierter Liste und Mehrfachauswahl; Mobile als Sheet, sichtbare Auswahlzahl und fixierte Hinzufügenaktion. Tastatur: Fokus ins Suchfeld, Tab/Shift-Tab gefangen, Space selektiert, Esc schließt und führt zurück zum Plusbutton/Composer. Keine neue Seite und kein neuer Composer.

Bestätigte Auswahl ruft `ChatBackend.ensure` erst beim Hinzufügen auf und setzt pending UploadEntryprojektionen in `useChatAttachments`; es findet kein Datei-Upload statt. Neues Gespräch übernimmt den bisherigen `__new__`-Entwurf synchron, so wie beim ersten Upload. Abbrechen oder eine leere Auswahl legt keinen Chat an. Nach Bestätigung erscheinen dieselben Attachmentkarten mit Entfernen/Fehlerstatus; Entfernen löst den pending Link.

Bilder/PDFs mit inkompatibler aktueller Modelcapability werden mit nachvollziehbarem Hinweis angezeigt; Versand bleibt nach derselben vorhandenen Modelprüfung gesperrt, bis ein verfügbares kompatibles Modell gewählt oder der Link entfernt ist. Kein automatischer Modellwechsel. Nur explizite Ressourcenvorschau lädt Bildbytes, keine vollständigen Dateien beim Suchlisting. Empty/Loading/Fehler/Retry sind echte Zustände.

## 7. Sicherheitskonzept

Ownerprüfung in Query, Linkservice, Contentreader und Generateaufnahme; kein vom Client festgelegter Owner. Single-Owner bedeutet weiterhin gemeinsame Bibliothek für alle Nutzer desselben Basiczugangs. Entsprechender UI-/Betriebshinweis gehört zur bestehend beschriebenen Betriebsgrenze, keine neu erfundene Userisolation.

Nur vorhandene zugängliche Ressourcen verknüpfen. Der Browser übergibt UUIDs, keine URLs oder Pfade. Die existing Datei-/Parser-/Integritätsgrenzen gelten auch bei Wiederverwendung. Quota zählt Dateien einmal, Links separat. Keine Kopie fremder Ressourcen nach bloßer Kenntnis einer ID. Entfernte Ursprungconversations liefern keine Titel in der Librarymetadatenansicht.

Raceprüfung: Ownerquota-/Attachmentlock vor Linkänderung; Cleanup darf nach einem konkurrierenden Link nicht löschen. Fileunlink erfolgt nur nach autoritativ bestätigter Nullreferenz und lässt sich bei OSError wiederholen. Libraryhide hat keine Berechtigung, aktive Chatbelege zu verändern. Dateien werden nicht via neues öffentliches Staticdirectory ausgeliefert.

## 8. Tests

Unit: Linkprojektion, Canonicalquota, Linklimits, Filter/cursor, Pin/Hide, Sourceprivacy, status ready/stored, Textreferenzen ohne physische Datei und idempotente Auswahl.

PostgreSQLintegration: Backfill mit Altbestand aller unterstützten MIMEtypen, v1-Upload/Textreference weiterhin nutzbar, gleiche Datei in zwei Chats/mehreren Nachrichten, Originalbytes/storage_key unverändert, Quota unverändert, PDFsections unverändert. Ursprungchat löschen bei anderer Bindung/Pin, pending Linkremove, Archivziel, foreign owner, concurrent Upload/Attach/Cleanup, DBrollback nach Slotreservation, repeated migrations und Schema-/FKcheck. Prüfen, dass Fileunlink erst bei letzter Retentionreferenz geschieht.

Providerintegration: BibliothekspDF/Bild über denselben GenerationManager-/Gateway-/image_input-Pfad; vorhandene Folgefrage-/Regenerate-/Continuationtests erweitern. Alleinige Pickerbenutzung löst keinen LLM-/Bildproviderrequest aus.

Playwright Desktop/Mobile: Suche, Pagination, Mehrfachauswahl, leere Liste, MIME-/Modellhinweise, Hinzufügen zum neuen/alten Chat, Entwurf erhalten, Linkremove, Reload, Chatwechsel, Tastatur und Screenkeyboard. Netzassertion: nach Bibliotheksauswahl kein POST Rawfileupload; Inhalt wird erst bei autorisierter Nutzung/Vorschau geladen.

## 9. Abnahmekriterien

- Eine vorhandene Datei lässt sich über das unveränderte Plusmenü zu einer anderen Unterhaltung hinzufügen und über den vorhandenen Modellpfad nutzen.
- Anzahl physischer Dateien, Hash und storage_key bleiben bei Wiederverwendung gleich; Ownerbytes werden nicht doppelt berechnet.
- Textreferenzen, PDFseiten, Visionprüfung, Uploadprogress und normale v1-Chats funktionieren unverändert.
- Löschen/Entfernen einer Bindung zerstört keine andere aktive Bindung; unreferenzierte Dateien werden begrenzt bereinigt.
- Fremde/gelöschte IDs, Quotaüberschreitung und konkurrierende Mutationen bestehen Sicherheits-/Integrationsprüfungen.
- Desktop/Mobile haben reale, zugängliche Auswahl-, Fehler- und Abbruchaktionen.

## 10. Abhängigkeiten

P0 Menüintegration, P1 Registry/Policykontrakt, P3 expand/backfill/cleanup und P4 Picker/Ressourcen-PR. P2 WS-v2 ist **keine Voraussetzung für normalen Bibliotheksversand**, da vorhandene Attachment-IDs/v1 verwendet werden; v2 gilt erst für generierte Tooloutputs. Bilderstellung und Research beziehen sich später auf dieselben Bindungen. Keine Embeddings, Vektordatenbank, OCR oder zweite Dateiablage als Bibliotheksvoraussetzung.
