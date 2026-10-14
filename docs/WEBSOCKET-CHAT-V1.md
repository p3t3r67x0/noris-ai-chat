# Chat-WebSocket-Vertrag v1

P7c integriert inzwischen die versionierte Benutzeraktivierung und autorisierte
Quellenanzeige: [Web Search UX](WEB-SEARCH-UX.md). Die nachfolgenden Angaben zu
P7b/P2 beschreiben deren ursprünglichen Stand; Researchstatus verwendet jetzt
additiv dieselbe Outboxsequenz mit `researchEventVersion: 1`. ToolEventVersion 1
und der bestehende Socket bleiben unverändert.

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

## Sichere Handshake-Diagnose

Ein `close()` vor `accept()` wird von Uvicorn als HTTP 403 ausgegeben, auch bei
Verbindungsüberlastung (Close-Code 1013). Der Backend-Logger
`noris_ai.api.v1.chat_ws` nennt jetzt die erste fehlgeschlagene Prüfung in dieser
Reihenfolge:

| `reason` | Bedeutung |
| --- | --- |
| `ORIGIN_NOT_ALLOWED` | Origin fehlt oder entspricht keiner erlaubten Origin. |
| `HOST_NOT_ALLOWED` | Host fehlt oder entspricht keinem erlaubten Host inklusive Port. |
| `INVALID_SCHEME` | In Produktion ist das ASGI-Scheme nicht `wss`. |
| `MISSING_SUBPROTOCOL` | `noris-chat.v1` fehlt. |
| `MISSING_TICKET_SUBPROTOCOL` | Kein `ticket.`-Subprotokoll vorhanden. |
| `MULTIPLE_TICKET_SUBPROTOCOLS` | Mehr als ein `ticket.`-Subprotokoll vorhanden. |
| `TICKET_INVALID_OR_EXPIRED` | Ticket leer, unbekannt, abgelaufen oder bereits verbraucht. |
| `CONNECTION_LIMIT` | Bereits 64 Verbindungen aktiv. |

Beispiel: `reason=INVALID_SCHEME scheme=ws forwarded_proto=https`. `scheme`
und `forwarded_proto` enthalten ausschließlich `http`, `https`, `ws`, `wss`,
`missing` oder `invalid`. Rohheader, URLs, Subprotokollwerte, Ticketwerte und
Zugangsdaten werden nicht protokolliert. Proxy- und Debuglogs dürfen ebenfalls
keine Authorization- oder `Sec-WebSocket-Protocol`-Header enthalten.

Bei leerem `NORIS_CHAT_WS_ALLOWED_HOSTS=[]` werden Hosts aus den freigegebenen
Origins abgeleitet. Compose reicht eine explizite Liste nun an das Backend
weiter. `X-Forwarded-Host` ersetzt den tatsächlichen `Host` nicht; nginx muss den
öffentlichen Host erhalten. Die bestehende Caddy-Konfiguration im Repository
liest vertrauenswürdige nginx-Peers aus `NORIS_CADDY_TRUSTED_PROXIES`. Eine davon
abweichende Produktionskonfiguration muss separat geprüft werden.

[Uvicorn 0.54.0](https://github.com/encode/uvicorn/blob/0.54.0/uvicorn/middleware/proxy_headers.py)
übersetzt bei WebSockets vertrauenswürdiges `X-Forwarded-Proto: https` in
ASGI-`wss`; `http` wird `ws`. Auch `ws`/`wss` werden verstanden. Ein einzelner
Wert ist erforderlich, keine kommaseparierte Protokollliste. Uvicorn ändert
dabei nicht den Host. Der Handler vertraut ausschließlich dem ASGI-Scheme
und wertet Forwarded-Header nicht eigenständig als Freigabe aus.
[Caddy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy#defaults)
übernimmt eingehende Forwarded-Header nur von konfigurierten vertrauenswürdigen
Proxies. nginx muss `X-Forwarded-Proto` selbst setzen; Caddy muss genau diesen
nginx-Peer vertrauen. Der Backend-Port darf nur für den bestehenden Proxy
erreichbar sein, da der Containerstart `--forwarded-allow-ips '*'` verwendet.

Das authentifizierte Ticket-POST prüft Basic-Zugangsdaten, Schreib-Origin und
Kapazität, bereinigt Stream-Events und erzeugt erst danach das Ticket. Damit
verkürzt eine langsame Bereinigung nicht mehr die zugesagte Ticketgültigkeit.
Das Frontend kauft vor jeder neuen Verbindung ein frisches Ticket über
`credentials: 'same-origin'`, wählt bei HTTPS `wss:` und sendet genau die beiden
vereinbarten Subprotokolle. Das Ticket wird erst nach bestandener Origin-,
Host-, Scheme- und Subprotokollprüfung einmalig eingelöst. Tickets sind
prozesslokal: Neustarts oder unterschiedliche Worker zwischen POST und Upgrade
führen ebenfalls zu `TICKET_INVALID_OR_EXPIRED`.

Der Produktionslog `reason=INVALID_SCHEME scheme=ws forwarded_proto=http`
belegt, dass der HTTPS-Header vor dem Backend verloren geht. Uvicorn bildet
den erhaltenen HTTP-Wert korrekt auf `ws` ab; der Produktionshandler lehnt
deshalb vor der Ticketeinlösung ab. Der Log allein unterscheidet nicht, ob
nginx bereits `http` setzt oder Caddy einen nicht vertrauten nginx-Peer sieht.
Die bisherigen Ticket- und Sicherheitsprüfungen bleiben aktiv.

## HTTPS hinter nginx und Caddy

nginx terminiert TLS und spricht mit Caddy über HTTP. Ohne passenden
`trusted_proxies`-Eintrag ersetzt Caddy einen eingehenden
`X-Forwarded-Proto: https` durch das Scheme dieser internen Verbindung,
also `http`. Die ursprüngliche Repository-Vorlage hatte keine solche
Vertrauenskonfiguration; die Integrationstests reproduzieren damit exakt
den obigen Ablehnungslog.

In der aktiven nginx-Location für den API-/WebSocket-Pfad müssen die
bereits vorhandenen Upgrade-Header und der öffentliche Host erhalten bleiben.
Der Scheme-Header muss vom TLS-terminierenden nginx selbst gesetzt werden:

```nginx
proxy_set_header Host $http_host;
proxy_set_header X-Forwarded-Proto $scheme;
```

Die Zeilen müssen auch in einer spezifischen WebSocket-Location wirksam sein:
nginx [erbt `proxy_set_header`](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_set_header)
nur, wenn auf der aktuellen Ebene keine eigenen `proxy_set_header`-Direktiven
stehen. Ein vom Browser gelieferter Scheme-Header
darf diese Werte nicht ersetzen.

Compose reicht die folgende Variable ausschließlich an Caddy weiter. Sie ist
eine **durch Leerzeichen getrennte Liste von IPs/CIDRs**, keine JSON-Liste:

```dotenv
# Beispiel für einen verifizierten Peer; NICHT ungeprüft übernehmen:
NORIS_CADDY_TRUSTED_PROXIES=192.0.2.10/32
```

Bei nginx auf dem Docker-Host sieht Caddy häufig die Bridge-Gateway-IP als
Peer, obwohl nginx `127.0.0.1:8080` adressiert. `127.0.0.1/32` im Container
vertraut dann nicht diesem nginx. Der folgende reine Lesebefehl zeigt nur die
Gateway-Adressen des Proxy-Containers, keine Umgebungsvariablen oder Header:

```sh
proxy_id="$(sh infrastructure/scripts/compose.sh ps -q proxy)"
docker inspect --format '{{range .NetworkSettings.Networks}}{{.Gateway}}{{"\n"}}{{end}}' "$proxy_id"
```

Die Adresse ist mit dem tatsächlichen nginx-Peer abzugleichen. Nur diese
einzelne IPv4-Adresse mit `/32` beziehungsweise IPv6-Adresse mit `/128`
freigeben; keine pauschalen privaten Netze oder `0.0.0.0/0`. Bei leerer Liste
vertraut Caddy weiterhin keinem Proxy. `trusted_proxies_strict` wertet
angehängte `X-Forwarded-For`-Ketten von rechts nach links aus und verwendet die
erste nicht vertraute Adresse als Client-IP.

Eine spätere manuelle Inbetriebnahme muss die neue Caddyfile **und** die
Proxy-Umgebungsvariable laden. Ein bloßer Caddy-Reload übernimmt keine in
Compose geänderten Container-Umgebungsvariablen. Der Agent verändert den
Produktionsserver nicht und führt keinen automatischen Merge durch.

## Regressionstests für die Proxy-Kette

Die Unit-Regressionen prüfen den Produktionshandler mit der echten
Uvicorn-Proxy-Middleware, alle Ablehnungskategorien, Ablauf und Logredaktion.
Zusätzlich startet der folgende Integrationstest ausschließlich lokale nginx-
und Caddy-Prozesse, einen Uvicorn-Server und verwendet eine wegwerfbare
PostgreSQL-Datenbank. Ein temporäres Zertifikat wird explizit vertraut; die
TLS-Prüfung bleibt aktiv. Erfolg liefert HTTP 101 und `chat.connected`; Ablauf,
Replay, falsche Origins/Hosts und gefälschtes HTTPS über einen HTTP-Eingang
liefern HTTP 403. Die Tests verwenden die Repository-Caddyfile und prüfen
zusätzlich leere beziehungsweise falsche Proxy-Freigaben und einen direkten
nicht vertrauten Caddy-Client mit gefälschten Forwarded-Headern. Diese Fälle
müssen weiterhin HTTP 403 mit `INVALID_SCHEME` ergeben.

```sh
# nginx/openssl installieren; Caddy 2.10.2 als lokale Binärdatei bereitstellen.
export NORIS_TEST_CADDY_BINARY=/pfad/zu/caddy
# NORIS_TEST_DATABASE_URL muss auf eine wegwerfbare DB mit Suffix _test zeigen.
uv run --project backend --locked pytest backend/tests/integration/test_chat_ws_proxy.py
```

Die CI stellt Caddy aus dem bereits verwendeten Image `caddy:2.10.2-alpine`
bereit und führt diese Tests mit den übrigen Datenbanktests aus. Lokal werden
sie bei fehlenden Proxy-Testwerkzeugen übersprungen.

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

Bei `finish_reason=length` setzt der Worker die Antwort automatisch über das
bestehende Gateway fort. Modell, Assistant-ID, Generierungs-ID und Sequenz bleiben
gleich; nur neuer Text wird angehängt. Es gibt ein einziges `started` und ein
abschließendes Terminalereignis. Während der Fortsetzungen bleibt der Status
`running`/`streaming`. Alle Generierungsereignisse enthalten `continuationCount`;
ein leeres Delta speichert und überträgt den Zähler eines zugelassenen Folgeaufrufs.
`incomplete` enthält bei erreichtem Fortsetzungslimit zusätzlich `code` und
`message`. Die Limits und ihre Konfiguration beschreibt
[AUTO-CONTINUATION.md](AUTO-CONTINUATION.md).

`chat.conversation.updated` liefert die Ressource inklusive neuer Version;
`chat.title.updated` informiert über den automatischen Titel. `chat.error`
enthält sichere Codes und gegebenenfalls `requestId`, keine Provider-Details.

## Sichtbarkeit und vorbereitete Chats

Die Sichtbarkeit wird aus persistierten Benutzernachrichten mit Status
`completed` abgeleitet. `sidebarVisible` im REST-/WebSocket-Vertrag transportiert
diese Autorität; das historische Datenbankfeld bestimmt die Listen nicht mehr.
Titel, Entwürfe und Uploads sind kein Nachweis einer gesendeten Nachricht.

| `lifecycle` | Persistierter Zustand | Normale Listen |
| --- | --- | --- |
| `EMPTY` | Keine gespeicherte Benutzernachricht | Ausgeblendet |
| `STARTED` | Benutzernachricht, keine vollständige letzte Antwort; auch Abbruch/Teilausgabe | Sichtbar |
| `GENERATING` | Letzte Modellantwort `pending` oder `streaming` | Sichtbar |
| `FAILED` | Letzte Modellantwort `failed`, Benutzernachricht bleibt gespeichert | Sichtbar |
| `COMPLETED` | Letzte Modellantwort `completed` | Sichtbar |

Die gemeinsame Datenbankabfrage filtert vor Sortierung, Limit und Cursorbildung.
Das gilt für Sidebar, letzte Chats, Titelsuche, Pins, Archiv und Conversation-Picker.
Auch ein gestarteter Chat mit dem Titel `Neuer Chat` bleibt sichtbar. Nach dem
atomaren Speichern der ersten Nachricht sendet der Server bereits
`chat.conversation.updated`, bevor Modell- und Titelgenerierung starten. Eine
geöffnete Suche fragt nach Metadatenereignissen erneut serverseitig ab; dadurch
gelten Suchbegriff und Pagination auch bei Änderungen aus einem anderen Tab.

Alte leere Datensätze werden ohne Migration, Rückdatierung oder Löschung
ausgeblendet. Ob solche Datensätze auf einer laufenden Installation existieren,
wird durch diese Änderung nicht geprüft. Entwürfe und Dateien bleiben erhalten;
der direkte Zugriff auf eine eigene Conversation bleibt möglich.
`GET /conversations?preparedOnly=true` ist ein ausdrücklich angeforderter,
separat begrenzter Recovery-Seek auf `EMPTY`-Conversations. Der Bootstrap lädt
diese Metadaten in denselben Chat-State, damit „Neuer Chat“ eine vorbereitete
Unterhaltung nach Navigation und Reload wiederverwenden kann. Diese Seite
speist keine normale Gesprächsliste; ihre Cursor gelten nur für Recovery.
Dateien und Entwürfe werden beim Auswählen über ihre bestehenden APIs geladen.

Die lokale Playwright-Abnahme verwendet einen simulierten Anbieter und eine
temporäre PostgreSQL-Datenbank. Visuelle Belege: [Desktop leer](screenshots/conversation-visibility/desktop-empty-search.png),
[Desktop gestartet](screenshots/conversation-visibility/desktop-started-search.png),
[Mobile leer](screenshots/conversation-visibility/mobile-empty-search.png),
[Mobile gestartet](screenshots/conversation-visibility/mobile-started-search.png).

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
Snapshots enthalten außerdem `continuationCount`, `code` und `message`, damit
Zähler und Fehler-/Limitstatus auch nach Replay-Bereinigung erhalten bleiben.
Der Browser übernimmt den vollständigen Text aus Terminalereignissen; damit
bleiben beim Stop auch bereits serverseitig gespeicherte, noch nicht angezeigte
Textabschnitte erhalten.

Der Browser versucht maximal sechs Wiederverbindungen mit 250-ms- bis
5-s-Backoff. Bei verlorenem Annahmeereignis wiederholt er denselben Befehl mit
derselben ID. Reload lädt PostgreSQL und resumed unvollständige Generierungen.
Stream-Events terminaler Generierungen werden nach sieben Tagen beim
Ticketabruf bereinigt; Nachrichtentext und Generierungsdaten bleiben erhalten.

Betriebsgrenze: ein Backend-Worker. Tickets, aktive Jobs, Kostenbudgets und
Benachrichtigungen sind prozesslokal. Mehrere Worker/Replicas benötigen vorab
eine verteilte Admission-, Ticket- und Pub/Sub-Schicht.
