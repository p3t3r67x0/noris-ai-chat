# Neuer Chat und Composer

## Bestandsanalyse vor Änderungen (2026-10-12)

`useChat.newChat()` ruft `useConversations.create()` auf. Das legt sofort eine UUID,
den Titel „Neuer Chat“, `titleSource=fallback` und einen aktiven lokalen Datensatz an.
`useChatBackend` überschreibt `create()`: Die UUID gelangt sofort in `sidebarIds`,
`ChatBackend.ensure()` stellt den POST `/conversations` in die bestehende Queue.
`ChatService.create_conversation()` und `ChatRepository.create_conversation()`
schreiben und committen den Datensatz in PostgreSQL. Ein Klick persistiert also
auch ohne Nachricht einen leeren Chat.

Der erste Upload und Gesprächseinstellungen verwenden ebenfalls `create()`;
der Workspace überträgt dabei den bisherigen `__new__`-Entwurf. Uploads benötigen
die Conversation-ID, werden separat gespeichert und bei Reload über die aktive
Conversation und die Attachment-API wiederhergestellt.

`send()` erstellt bei Bedarf die Conversation, hängt User- und Assistant-Nachricht
optimistisch an und startet den bestehenden Transport. Die synchrone Busy-Sperre
und die Resource-Queue verhindern parallele Sendungen/POSTs. Die UUID-basierte
Erstellung im Service ist idempotent. `begin_generation()` speichert User-Nachricht,
Attachment-Zuordnung, Generation und Assistant-Nachricht in einer Transaktion.
Es erhöht die Conversation-Version und löscht die gespeicherten Entwürfe.
Antwort-Snapshots und Replay-Events committen vor jeder WebSocket-Auslieferung.

Im PostgreSQL-/WebSocket-Modus folgt nach erfolgreicher erster Antwort die einzige
Backend-Titelgenerierung in `GenerationManager._generate_title()`. Ein persistierter
Claim verhindert weitere Provider-Aufrufe nach einem Titelfehler. Ein erfolgreicher
Titel erhöht die Version, setzt `titleSource=generated` und sendet
`chat.title.updated` sowie `chat.conversation.updated`. Der Client liest bei einem
unversionierten Titel-Event die autoritative Conversation nach; versionierte Events
laufen durch `ChatBackend.remember()`. Ältere Versionen werden verworfen. Der
Repository-Lock verhindert, dass automatische Titel manuelle Titel überschreiben.
Im Mock-/HTTP-Modus stößt der vorhandene Client die Titelgenerierung bislang schon
bei `streaming` an. Unbekannte Themen behalten „Neuer Chat“ als Fallback.

Entwürfe liegen in `useChatDrafts`: `__new__` ohne Conversation, sonst deren UUID.
Der Backend-Adapter schreibt nach 300 ms und sichert ausstehende Änderungen lokal.
Beim Laden sind PostgreSQL-Metadaten und aktiver Nachrichtenpfad autoritativ;
laufende Generierungen werden über `resume` fortgesetzt. Reconnect liest Metadaten
erneut. Der Sidebar-Adapter hat bislang keinen getrennten Sichtbarkeitsstatus.

`ChatWorkspace` rendert genau einen `ChatComposer`. `EmptyChatState` nimmt mit
`flex: 1` den freien Raum ein; `.composer-dock` bleibt unten. Begrüßung und Composer
bilden dadurch keine gemeinsame Einheit. `useChatViewport` verarbeitet bereits
`visualViewport.height/offsetTop`, Resize, Scroll und Pinch-Zoom.
`useComposerAutosize` erhält Textarea/IME und misst Inhalte/Controls mit Mirror und
ResizeObserver. Die Timeline besitzt ihren eigenen Scrollcontainer.

Die vorhandene bereinigte Desktopreferenz und `REFERENCE-ANALYSIS.md` beschreiben
einen aktiven Chat. Die anschließend angegebene lokale Datei
„ChatGPT-Bild 12. Okt. 2026, 18_29_41.png“ wurde visuell geprüft: Überschrift und
Composer bilden eine gemeinsame Einheit etwas oberhalb der Bildschirmmitte.
Die private Referenzdatei wird nicht in das Repository übernommen.

## Neuer Conversation-Lebenszyklus

1. **Öffnen / Neuer Chat:** `activeId=null`, der bestehende `__new__`-Entwurf
   bleibt erhalten. Es gibt weder eine neue UUID noch einen POST oder Sidebar-Eintrag.
   Der vorhandene Composer erhält den Fokus. Ein bereits vorbereiteter Upload-/
   Einstellungsentwurf wird beim Zurückkehren wieder geöffnet.
2. **Upload oder Gesprächseinstellung:** Der bestehende `create()`-Pfad erzeugt
   eine UUID. `ensure()` persistiert sie mit `prepared=true`. Der Backend-Datensatz
   enthält `sidebarVisible=false`. Der Workspace überträgt Text und die bestehende
   Attachment-Verwaltung verwendet diese UUID. Reload lädt Draft und Attachment-IDs
   über die bisherigen APIs. Der Datensatz erscheint noch nicht in der Sidebar.
3. **Erstes Senden:** Falls keine vorbereitete Conversation existiert, wird sie
   einmal über denselben Pfad erstellt. UUID-basierte Idempotenz, Queue und Busy-Sperre
   bleiben erhalten. `begin_generation()` persistiert beide Nachrichten und die
   Attachment-Zuordnung. Die erste Nachricht entfernt die Begrüßung; dieselbe Textarea
   wechselt mit ihrem Dock nach unten und behält den Fokus.
4. **Terminaler Antwortzustand:** Das Repository setzt die Sichtbarkeit gemeinsam
   mit dem Antwort-Snapshot in einer Transaktion. Bei einem bisherigen Fallback-Titel
   wird ein kurzer Themenauszug aus der Benutzernachricht gespeichert. Dieser sinnvolle
   vorläufige Titel verhindert dauerhaft versteckte Chats bei Fehlern oder Abbruch.
   Ein autoritatives `chat.conversation.updated` veröffentlicht den Zustand.
5. **Erfolgreiche Antwort:** Die vorhandene Titelgenerierung läuft anschließend.
   Ihr Ergebnis setzt `titleSource=generated`, erhöht die Version und aktualisiert
   die Sidebar ohne Reload. Bis dahin kann kurz der Themenauszug sichtbar sein.
   Beispiel: „SearXNG“ wird durch „SearXNG Funktionsweise“ ersetzt.
6. **Fehler / Neustart:** Antwortfehler erhalten die User-Nachricht. Auch Fehler bei
   Modellzulassung werden erst nach Persistenz als fehlgeschlagene Generation
   abgelegt. Eine leere fehlgeschlagene Antwort bietet nach Reload den vorhandenen
   Regenerieren-Button. Startup-Recovery macht unterbrochene vorbereitete Chats
   sichtbar. Titelfehler erhalten den Themenauszug; der bestehende persistierte Claim
   verhindert endlose Provider-Retries. Spätere autoritative Titelupdates bleiben möglich.

Migration `0012_conversation_visibility` ergänzt `sidebar_visible` mit Default `true`.
Bestehende Conversations behalten damit Titel, Nachrichten und Sichtbarkeit.
API-Aufrufe ohne `prepared=true` bleiben rückwärtskompatibel. OpenAPI und die
WebSocket-Verträge wurden über den bestehenden Generator aktualisiert.

## Frontend-State, Sidebar und Titel-Synchronisation

Die bestehenden Records in `useChat`/`useConversations` bleiben die einzige
Chatverwaltung. Ein optionaler lokaler `sidebarVisible`-Wert bildet den Backend-Wert
ab; alte lokale Snapshots ohne Feld bleiben sichtbar. Pagination und lokale Sidebar
filtern vorbereitete Datensätze. Sichtbar werdende Records gelangen auch bei gleichem
Zeitstempel in die Sidebar; alte Versionen werden vor der Aufnahme verworfen.

`chat.title.updated` liest weiterhin autoritative Metadaten nach.
`chat.conversation.updated` übernimmt weiterhin versionierte Backend-Metadaten.
`remember()` verwirft kleinere Versionsnummern. Manuelle Titel bleiben durch den
Repository-Lock und die vorhandene Konfliktbehandlung geschützt. Es gibt keine
zusätzliche Titelgenerierung. Der Mock-/HTTP-Adapter startet seinen bestehenden
Titelpfad nun ebenfalls erst bei erfolgreichem Antwortabschluss.

`useChatDrafts` abonniert auch noch nicht vorhandene Draft-Schlüssel. Dadurch
aktualisiert ein späterer Backend-Read die Textarea beim Wechsel zurück zu einem
gespeicherten Draft. Debounce, Offline-Sicherung und Draft-API bleiben erhalten.

## Composer und responsive Darstellung

`EmptyChatState` liegt im vorhandenen Composer-Dock unmittelbar vor dem einzigen
`ChatComposer`. Flex-Spacer positionieren die gemeinsame Einheit ohne absolute
Pixelkoordinaten. Breite, Autosize, Controls, Plus-Menü, Uploads und IME bleiben in
der bestehenden Komponente. Die kleine Viewport-Höhe reduziert Überschrift und
Abstand, statt die Begrüßung auszublenden. Safe-Area, `visualViewport` und ein
scrollbarer Empty-State berücksichtigen Tastatur und Landscape.

Die aktive Timeline behält ihren bisherigen Scrollcontainer und das untere Dock.
Beim mobilen Sidebar-Klick verhindert die verspätete Dialog-Fokusrückgabe ein
Zurückspringen auf den Sidebar-Trigger und fokussiert den vorhandenen Composer.

## Gezielte Validierung

Gemäß der Aufgabenpräzisierung werden lokal nur betroffene Tests ausgeführt;
die vollständige lokale Testsuite entfällt. Die nachträglich angeforderte
Konfliktlösung und CI-Prüfung ist unten dokumentiert. Alle Browser-/DB-Tests
verwenden lokale Fixture-Provider und isolierte PostgreSQL-Testdatenbanken.
Es gibt keinen Zugriff auf den Produktivserver.

- Frontend: gezielte Unit-Tests für Conversation-/Draft-/Titel-/Backend-State,
  Sidebar-Versionen, Attachments, Viewport und Autosize.
- Backend: gezielte Titel-/Readiness-Unit-Tests und PostgreSQL-/WebSocket-Integration
  inklusive neuer Fälle für idempotente Vorbereitung, Antwort-/Titelfehler und Recovery.
- Browser: neue Lifecycle-Matrix, Draft- und Upload-Reload, Doppelsenden, beide
  Titelereignisse in mehreren Tabs, Wiederholen, Fokus, IME, Tastatur und Scrollen.
- Geänderte Empty-State-Screenshot-Baselines werden aktualisiert; unveränderte
  aktive Screenshots werden nicht pauschal neu erzeugt.
- Lint, Frontend-/Test-/Backend-Typecheck, generierte API-Verträge und Produktionsbuild.

Lokale Ergebnisse (2026-10-12; wiederholte Fälle jeweils nur einmal gezählt):

| Prüfung | Ergebnis | Umfang |
|---|---|---|
| Frontend-Unit | 137 ausgewählte Fälle bestanden | 10 betroffene Dateien; neue Sidebar-/Draft-Fälle separat nachgeprüft |
| Backend-Unit | 22 ausgewählte Fälle bestanden | Persistierte Titel und DB-Readiness |
| Backend-Integration | 32 bestanden | 27 bestehende WebSocket-/Titel-Fälle + 5 neue Lifecycle-Fälle |
| Playwright Mock | 26 ausgewählte Fälle bestanden | Fokus, IME, Scrollen, Empty-State und Sidebar |
| Playwright WebSocket | 36 ausgewählte Fälle bestanden | 8 Lifecycle-Matrixfälle + 24 Composer-/Recovery-Fälle + 4 bestehende Titel-/Upload-Fälle |
| Playwright Composer-Layout | 24 betroffene Fälle bestanden | Modellnamen, mehrzeilige Eingabe und Stop; betroffene Baselines aktualisiert |
| ESLint / Ruff / Ruff Format | bestanden | Betroffene Quellen und Tests |
| Nuxt / vue-tsc / Pyright | bestanden | Anwendung und Tests; Pyright ohne Fehler |
| API-Generator `--check` | bestanden | OpenAPI und WebSocket-Verträge aktuell |
| Nuxt-Produktionsbuild | bestanden | Finaler Build nach allen Quellenänderungen |
| Visuelle Artefakte | 88 PNGs geprüft | 16 vorher / 72 nachher, Abmessungen verifiziert |

Ein paralleler lokaler Neuaufbau entfernte während einzelner Browserläufe deren
Build-Dateien. Die betroffenen Fälle wurden nach fertigem Build erfolgreich
wiederholt. Der finale 250-Pixel-Tastatur-Test läuft einschließlich Anhang und
langem Entwurf erfolgreich. Mobile Softwaretastaturen sind über Touch-Emulation
und `visualViewport`-Ereignisse geprüft, nicht auf einem physischen Smartphone.

Die visuellen Artefakte sind im [Screenshot-Index](screenshots/new-chat/README.md)
verlinkt. Der Pull Request bleibt offen; keine Zusammenführung in `main`, kein Deployment.

## Konfliktlösung und CI-Korrekturen für PR #57

`main` (Stand `d7c3100`) wird in den PR-Branch übernommen. Die Konfliktlösung
verbindet die neue Composer-Anordnung mit der aktuellen Modell-/Reasoning-Auswahl.
Die zwei widersprüchlichen WebSocket-Screenshot-Referenzen des Reasoning-Menüs
werden mit Playwright aus diesem gemeinsamen Stand neu erzeugt.

Der fehlgeschlagene CI-Lauf `38281756927` zeigte veraltete Annahmen in drei
Backend- und zehn Browserfällen:

- Attachment-Ablehnungen werden nach gespeicherter Nachricht als terminales
  Generation-Ereignis übermittelt. Die Tests prüfen jetzt zusätzlich erhaltene
  Nachrichten/Attachment-IDs, fehlende Provider-Aufrufe und Wiederholen ohne
  doppelte Benutzernachricht. Die Modellprüfung umfasst wieder Bilder im gesamten
  Verlauf, damit ein Textmodell auch nach Reload `ATTACHMENT_INCOMPATIBLE` meldet.
- Der Migrationstest reflektiert das historische Schema vor dem Upgrade und
  vergleicht dessen vollständige Zeilen vor/nach Upgrade und Rollback. Aktuelle
  ORM-Spalten werden nicht in ein älteres Schema geschrieben; bestehende Chats
  erhalten ausdrücklich `sidebar_visible = true`.
- Titeltests erwarten keinen Sidebar-Eintrag während der ersten Antwort und
  prüfen Fallback/Generierung nach Abschluss. Manuelles Umbenennen und Löschen
  während ausstehender Titelgenerierung bleiben geprüft.
- Der Tastaturtest verlangt die sichtbare Begrüßung direkt über dem Composer.
  Reasoning-Tests unterscheiden Autosize im zentrierten Startbildschirm vom
  stabilen unteren Composer einer aktiven Unterhaltung.
  Ausgangsmessungen warten auf die vollständig sichtbare mehrzeilige Textarea;
  das Reasoning-Menü wird vor dem Senden geschlossen. Die Geometriegenauigkeit
  bleibt erhalten; der betroffene 768-Pixel-Fall besteht dreimal hintereinander.
- Der nachfolgende Compose-WebSocket-Schritt benötigt keine Python-Umgebung auf
  dem Browserrunner mehr: Die mit dem vorhandenen Backend-Fixture erzeugte
  synthetische PDF liegt als Testdatei vor. Playwright liest dieselben Upload-Bytes
  direkt; Dateiupload und Draft-/Attachment-Recovery bleiben vollständig geprüft.
- Reconnect-Metadaten unveränderter Chats erhalten die bisherige Sidebar-Seite.
  Die vorhandene Aktualitätsprüfung bleibt erhalten; erstmals sichtbare vorbereitete
  Chats werden zusätzlich aufgenommen. Ein aktiver Chat außerhalb der ersten Seite
  lädt weiterhin nur sein eigenes Nachrichtenfenster.
- Der Titel-Fehlertest identifiziert seinen Chat anhand der Conversation-ID statt
  der durch asynchrone Titelupdates veränderlichen Listenreihenfolge. Er prüft
  zusätzlich genau einen Fehleraufruf und den Fallback-Titel nach Reload.

Gezielt lokal geprüft: 20 Attachment-/Migrationstests, 31 Backend- und 26
Frontend-Unit-Fälle, 36 Composer-/Titel-Browserfälle, acht Reasoning-Browserfälle
sowie vier WebSocket-Fälle für Lernmodus, Draft-Reload und Fehler-Recovery. Ruff/Format, ESLint,
Nuxt/vue-tsc/Pyright, API-Vertragsprüfung und Nuxt-Produktionsbuild bestehen.
Die CI-Workflows bleiben vollständig aktiviert und werden auf Anforderung
erneut geprüft; Tests und Prüfregeln werden nicht übersprungen.
