# Lernmodus: Bestandsanalyse vor der Umsetzung

Stand: 12.10.2026, Ausgangsbranch `main`. Die vier Referenzen aus
`~/Downloads/ChatGPT-Bild 12. Okt. 2026, 10_56_35.png` bis `10_57_00.png`
wurden lokal gelesen. Sie zeigen ein composerbreites Aktionsmenü, einen
kompakten blauen Lernindikator und Denkstufen mit Beschreibungen in einer Zeile.
Das zweite Bild zeigt einen Feedbackdialog; Feedback gehört nicht zum Auftrag.

| Bereich | Bereits vorhanden | Erweiterung / Wiederverwendung |
| --- | --- | --- |
| `ChatComposer.vue` | Ein `UChatPrompt`, Autosizing, Anhänge, Send/Stop, Modellwahl | Derselbe Composer erhält einen kompakten Modusindikator und ein gemeinsames Plus-/Slash-Dropdown |
| Plus-Menü | `UDropdownMenu` mit Dateiauswahl, Fokus-Rückgabe | Lernen ergänzen; native Reka-Tastaturbedienung, Escape und Touch wiederverwenden |
| `ChatWorkspace.vue` | Ein `useChat`-Zustand, ein Transport, Modellkatalog, Attachment-Composable | Gesprächseinstellungen verbinden, Speicherung abwarten, Entwürfe beim erstmaligen Aktivieren erhalten |
| `ChatModelMenu.vue` | Dynamisches `USelectMenu`, Kategorien und expliziter Modellwechsel | Weiterverwenden; Denkpräferenz daneben, kein automatischer Modellwechsel |
| Modellfähigkeiten | Exakte Modell-IDs, Evidenz, `reasoning_parameter`, `reasoning_efforts`, Providerprüfung | Serverseitiges Mapping abstrakter Denkstufen; nur freigegebene Stufen anzeigen |
| WebSocket v1 | `chat.generate`, Cancel, Resume, versionierte Gesprächszustände | Vorhandene Generierung verwendet gespeicherten Modus und Präferenz; keine Systemtexte vom Browser |
| `GenerationManager` | Persistierter aktiver Pfad, Varianten, PDF-/Bildkontext, automatische Fortsetzung | Modus zu Generierungsbeginn aus PostgreSQL übernehmen; Policy bei jedem Providersegment erhalten |
| `LLMGateway` | Ein Providerpfad, Kontext-/Byte-/Tokenlimits und Admission | Server-Policy bei Admission und Streaming gleich ergänzen; alle Limits zählen die Policy mit |
| PostgreSQL | Gespräch, Nachrichtenbaum, Entwürfe, Generationen, Benutzerpräferenzen | Gespräch hat bisher keine allgemeinen Metadaten: eine notwendige additive Migration mit Modus und optionaler Denkpräferenz |
| Tests | Vitest, pytest Unit/HTTP/Vertrag, PostgreSQL-Integration, Playwright Mock/HTTP/WebSocket | Bestehende Fixtures und echte lokale PostgreSQL-/WebSocket-Tests erweitern; drei Viewports und beide Themes |

Die Policy liegt versioniert in `backend/src/noris_ai/learning/`. Das öffentliche
`LLMMessage`-Schema erlaubt weiterhin nur Benutzer- und Assistentenrollen.
Dateien, PDF-Auszüge und Textreferenzen bleiben unvertrauenswürdiger Benutzerkontext.
Lernfortschritt wird aus dem vorhandenen aktiven Nachrichtenpfad abgeleitet;
andere Zweige gelangen nicht in den Lernkontext. Keine zweite Chatarchitektur.

GPT-OSS wird ausschließlich auf `low/medium/high` abgebildet. „Sofort“ bezeichnet
die niedrigste belegte Denkstufe, keine garantierte Latenz oder abgeschaltetes
Reasoning. GLM 5.2 kann anhand seines vorhandenen belegten Profils `high/max`
auf Hoch/Sehr hoch abbilden. Pro wird mangels belegtem Profil nicht angeboten. Quellen:
[GPT-OSS-Modellkarte](https://huggingface.co/openai/gpt-oss-120b),
[Noris GLM 5.2](https://noris.cloud/nai/models/glm-5-2/).

Ein laufender Stream behält seinen zu Beginn erfassten Modus. Ein ausdrücklicher
Moduswechsel gilt ab der nächsten Antwort. Speicherung verwendet die vorhandene
Versionsprüfung und Warteschlange. Fehlgeschlagene Speicherung wird angezeigt
und blockiert das Senden, bis der tatsächliche Serverzustand wiederhergestellt ist.

## Integration des inzwischen aktualisierten main-Branches

Während der Umsetzung wurde die Plus-Menü-Korrektur (#50) mit ihrem zentralen
`composerMenuItems`-Builder auf `main` zusammengeführt. Der Lernmodus-Branch
wurde anschließend auf diesen Stand gesetzt. Lernen wird als zweite Aktion in
diesem Builder registriert. Upload und alle fünf bislang deaktivierten Werkzeuge
bleiben erhalten; es gibt weiterhin nur ein Plus-/Slash-Dropdown. Auch die
Upload-Fehlermeldungen, die Übernahme des ersten Attachment-Entwurfs und der
aktive Plus-Kreis aus dieser Korrektur bleiben erhalten.

Die nun verfügbaren verbindlichen Referenzen bestimmen die weitere Gestaltung:
Das Aktionsmenü erhält die Breite und linke Kante des Composers sowie kompakte
Zeilen mit direkt anschließender Beschreibung. Bereits vorhandene Menütests
prüfen diese Geometrie und die zusätzliche verfügbare Lernaktion. Die Policy-
und Datenbankarchitektur aus der ursprünglichen Analyse bleibt unverändert.
