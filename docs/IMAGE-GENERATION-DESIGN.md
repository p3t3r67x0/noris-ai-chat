# Bild erstellen: geprüfte Fähigkeiten und Providerabstraktion

Status: technische Planung; keine echte Bildgenerierung, kein Providerkonto aktiviert. Stand: 2026-10-12.

Grundlage: [Tool-Architektur](TOOL-ARCHITECTURE.md), [Attachmentbindungen](FILE-LIBRARY-DESIGN.md), [PR-Roadmap](FEATURE-ROADMAP.md).

## 1. Bestandsaufnahme und tatsächliche Bildfähigkeiten

Vorhanden sind PNG-/JPEGupload, Signatur-/Pixelprüfung, SHA-256, private Speicherung und `content?preview=true`. `AttachmentService.image_input` liefert metadatafreies begrenztes JPEG für multimodale **Eingabe**. `supports_images` und `useModelSelection` verlangen frische Freigabe sowie vom Provider gemeldete Text-/Bildeingabemodalitäten. Nachrichten stellen gespeicherte Bilder im bestehenden Chat dar.

`LLMProvider.stream` liefert ausschließlich Textdeltas; `OpenAICompatibleProvider` spricht `/chat/completions` und lehnt function/tool_calls ab. Es gibt keinen `/images/generations`-Adapter, keinen Bildoutputvertrag und keinen Bildjob. Die öffentliche [Noris-Chat-Completions-Dokumentation](https://noris.cloud/nai/api/chat-completions/) belegt den Chatendpoint; aus ihr ergibt sich für diesen Plan kein Nachweis eines zugänglichen Bildgenerierungsendpoints. Die bestehende Visionfähigkeit oder ein Modellname autorisiert keine Bilderstellung.

| Kandidat | Dokumentationsnachweis | Nachweisgrenze |
| --- | --- | --- |
| Vorhandener Noris-Chatprovider | Textstreaming und gegebenenfalls Imageinput über vorhandenen Adapter/Modalkatalog. | **Keine im Repository implementierte Bildausgabe.** Kein live autorisierter Bildendpoint geprüft. |
| OpenAI Images API | Offizieller [Create-image-Vertrag](https://developers.openai.com/api/reference/resources/images/methods/generate) dokumentiert `/images/generations`, explizite Bildmodelle und Bilddaten/Usage. [Imagegeneration-Guide](https://developers.openai.com/api/docs/guides/image-generation) unterscheidet Images API und Responses-Tool. | Dokumentation beweist die APIfähigkeit, nicht Zugriff/Tarif/Regionalfreigabe des noris-Betreibers. Modell und Optionen vor Freigabe aktuell nachweisen. |
| Eigener ComfyUIservice | Offizielle [Serverrouten](https://docs.comfy.org/development/comfyui-server/comms_routes) beschreiben Promptqueue, History, Bildauslieferung und Interrupt. | Installierte Modelle/Workflows, Hardware, Lizenz, Last und jobbezogene Cancellation separat prüfen. Keine bereits vorhandene Instanz vorausgesetzt. |

Entscheidung: erster implementierbarer Adapter ist eine explizit konfigurierte Images API, sofern Betreiberzugriff und Kostenpolicy bestätigt sind. Selbst gehostetes ComfyUI bleibt eine austauschbare Alternative. Kein stiller Wechsel des vorhandenen Chatproviders und keine Behauptung, dass Noris-Chatmodelle Bilder erzeugen können. OpenAI Responses mit eingebautem Bildtool ist nicht nötig, da dafür der bestehende Textpfad gewechselt werden müsste.

## 2. Fehlende Komponenten

`ImageProvider`-Protocol, ein separater freigegebener Bildkatalog, Capability-/Optionnachweise, ToolRun mit Geld-/Callreservation, sicherer Bildresultatimport in den bestehenden AttachmentService, Outputbindung an die Assistantnachricht, Progress-/Fehlerkarte und Bildmodus im bestehenden Composer.

Providerinterface, noch kein Produktcode:

```python
class ImageProvider(Protocol):
    async def capabilities(self) -> ImageCapabilities: ...
    async def generate(self, request: ImageInput, context: ProviderContext) -> ImageOutput: ...
    async def inspect(self, operation_id: str) -> ProviderOperation: ...
    async def cancel(self, operation_id: str) -> CancellationOutcome: ...
    async def aclose(self) -> None: ...
```

`inspect/cancel` können ausdrücklich `unsupported` liefern; keine erfundene Remoteabbruchgarantie. `ImageOutput` ist ein begrenzter interner Bytestream oder ein serverseitig geprüftes Ergebnisreferenceobjekt, kein Browserblob. Start/Response kann synchron sein; async Jobadapter implementieren zusätzlich Operation-ID/Polling innerhalb derselben Deadline. Providerkennung und modelId sind serverseitig allowlisted.

`ImageCapabilities` enthält exact model ID, evidence (`documented/verified/unknown`), erlaubte size/quality/format/background, maxCount, timeout, Preis-/Quotaquelle und supportsCancel/supportsIdempotency. Eine vorhandene `/models`-Liste ohne Bildmodalitäts-/Endpointnachweis reicht nicht. Es wird keine generische „OpenAI-kompatibel bedeutet Bilder“ Fähigkeit erfunden.

## 3. Datenmodell

Gemeinsames `chat_tool_run` mit `tool=image.generate.v1`, inputDigest, Provider-/Modell-/Optionensnapshot, attempt, reservation und optional providerOperationId. `chat_tool_result.output`: canonical attachmentIds, Modell, Dimensions-/Formatmetadaten, erzeugtAt, safe revisedPrompt falls vorhanden, gemessene Usage oder null, Costreservation/-abrechnungsstatus.

Bilddatei: bestehendes `ChatAttachment`, `status=stored`, PNG oder JPEG, originKind `generated_image`, SHA-256, Größe, privater storage_key. Neue `chat_attachment_link` mit purpose `output` zeigt auf vorhandene Assistantnachricht. Toolresultat und Bildbindung verwenden dieselbe canonical ID. Text-/Bildmodell-ID wird nachvollziehbar getrennt gespeichert; ChatGeneration/Message hat im Bildmodus die tatsächliche Ausgabemodell-ID plus Modeprovenienz, keine angeblich verwendete Textmodell-ID.

Eine Bildantwort kann einen kurzen, escaped Status-/Prompttext und Bildoutput enthalten. Sie muss kein künstlich halluziniertes LLMbegleittextresultat erzeugen. Bild wird in Reload und active-path über bestehende MessageResponse-Attachmentprojektion geladen. Für spätere Folgefragen werden **nur Inputbindungen** als Visioneingabe verwendet; ein Bildoutput wird erst durch bewusstes „Als Anhang verwenden“ in eine Inputbindung überführt. Das schützt Textmodelle vor unerwarteten Assistantbildinputs.

Initial n=1. Optional spätere Mehrfachbilder brauchen atomaren Batchimport und passende Quoten. Kein Editing/Inpainting, Referenzbildupload an externen Imageprovider oder automatische Nutzung sämtlicher Chatbilder im initialen Vertrag.

## 4. API-Verträge und Ausführung

GET `/chat/tools/capabilities`: `features.image` plus `imageModels` mit öffentlichen exakten IDs/Optionen, verfügbarem Kostenscope, limits und evidenceStatus. Ausgabe beinhaltet keine Keys oder interne Base-URL. Fehlende/unknown Capability → unavailable.

V2 `chat.generate`: `responseMode={kind:"image",imageModelId,size,quality,grantId}`, content = Bildprompt. Vorhandene requestId, conversationId, inputMessageId, assistantMessageId, parentMessageId und conversationVersion bleiben. Initiales Bildcreate erlaubt keine `attachmentIds`; bereits im Composer vorhandene Dateien bleiben erhalten und erzeugen einen erklärten Versandkonflikt, bis der Nutzer sie entfernt oder zum Chatmodus wechselt. Dateien werden nicht still ignoriert/übertragen. Bildmodus kann auch bei fehlender Chatmodellcapability verwendet werden, wenn ein echtes Bildmodell verfügbar ist.

Feste options werden je Modell aus Capabilitydaten geprüft; der Client darf keine weiteren Providerfelder übergeben. Kein beliebiger `image_url`, kein Storagepfad, kein vom Client gelieferter APIkey. `size/quality` sind konzeptionell Strings, im erzeugten Schema werden die aktuell erlaubten Werte/harte Maxima festgelegt. Moneylimits und Providerwahl bestimmt der Server; ein Grant kann diese nicht überschreiten.

Ausführung: GenerationManager nimmt Input/Assistantplaceholder atomar auf → ToolRuntime prüft Policy/Costreservation → Providerrequest mit Deadline → begrenzte Bildbytes validieren → derselbe AttachmentService importiert File und erstellt Outputlink → Toolresultat/Assistantstatus/Event gemeinsam committen → v2 Ereigniszustellung. Vor Ergebniscommit erneut Cancel/Owner/Chatstatus prüfen. Bei erfolgreicher reiner Bilderstellung ist die vorhandene automatische Titelphase optional; wenn sie läuft, nur durch Gateway und zulässiges Textmodell, Fehler ändern das Bildresultat nicht.

Providerantwortpreferenz: base64-/Bytestream direkt, sofern vom Modell unterstützt. Base64dekodierung streng und bytebegrenzt; modellabhängige unsupported Parameters nicht senden. Liefert ein anderer Provider nur URLs, werden die Bytes ausschließlich backendseitig von dessen explizit erlaubten Resultathosts mit SSRF-/Redirectprüfung geladen. Keine Browsernavigation zu einer temporären Provider-URL.

GET `/chat/tool-runs/{id}` zeigt Ergebnis/Usage/unklaren Abschluss; Downloads/Previews bleiben `/chat/attachments/{id}/content`. Stop und Transportresume benutzen `chat.cancel/resume`, keine neue parallele Generierungs-API. Nach unklarem Ergebnis wird „Erneut erzeugen“ erst nach ausdrücklicher neuer Aktion und erneuter Budgetprüfung angeboten.

## 5. WebSocket-Ereignisse

`chat.tool.queued/started` → `chat.tool.progress(stage:"generating"\|"storing",completed,total:null)` → `chat.attachment.created(attachment, purpose:"output")` → `chat.tool.result(resultId,attachmentIds,usage)` → `chat.generation.completed`. Alle teilen die bestehende persistierte Generierungssequenz. Providerprozente werden nur bei tatsächlicher belastbarer Meldung verwendet.

Bei abgebrochener/fehlerhafter Verarbeitung: `chat.tool.failed` mit `TOOL_TIMEOUT`, `PROVIDER_RATE_LIMIT`, `IMAGE_INVALID`, `ATTACHMENT_QUOTA`, `CONTENT_REJECTED` oder `PROVIDER_OUTCOME_UNKNOWN`; dann korrekter Parentterminal. Cancel bestätigt erst lokales Ende, nicht den Stopp fremder Abrechnung.

Kein base64-Bild in WS-Frames. Partielle Bildpreviews sind zunächst nicht erforderlich; sie würden eigenständige begrenzte Attachment-/Retentionlogik benötigen. Resumesnapshot enthält fertige Attachmentmetadaten oder den wahrheitsgemäßen Pending-/Errorstatus, keine erneute Provideranforderung.

## 6. Frontend-UX

Plus → „Bild erstellen“ aktiviert einen entfernbaren Moduschip und erlaubt denselben Texteingabebereich. Kleine Bildoptionen verwenden vorhandene Popover/Dialogpatterns. Enter/Senden startet einen Bildjob. Der normale Textmodellpicker bleibt für den anschließenden Chat erhalten; im Bildmodus werden tatsächlich verfügbare Bildoptionen angezeigt, kein impliziter Vision-/Textmodellwechsel.

Bei externem, kostenpflichtigem Provider muss der vorab sichtbare Startscope Provider, Anzahl und Kostenobergrenze verständlich zeigen. Bereits beim Senden bestätigter unveränderter Scope wird nicht erneut abgefragt. Bei neuen Rechten/Optionen außerhalb des Grants verlangt der Server eine konkrete Freigabe. Bei keiner Fähigkeit gibt es keinen funktionslosen Menühandler.

Assistantkarte zeigt Fortschritt/Stop, anschließend Bildvorschau, Download und „Als Anhang verwenden“. Die letzte Aktion erstellt eine normale Inputbindung über die Bibliotheks-/Attachmentlogik; daraufhin gilt die vorhandene Vision-/Modelkompatibilitätsprüfung. Regeneration bedeutet neue explizite Bildanforderung/Assistantvariante mit neuer Reservation, niemals Wiederverwendung einer laufenden requestId mit anderem Prompt.

Desktop/Mobile: Bildfläche mit reserviertem Seitenverhältnis, begrenzter Breite, kein Timelineoverflow; Bilddetails als Dialog/Sheet. Fehlgeschlagene Vorschau hat Retry ohne neue Generierung. Modellprompt ist beschreibender Alternativtext, kein unbelegter Inhaltserkennungsbericht. Fehler erhalten Promptentwurf/gespeicherte Usernachricht und verständliche nächste Aktionen.

## 7. Sicherheitskonzept und Kosten

Imageprovider ist separat konfiguriert/allowlisted, Credentials nur Backend. Timeout/Cancel schließen HTTPstream, verhindern neue Calls und blockieren späte Ergebnispublication nach Parentterminal. Providerjobs dürfen nur den im Scope geprüften Prompt sehen. Kein automatischer Chat-/Attachmentexport.

Auch Providerbytes sind untrusted: bestehende MIME-/Signatur-/Dekodierungs-/Pixel-/Singleframe-/Größenprüfungen verwenden. Hard ceiling mindestens so streng wie existing Attachmentlimits; Blob wird vor Publicmetadatafreigabe validiert. ProvideroperationId nicht als Dateipfad verwenden. Vorschau nutzt dieselbe Integritätsprüfung/Metadataentfernung; PNG-Transparenz im Original bleibt erhalten, die heutige JPEG-Visionpreview hat weiterhin weißen Hintergrund.

Kostenreservation vor Dispatch umfasst konservativen worst-case Preis für Modell/size/quality und einen Call. Fehlende Usage bleibt null; keine aus Texttokens abgeleiteten angeblich gemessenen Bildkosten. Ohne bekannte Preisobergrenze/Betreiberpreis wird die Funktion gesperrt. Providercredits/Rate-/Moneylimits und bestehende Ownerstoragequota gelten unabhängig voneinander.

Provider mit belegtem Idempotencykey kann eine nachweislich sichere Wiederaufnahme erlauben; ohne diesen Nachweis bewirkt Timeout nach möglichem Dispatch `outcome_unknown`. Keine automatische kostenpflichtige Wiederholung. Fehlende jobbezogene Cancellation bei ComfyUI darf nicht durch globales Interrupt erledigt werden, falls andere Jobs betroffen wären; initial nur isolierte eigene Queue/Instanz oder korrekt scoper Cancel.

## 8. Tests und Capabilitynachweis

Unit: ImageCapabilities/evidence, verbotene Optionen, fresh/disabled Modell, Kostenberechnung/-reservation, Base64limits, MIME-/Pixel-/Signaturfehler, sichere Providerfehlermapping und Retry-/Unknownpolicy.

Integration: eigener lokaler Image-HTTPsimulator liefert echte synthetische PNG/JPEGbytes, falsche Bytes, langsame Antwort, Rate-Limit, optional idempotente Job-ID und Cancelzustände. PostgreSQL: atomarer Bild-/Link-/Resultatcommit, Storagequota, Rollbackcleanup, Cancel vs. Commit, replay/reload, Chatdelete, foreign owner, Neustart mitten nach Dispatch. Bestehende Bildvorschau und Visionfolgefrage mit bewusstem Inputlink müssen über denselben Attachment-/Gatewaypfad laufen.

Playwright Desktop/Mobile: Plus → Bildchip → Prompt/Optionen → Start/Stop → Bildkarte/Download → Reload → als Anhang nutzen → kompatibles Modell/Folgefrage. Test ohne Chatmodell, aber mit freigegebenem Bildmodell; unavailable Feature, fehlerhafte Previewretry, keine neue Generierung beim Download, bestehende Upload-/Composer-/Scrolltests.

**Spätere Livefreigabe:** dokumentierter Provider-/Endpoint-/exact-model-Nachweis plus gesondert autorisierter, eng budgetierter Smokejob, dessen Output real dekodierbar und persistent nutzbar ist. Options-/Usage-/Timeout-/Cancelbefund dokumentieren. Dieses Architektur-PR führt keinen Livejob aus; erfolgreiche APIfähigkeit des Betreiberkontos wird nicht behauptet. CI nutzt ausschließlich Simulatoren.

## 9. Abnahmekriterien

- Aktivierter Bildmodus erzeugt echte Bildbytes über einen belegten Bildprovider; Vision oder Textsimulation aktiviert die Funktion nicht.
- Dateien werden einmal im vorhandenen Attachmentvolume gespeichert und mit vorhandener Preview-/Downloadroute angezeigt.
- Kein Erfolg vor gültigem Bild-/Resultat-/Messagecommit; Reload/Reconnect dupliziert weder Kosten noch Bilder.
- Stop, Quota, Budget, denied Approval und unknown Outcome werden korrekt persistiert/angezeigt.
- Bewusst wiederverwendetes Bild kann über vorhandene Imageinputprüfung analysiert werden; Bildoutputs blockieren normale Textfolgefragen nicht pauschal.
- Alle Unit-/Integration-/Playwright-/Sicherheitsgates bestehen; Livecapability ist vor Betrieb nachgewiesen.

## 10. Abhängigkeiten

P0 Menüanschluss, P1 durable Runtime/Policy/Budget, P2 WS-v2, P3 Attachmentbindungen, P8 Imageprovider/-import und P9 UXintegration. P4 Bibliothekspicker ist nicht nötig für Erzeugung, aber sinnvoll für spätere Auswahl. Kein Rust/Codex-Sidecar, GPUservice oder zusätzlicher Bildstorage als Pflichtabhängigkeit. Providerkonto, Preis-/Datennutzung und reale Modellfreigabe bleiben spätere explizite Betriebsgates.
