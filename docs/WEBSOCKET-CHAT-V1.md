# Chat-WebSocket-Vertrag v1

Die verbindlichen Schemata liegen in [chat-v1.json](websocket/chat-v1.json).
`pnpm api:generate` exportiert Pydantic-Schemata und generiert die TypeScript-
Unions. `make check-api` prüft REST und WebSocket auf Drift. Zusätzliche Felder,
fehlende Versionen und andere Protokollversionen werden zurückgewiesen.

## Verbindung

1. Authentifiziertes `POST /api/v1/chat/ws-ticket` mit JSON `{}` über dieselbe
   Origin; bestehender HTTP-Basic-Anwendungszugang, niemals Provider-Key.
2. Browser: `new WebSocket(url, ['noris-chat.v1', 'ticket.' + ticketId])`.
   Der Server bestätigt ausschließlich `noris-chat.v1`; das Ticket ist einmalig,
   60 Sekunden gültig und steht weder in URL noch Browser-Storage. Proxy-Logs
   dürfen den `Sec-WebSocket-Protocol`-Requestheader nicht aufzeichnen.
3. Origin und Host müssen freigegeben sein. Öffentlicher Betrieb benötigt WSS;
   `production` verweigert WS. Konfiguration und Tickets bleiben serverseitig.
4. `chat.connected` enthält `heartbeatSeconds`. Server: `chat.heartbeat`;
   Browser: `chat.ping`; Antwort: `chat.pong`.

Maximal 64 Verbindungen und 64 offene Tickets pro Worker; 120 Befehle/Minute
pro Verbindung. Eingehende Frames maximal 262144 Bytes. Queue: 256 Ereignisse;
Sende-Timeout: 15 Sekunden; ausgehendes Ereignis maximal 8 MiB. Überlauf/langsame
Clients werden mit 1013 getrennt. Uvicorn begrenzt zusätzlich Frames und Queue.

## Generieren

```json
{
  "version": 1,
  "type": "chat.generate",
  "requestId": "00000000-0000-4000-8000-000000000010",
  "conversationId": "00000000-0000-4000-8000-000000000011",
  "conversationVersion": 1,
  "inputMessageId": "00000000-0000-4000-8000-000000000012",
  "assistantMessageId": "00000000-0000-4000-8000-000000000013",
  "parentMessageId": null,
  "modelId": "vllm/qsu/glm-5-3-flash",
  "content": "Erkläre WebSockets.",
  "operation": "generate",
  "attempt": 1
}
```

`requestId` ist die idempotente Generierungs-ID. Identische Wiederholung startet
keinen zweiten Provideraufruf. Abweichende IDs/Modell/Input/Operation erzeugen
Konflikte. Besitz, Version, Nachrichtenbaum, aktiver Parent, Modellfreigabe,
Kosten- und Tokenlimits werden serverseitig geprüft. Keine `owner_id`, API-Keys,
System-/Developer-Nachrichten oder autoritativen Nachrichtenverläufe im Befehl.

Bearbeitung: neue User-ID und `editedFromMessageId`, gleicher Parent wie die
Originalfrage. Regeneration: bestehende User-ID, neue Generierungs- und
Assistant-ID. Fortsetzung: `operation: "continue"`, `sourceAssistantMessageId`
auf die ausgewählte unvollständige Antwort, neue Assistant-/Generierungs-ID.
Das Backend kopiert deren Präfix aus PostgreSQL; die ursprüngliche Variante
bleibt unverändert. Nur der rekonstruierte ausgewählte Pfad erreicht den Provider.

Antworten: `chat.message.created`, `chat.generation.started`, dann
`chat.generation.delta` mit `generationId`, `conversationId`, `messageId`, `seq`
und `delta`. Sequenzen steigen pro Generierung lückenlos ab 1. Erst nach dem
Commit von Textsnapshot, Sequenz und Event wird gesendet. Batching: 100 ms oder
512 Zeichen. Terminal: `completed`, `incomplete` (Ausgabelimit), `failed`,
`cancelled` oder `interrupted`, jeweils mit vollständigem `content`.

`chat.conversation.updated` liefert die Ressource inklusive neuer Version;
`chat.title.updated` informiert über den automatischen Titel. `chat.error`
enthält sichere Codes und gegebenenfalls `requestId`, keine Provider-Details.

## Stop und Wiederaufnahme

`chat.cancel {version:1,generationId}` ist ein ausdrücklicher Nutzerabbruch.
Ein Disconnect setzt dagegen eine Frist von 60 Sekunden ohne verbundene
Teilnehmer. Reconnect stoppt die Frist. Danach wird `interrupted` gespeichert.
Providerfehler sind `failed`, Ausgabelimits `incomplete`. Beim Backend-Neustart
werden verwaiste queued/running-Generierungen ebenfalls `interrupted`.

`chat.resume {version:1,generationId,lastReceivedSeq:42}` prüft Ownership und
Sequenz, sendet `chat.resume.accepted` und fehlende Events. Replay und
Live-Subscription teilen die Schreibsperre, damit kein Delta dazwischen fehlt.
Unvollständiges/zu großes Replay führt zu `chat.resume.snapshot` mit
`content`, `status`, `lastSequence`; Fortsetzungen verwenden immer Snapshots,
damit das gespeicherte Präfix erhalten bleibt. Snapshot ersetzt den lokalen
Text vollständig. Sequenzen ≤ zuletzt verarbeiteter Sequenz werden ignoriert.
Terminale Snapshots beenden die Generierung ohne zusätzliche Deltas.

Der Browser versucht maximal sechs Wiederverbindungen mit 250-ms- bis
5-s-Backoff. Bei verlorenem Annahmeereignis wiederholt er denselben Befehl mit
derselben ID. Reload lädt PostgreSQL und resumed unvollständige Generierungen.
Stream-Events terminaler Generierungen werden nach sieben Tagen beim
Ticketabruf bereinigt; Nachrichtentext und Generierungsdaten bleiben erhalten.

Betriebsgrenze: ein Backend-Worker. Tickets, aktive Jobs, Kostenbudgets und
Benachrichtigungen sind prozesslokal. Mehrere Worker/Replicas benötigen vorab
eine verteilte Admission-, Ticket- und Pub/Sub-Schicht.
