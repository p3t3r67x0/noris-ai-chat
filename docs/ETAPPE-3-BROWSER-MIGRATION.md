# Browser-Chats in PostgreSQL übernehmen

Im WebSocket-Modus lädt die Sidebar ausschließlich serverseitige Chats. Der
alte Schlüssel `noris-ai:chat:v1` bleibt unangetastet. Er wird weder automatisch
importiert noch durch neue serverseitige Snapshots überschrieben.

1. Bei Bedarf den alten Schlüssel über die Browser-Entwicklerwerkzeuge als JSON
   sichern. Er enthält private Gesprächsdaten und gehört nicht ins Repository.
2. „Einstellungen → Datenkontrollen“ öffnen und bei „Lokale Chats importieren“
   auf „Importieren“ klicken. Einstellungen sind im Desktop-Kontomenü und auf
   Mobilgeräten in der Sidebar erreichbar. Der Dialog erklärt Übertragung und Sicherung.
3. „Import ausdrücklich starten“ auslösen. Erst dann sendet der Browser Daten.
4. Der Server prüft UUIDs, Rollen, Eltern, Zyklen, Titel, Blatt und Entwürfe vor
   dem Schreiben. Ein Import ist eine Transaktion. Bei Konflikten werden keine
   neuen Unterhaltungen oder Entwürfe geschrieben. Identische bestehende Chats
   werden übersprungen; deren inzwischen geänderte Entwürfe bleiben erhalten.
5. Nach Erfolg wird die Sidebar neu aus PostgreSQL geladen. Konversations- und
   Nachrichten-IDs, Varianten, aktiver Pfad, Titel und Archivierung bleiben erhalten.

Grenzen: 500 Chats, 10.000 Nachrichten, 8 MiB pro Import. Ungültige oder zu große
Bestände werden erhalten und mit einer Fehlermeldung abgelehnt. Unvollständige
lokale Antworten werden als abgebrochen importiert, niemals als fertig.

Wiederherstellung: Die ursprüngliche JSON-Sicherung bleibt verfügbar; im
Mock-Modus kann sie über den ursprünglichen Browser-Schlüssel wieder geladen
werden. Ein fehlgeschlagener Import verändert diesen Schlüssel nicht. Bereits
importierte Server-Chats können normal archiviert oder weich gelöscht werden.
Kein Datenbank-Downgrade ist ein Daten-Rollback; vor einem Betriebsrollback
PostgreSQL sichern und das Anwendungscode-Rollback bevorzugen.

Neue Browserdaten: `noris-ai:chat-cache:v1` ist ein ersetzbarer UI-Cache.
`noris-ai:offline-drafts:v1` sichert noch nicht bestätigte Eingaben. Der Server
bleibt für Nachrichten, Titel und den aktiven Gesprächspfad maßgeblich. Lokale
Varianten-Ansichtspräferenzen werden nur für weiterhin vorhandene Knoten benutzt.
