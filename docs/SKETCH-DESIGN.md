# Skizzieren: Canvas → bestehendes Bildattachment

Status: geplant; reine Canvas-/Uploadergänzung. Stand: 2026-10-12.

Basis: [Tool-Architektur](TOOL-ARCHITECTURE.md), [Roadmap](FEATURE-ROADMAP.md). Persistente Backendtools sind für das Zeichnen nicht erforderlich.

## 1. Bestandsaufnahme

`ChatComposer.vue`/`ChatWorkspace.vue` besitzen bereits Dateiaktionen, `useChatAttachments.add(File[])`, Uploadprogress, Cancel, Retry und bestehende Attachmentkarten. PNG/JPEG werden serverseitig signatur-/pixel-/größen-/integritätsgeprüft und im vorhandenen Volume gespeichert. `image_input`, `supports_images`, Preview und Modellkatalog erlauben die bewusste Nutzung als Bildeingabe.

Es gibt keine Zeichenoberfläche oder Canvasdraftpersistenz. Die lokal vorliegende Plusmenüdefinition reserviert `sketch`; im überprüften main ist nur die Uploadaktion vorhanden. Bildanalyse ist bei Sketch weiter abhängig von einer tatsächlich freigegebenen Visioncapability, Zeichnen selbst benötigt keinen Bildgenerierungsprovider.

## 2. Fehlende Komponenten

`SketchDialog.vue` als zusätzlicher Nuxt-UI-Dialog/Sheet, kleine `useSketchCanvas`-/`lib/sketch`-Zeichenlogik, Pointerevents, Undo/Redo, Clear, Brushfarbe/-breite, begrenztes PNGexport und Integration in vorhandenes `attachments.add`. Keine zweite Composerinstanz, keine Serverzeichensession und kein externer Canvasdienst.

Initialumfang: freihändige Linien, Stift/Radierer, kleine Palette, Strichbreite, Rückgängig/Wiederholen, Leeren mit sinnvoller Schutzaktion, Export/Hinzufügen. Formen, Ebenen, Kollaboration, SVGimport, Fotoimport oder professionelle Zeichenwerkzeuge sind keine Voraussetzung.

## 3. Datenmodell und Speicher

Browserdraft: logische Canvasgröße, weißer Hintergrund, strokes als begrenzte Commands (`tool,color,width,points`), historyCursor und optionaler beschreibender Text. Punkte in logischen/normalisierten Canvascoords speichern; Viewport-/DPRänderung rendert Commands neu und verändert sie nicht.

Startlimits: logische Fläche maximal 1024×1024, DPR maximal 2, Backingbitmap maximal 2048×2048 (=4 Mio. Pixel), maximal 2.000 Striche/100.000 Punkte und begrenzte History im Speicher. Undo nutzt Commands, keine unbounded Bitmapkopien. Maximaler Export über die vorhandenen Attachmentlimits; bei Übergröße nachvollziehbarer Fehler oder bewusste kleinere Auflösung, keine heimliche unleserliche Verkleinerung.

Der unbestätigte Sketch bleibt initial nur als begrenzter Workspaceentwurf im Speicher und wird je conversation/draft_key zugeordnet. Dialogschließen kann ihn für erneutes Öffnen desselben Chats erhalten. Reload vor Export kann ihn verlieren; diese Grenze vor Verlassen eines nicht exportierten Entwurfs verständlich anzeigen. Keine implizite Cloud-/localStorage-Bildpersistenz. Geräteübergreifende editierbare Zeichnungen wären ein eigener späterer Vertrag.

Nach „Als Anhang hinzufügen“: PNGblob → File `skizze.png` → vorhandener Upload → canonical `ChatAttachment(status=stored)` plus normale Inputbindung. MIME/Hash/Größe/Storage sind unverändert. Für auf main vorhandene Einzelzuordnung ist P3 Mehrfachbindung keine technische Pflicht; nach dessen Integration verwendet Sketch automatisch dieselben Linkreader. Kein Sketchblobspeicher. Eine optionale später eingeführte originKind-Annotation ist nur Herkunftslabel, keine vertrauenswürdige User-/Modelinformation.

## 4. API-Verträge

Kein neuer Backendendpoint erforderlich. Vorhanden und wiederverwendet:

- GET `/api/v1/chat/attachments/limits` vor Export/Upload.
- POST `/api/v1/chat/attachments?conversationId=<UUID>&filename=skizze.png`, Header `Content-Type:image/png`, Body PNGbytes → `201 AttachmentResponse`.
- DELETE pending Attachment bzw. nach Linkintegration die eindeutige Linkroute für Entfernen.
- GET vorhandene `/content?preview=true` und Originaldownload.
- Normaler `chat.generate` mit bestätigter Attachment-ID, Text und frischer Modelcapability.

`canvas.toBlob('image/png')` ist asynchron, null/Encodefehler sind sichtbare lokale Fehler. Canvas darf keine externen Bilder enthalten, dadurch kein Remoteimport/tainted-canvas-Ablauf. Leere Zeichnung darf nicht gesendet werden; Prüfkriterium sind sichtbare Commands/Zeicheninhalt, nicht nur eine existierende weiße Bitmap. Derselbe erzeugte File bleibt bei Uploadretry verfügbar; Retry rendert nicht aus inzwischen verändertem Canvas still ein anderes Bild.

Ein neuer Chat wird erst bei bestätigtem Export/Hinzufügen über dieselbe vorhandene Ensure-/Entwurfsübernahme angelegt. Nur Öffnen, Zeichnen, Schließen oder leeres Export erzeugt keine Conversation. Client meldet nach Upload ausschließlich Attachment-ID; keine Data-URL im Chat-/WScommand.

## 5. WebSocket-Ereignisse

Zeichnen, Undo/Redo und Export sind lokal; Uploadprogress bleibt der vorhandene XHRstatus. Keine Remote-Tool-/Generationereignisse oder fiktive generationId für einen Pointerstrich.

Nach Versand nutzt Sketch dieselben `chat.message.created`-Attachmentmetadaten und `chat.generation.*` wie jedes andere Bildattachment. Reload stellt das gespeicherte Bild und die bisherige Chatantwort wieder her. Ein nicht exportierter Zeichnungsdraft ist ausdrücklich kein persistenter Research-/ToolRun.

## 6. Frontend-UX und Canvasverhalten

Plus → „Skizzieren“ schließt das bestehende Menü und öffnet Dialog/Sheet. Desktop zeigt Werkzeugleiste, Canvas und Hinzufügen/Abbrechen. Mobile passt an visualViewport/Safe-Area an, Toolbar scrollt bei Bedarf nur intern, mindestens 44 px Touchziele, kein horizontaler Workspaceoverflow. Composertext, Modus, Modell und bestehende Attachments bleiben erhalten.

Pointerevents behandeln Maus/Stift/Touch mit `setPointerCapture`; nur ein aktiver Pointer zeichnet. `pointercancel/lostpointercapture` verwirft den noch nicht bestätigten Strich und setzt Capture-/Drawingzustand zurück. Andere Pointer werden ignoriert. `touch-action:none` nur auf Zeichenfläche; außerhalb bleiben Scrollen/Dialogbedienung normal. Boundingrect-/CSSscale-/DPRkoordinaten sauber umrechnen, Punkte mit requestAnimationFrame bündeln, Stiftpressure optional begrenzen. Resize/Orientationwechsel löscht den Draft nicht.

Hinzufügen erzeugt File und ruft **die vorhandene** `attachments.add`-Aktion auf. Die bekannte Attachmentkarte zeigt Progress/Fehler/Retry/Remove. Schlägt Upload fehl, existiert der File weiter für Retry; Sketchdraft bleibt bis bestätigtem Upload verfügbar. Erfolgreich zurück zum gleichen Composer, Fokus ohne Scrollsprung. Attachmentslot-/Ownerquota wird vorab erklärt und weiterhin serverseitig geprüft.

Tastatur: Dialogfokus, beschriftete Toolbarbuttons, Undo/Redo via Buttons und scoped Shortcut, Esc schließt zuerst den Dialog. Bei geändertem Draft ist Verwerfen eine bewusste Aktion, kein automatisches Löschen. Farb-/Toolstatus nicht nur farblich anzeigen. Zugängliche Zeichenflächenbeschreibung und optionaler Text zum Sketch; keyboard drawing kann über Cursor/Pfeiltasten und Start/Ende-Taste eine einfache Linie erlauben. Eine textliche Alternative zum Bild unterstützt Nutzer, für die Canvaszeichnen nicht bedienbar ist. Keine vollständige Accessibilitygleichwertigkeit von Freihandzeichnen behaupten.

Bei nicht visionfähigem aktuellem Modell darf die Zeichnung lokal erstellt/gespeichert werden; Versand mit Bildattachment bleibt nach derselben vorhandenen Prüfung blockiert. UI bietet bewussten Modellwechsel oder Entfernen, kein automatisches Umschalten. Initial produktiver Sketchhandler verlangt funktionierenden WebSocket-/Attachmentbackend; kein funktionsloser Upload im mock/SSEmodus.

## 7. Sicherheitskonzept

Canvas nimmt nur lokale begrenzte Zeichencommands entgegen, keine eval-/HTML-/SVG-/URLinputs. Beschriftung escaped. Pixel-/Historylimits begrenzen Browsermemory/CPU; Cleanup entfernt Eventlistener, Pointercapture und temporäre Blob-/ObjectURLs. Kein vollständiges `getImageData` pro pointermove, keine unbounded Undo-Images.

Server vertraut der PNGbezeichnung nicht: existing Parservalidierung, Größen-/Pixel-/Quota-/Ownershipprüfung, privater Dateikey und Downloadheaders bleiben verpflichtend. Browserseitige Bounds ersetzen keine Serverchecks. Text-/Bildprompt enthält nur bewusst hinzugefügte Sketchbytes; Zeichnen allein kontaktiert keinen LLM-/Bildgenerierungsprovider.

Origin und bestehende Basic-/WS-/Uploadzugriffskontrollen unverändert verwenden. Nur begrenztes File in `useChatAttachments`; keine localStoragebase64kopie und keine neue öffentliche Bildroute. Uploadcancel/removing hat dieselbe autoritative Bestätigungs-/Cleanupsemantik wie existing Fotos.

## 8. Tests

Unit: Pointerkoordination/DPR/resize, single active pointer, cancel/lostcapture, Undo/Redo nach neuem Strich, Clear/emptyexport, Brushbounds, Punkte-/Pixel-/Historylimits, null toBlob, snapshot File für Uploadretry und Cleanup. Testfälle verifizieren Bedienverhalten/Bounds, nicht nur Canvasmethodcalls.

Integration: über vorhandene Upload-/Attachmentfixtures ein reales synthetisches Sketch-PNG speichern/previewn/versenden, bytegleiches Retry, MIME-/Pixel-/Quotaabwehr, PDF-/Textreferenzen im selben Chat erhalten. Keine neue Produkt-API nötig; existing PostgreSQL-/Vision-/Canceltests um Sketchherkunft ergänzen. Linking/Quota nach P3 sowie Modellrevocation vor Versand absichern.

Playwright Desktop/Mobile: Plus öffnen, mit Mouse/Touch zeichnen, Undo/Redo, exportieren, Attachmentprogress und Bildanalyse mit lokalem Visionprovider, Reload des gespeicherten Bilds. Abbrechen/emptydraft erzeugt keinen Chat; Entwurf/Anhänge erhalten, Uploadfehler/Retry/Remove, fehlende Visioncapability, mobile Resize/Keyboard, Fokus/Esc und horizontaler Overflow. Screenshotfixtures nur synthetische Striche, keine Nutzerbilder. Canvas-Rastertoleranzen berücksichtigen, Exportinhalt zusätzlich dekodieren/auf nicht weißen Zeichnungsbereich prüfen.

## 9. Abnahmekriterien

- Desktop und Mobile können tatsächlich zeichnen, korrigieren und ein nicht leeres PNG als bestehenden Anhang hinzufügen.
- Keine zusätzliche Dateiablage, keine zweite Composerinstanz und keine neuen Bildbytes im WSvertrag.
- Bild-/Modell-/Uploadquotaprüfung, Fortschritt/Retry/Cancel/Remove und normale Chat-/PDF-/Textreferenzfunktionen funktionieren weiter.
- Dialogschließen/Cancel/Resize verliert nicht unerwartet den aktiven lokalen Draft; nicht persistierte Reloadgrenze ist verständlich.
- Pointer-/Memory-/A11y-/Owner-/Parserprüfungen bestehen, lokale Zeichnung startet keinen kostenpflichtigen Providercall.

## 10. Abhängigkeiten

P0 Menüanschluss und P5 Canvas-/Upload-PR. Existing Attachmentbackend genügt; P1 Registry, P2 WS-v2, P3 Mehrfachbindung, P8 Imageprovider und P10 Research sind **keine Pflichtabhängigkeiten** des Zeichnens. Falls P3 schon integriert ist, dessen Projektion/Removerouten verwenden. Abnahme von Zeichnen ist unabhängig von echtem Visionanbieter; CI simuliert Bildanalyse. Eine reale Analyse benötigt weiterhin frische bestehende Visioncapability, keine Bildgenerierungsfähigkeit.
