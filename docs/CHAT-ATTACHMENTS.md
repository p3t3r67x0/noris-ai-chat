# Persistente Chat-Dateianhänge

Der Plus-Button öffnet das vorhandene Nuxt-UI-Aktionsmenü mit „Dateien hinzufügen“ und den nativen Mehrfach-Dateidialog. Jeder Upload verwendet die authentifizierte API. Erst eine erfolgreiche `201`-Antwort bestätigt den Anhang; Browserfortschritt allein gilt nicht als erfolgreicher Upload. Fehler lassen sich vor dem Senden erneut versuchen, laufende Uploads abbrechen und bestätigte, noch nicht gesendete Dateien entfernen.

## API und Persistenz

- `GET /api/v1/chat/attachments/limits`: konfigurierte Grenzen und erlaubte MIME-Typen.
- `POST /api/v1/chat/attachments?conversationId=<UUID>&filename=<Anzeigename>`: ein roher Datei-Body mit passendem `Content-Type`, Antwort mit Attachment-Metadaten.
- `GET /api/v1/chat/attachments?conversationId=<UUID>`: bestätigte Metadaten für die Unterhaltung, einschließlich ungesendeter Anhänge zur Wiederherstellung nach Reload.
- `DELETE /api/v1/chat/attachments/<UUID>`: entfernt einen ungesendeten Anhang und seine gespeicherten Bytes. Bereits einer Nachricht zugeordnete Anhänge liefern `409`.
- `GET /api/v1/chat/attachments/<UUID>/content`: kontrollierter Download nach Besitzprüfung, mit `Content-Disposition: attachment`, `nosniff`, Sandbox-CSP und `no-store`.

Die Alembic-Migration `0006_chat_attachments` ergänzt `chat_attachment`, ohne bestehende Gespräche oder Nachrichten zu löschen. PostgreSQL enthält Besitz, Unterhaltung, Nachrichtenzuordnung, Anzeigenamen, zufälligen Storage-Key, MIME-Typ, Größe, SHA-256, Status, Erstellungszeit und begrenzten extrahierten Text. Binärinhalte werden nicht in Chat-Nachrichten oder WebSocket-JSON gespeichert. API-Antworten enthalten keine Storage-Pfade, extrahierten Inhalte oder Provider-Zugangsdaten.

Docker Compose verwendet das separate Named Volume `attachment_data` unter `/var/lib/noris-ai/attachments`, außerhalb des Webroots. Das Verzeichnis gehört dem nicht privilegierten Backend-Benutzer und ist mit `0700`, Dateien mit `0600` geschützt. Lokaler Betrieb verwendet standardmäßig `backend/.local/attachments`, ausgeschlossen von Git und Docker-Build-Kontext. Datenbank und Attachment-Volume gehören gemeinsam in Backup und Wiederherstellung. Ein Backend-Neustart erhält bestätigte Metadaten und Dateiinhalt.

Vor dem Start der neuen Backend-Version muss `make migrate` mit dem bestehenden Migrationszugang ausgeführt werden. Compose erledigt dies über den bestehenden `migrate`-Dienst. Keine bestehenden Datenbankvolumes entfernen.

## Unterstützte Verarbeitung

| Typ | Prüfung und Verarbeitung | Verwendung im Modell |
| --- | --- | --- |
| UTF-8 TXT/Markdown | Erweiterung/MIME, strikte UTF-8-Dekodierung, keine binären Steuerzeichen, begrenzte Textlänge | Extrahierter Text als Benutzerinhalt |
| PDF | `%PDF-`-Signatur, strikter Parser, unverschlüsselt, Seiten- und Dekompressionsgrenzen, Textextraktion | Nur tatsächlich extrahierter Text; kein OCR |
| PNG/JPEG | Erwartetes Bildformat, Signatur und vollständiges Dekodieren, Pixel-/Dimensionsgrenzen, keine Animationen | Speicherung und Download; keine Bildanalyse |

Die Zustände sind bewusst verschieden: `ready` bedeutet gespeichert und Text extrahiert; `stored` bedeutet gespeichert, jedoch kein für den aktuellen Textvertrag verwendbarer Inhalt. Die API nennt zusätzlich `extractionStatus` und `modelUsable`. Bilder und textlose PDFs blockieren das Senden mit verständlicher Vorschauinformation, bis sie entfernt werden. Ein leerer oder rein aus Leerzeichen bestehender Textanhang wird ebenfalls nicht als analysierbar angezeigt.

Der bestehende Noris-Providervertrag sendet Textnachrichten. Modellkatalog, Freigabe, Modalitäten, Kontextfenster und Ausgabelimits bleiben dynamisch. Es gibt keinen erfundenen Vision-Vertrag, automatischen Modellwechsel, OCR-Dienst oder Upload an weitere externe Dienste. Sobald ein bestätigter Vision-Vertrag implementiert wird, muss dessen Payload separat geprüft werden; eine `image`-Modalität allein schaltet die Funktion hier nicht frei.

## WebSocket und Kontextbudget

`chat.generate` erhält optional `attachmentIds`. Das Backend prüft konfigurierte Anzahl, vorhandenen und abgeschlossenen Upload, Besitzer, Unterhaltung, Nachrichtenzuordnung, zugelassenen Status und Modellkompatibilität. Die Zuordnung erfolgt in derselben Transaktion wie die bestehende Generierung. Doppelte oder fremde IDs und inkompatible Inhalte werden abgelehnt.

Der Nachrichtenpfad wird weiterhin aus PostgreSQL rekonstruiert. Extrahierter Dateiinhalt wird als ausdrücklich unvertrauenswürdige Daten innerhalb einer Benutzer-Nachricht ergänzt. Er kann keine privilegierte Systemrolle erhalten. Dateitext zählt zu den vorhandenen Zeichen-, Byte-, Token-, Kontext- und Budgetgrenzen; er wird weder still abgeschnitten noch an diesen Grenzen vorbei zum Provider geschickt. Gesendete Anhänge bleiben in gespeicherten Nachrichten sichtbar und nach Reload kontrolliert herunterladbar.

## Grenzen und Schutzmaßnahmen

| Umgebungsvariable | Standard |
| --- | --- |
| `NORIS_CHAT_ATTACHMENT_MAX_FILE_BYTES` | 10 MiB, hart maximal 20 MiB |
| `NORIS_CHAT_ATTACHMENT_MAX_FILES` | 5 pro Nachricht, hart maximal 10 |
| `NORIS_CHAT_ATTACHMENT_OWNER_QUOTA_BYTES` | 100 MiB |
| `NORIS_CHAT_ATTACHMENT_MAX_TEXT_CHARS` | 16.000 |
| `NORIS_CHAT_ATTACHMENT_MAX_PDF_PAGES` | 20 |
| `NORIS_CHAT_ATTACHMENT_MAX_IMAGE_PIXELS` | 16.000.000, zusätzlich höchstens 8192 px pro Dimension |
| `NORIS_CHAT_ATTACHMENT_ORPHAN_HOURS` | 24 |
| `NORIS_CHAT_ATTACHMENT_STORAGE_DIR` | privates Volume / lokales privates Verzeichnis |

Zusätzlich gelten höchstens 200 aktive Dateien je Besitzer, 60 Sekunden für den Uploadstream und 15 Sekunden Parser-Wartezeit. Quoten werden durch eine PostgreSQL-Transaktionssperre je Besitzer über parallele Anfragen hinweg gesichert. Speicherpfade stammen ausschließlich aus zufälligen serverseitigen Keys; Clientnamen werden nie als Pfade übernommen. ZIP, SVG, Office-Dateien und ausführbare Formate werden abgelehnt.

PDF-/Bildparser laufen in separaten, begrenzten Prozessen ohne geerbte Anwendungskonfiguration oder Provider-Schlüssel: 256 MiB Adressraum, 10 CPU-Sekunden, 32 Dateideskriptoren und maximal zwei gleichzeitige Parser pro Backend-Prozess. Der Prozess führt keine eingebetteten PDF-Inhalte aus. Diese Ressourcenbegrenzung ersetzt keine Betriebssystem-Sandbox; ein kompromittierter Parser läuft weiterhin mit dem nicht privilegierten Backend-Benutzer. Parser müssen aktuell gehalten werden. Die Grenze für PDF-Dekompression und die Bildgrenzen folgen den Sicherheitsmechanismen von [pypdf](https://pypdf.readthedocs.io/en/6.7.3/user/security.html) und [Pillow](https://pillow.readthedocs.io/en/stable/handbook/security.html).

Abgebrochene oder ungültige Uploads hinterlassen keine bestätigten Metadaten und räumen die temporären Bytes auf. Die Bereinigung läuft beim Start, stündlich und nach Gesprächslöschung. Sie entfernt abgelaufene ungesendete Dateien, Dateiinhalt gelöschter Gespräche und alte, unbekannte zufällige Storage-Keys. Extrahierter Text wird dabei ebenfalls entfernt. Die bestehende Gesprächslöschung bleibt eine Soft-Delete-Operation. Ein Absturz zwischen Dateischreiben und Datenbankcommit wird durch die Bereinigung unbekannter Dateien aufgefangen.

## Tests

Unit-Tests erzeugen ausschließlich synthetische TXT-, PDF- und Bilddateien. PostgreSQL-/WebSocket-Integrationstests prüfen Uploadbestätigung, Besitz, Herkunft, MIME/Signaturen, Größen- und Speicherquoten, Abbruch/Rollback, Downloadrechte, Neustartpersistenz, Bereinigung, tatsächlichen Modellkontext und dessen vorhandenes Limit. Browsertests verwenden die reale API und den lokalen Provider-Simulator für Mehrfachauswahl, Wiederherstellung, Fehler/Wiederholung, Entfernen, Grenzen, adaptive Vorschau und mobile Geometrie. Keine CI-Prüfung ruft kostenpflichtige Noris-Modelle auf.
