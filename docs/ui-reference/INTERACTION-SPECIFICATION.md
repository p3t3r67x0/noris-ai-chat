# Interaktionen

Die zeitlichen Abläufe sind nicht aus einem Standbild beobachtbar. Die folgenden Anforderungen stammen vom Auftraggeber (**INFERRED / verbindliche Produktspezifikation**); Tests belegen Noris-Verhalten, keine ausgelesene private ChatGPT-Sitzung.

- Ein UChatPrompt bleibt über den Leer/Verlauf-Wechsel gemountet. Enter sendet genau einmal; Shift+Enter bleibt Zeilenumbruch; der vorhandene Nuxt-UI-IME-Guard verhindert Send während Komposition. Whitespace und Limits bleiben unverändert.
- Neue Frage reserviert mit ihrem Antwortschritt den sichtbaren Verlauf und erscheint unter dem Header. Inhalt wächst in genau einem vertikalen Verlauf. ResizeObserver und RAF bündeln Folgebewegungen; kein window.scroll und kein scrollIntoView auf Tokens.
- Hochscrollen per Wheel, Touch oder Verlaufstaste pausiert vor der nächsten RAF. Nachwachsender Text bewegt den Leser nicht. Zurückscrollen ans Ende oder der Ende-Button reaktiviert Folgen. Pro Gespräch werden flüchtige Position und Follow-Absicht restauriert.
- Stop nutzt denselben AbortSignal-Lauf, hält die Sperre bis zum terminalen Ereignis und erhält Teiltext. Der Composer erhält den Fokus mit preventScroll zurück. Abschluss stiehlt keinen Fokus aus einer anderen inzwischen bedienten UI.
- Entwürfe pro Gespräch, atomare Persistenz, nichtdestruktives Editieren, Assistant-Geschwister und alte Fortsetzungen bleiben unverändert. Variantenaktionen sind während einer Generation gesperrt.
- Desktop-Sidebarpräferenz wird getrennt von Chatdaten gespeichert; mobile Drawer-Nutzung überschreibt diese Einstellung nicht. Suche/Archiv/Umbenennen/Löschen verwenden bestehende Nuxt-UI-Overlays.
- Icon-Leiste: eigenes Noris-Home erzeugt einen Chat; Suche/Archiv öffnen bestehende Dialoge. Der Kontobereich ist eindeutig lokale Demo, keine vorgetäuschte Anmeldung. Anhänge sind ausdrücklich unavailable, Sprache/Sharing/Projekte werden nicht angeboten.
- Escape beendet vorhandene Overlays über Reka/Nuxt UI; andernfalls stoppt es die Generierung. Ctrl/Cmd+K und Ctrl/Cmd+Shift+O bleiben erhalten. IME und wiederholte Tastenevents werden nicht für Shortcuts verwendet.

Zustandsvertrag bleibt `idle → submitting → streaming → completed/cancelled/failed`. Der Composition Root wählt den deterministischen Mock; Komponenten hängen nur an ChatTransport und typisierten Nachrichten.
