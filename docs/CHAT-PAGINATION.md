# Chat-Pagination

## Bestandsaufnahme auf main (e2c9a8f)

`ChatBackend.load()` lädt derzeit alle Konversationsmetadaten, alle Entwürfe und anschließend mit einem unbegrenzten `Promise.all` sämtliche Nachrichtenbäume. Die Sidebar, Archivansicht und Titelsuche arbeiten ausschließlich mit diesen lokalen Daten. Damit wachsen Startkosten und Speicherbedarf mit dem gesamten Datenbestand.

Der einzige Chat-State liegt in `useChat`: immutable Nachrichten mit Parent-IDs, aktive Leaf-ID und bevorzugte Leaves. `visiblePath` setzt bisher voraus, dass sämtliche Eltern geladen sind. Varianten werden aus geladenen Geschwistern berechnet. Deshalb darf eine paginierte Seite nicht als vollständiger Baum behandelt werden. Bearbeiten und Regenerieren erzeugen Geschwister; ein Variantenwechsel muss auch noch ungeladene Nachfahren auflösen können.

`useChatBackend` verbindet diesen State mit REST, persistierten Entwürfen und WebSocket-Metadaten. Sein bisheriger Metadaten-Callback lädt bei einer unbekannten Leaf den gesamten Nachrichtenbaum nach. Dies muss auf die aktive Ansicht begrenzt werden. WebSocket-Deltas und Snapshots sind generation- und nachrichtenbezogen; dieser Vertrag bleibt bestehen. Laufende Generierungen und ungesicherte Änderungen müssen vor Cache-Verdrängung geschützt werden.

Im Backend laden sowohl `active_path` als auch `begin_generation` bisher alle Nachrichten einer Unterhaltung und rekonstruieren den ausgewählten Pfad in Python. Der Provider braucht den vollständigen ausgewählten Pfad, während die UI nur einen Abschnitt benötigt. Diese zwei Anforderungen werden getrennt. Ownership, immutable Parent-Beziehungen, optimistische Versionierung und der bestehende Provider-Gateway bleiben verbindlich.

Die vorhandenen Indizes enthalten keine vollständigen deterministischen Sortierschlüssel. Listen werden bisher unbeschränkt ausgegeben. `archived=true` bedeutet weiterhin **einschließlich** archivierter Chats. Die neue Sortierung verwendet `updated_at DESC, id DESC`, passend zur bestehenden Sidebar und ihren Titel-/Aktivitätsupdates.

Risiken: fehlende Eltern bei Teilpfaden; falsche Variantenzahl bei ungeladenen Geschwistern; verspätete Antworten nach einem Chatwechsel; Überschreiben von Streaming-Text durch alte REST-Snapshots; Entwürfe außerhalb der ersten Seite; aktive Unterhaltung außerhalb der ersten Seite; lokale Suche über unvollständige Metadaten. Die Implementierung und Tests adressieren diese Abhängigkeiten ausdrücklich.

## Umsetzung und Messungen

Dieser Abschnitt wird mit den implementierten Verträgen, gemessenen Ergebnissen und verbleibenden Einschränkungen ergänzt.
