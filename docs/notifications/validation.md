# Lokaler Prüfbericht

Datum: 12. Oktober 2026. Ausgangspunkt: `main` / `d7c3100`. Alle Prüfungen liefen lokal. Auf ausdrücklichen Wunsch wurden ausschließlich direkt betroffene Tests ausgeführt und keine CI gestartet. Der Commit enthält `[skip ci]`; die vorhandenen Workflows werden nicht verändert.

## Ergebnisse

| Prüfung | Ergebnis | Umfang |
| --- | --- | --- |
| ESLint | bestanden | 33 neue/geänderte TypeScript-/Vue-Dateien; die zuletzt angepassten beiden Testdateien nochmals geprüft |
| Nuxt-Typecheck | bestanden | bestehender Frontend-Typecheck |
| Strikter Test-/Frontend-Typecheck | bestanden | `tsconfig.tests.json`, einschließlich neuer Composables, Vue-Komponenten und Browserfixtures |
| Vitest Unit-/Composable-Integration | 281 Tests in 18 Dateien bestanden | ausschließlich Notification-, Chat-, Transport-, Upload-, Modell-, Settings-, Such- und Recoverypfade |
| Abschließende Prüfung der Notification-Testdoubles | 141 Tests in 2 Dateien bestanden | nach Anpassung an die strikten Nuxt-UI-Toasttypen |
| Playwright | 16 Fälle bestanden | tatsächlicher Produktionsbuild mit synthetischen REST-/WebSocketantworten |
| Vorher-Screenshots | 6 Browserfälle bestanden | unveränderter Ausgangsstand auf `main`, 12 Bilder |
| Produktionsbuild | bestanden | Nuxt/Nitro, vorhandene WebSocketkonfiguration |
| Whitespaceprüfung | bestanden | `git diff --check` |

Die 141 abschließenden Tests sind eine Teilmenge der 281 Tests und werden nicht zusätzlich gezählt.

## Reproduzierbare Befehle

Die Befehle werden im Verzeichnis `frontend` ausgeführt. Die lokalen Node-Einstiegspunkte verwenden die bereits installierten, durch den Lockfile festgelegten Abhängigkeiten und installieren keine Pakete.

```sh
node node_modules/vitest/vitest.mjs run \
  tests/unit/app-notifications.spec.ts \
  tests/unit/notification-recovery.spec.ts \
  tests/unit/chat-composer.spec.ts \
  tests/unit/model-selection.spec.ts \
  tests/unit/chat-lazy-loading.spec.ts \
  tests/unit/chat-import.spec.ts \
  tests/unit/reasoning-selection.spec.ts \
  tests/unit/chat-stream.spec.ts \
  tests/unit/real-transport.spec.ts \
  tests/unit/websocket-transport.spec.ts \
  tests/unit/chat-backend.spec.ts \
  tests/unit/text-reference-attachments.spec.ts \
  tests/unit/learning-mode.spec.ts \
  tests/unit/delete-dialog.spec.ts \
  tests/unit/settings-dialog.spec.ts \
  tests/unit/message-actions.spec.ts \
  tests/unit/long-output.spec.ts \
  tests/unit/conversation-search.spec.ts

NUXT_TELEMETRY_DISABLED=1 node node_modules/nuxt/bin/nuxt.mjs typecheck
node node_modules/vue-tsc/bin/vue-tsc.js --noEmit --project tsconfig.tests.json

NUXT_TELEMETRY_DISABLED=1 NUXT_PUBLIC_CHAT_TRANSPORT=websocket \
  node node_modules/nuxt/bin/nuxt.mjs build
node node_modules/@playwright/test/cli.js test --config playwright.notifications.config.ts
```

ESLint wurde mit `node node_modules/eslint/bin/eslint.js` und einer expliziten Liste aller neuen/geänderten Frontenddateien mit den Endungen `.ts` und `.vue` ausgeführt. Vor Veröffentlichung kann diese Liste aus `git diff --name-only main` ermittelt werden. Die bestehende CI, Backendtests und nicht betroffene Browser-Suites wurden nicht ausgeführt.

## Abdeckung

- Alle öffentlichen Fehlercodes aus den bestehenden Chat-/LLM-Fehlerverträgen und REST-Fehlerantworten sowie sämtliche zentral gemappten Clientcodes; verständlicher Fallback ohne Exceptiontext, validierte IDs und ausschließlich erlaubte Diagnosedaten.
- Gleicher Fehler vor asynchroner Toast-Insertion, getrennte Operationen/Chats/Generierungen/Requests/Anhänge, spätere eigenständige Versuche, Deduplikationsablauf, maximal drei sichtbare Toasts, begrenzte Warteschlange und zusammengefasster Überlauf.
- Lebensdauer für Erfolg, Information, Warnung und Fehler; notwendige Aktionen ohne Kontext-Recovery bleiben stehen. Kontext-Recovery bleibt unabhängig von der Toast-Lebensdauer verfügbar.
- Provider-/Netzwerkfehler, Timeout, Rate-Limit, Model-Unavailable, Fehler während Streaming und nach Teilantwort, erhaltene ältere Nachrichten und Text bei wartendem Resume.
- WebSocket-Reconnect mit Resume derselben Generation; keine zweite Modellanfrage und kein Fehler-Toast für eine erfolgreiche Wiederverbindung.
- Fehlgeschlagene Uploads mit beibehaltenem `File`, Netzwerk-/Timeout-/Formatfehler, Wiederholung mit denselben Bytes und dauerhaft sichtbarer Attachmentkarte.
- Fehler beim Speichern von Einstellungen und Entwürfen, gezielter ausdrücklicher Retry im betroffenen Chat, kein Autosave-Fehlerloop, kein Überschreiben mit einem veralteten Entwurf.
- Fehlgeschlagenes serverseitiges Löschen bewahrt Nachrichten und Entwurf; Erfolg erst nach Serverbestätigung, ohne erfundenes Undo.
- Normale erfolgreiche Generierung ohne Toast, Tastaturaktionen, sichtbarer Fokus, Escape, einmalige zentrale Alert-/Statusregionen, Diagnosedialog und Kopieren ohne Chatinhalt.
- Viewports 1700 × 900, 1440 × 900 und 390 × 844 jeweils in Light/Dark; unveränderte Composer-Geometrie beim Toast-Einblenden, keine horizontale Überbreite, maximal drei Karten, Reduced Motion und verkleinerter mobiler Viewport (390 × 420).

## Bildnachweise

Die [Galerie in der Bestandsaufnahme](README.md#screenshots) enthält alle 54 PNG-Dateien: 12 Vorher-Bilder der beiden tatsächlichen Fehlerzustände und 42 Nachher-Bilder für Erfolg, Information, Warnung, Fehler mit Retry, mehrere Benachrichtigungen, fehlgeschlagene Modellantwort und fehlgeschlagenen Upload. Alle Bilder verwenden synthetische Testinhalte. Die Nachher-Bilder stammen aus dem Produktionsbuild.

## Grenzen und Werkzeughinweise

- Browserfixtures prüfen das Frontend gegen die bestehenden Verträge. Liveprovider, Datenbankintegration und Produktivserver wurden nicht angesprochen.
- Screenreader-Prüfung ist automatisierte DOM-/Live-Region-Prüfung. Manuelle NVDA-/VoiceOver-Tests und eine echte mobile Bildschirmtastatur wurden nicht durchgeführt. Der verkleinerte Viewport prüft die Platzierung bei geringer sichtbarer Höhe.
- Die vorhandene Installation meldet beim Typecheck ein fehlendes optionales Volar-Plugin `vue-router/volar/sfc-route-blocks`. Beide Typechecks enden erfolgreich; Abhängigkeiten wurden deswegen nicht geändert. Der Build meldet vorhandene Rollup-Annotation-/Timinghinweise, endet aber erfolgreich.
- Lokal installiert: Node 22.22.1; Repository-Mindestversion: 22.22.3. Alle genannten Prüfungen bestehen mit der vorhandenen Installation. Der vorhandene Paketmanager/Lockfile und die CI bleiben unverändert.
- Vollständiger Reload verliert die originale, fehlgeschlagene Browserdatei; Retry ist mit erhaltenem `File` im aktuellen Workspace verfügbar. Weitere fachliche Grenzen stehen in der [Bestandsaufnahme](README.md#grenzen).

Keine automatische Zusammenführung und keine Änderungen am Produktivserver.
