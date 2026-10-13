# Websuche: Architektur- und Implementierungsplan

Status: End-to-End-Websuche geplant; der isolierte SearXNG-Adapter ist
[vorbereitet und testbar](SEARXNG-PROVIDER.md), ohne Provider-/Runtimeaktivierung.
Stand: 2026-10-13.

Übergreifende Regeln: [Tool-Architektur](TOOL-ARCHITECTURE.md); PRs und Gates: [Roadmap](FEATURE-ROADMAP.md).

## 1. Bestandsaufnahme

`ChatSearchDialog.vue`/`useConversationSearch.ts` durchsuchen vorhandene Unterhaltungen, keine Webseiten. Der isolierte SearXNG-Provider ergänzt jetzt die P1a-Suchtypen; Fetcher, Quellenkatalog und ausführbarer Webmodus fehlen weiterhin. Der vorhandene Menüeintrag `web` bleibt deaktiviert.

Wiederverwendung: `ChatComposer.vue`/`ChatWorkspace.vue`, `useChatStream`, `webSocketTransport.ts`, `GenerationManager`, `ChatRepository`, `LLMGateway`, Modellkatalog, vorhandene Markdownanzeige und PostgreSQL-Replay. Textreferenzen/PDFs bleiben lokaler Chatkontext und werden nicht an einen Suchprovider übertragen.

## 2. Fehlende Komponenten und Providerbewertung

Benötigt werden SearchProvider, normalisierte SearchResult/SourceDocument-Typen, ein kontrollierter Fetcher, Quellenpersistenz/-darstellung, budgetierter Kontext, Tooladmisson und v2-Ereignisse. Eine normale Webantwort ist ein begrenzter Suchdurchlauf mit anschließender Antwort; mehrere selbständig geplante Iterationen gehören zu Deep Research.

| Provider | Verifizierte Fähigkeiten | Betrieb und Grenzen | Entscheidung |
| --- | --- | --- | --- |
| SearXNG, eigene Instanz | HTTP GET/POST auf `/search`, JSONformat und Sprach-/Zeitfilter. JSON muss explizit freigeschaltet sein; nicht unterstütztes Format ergibt 403. [Search API](https://docs.searxng.org/dev/search_api.html), [Settings](https://docs.searxng.org/admin/settings/settings_search.html). | Betreiber kontrolliert Instanz/Engines; Suchbegriffe gehen dennoch an konfigurierte Suchmaschinen. Kein eigener garantierter Index. JSON liefert Suchergebnisse, nicht automatisch verlässlich extrahierten Seitenvolltext. | Bevorzugter erster Adapter, sofern Betriebs-/Qualitätsprobe besteht. |
| Brave Search API | Dokumentierter Websuchendpoint, Tokenheader, Länder-/Sprach-/Freshnessfilter und Pagination. [Offizielle API](https://api-dashboard.search.brave.com/app/documentation/web-search). | Externes Providerkonto, Tarif/Quoten und Regeln zur Ergebnisaufbewahrung müssen zum Einsatz passen; kein kostenloser Betrieb vorausgesetzt. | Erste Alternative als eigener Adapter; kein heimlicher automatischer Fallback. |
| Tavily Search | Search-API mit begrenzbaren Results, Domainfiltern und optionalem raw content. [APIvertrag](https://docs.tavily.com/documentation/api-reference/endpoint/search). | Externe Verarbeitung; Resultattext und optional erzeugte Antworten ersetzen keine eigenen Provenienz-/Policyprüfungen. Kosten hängen von Optionen ab. | Spätere Alternative, insbesondere bei belegtem Extraktionsvorteil. `include_answer=false`; roh gelieferter Content wird normalisiert/begrenzt. |
| Unkontrollierte öffentliche SearXNG-Instanz / HTML-Scraping | Kein verlässlicher eigener Vertrag für die Anwendung. | JSON oft deaktiviert, Kontingente und Ergebnisqualität fremdbestimmt. | Keine Produktionsgrundlage; nicht als stiller Fallback verwenden. |
| Providergebundene LLM-Webtools | Könnten den Chatprovider und dessen Requestformat verändern. | Vorhandener Norisadapter weist Toolcalls ab und verwendet `/chat/completions`. | Nicht für die initiale Umsetzung; eigener Capability-/Vertragsnachweis erforderlich. |

SearXNGs [Limiter-Dokumentation](https://docs.searxng.org/admin/searx.limiter.html) beschreibt Abuse-/Bot-Schutz und Suchmaschinensperren. Die Serviceintegration muss zu diesem Schutz passen; den Limiter pauschal abzuschalten ist keine Architekturentscheidung. Interne Ratebegrenzung und korrektes Proxytrust konfigurieren. Nur Backendzugriff, kein öffentlicher Browserzugang zur Suchinstanz, feste erlaubte Engines und JSONformat.

Providerprobe vor Aktivierung: ein synthetischer deutscher/englischer Fragenkorpus mit aktuellen Fakten, Primärquellen, mehrdeutigen Fragen und Nulltreffern; messen Trefferrelevanz, zitierbare Quellen, Freshness, p50/p95-Latenz, 403/429/Timeoutquote und Betriebskosten. Startgate als Vorschlag: bei mindestens 40 Fragen ≥80 % mit mindestens einer fachlich geeigneten Quelle in den ersten fünf Treffern; normale erfolgreiche Searchrequests p95 ≤10 s im vereinbarten Testfenster. Das sind geplante Abnahmewerte, keine durchgeführten Messungen. SearXNG wird bei Nichterfüllung nicht freigegeben; Brave wird getrennt geprüft.

## 3. Datenmodell

`web.search.v1` und `web.fetch.v1` verwenden `chat_tool_run`/`chat_tool_result`. Strukturierte Quellen werden zusätzlich über die gemeinsame Quellenrelation gespeichert:

| Entität | Felder / Bedeutung |
| --- | --- |
| `chat_source` | id, owner/conversation/generation/run, canonical_url, original_url, title, provider, source_kind=`search_snippet/web_page`, rank, snippet, optional published_at, fetched_at, content_digest, bounded extracted_text, fetch_status und sichere warnings. |
| `chat_message_source` | message_id, source_id, citation_key, optional claim_locator; eindeutiger Schlüssel pro Antwort. Zusammengesetzte FKs verhindern Cross-Chat-Zitate. |
| SearchResult | query, normalized sources, provider/configVersion, fetchedAt, warnings, partial flag. |
| SourceDocument | sourceId, text, sha256, mime, finalUrl, fetchedAt; leere/gesperrte Quellen ausdrücklich unterscheiden. |

URLkanonisierung entfernt Fragment und bekannte Trackingparameter, behält inhaltlich relevante Queryparameter. Gleiche URLs innerhalb eines Runs deduplizieren; nicht unterschiedliche Veröffentlichungen nach Domain zusammenwerfen. `published_at` nur bei vorhandener Evidenz, `fetched_at` nie als Publikationsdatum ausgeben. Kein Roh-HTML-Archiv und keine Quellbilder im Attachmentstorage.

Begrenzungsvorschlag: eine Suchanfrage, höchstens 8 Treffer, höchstens 5 Seiten, 64 KiB extrahierter Text je Seite; insgesamt maximal 16.000 zusätzlich budgetierte Kontextzeichen. Deadline für Vorstufe 45 s, Searchcall maximal 15 s, Fetch je 10 s, Fetchparallelität maximal 2. Gatewaykontext kann eine kleinere Auswahl erzwingen; Ausschnittauswahl und ausgelassene Quellen bleiben nachvollziehbar.

Automatische Antwortfortsetzungen behalten dieselbe bereits ausgewählte Quellenbasis, wie heute der PDFkontext. Eine normale spätere Folgefrage kann gespeicherte Quellen des aktiven Nachrichtenpfads budgetiert als untrusted Kontext verwenden; sie startet keine neue Suche oder einen Refetch ohne erneut aktivierten Webmodus. Dieser Quellenkontext wird im gemeinsamen Manager-Contextbuilder ergänzt und durch dieselbe Gatewayprüfung begrenzt.

## 4. API-Verträge

Capability `features.web` zeigt Status, feste reasonCodes, verfügbare Sprachen/Zeitfilter und oben begrenzte Limits. Der Browser wählt keinen Suchprovider, keine Engine und keine fremde URL.

Start: v2 `chat.generate` mit den vorhandenen IDs/Text/Attachment-IDs und `responseMode={kind:"web",modelId,language,timeRange}`. Beispielprompt: „Welche Veröffentlichungen gibt es zu Thema X seit diesem Monat?“ Server nimmt nur diese aktuelle Frage als Suchbasis; deterministische Bereinigung kann Suchbegriffe erzeugen. Kein vollständiger History-/PDF-/Textreferenzupload an Searchprovider. Eine spätere LLM-Queryrewritephase muss ebenfalls durch Gateway/Budget und darf keine vertraulichen Kontextteile einschleusen.

Der Backendadapter ruft SearXNG per POST form-encoded mit `q`, `format=json`, `language`, festem `categories=general`, `pageno=1` und validiertem `time_range` auf. Operator-/Bangsyntax, die feste Engines oder Kategorien umgehen könnte, wird abgewiesen. Suchprovider-Basisadresse ist ausschließlich Betreiberkonfiguration.

GET `/chat/tool-runs/{id}` liefert Search-/Fetchzustand und Ergebnis. Geplant: GET `/conversations/{id}/messages/{messageId}/sources` → `{sources, limitations}` mit Owner-/Messageprüfungen; keine beliebige URLfetchroute. `web.fetch` akzeptiert nur eine Source-ID aus dem zugelassenen Parentrun. `chat.cancel`/`chat.resume` bleiben die bestehenden Steuersignale.

Bei fehlender Toolcapability wird die Webanfrage vor Dispatch abgewiesen. Bei Nulltreffern entsteht eine gespeicherte Ergebnisprojektion mit `sources=[]`; der Assistant darf die fehlende Webgrundlage erklären. Providerfehler werden nicht als Nulltreffer getarnt. Ein Antwortfallback ohne Webbelege ist nur nach einer ausdrücklich sichtbaren Nutzeraktion zulässig.

## 5. WebSocket-Ereignisse

| Ereignis | Fachliche Payload |
| --- | --- |
| `chat.tool.queued/started` | Tool-ID, Run-ID und Phase `searching` |
| `chat.tool.progress` | `searching/fetching/preparing_answer`, geladene Anzahl, optional total; keine erfundene Prozentanzeige |
| `chat.sources.updated` | Source-IDs, Titel, geprüfte URLs, snippet/page-Status, warnings |
| `chat.tool.result` | Result-ID/digest, sourceIds, partial flag |
| `chat.tool.failed/cancelled` | fester Fehlercode oder bestätigter Cancelstatus |
| `chat.generation.delta/completed` | derselbe bestehende Antwortpfad, unter v2 mit gemeinsamer Sequenz |

Ein fertiges SearXNGresultat beendet den Assistant nicht. Search/Fetch und Antwort bilden einen gemeinsamen Generationlebenszyklus; Tool- und Chatabschluss getrennt persistieren. Snapshot enthält bereits gewonnene Quellen und Toolzustände. Reconnect startet keine neue Suche.

## 6. Frontend-UX

Plus → „Websuche“ schließt das bestehende Menü und setzt einen entfernbaren „Websuche“-Moduschip im vorhandenen Composer. Textentwurf, Anhänge und Modell bleiben erhalten. Enter/Senden startet eine Anfrage; erneutes Entfernen des Chips kehrt zu normalem Chat zurück. Modi `web/image/research` sind exklusiv; Bibliothek/Sketch ergänzen Anhänge unabhängig davon. Modus gilt für den nächsten Versand und wird danach zurückgesetzt, außer im gespeicherten noch nicht versendeten Entwurf.

In der bestehenden Assistantansicht erscheinen Phase, Stop und Quellen. Desktop kann Quellen als bestehendes Dialog-/Drawerpattern zeigen, Mobile als Sheet mit sicheren Touchzielen. Quellenlabels sind normaler escaped Text. Linkklick ist eine bewusste Navigation; `noopener noreferrer`, HTTP(S)-Schema, keine Fremdfavicons oder automatisch geladene Trackingbilder. Aussagen mit nicht verfügbarem Volltext heißen „Suchtreffer“, nicht „geprüfte Seite“.

Bei fehlender Konfiguration wird die Aktion ausgeblendet; bei temporärem Ausfall bleibt ein zuvor nutzbarer Modus verständlich gesperrt und der Entwurf erhalten. Keine anklickbaren Platzhalter. Während der Suche bleibt der Stopbutton aktiv, Esc in einem geöffneten Quelldialog schließt zuerst den Dialog.

## 7. Sicherheitskonzept

Providerendpointallowlist und öffentlicher Quellenfetch sind getrennte Vertrauensgrenzen. Für einen internen SearXNGservice ist nur die exakte konfigurierte Serviceadresse erlaubt; öffentliche Quellen dürfen diese Ausnahme nicht verwenden. Fetcher: `trust_env=false`, keine Auth-/Cookieweitergabe, HTTPS im Betrieb, keine userinfo, feste Ports, vollständige DNS-/IPprüfung und Bindung der tatsächlichen Verbindung an die freigegebenen IPs. Jede Redirectzieladresse wird erneut geprüft; maximal 3 Hops. Private/loopback/link-local/multicast/Metadaten-/IPv6mapped-Ziele sperren, auch über alternative IPschreibweisen und DNSwechsel.

Antwortbytes streamend begrenzen: maximal 2 MiB dekodierter Inhalt, Kompressionsverhältnis-/Zeitlimit und anschließend 64 KiB Plaintext. MIMEallowlist zunächst HTML/plain text; heruntergeladene PDFs nur nach zusätzlichem Parser-/Attachmentkonzept, kein beliebiges Binärdownload. HTML wird ohne JS/Browser in einem begrenzten, credentialfreien Parser zu Text extrahiert. Qualität/Abhängigkeit eines weitergehenden Extractors wird im Fetch-PR geprüft; keine neue Parserbibliothek ungeprüft einführen.

Quelltexte gelten als untrusted data. Sie dürfen keine Systemanweisungen oder Toolfreigaben erzeugen; LLM-Ausgabe mit unbekannten Citation-IDs wird als nicht belegte Aussage markiert. Keine Source-URLs aus freien LLMlinks in die geprüfte Quellenliste übernehmen. Nicht behaupten, dass eine URLzuordnung bereits fachliche Richtigkeit beweist.

Suchpayloads, Aufbewahrung und erlaubte Inhaltsnutzung werden vor Providerfreigabe betrieblich geprüft. Keine juristischen Garantien aus dem Vorhandensein einer Such-API ableiten. Logs enthalten Providerkennung, Request-ID, Statusklasse und Dauer, keine Zugangstoken oder vollständigen Such-/Quelltexte.

## 8. Tests

Unit: SearchInput, Provider-Schemanormalisierung, dedup/URLfilter, snippet-vs-page, Datumsevidenz, Kontextauswahl, Citationauflösung, begrenzte Retries, Deadline-/Budgetgrenzen. SSRFmatrix umfasst DNS-Rebinding, Redirect in private Netze, IPv6, userinfo und Kompressionsbomben. Prompt-Injectionfixture fordert zusätzliche Tools/Secrets an und darf keinen Call auslösen.

Integration: lokaler SearXNG-/Brave-HTTPsimulator mit JSON, 403, 429/Retry-After, timeout, malformed payload, leerem/teilweisem Ergebnis und kontrollierten Seiten. Echte PostgreSQLpersistenz, Event-/Snapshotkonsistenz, Doppelsendungen, Cancel während Fetch/Commit, Chatdelete, Ownerfilter und Neustartbudget. Bestehender Chat/PDF-/Vision-/Fortsetzungspfad muss mit zusätzlichem Quellenkontext weiterlaufen.

Playwright Desktop/Mobile: vorhandenes Plusmenü → Moduschip → Senden → Fortschritt → zitierte Antwort → Quellen → Reload/Reconnect; Entfernen des Chips, fehlende Capability, Stop, Tastatur und mobile Screenkeyboard. Regression: normaler Chat, Fileupload und Textreferenz ohne Webmodus lösen keinen Suchrequest aus.

## 9. Abnahmekriterien

- Expliziter Webversand liefert eine Antwort mit persistierten, zugänglichen Quellen oder einen klaren gespeicherten Fehler/Nulltrefferzustand.
- Keine Webausführung ohne aktivierten Modus/Betreiberfreigabe; keine vertraulichen Attachments im Suchrequest.
- Wiederverbinden/Replaying erzeugt weder neue Suche noch doppelte Antwort-/Quellenknoten.
- Stop verhindert weitere Calls; gespeicherte Quellen/Antwortpräfixe bleiben konsistent.
- SSRF-/Owner-/XSS-/Budgettests bestehen, Qualitätsprobe ist dokumentiert.
- Alle bestehenden Chat-, PDF-, Upload-, Modellkatalog- und WS-v1-Checks bleiben grün.

## 10. Abhängigkeiten und Grenzen

Benötigt P0 Menüanschluss, P1 Toolruntime/Policy/Budget, P2 WS-v2 und P6/P7 Search-/Fetch-/UX-PRs aus der Roadmap. SearXNGdeployment und Providerkonto sind spätere Betriebsarbeit; in diesem Planungsauftrag wird nichts gestartet oder veröffentlicht. Bibliotheksrelationen sind für einfache Websuche nicht erforderlich. Deep Research baut auf denselben Search-/Fetchtools auf; die normale Websuche bekommt keine unbegrenzte Agentenschleife.
