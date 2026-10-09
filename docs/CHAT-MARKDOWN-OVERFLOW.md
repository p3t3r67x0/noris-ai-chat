# Chat-Antworten ohne horizontalen Überlauf

Stand: 9. Oktober 2026. Branch: `fix/chat-markdown-overflow`.

## Ursache und Umsetzung

Der Markdown-Renderer erzeugt native Tabellen in `.markdown-table`. Der bisherige Stil `width: max-content` berechnet ihre Breite aus dem Inhalt statt aus der verfügbaren Chatspalte. `overflow-x: auto` am Wrapper verdeckte den Fehler durch einen eigenen horizontalen Scrollbereich. Codeblöcke verwendeten ausdrücklich `white-space: pre` und horizontales Scrollen.

Tabellen erhalten jetzt `width: 100%`, `max-width: 100%` und `table-layout: fixed`. Kopf- und Datenzellen umbrechen mit `overflow-wrap: anywhere`, behalten vollständige Inhalte und richten sich oben aus. Auch Inline-Code, Links, Dateinamen, Absätze und verschachtelte Listen können innerhalb der Chatspalte umbrechen. Die Markdown-Wurzel und das vorhandene Flex-Kind `.chat-scroll` erhalten explizite Breitenbegrenzungen beziehungsweise `min-width: 0`. Der Tabellenwrapper ist kein Scrollbereich mehr und benötigt keinen zusätzlichen Tabstopp. Native Tabellen, Zeilen und Kopfzellen bleiben erhalten.

Codeblöcke verwenden standardmäßig `white-space: pre-wrap` und `overflow-wrap: anywhere`. Der mit Tastatur bedienbare Schalter **Zeilenumbruch umschalten** zeigt seinen Zustand über `aria-pressed`. Nur nach ausdrücklichem Abschalten des Umbruchs darf das vorhandene `pre` horizontal scrollen; die Unterhaltung und die Nachricht bleiben weiterhin innerhalb der Chatspalte. Einrückungen, originale Zeilenumbrüche, Shiki-Highlighting und das Kopieren des unveränderten Quelltexts bleiben erhalten. Auch lange Sprachbezeichnungen umbrechen neben den Bedienelementen.

Beim Streaming kann die Umwandlung unvollständigen Markdowns in eine Tabelle die Inhaltshöhe verringern. Der Browser begrenzt dann automatisch eine zuvor größere Scrollposition. Die bestehende Scrollentscheidung berücksichtigt nun diese maximal mögliche Position, damit die automatische Begrenzung das Folgen nicht pausiert. Tatsächliches Hochscrollen pausiert weiterhin; die Schaltfläche zum Ende nimmt das Folgen wieder auf. Es entsteht kein weiterer Scrollcontainer.

## Regressionen und visuelle Abnahme

Die synthetischen Fixtures enthalten Zwei- und Fünfspaltentabellen, lange deutsche Beschreibungen, anklickbare lange URLs, Inline-Code, Dateinamen, ununterbrochene Zeichenketten, Zitate, verschachtelte Listen, lange Codezeilen und eine lange Antwort. Mehrzeilig dargestellte Tabellenzellen entstehen durch natürlichen Textumbruch; die vorhandene Markdown-Grammatik und der Inhalt werden nicht verändert.

Playwright prüft sowohl `document.documentElement.scrollWidth <= document.documentElement.clientWidth` als auch Scrollbreiten und Geometrie der tatsächlichen Nachrichten, Markdown-Container, Tabellen, Zellen und Codeblöcke. Zusätzlich werden die gerenderten Textfragmente innerhalb von Zellen und umgebrochenem Code gemessen, damit bloßes Abschneiden keinen Test bestehen lässt. Code-Schalter und Kopierfunktion werden per Tastatur beziehungsweise über die echte Zwischenablage geprüft. Inkrementelle Markdown-Tabellen werden während des Streamings vermessen; Folgen, manuelles Lesen und Wiederaufnahme sind Bestandteil des Tests.

Geprüfte Größen: **1920 × 975**, **1440 × 900**, **1280 × 800**, **768 × 1024**, **390 × 844** und **360 × 800**. Desktop-Fälle prüfen geöffnete und geschlossene Sidebar. Beide Browserprojekte führen die neuen Fälle aus.

Die Tabelle mit **Stärke / Bedeutung** und vollständigen deutschen Beschreibungen wurde visuell auf Desktop und Mobile geprüft:

- [Desktop, 1920 × 975](../frontend/tests/e2e/__screenshots__/linux/desktop/markdown-strengths.png)
- [Mobile, 390 × 844](../frontend/tests/e2e/__screenshots__/linux/mobile/markdown-strengths.png)

Die zwei bestehenden Desktop-Code-Baselines in Light/Dark wurden gezielt für den neuen Schalter und die veränderte Tabellenaufteilung aktualisiert. Die Screenshot-Toleranz bleibt bei `maxDiffPixelRatio: 0.001`; bestehende übrige Baselines und Tests bleiben aktiviert.

## Prüfstand

- Frontend: 112 Unit-Tests erfolgreich.
- Browser: alle 129 Desktop-/Mobile-Tests einschließlich Screenshot-Vergleichen erfolgreich; anschließend sechs RealTransport-Browsertests erfolgreich mit dem lokalen HTTP-Simulator.
- Backend: 102 Unit-, OpenAPI-Vertrags- und lokale HTTP-Streamingtests erfolgreich.
- PostgreSQL: drei Integrationstests erfolgreich gegen eine eigens angelegte disposable Testdatenbank.
- Screenshot-Dokumentation: elf Tests erfolgreich; Pillow wurde ausschließlich für diesen Lauf temporär bereitgestellt.
- Lint, strikte Python-/Nuxt-/Vue-/Werkzeug-Typprüfungen und API-Driftprüfung erfolgreich.
- Backend-Paket und Nuxt-Produktionsbuild erfolgreich.

Die vollständige Browserabnahme verwendet wegen belegter Standardports eine temporäre Frontend-Kopie, separate Loopback-Ports, eine lokale PostgreSQL-Instanz unter `/tmp` und den gebauten Nuxt-Produktionsserver mit einem lokalen Same-Origin-Proxy zur API. Testfälle, Bildschirmgrößen und Vergleichstoleranzen entsprechen der regulären Suite. Für die bestehenden RealTransport-Browserprüfungen wird ausschließlich der lokale HTTP-Providersimulator verwendet; das Anfragebudget seines Test-Backends ist temporär erhöht, damit lokale Umgebungseinstellungen den kombinierten Desktop-/Mobile-Lauf nicht begrenzen. Diese Laufkonfigurationen ändern keine eingecheckte Anwendungs- oder Providerkonfiguration.

Reproduktion in der regulären Entwicklungsumgebung mit freier API-/Frontend-Portbelegung und bereiter Datenbank:

```sh
make lint
make typecheck
make check-api
make test-unit
make test-integration
make test-e2e
make build
```
