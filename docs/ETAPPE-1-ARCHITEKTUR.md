# Etappe 1: Architektur und Implementierungsplan

Etappe 1 erweitert ausschließlich die vorhandene Nuxt-4-Anwendung unter `frontend/app`. FastAPI, PostgreSQL, Alembic und die OpenAPI-Verträge aus Etappe 0 bleiben die Grundlage. Es entstehen keine Authentifizierung, Domänentabellen oder echten Modellaufrufe aus Etappe 2/3.

## Reihenfolge und prüfbare PRs

| PR / Branch | Basis | Implementierung und Nachweis |
| --- | --- | --- |
| `feat/chat-shell` | `main` | Nuxt UI, Designsystem, eigene noris-Marke, Sidebar samt Gesprächsverwaltung/Suche, Header, leere Ansicht, responsiver Drawer, Light/Dark/System; Shell-Unit-/Browsertests |
| `feat/chat-composer` | `feat/chat-shell` | Nuxt-UI-Composer, sichere Markdown-/Code-Darstellung, austauschbarer deterministischer Transport, Zustandsmaschine, Streaming/Stop/Fehler; Interaktions- und Transporttests |
| `feat/chat-branches` | `feat/chat-composer` | Normalisierter Nachrichtenbaum, unveränderliches Editieren, Regeneration, ausgewählte Varianten, Entwürfe und lokale Mock-Persistenz; Invarianten- und Browsertests |
| `feat/chat-ux-polish` | `feat/chat-branches` | Scroll-Follow/Positionen, Shortcuts, Fokus, Reduced Motion, Visual Viewport, lange Verläufe, mobile UX, Screenshot-/Regressionsnachweise |

Jeder Branch enthält seinen Vorgänger. Ein abhängiger PR zeigt nur sein eigenes Delta gegen den Vorgängerbranch. Die PR-Beschreibung nennt die Abhängigkeit. Keine automatischen Merges; keine Implementierung von Etappe 2.

Vor Abschluss jedes PR laufen ESLint, strikte TypeScript-Prüfungen, Vitest, Playwright, API-Drift und Produktionsbuild sowie die unveränderten Backend-Prüfungen. Lokale Sperren werden als **BLOCKED** dokumentiert; Remote-Ergebnisse werden mit dem konkreten CI-Lauf verknüpft.

## Komponenten und Zustand

`ChatWorkspace` koordiniert anwendungsbezogene Komponenten: `ChatSidebar`, `ChatHeader`, `EmptyChatState`, später `ChatComposer`, `ChatMessage`, `ChatTimeline` und `MarkdownContent`. Buttons, Dialoge, Dropdowns, Suche, Textarea, Theme und mobile Overlays verwenden die entsprechenden Nuxt-UI-Komponenten. Das bestehende `ServiceStatus` bleibt unter `/status` mit allen Foundation-Tests erreichbar.

Gesprächsdaten und ihre Invarianten liegen in typisierten Modulen unter `app/lib/chat`. Vue-Composables verbinden diese Daten mit der Darstellung. Transportereignisse, Gesprächszustand, flüchtiger UI-Zustand und persistierte Einstellungen bleiben getrennt. Der Workspace besitzt den gemeinsamen Zustand; es gibt keinen prozessweiten Singleton und keinen zusätzlichen Pinia-Store. Browser-Speicher wird erst nach dem Mount gelesen. SSR und erster Client-Render beginnen mit derselben leeren Struktur.

## Design und geprüfte APIs

Nuxt **4.5.2** bleibt bestehen. Nuxt UI **4.11.3** ergänzt Tailwind 4. Seine Modulregistrierung übernimmt die Tailwind-Integration; der bisher separat registrierte Vite-Plugin-Aufruf entfällt. `app/app.config.ts` definiert die semantischen Farben. `UApp` stellt den deutschen UI-Kontext bereit. Systemschriften und gebündelte Lucide-Icons benötigen keine externen Font-/Icon-Anfragen.

Die Oberfläche hat eine unabhängig scrollbar bleibende Sidebar, einen schmalen Header, eine begrenzte Lesebreite und genau einen Scrollbereich für den aktiven Verlauf. Eine ruhige neutrale Palette und ein dezenter noris-Akzent unterstützen die tägliche Arbeit. Große Touch-Ziele und sichtbarer Fokus gelten bereits in der Shell.

Primärquellen, geprüft am 2026-10-09: [Nuxt-4-Verzeichnisstruktur](https://nuxt.com/docs/4.x/directory-structure/app), [Nuxt UI 4.11.3](https://github.com/nuxt/ui/releases/tag/v4.11.3), [Nuxt-UI-Installation](https://github.com/nuxt/ui/blob/v4.11.3/docs/content/docs/1.getting-started/2.installation/1.nuxt.md), [Sidebar](https://github.com/nuxt/ui/blob/v4.11.3/src/runtime/components/Sidebar.vue), [ChatPrompt einschließlich IME-Behandlung](https://github.com/nuxt/ui/blob/v4.11.3/src/runtime/components/ChatPrompt.vue).

## Transport und Darstellung

`ChatTransport.stream(request, signal)` liefert einen `AsyncIterable<StreamEvent>`. Der Request enthält Generation, Gespräch, unveränderliche Eingabenachricht, Modell und die aus ihrem Parent-Pfad abgeleitete Historie. Ein FastAPI-SSE-Adapter kann später dieselben typisierten Ereignisse liefern; ausschließlich der Composition Root wählt den Mock aus. UI-Komponenten kennen seine Implementierung nicht.

`useChatStream` sperrt den Lauf synchron vor dem ersten Await: `idle → submitting → streaming → completed/cancelled/failed`. Terminale Zustände bleiben final. Sequenzen beginnen bei 1; wiederholte Ereignisse werden ignoriert, Lücken und unvollständig geschlossene Streams führen zu einem Fehler. Stop signalisiert `AbortSignal`; bis zum terminalen Abbruch bleibt die Generierung gesperrt. Teiltexte bleiben erhalten. Antwort- und Eingabelimits sind 32.000 Zeichen.

Der Mock verwendet eine injizierbare Uhr, feste Chunks und Verzögerungen. `/fehler` liefert einen Fehler nach einer Teilantwort, `/lang` einen langen Stream; diese Befehle sind ausschließlich Demo-/Testkonventionen. Vitest steuert die Uhr und Ereignisfolgen deterministisch. Modelle sind vorbereitete Demo-Auswahlen, keine echte Provider-Registry.

`UChatPrompt` übernimmt Autosize, maximale Zeilenhöhe, Enter/Shift+Enter und IME-Schutz. Die Wrapper-Komponente verhindert inkompatible Sends. `MarkdownContent` erzeugt Vue-Knoten aus Markdown-it-Tokens mit `html: false`, einer Tag-Allowlist und geprüftem Linkprotokoll. Es gibt kein `v-html`. Externe Links tragen `noopener noreferrer`; Markdown-Bilder werden als Alt-Text angezeigt, ohne Netzwerkzugriff. Code ist immer Text; Shiki lädt acht fest definierte Sprachen und zwei Themes erst nach Mount. Unbekannte Sprachen und sehr große Blöcke bleiben lesbarer Klartext. Code-/Tabellen-Scrollen bleibt auf den jeweiligen Block begrenzt.

PR 2 erhält lokale Gesprächsmetadaten. Nachrichten und Entwürfe werden erst mit der validierten gemeinsamen Persistenz in PR 3 dauerhaft gespeichert.

## Verzweigungen und lokale Persistenz

Nachrichten liegen einmalig in einem nach ID normalisierten Record. `parentMessageId` bildet den Baum; `activeLeafMessageId` wählt den sichtbaren Parent-Pfad. Rollen wechseln entlang eines gültigen Pfads. Editieren erzeugt eine neue Nutzernachricht mit demselben Parent und optionaler `editedFromMessageId` als Herkunft. Regeneration erzeugt eine Assistant-Schwester. Der Transport erhält jeweils nur die Historie bis zur gewählten Eingabe. Alte Texte und Fortsetzungen bleiben erhalten.

`useChatBranches` ist durch die reinen Funktionen `siblingVariants` und `variantLeaf` umgesetzt; ein zusätzlicher Store wäre redundant. Beim Wechsel werden die zuletzt betrachteten Blätter für die Pfadknoten gespeichert. Zurückwechseln stellt damit auch eine frühere Fortsetzung wieder her. Neue Varianten folgen deterministisch der Erstellungsreihenfolge. Während eines laufenden Streams sind Editieren, Regeneration und Variantenwechsel gesperrt.

`useChatDrafts` verwaltet einen Entwurf pro Gespräch und einen für die noch nicht angelegte Unterhaltung. Senden löscht nur den eingereichten Entwurf. `useChat` speichert Gesprächsmetadaten, Nachrichten, Blätter und Entwürfe atomar unter `noris-ai:chat:v1`. Der synchron beobachtete Zustand wird höchstens einmal pro 120 ms geschrieben; `pagehide` sichert ausstehende Änderungen. Einstellungen wie Modell und Theme haben eigene Speichergrenzen.

Die Laufzeitvalidierung prüft Version, Größen, eigene Schlüssel, IDs, Rollen, Parents, Zyklen, Herkunft und Gesprächszugehörigkeit vor Hydration. Beschädigte Daten werden nicht überschrieben. Ein beim Reload unterbrochener Mock-Stream wird als abgebrochen dargestellt. Browser-Speicher beginnt erst nach Mount; der Server kennt keine privaten lokalen Daten. Bei konkurrierenden Änderungen in einem anderen Tab werden weitere Schreibvorgänge gestoppt und ein Neuladen empfohlen. Die Demo synchronisiert keine Chats zwischen Geräten und enthält keine PostgreSQL-Domänentabellen.

## Scrollmanagement (PR 4)

Scroll-Follow richtet sich nach Position und Nutzerabsicht vor einem Layout-Update. Konkrete Umsetzung und Nachweise werden mit PR 4 ergänzt.

Ergänzte UX-Vorgabe: Beim Senden mit Enter wird die neue Nutzernachricht am oberen Rand des Verlaufs unter dem Header positioniert. Der letzte Gesprächsschritt reserviert dafür genug Höhe. Während die Antwort wächst, folgt der Viewport ihrem Ende; manuelles Hochscrollen pausiert dieses Folgen. Dies wird in PR 4 implementiert und mit langen Streams auf Desktop/Mobile geprüft.
