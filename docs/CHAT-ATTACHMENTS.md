# Persistente Chat-Dateianhänge

Textauswahlen aus Chatnachrichten verwenden dasselbe Attachment-System. Bedienung, Herkunftsmetadaten und Modellkontext sind in [CHAT-TEXT-REFERENCES.md](CHAT-TEXT-REFERENCES.md) dokumentiert.

Der Plus-Button öffnet das vorhandene Nuxt-UI-Aktionsmenü. „Fotos und Dateien hinzufügen“ verwendet den nativen Mehrfach-Dateidialog; Struktur, deaktivierte Erweiterungen, Fokus und Positionierung sind in [COMPOSER-PLUS-MENU.md](COMPOSER-PLUS-MENU.md) dokumentiert. Jeder Upload verwendet die authentifizierte API. Erst eine erfolgreiche `201`-Antwort bestätigt den Anhang; Browserfortschritt allein gilt nicht als erfolgreicher Upload. Fehler lassen sich vor dem Senden erneut versuchen, laufende Uploads abbrechen und bestätigte, noch nicht gesendete Dateien entfernen.

## API und Persistenz

- `GET /api/v1/chat/attachments/limits`: konfigurierte Grenzen und erlaubte MIME-Typen.
- `POST /api/v1/chat/attachments?conversationId=<UUID>&filename=<Anzeigename>`: ein roher Datei-Body mit passendem `Content-Type`, Antwort mit Attachment-Metadaten.
- `GET /api/v1/chat/attachments?conversationId=<UUID>`: bestätigte Metadaten für die Unterhaltung, einschließlich ungesendeter Anhänge zur Wiederherstellung nach Reload.
- `DELETE /api/v1/chat/attachments/<UUID>`: entfernt einen ungesendeten Anhang und seine gespeicherten Bytes. Bereits einer Nachricht zugeordnete Anhänge liefern `409`.
- `GET /api/v1/chat/attachments/<UUID>/content`: kontrollierter Download nach Besitzprüfung, mit `Content-Disposition: attachment`, `nosniff`, Sandbox-CSP und `no-store`.
- Derselbe Endpunkt mit `?preview=true` liefert nur für PNG/JPEG eine normalisierte, authentifizierte JPEG-Vorschau. Gesendete Bilder werden damit in `ChatMessage.vue` dargestellt; Fehler können ohne erneute Generierung wiederholt werden. Das Original bleibt über den normalen Download verfügbar.

Die Alembic-Migration `0006_chat_attachments` ergänzt `chat_attachment`, ohne bestehende Gespräche oder Nachrichten zu löschen. PostgreSQL enthält Besitz, Unterhaltung, Nachrichtenzuordnung, Anzeigenamen, zufälligen Storage-Key, MIME-Typ, Größe, SHA-256, Status, Erstellungszeit und begrenzten extrahierten Text. Binärinhalte werden nicht in Chat-Nachrichten oder WebSocket-JSON gespeichert. API-Antworten enthalten keine Storage-Pfade, extrahierten Inhalte oder Provider-Zugangsdaten.

Die Migration `0008_pdf_sections` erweitert dieselbe Tabelle um `pdf_sections` (JSONB) und `pdf_page_count`. Neue PDFs speichern jeden nicht leeren Seitentext vollständig in geordneten Abschnitten mit höchstens 2.000 Zeichen und der physischen, bei 1 beginnenden PDF-Seitennummer. Auch Abschnitte einer langen Einzelseite behalten ihre Seitennummer. `pdf_page_count` zählt leere Seiten mit. Es gibt keine zweite Upload-API, keine Vektordatenbank und keinen zusätzlichen externen Dienst. PDF-Bytes und SHA-256 bleiben unverändert im bestehenden privaten Storage. Bestehende Anhänge mit `extracted_text` bleiben nutzbar; ihre früher nicht gespeicherten Seitenangaben werden nicht erfunden.

Docker Compose verwendet das separate Named Volume `attachment_data` unter `/var/lib/noris-ai/attachments`, außerhalb des Webroots. Das Verzeichnis gehört dem nicht privilegierten Backend-Benutzer und ist mit `0700`, Dateien mit `0600` geschützt. Lokaler Betrieb verwendet standardmäßig `backend/.local/attachments`, ausgeschlossen von Git und Docker-Build-Kontext. Datenbank und Attachment-Volume gehören gemeinsam in Backup und Wiederherstellung. Ein Backend-Neustart erhält bestätigte Metadaten und Dateiinhalt.

Vor dem Start der neuen Backend-Version muss `make migrate` mit dem bestehenden Migrationszugang ausgeführt werden. Compose erledigt dies über den bestehenden `migrate`-Dienst. Keine bestehenden Datenbankvolumes entfernen.

## Unterstützte Verarbeitung

| Typ | Prüfung und Verarbeitung | Verwendung im Modell |
| --- | --- | --- |
| UTF-8 TXT/Markdown | Erweiterung/MIME, strikte UTF-8-Dekodierung, keine binären Steuerzeichen, begrenzte Textlänge | Extrahierter Text als Benutzerinhalt |
| PDF | `%PDF-`-Signatur, strikter Parser, unverschlüsselt, Seiten- und Dekompressionsgrenzen, Textextraktion | Nur tatsächlich extrahierter Text; kein OCR |
| PNG/JPEG | Erwartetes Bildformat, Signatur und vollständiges Dekodieren, Pixel-/Dimensionsgrenzen, keine Animationen; erneute Integritätsprüfung und begrenzte Normalisierung vor Modellanfragen | Bildparts im Benutzerinhalt, ausschließlich bei bestätigter Bildeingabe des gewählten Modells |

Die Zustände sind bewusst verschieden: `ready` bedeutet gespeichert und Text extrahiert; `stored` bedeutet gespeichert, ohne Textextraktion. Validierte PNG/JPEG-Dateien bleiben `stored`, haben `extractionStatus=not_applicable` und `modelUsable=true`: Die Datei ist grundsätzlich als Bild verwendbar, jedoch nur zusammen mit einem kompatiblen Modell. Der Browser prüft zusätzlich den aktuellen Modellkatalog und zeigt „Für Bildanalyse bereit“ oder „Wähle ein Modell mit Bildeingabe“. Textlose PDFs und leere Textdateien bleiben gesperrt. Ein erfolgreicher Upload behauptet keine erfolgreiche Analyse.

Der [offizielle Noris-Vision-Vertrag](https://noris.cloud/nai/how-tos/multimodal/) bestätigt `content`-Arrays mit Text- und `image_url`-Parts, einschließlich Base64-data-URLs. Die Anwendung erzeugt solche URLs ausschließlich serverseitig aus bereits authentifiziert hochgeladenen Dateien. Sie stellt keine öffentliche Bild-URL bereit und lässt keine vom Browser gelieferten Bild-URLs im Providerkontext zu. WebSocket v1 überträgt weiterhin nur Attachment-IDs; der öffentliche REST-Chatvertrag bleibt textbasiert.

Zwei authentifizierte, ausschließlich lesende Modellkatalog-GETs am 2026-10-11 bestätigten Schema 2.4 und `image`-Eingabe für DeepSeek V4.1 Flash, GLM 5.3 Flash, Qwen3.8 27B, Gemma 4 31B und Qwen3.6 27B. GPT-OSS 120B und GLM 5.2 melden nur Texteingabe. Entscheidend bleibt bei jeder Anfrage der frische dynamische Katalog, zusammen mit bestehender Modellfreigabe und Streaming-/Textfähigkeit. Es gibt keinen automatischen Modellwechsel, OCR-Dienst oder weiteren externen Uploaddienst. Die GETs bestätigen Metadaten; eine echte kostenpflichtige Bildgenerierung wurde nicht ausgeführt.

Vor jeder Bildanfrage kontrolliert der begrenzte Parserprozess die gespeicherte Bytezahl und SHA-256 über einen mit `O_NOFOLLOW` geöffneten Storage-Key. Er dekodiert nur PNG/JPEG innerhalb der bestehenden Pixel-/Dimensionsgrenzen, korrigiert die EXIF-Orientierung und erzeugt ein neues JPEG ohne EXIF/XMP/ICC auf weißem Hintergrund. Die längste Seite beträgt maximal 1024 Pixel, das Ergebnis maximal 512 KiB. Das Original bleibt unverändert für den kontrollierten Download erhalten. Die Normalisierung kann kleine Schrift oder Bilddetails verlieren; Bildanalyse ersetzt keine garantierte OCR.

## WebSocket und Kontextbudget

`chat.generate` erhält optional `attachmentIds`. Das Backend prüft konfigurierte Anzahl, vorhandenen und abgeschlossenen Upload, Besitzer, Unterhaltung, Nachrichtenzuordnung, zugelassenen Status und Modellkompatibilität. Die Zuordnung erfolgt in derselben Transaktion wie die bestehende Generierung. Doppelte oder fremde IDs und inkompatible Inhalte werden abgelehnt.

Der Nachrichtenpfad wird weiterhin aus PostgreSQL rekonstruiert. Extrahierter Dateiinhalt wird als ausdrücklich unvertrauenswürdige Daten innerhalb einer Benutzer-Nachricht ergänzt. Er kann keine privilegierte Systemrolle erhalten. Dateitext zählt zu den vorhandenen Zeichen-, Byte-, Token-, Kontext- und Budgetgrenzen; er wird weder still abgeschnitten noch an diesen Grenzen vorbei zum Provider geschickt. Gesendete Anhänge bleiben in gespeicherten Nachrichten sichtbar und nach Reload kontrolliert herunterladbar.

Bei neuen PDFs ist die Speichermenge vom Anfragekontext getrennt: Bis zu `NORIS_CHAT_ATTACHMENT_MAX_PDF_TEXT_CHARS` extrahierte Zeichen werden vollständig gespeichert. Kurze PDFs gelangen vollständig in den Kontext, wenn sie passen. Bei längeren PDFs wählt eine lokale lexikalische Suche relevante ganze Abschnitte zur aktuellen Benutzerfrage aus. Explizite Fragen nach „Seite 29“ oder „Seiten 1–3“ priorisieren diese physischen Seiten. Kurze Folgefragen berücksichtigen vorherige Benutzerfragen. Breite Fragen ohne Suchtreffer verwenden verteilte Auszüge vom Anfang, Ende und aus der Mitte. Die Suche erkennt Wortüberschneidungen, garantiert keine semantischen Treffer und führt kein OCR aus.

Die Auswahl reserviert Gesprächsverlauf, Bilder, Fortsetzungsanweisungen, Antwort-, Reasoning-, System- und Sicherheitstokens mit demselben Tokenzähler wie der Gateway. Sie prüft außerdem die UTF-16-Nachrichtenlänge und serialisierte Requestbytes. Alle PDF-Auszüge zusammen enthalten höchstens `NORIS_CHAT_ATTACHMENT_MAX_TEXT_CHARS` Textzeichen; ein kleineres Modellkontextfenster kann weniger zulassen. Es werden ausschließlich ganze gespeicherte Abschnitte eingefügt. Passt kein Abschnitt, folgt `CONTEXT_LIMIT`; Gespräch oder Dokument werden nicht abgeschnitten. Die normale Gateway-Zulassung prüft anschließend Rate und Tagesbudget.

Der Benutzerkontext kennzeichnet die Auswahl als `complete` oder `excerpts`, enthält Dateinamen, Gesamtseitenzahl, Gesamtabschnittszahl sowie Seitennummern und fordert Quellenangaben wie `[bericht.pdf, Seite 29]`. Bei Auszügen soll das Modell die Einschränkung für Zusammenfassungen und dokumentweite Aussagen nennen. Seitenverweise sind Quellenangaben im Antworttext und weiterhin vom Modell erzeugt. Folgefragen, Regenerierung und Fortsetzung rekonstruieren die Abschnitte erneut aus PostgreSQL; die gespeicherten Benutzertexte bleiben unverändert.

Bildanhänge historischer Benutzernachrichten werden bei Folgeanfragen, Regenerierung und Fortsetzung erneut aus dem privaten Storage rekonstruiert. Ein Wechsel zu einem Textmodell wird abgelehnt, statt die vorhandenen Bilder still wegzulassen. Während Vorbereitung und Streaming bleibt Stop wirksam; ein abgebrochener Parser wird beendet. Bilder gelangen ausschließlich in Benutzerrollen. Interne `VisionMessage`-Objekte sind keine zusätzlichen Browserverträge; ihre Bildbytes sind von Standardserialisierung und Repräsentation ausgeschlossen.

Pro normalisiertem Bild reserviert der Tokenzähler zusätzlich 4096 Kontext-/Tagestokens. Das ist eine konservative lokale Schätzung, kein vom Noris-Katalog belegter exakter Bildtokenpreis oder Tokenizer. Bis zu zehn Bilder im vollständigen Gesprächspfad werden rekonstruiert; der tatsächliche serialisierte Providerrequest muss außerdem innerhalb von `NORIS_LLM_MAX_REQUEST_BYTES` bleiben. Output-, Reasoning-, System-, Sicherheits- und Tagesreserven bleiben unverändert.

Das Kontextfenster folgt seit der Korrektur vom 2026-10-11 der gültigen `max_context_length`-Angabe des frischen Providerkatalogs. Der bisherige Registry-Standard von 8192 Tokens begrenzt einen bestätigten größeren Kontext nicht mehr. DeepSeek meldet 1048576 Kontexttokens und behält 4096 Outputtokens; damit passt ein einzelnes Bild samt kurzem Text und Reserven in den Kontext. Explizite `context_window`-/`provider_context_window`-Betreibergrenzen bleiben wirksam; bei fehlenden oder anders dimensionierten Providerwerten bleibt der konservative Rückfall von höchstens 8192 Tokens bestehen. Die strukturelle Obergrenze von zwei Millionen Tokens und die übrigen Sicherheits-/Budgetlimits bleiben erhalten. Ein ausdrücklich auf 8192 Kontext und 4096 Output begrenztes Profil kann weiterhin kein Bild zusätzlich aufnehmen. Die Kontextfehlermeldung erklärt jetzt Gespräch, Anhänge und reservierte Antwort, statt stets einen neuen Chat zu empfehlen.

## Grenzen und Schutzmaßnahmen

| Umgebungsvariable | Standard |
| --- | --- |
| `NORIS_CHAT_ATTACHMENT_MAX_FILE_BYTES` | 10 MiB, hart maximal 20 MiB |
| `NORIS_CHAT_ATTACHMENT_MAX_FILES` | 5 pro Nachricht, hart maximal 10 |
| `NORIS_CHAT_ATTACHMENT_OWNER_QUOTA_BYTES` | 100 MiB |
| `NORIS_CHAT_ATTACHMENT_MAX_TEXT_CHARS` | 16.000, hart maximal 32.000; TXT/Markdown/Referenzen und PDF-Auszüge pro Anfrage |
| `NORIS_CHAT_ATTACHMENT_MAX_PDF_TEXT_CHARS` | 500.000, hart maximal 1.000.000; vollständige PDF-Extraktion |
| `NORIS_CHAT_ATTACHMENT_MAX_PDF_PAGES` | 100, hart maximal 100 |
| `NORIS_CHAT_ATTACHMENT_MAX_IMAGE_PIXELS` | 16.000.000, zusätzlich höchstens 8192 px pro Dimension |
| `NORIS_CHAT_ATTACHMENT_ORPHAN_HOURS` | 24 |
| `NORIS_CHAT_ATTACHMENT_STORAGE_DIR` | privates Volume / lokales privates Verzeichnis |

Zusätzlich gelten höchstens 200 aktive Dateien je Besitzer, 60 Sekunden für den Uploadstream und 15 Sekunden Parser-Wartezeit. Quoten werden durch eine PostgreSQL-Transaktionssperre je Besitzer über parallele Anfragen hinweg gesichert. Speicherpfade stammen ausschließlich aus zufälligen serverseitigen Keys; Clientnamen werden nie als Pfade übernommen. ZIP, SVG, Office-Dateien und ausführbare Formate werden abgelehnt.

Explizit konfigurierte niedrigere PDF-Seiten- und Textgrenzen bleiben wirksam. Für die gemeldete 29-Seiten-PDF mit 43.313 Textzeichen genügen die neuen Standards; eine bestehende Betreiberkonfiguration mit weniger als 29 erlaubten Seiten muss angepasst werden. Überschreitet die vollständige Extraktion ein Limit, wird der Upload vollständig zurückgerollt. Es wird kein unvollständiges Dokument als erfolgreich gespeichert.

Fehler unterscheiden beschädigtes/falsches Format (`ATTACHMENT_INVALID`), Verschlüsselung (`ATTACHMENT_PDF_ENCRYPTED`), Seitenlimit (`ATTACHMENT_PDF_PAGE_LIMIT`), extrahierte Textmenge (`ATTACHMENT_TEXT_LIMIT`), sichere Ressourcen-/Dekompressionsgrenzen (`ATTACHMENT_PROCESSING_LIMIT`), Parserzeit (`ATTACHMENT_PROCESSING_TIMEOUT`) und Uploadzeit (`ATTACHMENT_UPLOAD_TIMEOUT`). Dateigröße und Besitzerquote behalten `ATTACHMENT_SIZE` bzw. `ATTACHMENT_QUOTA`. Die Meldungen enthalten keine Parserdetails, Dateiinhalte oder Zugangsdaten. Textlose PDFs werden gespeichert, bleiben aber für Textfragen gesperrt.

PDF-/Bildparser laufen in separaten, begrenzten Prozessen ohne geerbte Anwendungskonfiguration oder Provider-Schlüssel: 256 MiB Adressraum, 10 CPU-Sekunden, 32 Dateideskriptoren und maximal zwei gleichzeitige Parser pro Backend-Prozess. Der Prozess führt keine eingebetteten PDF-Inhalte aus. Diese Ressourcenbegrenzung ersetzt keine Betriebssystem-Sandbox; ein kompromittierter Parser läuft weiterhin mit dem nicht privilegierten Backend-Benutzer. Parser müssen aktuell gehalten werden. Die Grenze für PDF-Dekompression und die Bildgrenzen folgen den Sicherheitsmechanismen von [pypdf](https://pypdf.readthedocs.io/en/6.7.3/user/security.html) und [Pillow](https://pillow.readthedocs.io/en/stable/handbook/security.html).

Abgebrochene oder ungültige Uploads hinterlassen keine bestätigten Metadaten und räumen die temporären Bytes auf. Die Bereinigung läuft beim Start, stündlich und nach Gesprächslöschung. Sie entfernt abgelaufene ungesendete Dateien, Dateiinhalt gelöschter Gespräche und alte, unbekannte zufällige Storage-Keys. Extrahierter Text wird dabei ebenfalls entfernt. Die bestehende Gesprächslöschung bleibt eine Soft-Delete-Operation. Ein Absturz zwischen Dateischreiben und Datenbankcommit wird durch die Bereinigung unbekannter Dateien aufgefangen.

## Tests

Die ergänzte Bestandsaufnahme, wiederverwendeten Komponenten und offenen Einschränkungen stehen in [MULTIMODAL-AUDIT.md](MULTIMODAL-AUDIT.md). Die lokalen Regressionstests prüfen auch die bestehenden Bild-/Vorschaufunktionen mit synthetischen Dateien und Provider-Simulatoren; erfolgreicher Live-Modellbetrieb wird damit nicht behauptet.

PDF-Regressionstests bilden den gemeldeten Fall ausschließlich synthetisch nach: PDF 1.5, 29 Seiten, 995.537 Bytes und exakt 43.313 extrahierte Zeichen. Sie prüfen vollständige Extraktion im isolierten Prozess, Seiten-/Abschnittszuordnung, unveränderte Originalbytes, PostgreSQL-Persistenz, Wiederherstellung durch eine weitere App-Instanz, relevante Fundstellen auf der letzten Seite, erneute Auswahl bei Folgefragen, Modellkontextgrenzen, differenzierte Fehler sowie Bereinigung. Kostenpflichtige Modelle werden dafür nicht aufgerufen.

Unit-Tests erzeugen ausschließlich synthetische TXT-, PDF- und Bilddateien. PostgreSQL-/WebSocket-Integrationstests prüfen Uploadbestätigung, Besitz, Herkunft, MIME/Signaturen, Größen- und Speicherquoten, Abbruch/Rollback, Downloadrechte, Neustartpersistenz, Bereinigung, tatsächlichen Modellkontext und dessen vorhandenes Limit. Browsertests verwenden die reale API und den lokalen Provider-Simulator für Mehrfachauswahl, Wiederherstellung, Fehler/Wiederholung, Entfernen, Grenzen, adaptive Vorschau und mobile Geometrie. Keine CI-Prüfung ruft kostenpflichtige Noris-Modelle auf.
