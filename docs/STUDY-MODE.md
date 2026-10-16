# Lernmodus und Lernzustand

PR #85 ist seit 16.10.2026 in `main` enthalten. Sein kompakter `UChatPrompt`,
Inline-Websuche, Autosizing, Uploads, Modellwahl und Denkaufwand bleiben die Basis.
Moduswahl, PostgreSQL-Migration und serverseitiger Lernprompt waren bereits vorhanden.

`learning/state.py` rekonstruiert eine kleine Zustandsprojektion aus dem aktiven,
gespeicherten Nachrichtenpfad: Benutzer-/Tutorbeiträge, Orientierung oder Dialog
und eine Gelegenheit zur Wiederholung nach jeweils vier Tutorbeiträgen. Leere
Antworten nach frühem Stop zählen nicht. Die Zahlen messen Aktivität, keine
Beherrschung eines Themas. Vorwissen, Lernziel und Schwierigkeit beurteilt das
Modell anhand der Antworten im gleichen Pfad. Bei Verwirrung soll es vereinfachen,
bei nachgewiesenem Verständnis anspruchsvollere Aufgaben anbieten.

Der `GenerationManager` erstellt den Zustand vor dem Anreichern mit Dateiinhalten.
Der interne `PersistedChatRequest` trägt den Snapshot zum `LLMGateway`. Dort
ergänzt `learning_instruction` den festen pädagogischen Systemprompt mit ausschließlich
validierten Zahlen und festem Text. Dateitexte und Nutzerformulierungen werden
nicht in privilegierte Anweisungen interpoliert. Öffentliche REST-/WebSocket-
Eingaben können weder Modus noch Lernzustand einer Generierung überschreiben.
Die Moduswahl erfolgt über die bestehende versionierte Conversation-API.

Die Projektion benötigt keine weitere Datenbanktabelle: Der gespeicherte Modus
und Nachrichtenbaum sind die maßgebliche Quelle. Reload und Modellwechsel
rekonstruieren denselben Stand; Retry zählt keine neue Übung. Ein anderer Zweig
enthält nur seine eigenen Beiträge. Auch bisherige normale Gesprächsinhalte
bleiben beim Aktivieren nutzbar. Das Deaktivieren verändert keine Nachrichten.
Ein laufender Stream verwendet seinen ursprünglichen Snapshot; Änderungen
gelten ab der nächsten Generierung. Fortsetzungen behalten die Lernanweisung,
die auch bei Admission, Token-/Bytelimits und Streaming berücksichtigt wird.

Die Policy unterstützt Deutsch und Englisch über die Gesprächssprache. Sie
verlangt kleine Schritte, höchstens eine Lernfrage, Übungen und konstruktives
Feedback. Explizite Wünsche nach einer direkten/vollständigen Lösung haben
Vorrang: Das Modell soll sofort antworten, ohne einen Versuch zu erzwingen.
Der Modus bleibt dabei aktiv. Natürlichsprachliche Wünsche werden vom Modell
verstanden, nicht über eine begrenzte Liste von Schlüsselwörtern erkannt.

Die Umsetzung ist unabhängig von Modell-ID und Reasoning-Optionen. Die Qualität
der pädagogischen Antworten hängt weiterhin vom eingesetzten Modell ab.
Deterministische Tests belegen Kontextaufbau und Lebenszyklus, keine allgemeine
pädagogische Qualität. Die vorhandenen Tests prüfen Plus-Menü, `/lernen`, Reload,
Modellwechsel, Anhänge, Retry, Stop, beide Themes und responsive Composer-Geometrie.
