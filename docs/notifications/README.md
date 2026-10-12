# Fehler und Benachrichtigungen im Frontend

Stand: 12. Oktober 2026. Ausgangspunkt: `d7c3100` auf `main`.

## Bestandsaufnahme und Darstellungsmatrix

Die fachlichen Zustände bleiben in den bestehenden Composables und Nachrichten. „Persistent“ bedeutet hier: Der Zustand muss im Kontext auffindbar bleiben, bis eine explizite Aktion oder ein erfolgreicher fachlicher Vorgang ihn auflöst. Die Lebensdauer eines Toasts verändert keinen dieser Zustände.

| Quelle / Erzeugung | Bestehender Speicher | Anzeige vorher | Doppelung / bisherige Recovery | Neue Darstellung und Recovery | Dauer / Kategorie |
| --- | --- | --- | --- | --- | --- |
| REST: `ChatBackend.request`, Modellkatalog, Titel, SSE-Start | `TransportError.code`, bislang ohne Request-ID | Exception-/Backend-Text an jeweiligem Aufrufer | Gleicher Initialladefehler in `storageWarning` und `sidebarError` | Vertrag und IDs erhalten; ausschließlich Codeübersetzung; Anzeige entscheidet der fachliche Aufrufer | Je Code |
| WebSocket: Ticket, `chat.error`, Generation, Resume-Snapshot | TransportError / Streamereignis; vorhandene Generation-ID | Ereignistext im Stream und Assistant | Generation teils an zwei Orten; Reconnect automatisch im bestehenden Transport | Bestehender Reconnect/Resume; erst terminaler Fehler erzeugt einen Toast, keine neue Modellanfrage | Transient / Generation |
| `useChatStream`: Providerfehler, Timeout, Verbindung, Protokoll, Größenlimits | `status`, `error`, `errorCode`; Assistant `status/errorCode/errorMessage` | `ChatMessage` und `ChatWorkspace.chat-status` | Gleiche Meldung zweimal; Workspace-Retry, Regenerate/Continue am Knoten | Ein zentraler Toast mit Retry/Details; Knoten: „Antwort fehlgeschlagen“, eine ausdrückliche Retry-Aktion, aufklappbare sichere Details; Text und Varianten bleiben erhalten | Toast 12 s; Knoten persistent |
| Stream unterbrochen nach Teilantwort | Nachricht `content`, Streamstatus | Teilantwort plus doppelte Fehlermeldung | Regenerate, teilweise Continue | Teilantwort bleibt; Retry erstellt auf ausdrückliche Aktion eine Antwortvariante; Continue bleibt im Kontext, soweit fachlich zulässig | Generation |
| Ausgabelimit / automatische Fortsetzung / Wiederholung | `incomplete`, `continuationCount`, `errorCode` | Nachricht mit Backendtext; zusätzliche Limitzeilen | Continue nur innerhalb bestehender Limits | Zentraler Warn-Toast; kurzer Status und Details am Knoten; keine neue Anfrage durch Notification Center | 7 s; Kontext persistent |
| Abbruch durch Stop / Escape | `cancelled`, bestehender Text | Statusbereich und kurzer Knotenstatus | Continue, falls zulässig | Fachlicher Status bleibt; kein Fehler-Toast für eine absichtliche Benutzeraktion | Generation / Information |
| `useChatBackend`: Initialisieren / Sidebar / weitere Chats | `sidebarError`, `storageWarning`, `backendReady` | Sidebar und Workspace, teils gleichzeitig | „Neueste Chats laden“ | Ein Toast für die Operation; Sidebar enthält aufklappbaren Status und Laden-Aktion; globale Speicheranzeige ohne zweite Live-Ankündigung | Action; Kontext persistent |
| Aktiver Pfad / ältere Nachrichten / Variante | `historyError`, Ladezustände und Cache | Workspace, Exceptiontext | Chat erneut laden; ältere Seiten teils über generischen Retry | Normalisierter Toast mit zutreffendem Retry; aufklappbarer Status im Verlauf; bereits vorhandene Nachrichten bleiben erhalten | Action; Kontext persistent |
| `useChatBackend.persist`: Create/Rename/Archive/Restore | `storageWarning`, bestehende Ressourcen-/Persistenzqueue | Globaler Workspace-Hinweis mit Exceptiontext | Autorität neu lesen; bislang kein gezielter Retry | Fehler je Operation/Chat identifizieren; Retry führt die betroffene bestehende Ressourcenaktion aus; offene Persistenzaktionen bleiben beim fachlichen Owner und über „Erneut speichern“ auffindbar | Action / Transient |
| Aktiver Chat / Modellpräferenz | bestehender Preferences-Client; zuvor Modell-Speicherfehler still ignoriert | teils nur `storageWarning`, teils keine Anzeige | Keine sichtbare Model-Save-Recovery | Zentrale Fehlermeldung; Wiederholen aus Toast und Kontext. Modellseite enthält Speicherstatus | Action |
| Entwurf speichern / lokale Offlinekopie / Cache | `pendingDrafts`, `sentDrafts`, `storageWarning` | Workspace; lokale Speicherfehler fest formuliert | Wiederherstellen aus Offlinekopie | Warn-/Fehler-Toast, im Kontext aufklappbare Sicherungsinformation; Retry speichert den aktuellen Entwurf, keinen veralteten Snapshot | Persistent / Action |
| Lokale Chats laden / anderer Tab / Speichergrenze (`useChat`) | `storageWarning`, `persistenceAllowed` | Workspace-Hinweis | Reload bei anderem Tab; Backup bleibt | Zentraler Warn-Toast und aufklappbarer Kontext; Reload ausdrücklich; lokale Sicherung nicht überschreiben | Persistent |
| Offlineentwurf gefunden | `pendingDrafts` und vorhandener Entwurf | `storageWarning` als Warnung | Entwurf weiter bearbeiten | Kurze Information „Entwurf wiederhergestellt“; vorhandener Entwurf ist die dauerhafte Recovery | 4,5 s; Information |
| `useChatDrafts`: übergroßer Entwurf | `drafts.error`, unveränderter vorheriger Entwurf | einmal unter Composer; zusätzlich `inputError` sperrt Senden | Eingabe kürzen | Lokale Eingabevalidierung bleibt einmalig im Composer-Kontext; kein globaler Toast | Persistent / Validation |
| Composer / Edit-Dialog: Zeichengrenze | `tooLong`, `editText.length`, konfigurierte Limits | lokaler Hinweis und gesperrte Sendeaktion | Kürzen | Kontextvalidierung unverändert; kein Toast bei jedem Tastendruck | Validation |
| `useModelSelection`: Catalog/Access/Auth/ungültige Konfiguration | `error`, `notice`, `loading`, `stale`, ausgewählte ID | über Composer und Modellseite | Refresh, ausdrückliche Fallbackauswahl | Codeübersetzung, zentraler Toast; aufklappbare Modellzugriffsinformation mit Refresh/Fallback; keine automatische Modellauswahl | Persistent / Transient |
| Modell widerrufen / Katalog veraltet / kein Modell | bestehende Auswahl und Catalog-Metadaten | Statushinweis, Sendesperre | Verfügbares Modell wählen / Katalog laden | Vorhandene Sendesperre bleibt. Eine vom Generierungsfehler ausgelöste Katalogprüfung erzeugt keinen zweiten Toast | Persistent |
| `useChatAttachments.refresh`: Limits / vorhandene Anhänge | `limits`, `records`, `error` | Composer-Hinweis und Upload-Unavailable-Grund | Kein ausdrücklicher Lade-Retry | Normalisierter Toast „Anhänge neu laden“; lokale Information bleibt am Upload-Kontext | Action |
| Dateiupload: Netzwerk/Timeout/Backend/Format/Dateigröße | `UploadEntry.status/error/file/attachment` | Karte mit vollständiger Fehlermeldung; Retry wenn File vorhanden | Originaldatei wurde schon gehalten | Karte bleibt, „Fehlgeschlagen“, normalisierte Erklärung, Retry und Diagnose. Original-File als `markRaw` behalten; bewusst kein zusätzlicher Upload-Toast | Kontext persistent |
| Textreferenz anlegen | `UploadEntry.reference`, Status | Karte, Exceptiontext | Retry mit erhaltener Referenz | Wie Upload; Originalreferenz bleibt bis zum Erfolg | Action |
| Upload-Slots / übergroße Textreferenz | `attachments.error`, unveränderte Auswahl | lokaler Composer-Hinweis | Anzahl reduzieren / kürzer markieren | Kontextvalidierung bleibt mit sicheren Grenzwerten; kein Toast | Persistent / Validation |
| Anhang löschen | Karte, `attachments.error` | Composer-Hinweis | Entfernen erneut anklicken | Zentraler Toast mit Retry, Karte bleibt; kein automatisches Löschen oder Datenverlust | Action |
| Inkompatibler Anhang / Bildmodell / PDF ohne Text | `modelUsable`, `imageCompatible`, bestehende Karte | „Gespeichert · …“; Senden blockiert | Modell wählen oder Anhang entfernen | Vorhandene Karte genügt; kein zusätzlicher Toast für normalen Upload-Erfolg | Persistent / Information |
| Lokale Attachmentkopie in Demo | `attachments.error` | Composer-Hinweis | weiterhin sichtbare Referenzen | Normalisierte Speicherwarnung; Karte bleibt | Persistent |
| `DeleteConversationDialog`: Delete-Fehler | Dialog `error/pending`, vorhandener Chat | Dialog-Alert | Dialog bleibt offen; serverseitige Fehler im alten Backendwrapper jedoch verschluckt | Normalisierter Dialog-Alert mit Diagnose; Serverfehler propagiert, Chat/Nachrichten/Entwurf bleiben bis zur Serverbestätigung; explizites Wiederholen | Action; Dialog persistent |
| Chat gelöscht | bestehende erfolgreiche Delete-Operation | Keine Bestätigung | Kein Undo-Vertrag | Kurzer Erfolgs-Toast erst nach bestätigtem Erfolg; kein Undo | 3,5 s; Erfolg |
| Archiv in Sidebar / Settings | `archiveError` / lokale Archivfehler | lokaler Alert | Archiv erneut laden | Codeübersetzung, lokaler Alert und vorhandener Retry; kein zusätzlicher globaler Toast im Dialog | Action |
| `useConversationSearch` | `error`, bisherige Treffer, Cursor | Suchdialog-Alert, festes UI-Wording | Suche erneut ausführen | Normalisiert, lokale einmalige Ankündigung und Details; Treffer und Cursor bleiben für Retry | Action |
| `SettingsDialog`: Import | `importBusy/importAvailable/storageWarning`, lokales Backup | Feedback in Settings und Workspace | ausdrücklich bestätigter Import; Konflikte behalten Backup | Fehler zentral mit Import-Retry, Ergebnis als aufklappbarer Kontext; Erfolg kurz bestätigen; keine zweite Screenreader-Ankündigung | Action / Erfolg |
| Sprache lokal speichern (`useAppLocale`) | `storageError`, aktuelle Sprachpräferenz | Settings-General-Hinweis | Auswahl bleibt für Sitzung | Kontextbezogene Einstellungsinformation bleibt; keine globale Meldung für einen lokal aufgefangenen Speicherfehler | Persistent |
| Theme / Sidebar-/Scrollpräferenz / optionale Caches | Einstellungen oder gespeicherte Position; Exceptions abgefangen | Keine Fehlermeldung | Anwendung arbeitet mit Sitzungsauswahl/Fallback | Keine neue Benachrichtigung für optionale Caches | Stiller Fallback |
| Nachrichten-/Code-/Diagnosekopie (`useCopy`) | `copied`, `copyError`, Timer | Iconbestätigung / lokaler Hinweis | Text manuell auswählen | Lokale Bestätigung/Recovery bleibt; keine globalen Copy-Toasts | 1,8 s; lokal |
| Bildvorschau fehlgeschlagen | `failedImages` | Bildkartenstatus | Bild erneut laden, Original herunterladen | Kontextstatus und bestehender Retry bleiben | Action |
| Automatischer Titel (`useConversationTitles`) | `pending`, bestehender Fallbacktitel | keine Fehleranzeige | Fallback bleibt, manuelles Umbenennen | Stiller Fallback bleibt; kein Toast, der die Chatantwort stört | Stiller Fallback |
| Markdown / Highlighting | Originaltext, optionaler Highlighter | lesbarer Plaintext bei Fehler | Lesen/Kopieren weiter möglich | Stiller Fallback bleibt | Stiller Fallback |
| Readiness (`useServiceHealth`, Statusseite) | `checking/healthy/unavailable` | lokale `role=status`-Anzeige mit Refresh | Status erneut prüfen | Bestehende Statusseite bleibt die lokale Serviceanzeige; kein dauerhafter Toast | Progress / Action |
| Websuche / Research / Lernen | bestehender Composer-/Chatmodus und deaktivierte Toolmenüpunkte | Verfügbarkeitsgründe und Lernmodus im Kontext | vorhandene Modi/Aktionen | Keine neuen Toasts für fortlaufende Arbeit. Noch nicht implementierte Tools werden durch diese Arbeit nicht eingeführt | Progress / Information |

## Architektur

`useAppNotifications.ts` ist eine durch `AppNotificationCenter.vue` bereitgestellte Präsentationsschnittstelle innerhalb von `UApp`. Nur diese Schicht schreibt über `useToast()` in den bestehenden Nuxt-UI-Toaster. Es gibt keine zusätzliche UI-Abhängigkeit und keine Änderung am Backend oder GenerationManager.

`normalizeAppError(cause, context)` liest den vorhandenen Fehlercode und die Request-ID aus REST-Envelope oder TransportError. `ERROR_PRESENTATIONS` bestimmt Kategorie, übersetzte Nachricht, Schwere und Recoverystrategie. `OPERATION_TITLES` ergänzt den betroffenen Vorgang. Unbekannte Codes behalten eine sichere technische Kennung für Diagnose und bekommen eine feste verständliche Fallbacknachricht. Exception-, Provider-, Proxy- und Stacktrace-Texte werden nicht als UI-Nachrichten übernommen.

REST-IDs aus `error.request_id` beziehungsweise `X-Request-ID` bleiben erhalten. SSE übernimmt die Request-ID des Responses; WebSocket verwendet die bestehende `requestId`/Generation-ID. Der Assistant erhält ausschließlich sichere Diagnosedaten. Die Detailsansicht exportiert nur Code, Request-ID, Conversation-ID, Generation-ID, Funktion und Zeitpunkt. Kennungen werden auf Länge und zulässige Zeichen geprüft; keine Prompts, Secrets oder Stacks werden kopiert.

Chat-, Generierungs-, Upload- und Einstellungsfehler bleiben beim vorhandenen Owner. Auch fehlgeschlagene Persistenzaktionen werden ausschließlich im bestehenden Backend-Composable für ihre ausdrückliche Wiederholung gehalten. Das Notification Center hält nur maximal drei sichtbare Präsentationen, zwölf wartende Präsentationen und kurzlebige Deduplikationskennungen. Es speichert keine dauerhafte Fehlerhistorie. Toast-Schließen oder -Timeout verändert keine Nachricht und keinen Uploadstatus.

## Deduplikation, Lebensdauer und Overflow

Der Schlüssel besteht aus Fehlercode, Operation, Conversation-ID, Ressourcen-ID und Generation-ID **oder** Request-ID **oder** lokaler Attempt-ID. Eine vorhandene Generation-ID ist stabil auch dann, wenn ein weiterer Beobachter später die Request-ID ergänzt. Zwei Uploads und zwei fachlich unterschiedliche Operationen bleiben getrennt. Neue Versuche ohne serverseitige ID erhalten neue Attempt-IDs.

Die sichtbare oder wartende Meldung wird nicht erneut angelegt. Nach Schließen gilt ein zehnsekündiges, auf maximal 200 Einträge begrenztes Wiederholungsfenster. Spätere unabhängige Operationen werden sofort wieder angezeigt; gleiche Kennungen werden nach dem Fenster wieder zugelassen.

| Schwere | Dauer | Ankündigung |
| --- | --- | --- |
| Erfolg | 3,5 s | `role=status`, polite |
| Information | 4,5 s | `role=status`, polite |
| Warnung | 7 s | `role=status`, polite |
| Fehler | 12 s | `role=alert`, assertive |
| notwendige Aktion ohne Recovery im Kontext | bis Benutzeraktion (`duration: 0`) | je Schwere |

Eine Karte belegt ihren Platz bis zum Abschluss der Nuxt-UI-Schließanimation. Erst danach wird eine wartende Meldung angezeigt. Bei mehr als zwölf wartenden Meldungen erscheint eine zusammengefasste Meldung. Fachliche Recovery bleibt an den Nachrichten, Anhängen, Ladeaktionen und Einstellungs-/Speicherinformationen verfügbar. Normales Senden, Upload-Erfolg, automatischer Titel und laufende Arbeit lösen keine Erfolgs-/Fortschrittstoasts aus.

## Accessibility und Layout

Der Toaster liegt fest oben rechts unter dem vorhandenen Header und außerhalb des Chatlayouts. Farben, Flächen, Rahmen und Typografie verwenden die vorhandenen Tokens. Auf Mobile gelten Safe-Area-Abstände und eine begrenzte Breite. Die Höhe und der obere Offset folgen `visualViewport`, auch bei Bildschirmtastatur; überlange Stapel scrollen innerhalb dieses Bereichs. `prefers-reduced-motion` deaktiviert Toastanimationen und Übergänge.

Das Center besitzt genau eine Alert- und eine Status-Live-Region. Die installierte Reka-Version markiert ihren eigenen versteckten Toast-Announcer mit `aria-hidden`; deshalb übernimmt das Center die Ankündigungen ausdrücklich selbst. Kontextstatus, die bereits über den Center-Toast angekündigt wurden, besitzen keine zweite Live-Region. Lokal allein angezeigte Upload-/Dialog-/Validierungsfehler behalten ihre eigene Ankündigung. Normale Toasts übernehmen keinen Fokus. Aktionen und Schließen sind per Tastatur bedienbar; Nuxt UI/Reka behandeln Escape, F8-Zugang zum Notificationbereich und Fokus bei ausdrücklichen Aktionen. Sichtbare Fokusindikatoren bleiben bestehen.

## Screenshots

Die Bilder enthalten ausschließlich synthetische Daten. Vorher: unveränderter Produktionsbuild des Ausgangscommits. Nachher: Produktionsbuild dieses Branches; echte Frontend-Ressourcen-/WebSocket-Abläufe gegen kontrollierte Browserfixtures. Erfolg/Information/Warnung und mehrere Karten sind zusätzliche Palettefälle der Produktions-Präsentationsschnittstelle; Fehler, Retry und Upload laufen über die fachlichen UI-Aktionen.

| Größe / Theme | Modellfehler vorher → nachher | Upload vorher → nachher | Weitere neue Toasts |
| --- | --- | --- | --- |
| 1700 × 900 / light | [Vorher](screenshots/before/1700-light-generation.png) → [Nachher](screenshots/after/1700-light-generation.png) | [Vorher](screenshots/before/1700-light-upload.png) → [Nachher](screenshots/after/1700-light-upload.png) | [Erfolg](screenshots/after/1700-light-success.png), [Info](screenshots/after/1700-light-info.png), [Warnung](screenshots/after/1700-light-warning.png), [Retry](screenshots/after/1700-light-error-retry.png), [Mehrere](screenshots/after/1700-light-multiple.png) |
| 1700 × 900 / dark | [Vorher](screenshots/before/1700-dark-generation.png) → [Nachher](screenshots/after/1700-dark-generation.png) | [Vorher](screenshots/before/1700-dark-upload.png) → [Nachher](screenshots/after/1700-dark-upload.png) | [Erfolg](screenshots/after/1700-dark-success.png), [Info](screenshots/after/1700-dark-info.png), [Warnung](screenshots/after/1700-dark-warning.png), [Retry](screenshots/after/1700-dark-error-retry.png), [Mehrere](screenshots/after/1700-dark-multiple.png) |
| 1440 × 900 / light | [Vorher](screenshots/before/1440-light-generation.png) → [Nachher](screenshots/after/1440-light-generation.png) | [Vorher](screenshots/before/1440-light-upload.png) → [Nachher](screenshots/after/1440-light-upload.png) | [Erfolg](screenshots/after/1440-light-success.png), [Info](screenshots/after/1440-light-info.png), [Warnung](screenshots/after/1440-light-warning.png), [Retry](screenshots/after/1440-light-error-retry.png), [Mehrere](screenshots/after/1440-light-multiple.png) |
| 1440 × 900 / dark | [Vorher](screenshots/before/1440-dark-generation.png) → [Nachher](screenshots/after/1440-dark-generation.png) | [Vorher](screenshots/before/1440-dark-upload.png) → [Nachher](screenshots/after/1440-dark-upload.png) | [Erfolg](screenshots/after/1440-dark-success.png), [Info](screenshots/after/1440-dark-info.png), [Warnung](screenshots/after/1440-dark-warning.png), [Retry](screenshots/after/1440-dark-error-retry.png), [Mehrere](screenshots/after/1440-dark-multiple.png) |
| 390 × 844 / light | [Vorher](screenshots/before/390-light-generation.png) → [Nachher](screenshots/after/390-light-generation.png) | [Vorher](screenshots/before/390-light-upload.png) → [Nachher](screenshots/after/390-light-upload.png) | [Erfolg](screenshots/after/390-light-success.png), [Info](screenshots/after/390-light-info.png), [Warnung](screenshots/after/390-light-warning.png), [Retry](screenshots/after/390-light-error-retry.png), [Mehrere](screenshots/after/390-light-multiple.png) |
| 390 × 844 / dark | [Vorher](screenshots/before/390-dark-generation.png) → [Nachher](screenshots/after/390-dark-generation.png) | [Vorher](screenshots/before/390-dark-upload.png) → [Nachher](screenshots/after/390-dark-upload.png) | [Erfolg](screenshots/after/390-dark-success.png), [Info](screenshots/after/390-dark-info.png), [Warnung](screenshots/after/390-dark-warning.png), [Retry](screenshots/after/390-dark-error-retry.png), [Mehrere](screenshots/after/390-dark-multiple.png) |

## Fehlercodes und Präsentationsentscheidungen

Die Tabelle enthält alle vorhandenen öffentlichen Chat-/LLM-/REST-Fehlercodes sowie die bereits verwendeten Transport-/Runtimecodes und explizite lokale Präsentationszustände. `MODEL_CATALOG_STALE`, `NO_MODELS`, `INVALID_CONFIGURATION` und `STORAGE_*` benennen vorhandene lokale Zustände; sie erweitern keinen Backendvertrag. Kategorie und Recovery beziehen sich auf den Code, die betroffene Funktion bestimmt den oben dokumentierten Anzeigeort. Upload-, Such- und Dialogfehler können dieselben Codes ausschließlich lokal darstellen.

| Code / interner Präsentationszustand | Kategorie | Nachricht | Globale Schwere | Recoverystrategie |
| --- | --- | --- | --- | --- |
| `ACCESS_DENIED` | persistent | Bitte melde dich für den Chatzugriff an. | error | signin |
| `ORIGIN_DENIED` | persistent | Der Chatzugriff ist für diese Adresse nicht freigegeben. | error | configuration |
| `LLM_DISABLED` | persistent | Die Modellanbindung ist noch nicht freigeschaltet. | error | configuration |
| `MODEL_UNAVAILABLE` | persistent | Dein gewähltes Modell ist nicht mehr verfügbar. Wähle ein verfügbares Modell; dein Chat und Entwurf bleiben erhalten. | error | models |
| `MODEL_CATALOG_STALE` | persistent | Der Modellkatalog ist veraltet. Neue Anfragen sind bis zur Prüfung gesperrt. | warning | reload |
| `NO_MODELS` | persistent | Für diesen Zugang sind derzeit keine Chatmodelle verfügbar. | warning | models |
| `INVALID_CONFIGURATION` | persistent | Die Modellkonfiguration konnte nicht gelesen werden. Bitte lade die Modelle erneut. | error | reload |
| `PROVIDER_AUTH_FAILED` | persistent | Die Anmeldung beim Modelldienst funktioniert derzeit nicht. Bitte prüfe den Modellzugriff. | error | configuration |
| `PROVIDER_UNREACHABLE` | transient | Der Modelldienst ist momentan nicht erreichbar. Bitte versuche es erneut. | error | retry |
| `PROVIDER_ERROR` | transient | Der Modelldienst konnte die Anfrage gerade nicht bearbeiten. Bitte versuche es erneut. | error | retry |
| `NETWORK_ERROR` | transient | Die Verbindung ist unterbrochen. Prüfe deine Internetverbindung und versuche es erneut. | error | retry |
| `TIMEOUT` | transient | Die Anfrage hat zu lange gedauert. Bitte versuche es erneut. | error | retry |
| `RATE_LIMIT` | transient | Es laufen gerade zu viele Anfragen. Warte einen Moment und versuche es erneut. | warning | retry |
| `CONNECTION_LIMIT` | transient | Es sind zu viele Chatverbindungen geöffnet. Schließe einen anderen Chat-Tab und verbinde dich erneut. | warning | reload |
| `NOT_READY` | transient | Der Chatdienst ist momentan nicht bereit. Bitte versuche es gleich erneut. | error | retry |
| `BUDGET_LIMIT` | persistent | Das tägliche Nutzungslimit ist erreicht. Bitte versuche es morgen erneut. | warning | none |
| `STREAM_INTERRUPTED` | generation | Die Antwort wurde unterbrochen. Der bisherige Text bleibt erhalten. Bitte versuche es erneut. | error | retry |
| `INTERRUPTED` | generation | Die Generierung wurde unterbrochen. Der gespeicherte Antwortstand bleibt erhalten. | error | retry |
| `INVALID_RESPONSE` | generation | Die Antwort konnte nicht vollständig übertragen werden. Bitte versuche es erneut. | error | retry |
| `OUTPUT_LIMIT` | generation | Das Ausgabelimit ist erreicht. Der bisherige Text bleibt erhalten. | warning | none |
| `RESPONSE_SIZE_LIMIT` | generation | Die Antwort hat ihre Größenbegrenzung erreicht. Der bisherige Text bleibt erhalten. | warning | none |
| `STREAM_SIZE_LIMIT` | generation | Die Übertragung hat ihre Größenbegrenzung erreicht. Der bisherige Text bleibt erhalten. | warning | none |
| `CONTINUATION_LIMIT` | generation | Das Fortsetzungslimit ist erreicht. Der bisherige Text bleibt erhalten. | warning | none |
| `AUTO_CONTINUATION_LIMIT` | generation | Das Limit für automatische Fortsetzungen ist erreicht. Der bisherige Text bleibt erhalten. | warning | none |
| `DUPLICATE_CONTINUATION` | generation | Das Modell hat vorhandenen Text wiederholt. Die bisherige Antwort bleibt erhalten. | warning | none |
| `CANCELLED` | generation | Die Antwort wurde gestoppt. Der bisherige Text bleibt erhalten. | info | none |
| `CONTENT_FILTERED` | persistent | Der Modelldienst konnte diese Anfrage nicht beantworten. Bitte formuliere sie anders. | error | edit |
| `CONTEXT_LIMIT` | persistent | Der Chat mit seinen Anhängen ist für dieses Modell zu lang. Kürze den Inhalt oder wähle ein Modell mit größerem Kontext. | error | edit |
| `REQUEST_TOO_LARGE` | persistent | Die Anfrage ist zu groß. Bitte kürze die Nachricht oder entferne Anhänge. | error | edit |
| `REASONING_UNSUPPORTED` | persistent | Diese Denkstufe wird vom ausgewählten Modell nicht unterstützt. Wähle eine andere Denkstufe. | error | edit |
| `ATTACHMENT_NOT_FOUND` | persistent | Diese Datei ist nicht mehr verfügbar. Bitte hänge sie erneut an. | error | remove |
| `ATTACHMENT_TYPE` | persistent | Dieser Dateityp wird nicht unterstützt. Verwende Text, Markdown, PDF, PNG oder JPEG. | error | remove |
| `ATTACHMENT_INVALID` | persistent | Die Datei ist beschädigt oder hat ein anderes Format. Bitte wähle eine gültige Datei. | error | remove |
| `ATTACHMENT_PDF_ENCRYPTED` | persistent | Verschlüsselte PDFs werden nicht unterstützt. Bitte wähle eine unverschlüsselte Datei. | error | remove |
| `ATTACHMENT_PDF_PAGE_LIMIT` | persistent | Die PDF hat zu viele Seiten. Bitte wähle eine kleinere Datei. | error | remove |
| `ATTACHMENT_TEXT_LIMIT` | persistent | Die Datei enthält zu viel Text. Bitte kürze sie oder wähle eine kleinere Datei. | error | remove |
| `ATTACHMENT_PROCESSING_LIMIT` | persistent | Die Datei ist zu aufwendig zu verarbeiten. Bitte wähle eine kleinere Datei. | error | remove |
| `ATTACHMENT_SIZE` | persistent | Die Datei ist leer oder zu groß. Bitte wähle eine kleinere Datei mit Inhalt. | error | remove |
| `ATTACHMENT_QUOTA` | persistent | Die Datei- oder Speichergrenze ist erreicht. Entferne nicht mehr benötigte Anhänge. | error | remove |
| `ATTACHMENT_IN_USE` | persistent | Eine gesendete Datei kann nur zusammen mit dem Chat gelöscht werden. | error | none |
| `ATTACHMENT_INCOMPATIBLE` | persistent | Das gewählte Modell kann diesen Anhang nicht verwenden. Wähle ein passendes Modell oder entferne den Anhang. | error | models |
| `ATTACHMENT_PROCESSING_TIMEOUT` | transient | Die Dateiverarbeitung hat zu lange gedauert. Bitte versuche es erneut. | error | retry |
| `ATTACHMENT_UPLOAD_TIMEOUT` | transient | Der Upload hat zu lange gedauert. Bitte versuche es erneut. | error | retry |
| `NOT_FOUND` | persistent | Dieser Chat ist nicht mehr verfügbar. Lade die Chatliste erneut. | error | reload |
| `VERSION_CONFLICT` | action | Der Chat wurde inzwischen geändert. Lade den aktuellen Stand und versuche es erneut. | error | reload |
| `INVALID_CURSOR` | action | Die Chatliste hat sich geändert. Bitte lade sie erneut. | error | reload |
| `INVALID_PARENT` | action | Die ursprüngliche Nachricht ist nicht verfügbar. Bitte lade den Chat erneut. | error | reload |
| `INVALID_LEAF` | action | Diese Chatvariante ist nicht verfügbar. Bitte lade den Chat erneut. | error | reload |
| `INVALID_MESSAGE` | action | Die Nachricht konnte nicht übernommen werden. Bitte prüfe deine Eingabe. | error | edit |
| `MESSAGE_EXISTS` | action | Diese Nachricht wurde bereits geändert. Bitte lade den Chat erneut. | error | reload |
| `CONVERSATION_EXISTS` | action | Dieser Chat ist bereits mit anderen Daten vorhanden. Die lokale Sicherung bleibt erhalten. | error | none |
| `IMPORT_CONFLICT` | action | Der Import enthält Konflikte. Es wurden keine neuen Chats übernommen; der lokale Bestand bleibt erhalten. | error | none |
| `IMPORT_INVALID` | persistent | Die lokale Chatsicherung konnte nicht gelesen werden. Sie bleibt erhalten. | error | none |
| `GENERATION_NOT_FOUND` | generation | Die Generierung ist nicht mehr verfügbar. Lade den Chat erneut. | error | reload |
| `GENERATION_ACTIVE` | generation | Für diese Nachricht läuft bereits eine Antwort. Bitte warte auf ihren Abschluss. | info | none |
| `TITLE_ALREADY_ATTEMPTED` | action | Der Chat behält seinen bisherigen Titel. | info | none |
| `INVALID_INPUT` | action | Die Eingabe konnte nicht übernommen werden. Bitte prüfe sie und versuche es erneut. | error | edit |
| `INVALID_REQUEST` | action | Die Anfrage konnte nicht übernommen werden. Bitte lade den Chat erneut. | error | reload |
| `VALIDATION_ERROR` | action | Die Eingabe konnte nicht übernommen werden. Bitte prüfe sie und versuche es erneut. | error | edit |
| `HTTP_ERROR` | action | Die Anfrage konnte gerade nicht ausgeführt werden. Bitte versuche es erneut. | error | retry |
| `DATABASE_ERROR` | transient | Der Chat konnte gerade nicht gespeichert werden. Dein bisheriger Text bleibt erhalten. | error | retry |
| `INTERNAL_ERROR` | transient | Der Chatdienst konnte die Anfrage gerade nicht bearbeiten. Bitte versuche es erneut. | error | retry |
| `REQUEST_FAILED` | action | Die Aktion konnte gerade nicht ausgeführt werden. Bitte versuche es erneut. | error | retry |
| `MOCK_FAILURE` | generation | Die Antwort konnte nicht abgeschlossen werden. Bitte versuche es erneut. | error | retry |
| `STORAGE_UNAVAILABLE` | persistent | Änderungen können gerade nicht lokal gespeichert werden. Behalte die Seite geöffnet, um deinen Entwurf zu sichern. | warning | none |
| `STORAGE_CHANGED` | persistent | Chats wurden in einem anderen Tab geändert. Lade diese Seite neu, um den aktuellen Stand zu verwenden. | warning | reload |
| `STORAGE_INVALID` | persistent | Gespeicherte Chats konnten nicht geladen werden. Die bisherige Sicherung bleibt erhalten. | warning | none |

Recoverystrategien: `retry` = betroffene Aktion ausdrücklich wiederholen; `reload` = vorhandene Ressourcen erneut laden; `models` = verfügbare Modellauswahl prüfen; `signin` = bestehenden Zugang anmelden; `configuration` = Dienst-/Zugriffskonfiguration prüfen; `edit` = Eingabe/Denkstufe/Anhänge ändern; `remove` = inkompatiblen Anhang entfernen/ersetzen; `none` = vorhandenen Text/Status erhalten, kein automatischer Versuch. Eine Strategie ist kein zusätzlicher Backend-Endpunkt.

## Lokale Prüfung

Die direkt betroffenen Unit- und Composable-Integrationstests, die separate Notification-Playwrightsuite, Linting der geänderten Frontenddateien, Nuxt-/Test-Typecheck und Produktionsbuild wurden lokal ausgeführt. Ausführliche Ergebnisse und Befehle stehen in [validation.md](validation.md). CI wurde auf ausdrücklichen Wunsch nicht ausgeführt; der Commit enthält `[skip ci]` für die vorhandenen `push`-/`pull_request`-Workflows. Keine automatische Zusammenführung und keine Änderungen am Produktivserver.

## Grenzen

- Browserfixtures simulieren vorhandene REST-/WebSocketverträge, einschließlich Fehlern. Es werden keine externen Provider angefragt; Backend-Datenbank-/Produktivtests wurden nicht ausgeführt.
- Browserchecks prüfen DOM-Live-Regionen, Tastatur und Fokus. Eine manuelle Prüfung mit NVDA/VoiceOver und einer echten iOS-/Android-Bildschirmtastatur bleibt sinnvoll; diese wird nicht als automatisch bestanden ausgewiesen.
- Fehlertexte folgen wie die bestehenden Chatstatusmeldungen der deutschen Produktsprache. Eine vollständige Übersetzung der Chatfehler in Englisch ist kein Bestandteil dieser Änderung.
- Originaldateien stehen für Retry im aktuellen Workspace zur Verfügung. Nach einem vollständigen Browserreload kann der Browser ein fehlgeschlagenes `File` ohne erneute Auswahl nicht rekonstruieren. Gespeicherte Serveranhänge verwenden weiterhin die bestehende Wiederherstellung.
- WebSocket-Diagnose verwendet die im bestehenden Vertrag vorhandene Generation-/Request-ID; es wird kein neuer Backend-Diagnosevertrag eingeführt. REST-Request-IDs am lokalen Nachrichtenknoten bleiben für die laufende Sitzung beziehungsweise lokale Demo-Sicherung erhalten; der Server persistiert weiterhin seinen vorhandenen Vertrag.
- Optionales Löschen-Undo ist nicht implementiert, da es keine serverseitige Wiederherstellung gibt.
