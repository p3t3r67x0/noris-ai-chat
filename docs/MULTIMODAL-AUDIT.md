# Bestandsaufnahme: Uploads und multimodaler Chat

Stand: 2026-10-11. Der aktuelle Remote-`main` wurde neu abgerufen: `1e034c3` (PR #42). Die vorhandene Upload-/Vision-Arbeit in [PR #44](https://github.com/p3t3r67x0/noris-ai-chat/pull/44), Ausgangsstand `cc37a0a`, baut über [PR #43](https://github.com/p3t3r67x0/noris-ai-chat/pull/43) auf genau diesem `main` auf. Deshalb wird PR #44 ergänzt. Es wird keine konkurrierende Upload- oder Composer-Implementierung eröffnet; die vorhandene PR-Abhängigkeit bleibt bestehen.

„Implementiert“ beschreibt im Folgenden den geprüften Quellcode. Die nachträglich ergänzte Vision-Implementierung und diese Änderungen wurden auf Nutzerwunsch nicht ausgeführt oder getestet. Eine erfolgreiche Analyse durch einen kostenpflichtigen Live-Anbieter ist damit nicht bestätigt.

## Bestehende Funktionen und wiederverwendete Komponenten

| Bereich | Aktueller main | Bereits in PR #44 vorhanden und wiederverwendet |
| --- | --- | --- |
| Datei-Auswahl / Composer | Eine `UChatPrompt`-Instanz; Plus deaktiviert | `ChatComposer.vue`, adaptives Grid aus PR #43, natives Mehrfach-Dateimenü, Fortschritt/Fehler/Retry/Abbruch, `useChatAttachments` |
| Upload-API | Noch kein Upload-Endpunkt | Authentifizierte `/api/v1/chat/attachments`-API mit rohem Datei-Body, Grenzen, Listing, Entfernen und Download |
| Datei-Storage | Keine Attachment-Verwaltung | `AttachmentService`, zufällige private Storage-Keys, persistentes Attachment-Volume, Besitzerquoten und Bereinigung |
| Nachrichtenzuordnung | PostgreSQL-Nachrichtenbaum, Varianten und Generationen | Additive Migration `0006_chat_attachments`; `ChatAttachment` mit Besitzer, Conversation, Message, SHA-256, MIME und Status; atomare Zuordnung in `ChatRepository.begin_generation` |
| Darstellung / Reload | Text und Markdown im Nachrichtenverlauf | Persistierte Attachment-Metadaten in `MessageResponse` und WebSocket-Ereignissen, originale Downloadlinks; ungesendete Anhänge nach Reload im Composer |
| Modellverwaltung | Dynamischer `/models`-Katalog und explizite Auswahl | Derselbe `ModelCatalogService`, `resolve_model`, `useModelSelection` und aktuelle `input_modalities`; Provider-Kontextfenster mit ausdrücklich konfigurierten Betreibergrenzen |
| Bildvorbereitung | Kein Bildkontext | Derselbe begrenzte Parserprozess: Signatur/Dekodierung, Integritätsprüfung, EXIF-Orientierung und neues begrenztes JPEG ohne Metadaten |
| Modellkommunikation | `OpenAICompatibleProvider` mit Text-Payloads | Interne `VisionMessage` aus kontrolliertem Storage; `provider_payload` erzeugt echte `image_url`-Parts mit Bildbytes für denselben `/chat/completions`-Endpunkt |
| Streaming / Abbruch | Bestehender SSE-Providerpfad und persistierter WebSocket-v1-Lebenszyklus | Derselbe `LLMGateway`, `GenerationManager`, Event-Replay und Cancellation; Bilder auch bei Folgeanfragen, Regenerierung und Fortsetzung |
| Tests | Unit-, PostgreSQL-, HTTP-/SSE-, WebSocket- und Browser-Simulatoren | Bereits vorhandene synthetische Upload-/Vision-Fälle, MockTransport, Provider-Simulatoren und Attachment-Fixtures; keine echten Provider-Generierungen in CI |

Die Vision-Erkennung verwendet keine Modellnamen. `resolve_model` übernimmt Bildeingabe aus den Provider-Modalitäten; `supports_images` verlangt zusätzlich Text-Eingabe, Freigabe und Streaming. Der Browser verwendet dieselben veröffentlichten Fähigkeiten und blockiert gespeicherte Bilder bei inkompatiblen Modellen. Eine lokale `vision=true`-Behauptung oder eine Selbstauskunft des Modells ersetzt keine Provider-Metadaten.

## Tatsächlich ergänzte Funktion

Vor dieser Ergänzung enthielt `ChatMessage.vue` für Bilder ausschließlich Dateisymbol und Downloadlink. Eine sichtbare Bilddarstellung im Chat fehlte. Sie ist jetzt im selben Nachrichtenbaustein ergänzt:

- `GET /api/v1/chat/attachments/<ID>/content?preview=true` erweitert den vorhandenen Download-Endpunkt. Die normale Anfrage liefert weiterhin das Original als Download.
- Die Vorschau verwendet `AttachmentService.image_input` und denselben Parser wie die Provideranfrage. Nur PNG/JPEG werden nach Besitzer-/Conversation-/Statusprüfung und erneuter SHA-256-/Größenprüfung als normalisiertes JPEG ausgeliefert. Texte, PDFs, gelöschte und fremde Anhänge können nicht als Vorschau abgerufen werden.
- Die Antwort verwendet `image/jpeg`, `Content-Disposition: inline`, `private, no-store`, `nosniff` und die vorhandene Sandbox-CSP. Es gibt keine öffentliche Storage-URL oder clientseitig auswählbare Speicherpfade.
- `ChatMessage.vue` zeigt das Bild mit zugänglichem Namen, reserviertem und begrenztem Platz sowie Lazy Loading. Download und vollständiger Anzeigename bleiben verfügbar. Fehler sind sichtbar und lassen sich erneut versuchen, ohne eine Generierung auszulösen.
- Laden und Fehler melden ihre Layoutänderung über das vorhandene `rendered`-Ereignis an `useChatScroll`. Das vorhandene Verhalten für manuelles Lesen bleibt bestehen.
- OpenAPI und generierte TypeScript-Typen enthalten den optionalen Vorschauparameter und beide binären Antworttypen. Die Codegenerierung wurde erweitert, ohne den öffentlichen Chat-/WebSocket-Vertrag für Bildbytes zu öffnen.

## Bilddaten im Modellrequest

Der Browser überträgt nach erfolgreichem Upload ausschließlich Attachment-IDs mit `chat.generate`. Das Backend lädt den Nachrichtenpfad aus PostgreSQL und lädt dessen Bilddateien über `AttachmentService.image_input`. Die interne Benutzer-Nachricht erhält Text und tatsächliche Bildbytes:

```json
{
  "role": "user",
  "content": [
    {"type": "text", "text": "Beschreibe dieses Bild."},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,<serverseitige Bildbytes>"}}
  ]
}
```

Das entspricht dem [dokumentierten Noris-Vertrag](https://noris.cloud/nai/how-tos/multimodal/). Dateinamen oder Metadaten ersetzen die Bilddaten nicht. Die bestehenden Antwortdeltas werden unverändert gestreamt und gespeichert. Größen-, Kontext-, Output- und Tagesbudgetprüfungen bleiben wirksam; Bilder zählen zusätzlich zur lokalen Tokenreserve. Einzelheiten stehen in [CHAT-ATTACHMENTS.md](CHAT-ATTACHMENTS.md).

## Modellauswahl und Routing

Der bestehende Katalog enthält eine virtuelle `smart_router`-Policy für das optionale Provider-Modell. Diese Policy erscheint nur mit tatsächlich vom Provider gelieferten und freigegebenen Metadaten. Sie ist kein automatischer Bildrouter der Anwendung.

Die Anwendung respektiert weiterhin die ausdrücklich ausgewählte Modell-ID. Textanfragen können GPT-OSS 120B verwenden; Bilder erfordern `image` und `text` in den aktuellen Modalitäten sowie Streaming/Freigabe. Qwen3.8 27B, Gemma 4 31B, Qwen3.6 27B und GLM 5.3 Flash sind entsprechend den bereitgestellten Katalogdaten kompatibel. Die gleiche Logik akzeptiert DeepSeek V4.1 Flash, wenn dessen Katalog Bildeingabe bestätigt. Video-Metadaten allein erteilen keine Bildeingabe-Erlaubnis.

Bei inkompatibler Auswahl fordert der Composer zur Auswahl eines Modells mit Bildeingabe auf. Auch das Backend weist neue oder historische Bilder in einem Textmodellrequest ab. Der Modellname bleibt erhalten; es gibt keinen stillen Wechsel oder Ersatzrequest. Automatisches Routing ist optional im Auftrag und wurde nicht zusätzlich eingeführt.

## Sicherheitsprüfung

Die bereits vorhandenen Schutzmaßnahmen wurden wiederverwendet: Authentifizierung und Single-Owner-Zuordnung, Conversation-Besitz, begrenzte rohe Uploadstreams, Erweiterungs-/MIME-/Inhaltsprüfung, private Storage-Rechte, zufällige Keys, Owner-Quoten, nicht öffentliche Downloads und Bereinigung von verwaisten Dateien. PNG/JPEG müssen tatsächlich dekodierbar sein; Pixel-, Dimensions-, Prozess-, Laufzeit- und Request-Limits verhindern unbeschränkte Verarbeitung.

Bildbytes werden vor Provideranfragen und Vorschauen erneut geprüft und normalisiert. EXIF/XMP/ICC werden nicht weitergegeben. Bilder bleiben Benutzerinhalt; sie können keine Systemrolle annehmen. Interne Bildfelder sind aus Standardserialisierung und Repräsentation ausgeschlossen. Provider-/Parserfehler werden in feste öffentliche Fehler übersetzt; Dateitext, Bildpayloads, rohe Providerantworten und Zugangsdaten werden nicht protokolliert.

Die neue Vorschau nutzt dieselben Schutzmaßnahmen. Sie akzeptiert weder URLs noch Pfade als Eingabe. Ein neuer synthetischer Fehlerfall stellt sicher, dass ein vom Provider zurückgespiegelter Bildrequest weder in öffentlichen Events noch in Logs auftaucht.

## Testfälle und tatsächlicher Prüfstand

Ergänzte, nicht ausgeführte Fälle:

- Backend: authentifizierte normalisierte Vorschau, Originalerhalt, Ablehnung von Nichtbildern, gelöschten/fremden Anhängen und manipulierten Storage-Bytes; Vorschau bereits gesendeter Bilder.
- Modellfähigkeiten: alle genannten Modelle anhand synthetischer Schema-2.4-Metadaten; dieselbe Modell-ID verliert Bildberechtigung bei Entfernung der `image`-Modalität.
- Provider-Payload: HTTP-Inhalt als echtes JPEG dekodieren und synthetische Pixel prüfen, gewählte Modell-ID erhalten; Providerfehler dürfen keine Bildbytes, Prompts oder Schlüssel zurückspiegeln.
- Vue: Bildvorschau, zugänglicher Name, Layoutmeldung, Download-Erhalt bei Fehler und Retry.
- Playwright: echte API-Vorschau vor/nach Reload, Fehler/Retry ohne weitere Generierung oder Modellwechsel. Bestehende Fälle prüfen Upload, kompatible Auswahl, Streaming/Stop, Persistenz und mobile Bedienung.

Es wurden in dieser Ergänzung keine Tests, Lint-/Typecheck-/Build-Gates oder Docker-Kommandos gestartet und nicht auf CI gewartet. Nur bestehende Quelltexte und abgeschlossene, vom Nutzer verlinkte CI-Belege wurden geprüft. Die HTTP-/WebSocket-Typen wurden als Codegenerierung aktualisiert; dies ist kein Testergebnis. Historische Ergebnisse vor der Vision-Erweiterung stehen in [COMPOSER-ATTACHMENTS-VALIDATION.md](COMPOSER-ATTACHMENTS-VALIDATION.md) und bestätigen keine nachträgliche Änderung.

Der abgeschlossene [Compose-Job von PR #43](https://github.com/p3t3r67x0/noris-ai-chat/actions/runs/38130007749/job/114442197518?pr=43) bestand 275 Produktions-Browserfälle und 41 WebSocket-Fälle, mit einem mobilen Sidebar-Fehler vor vollständiger Hydrierung. Dessen Testhelfer wurde im Basis-PR korrigiert. Der separate checks-Job desselben Laufs meldete 55 erfolgreiche SSE-Browserfälle und 20 veraltete Composer-Snapshots; die vorhandenen synthetischen Actual-Bilder wurden einzeln geprüft und übernommen. Auch diese Korrekturen wurden nicht erneut ausgeführt.

## Noch vorhandene Einschränkungen

- Erfolgreiche Bildanalyse durch ein echtes Noris-Modell und erneute Regressionstests sind offen. Es wurde kein kostenpflichtiger Modellrequest ausgeführt und die laufende Anwendung nicht neu gestartet.
- Die existierende REST-Textchat-API bleibt textbasiert; Attachment-IDs verwenden den vorhandenen persistierten WebSocket-Chat.
- Videos, SVG, GIF und andere Formate werden nicht hochgeladen oder an Modelle geschickt, auch wenn der Provider weitere Modalitäten meldet.
- Normalisierung auf maximal 1024 Pixel und 512 KiB kann kleine Schrift oder Details verlieren. Es gibt keine garantierte OCR oder separate OCR-Pipeline.
- Gesendete Bilder bleiben an ihre ursprüngliche, unveränderliche Benutzernachricht gebunden. Die bestehende Textbearbeitung erzeugt eine neue Variante und übernimmt diese Anhänge derzeit nicht automatisch. Regenerierung, Fortsetzung und Folgeanfragen desselben Bildpfads rekonstruieren sie bereits.
- Parser-Prozesslimits sind keine vollständige Betriebssystem-Sandbox. Bestehende Ressourcen- und Speichergrenzen sind in der Upload-Dokumentation beschrieben.

Die beiden PRs bleiben ohne Merge; private Referenzbilder und private Uploads sind weder Teil der Änderungen noch der Testbelege.
