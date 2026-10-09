# Accessibility-Spezifikation

Ziel WCAG2.2AA im Etappe-1-Umfang, keine ungeprüfte Konformitätserklärung. Fokus/Hover/Screenreader sind in der Referenz UNVERIFIED.

- Native Main/Nav/Article-Struktur; Sprunglink zum Chat; benannte unabhängige Navigationen und Nachrichtenregion.
- Nuxt UI/Reka übernimmt Menü-/Dialogtastatur, Fokusmanagement und mobile Overlays. Jede Iconaktion bekommt einen verständlichen Namen, relevante Buttons mindestens44×44px.
- Aktionen bleiben per Touch und Tastatur erreichbar; kein ausschließliches Hover-Verhalten und keine beim Hover wachsenden Toolbars.
- Sichtbarer neutraler Fokus; Text-/Placeholderkontrast wird im Browser aus tatsächlich berechneten Farben geprüft. Sekundärtexte werden bewusst dunkler als im Referenzbild.
- Streaming-Livetext bleibt außerhalb aria-live. Nur kurze Phasenstatusmeldungen werden polite/atomic angekündigt, nicht jedes Token. Abbruch und Fehler bleiben sichtbar verständlich.
- Sichere Markdown-VNodes, html:false, Protokoll-Allowlist und rel=noopener noreferrer; Bilder laden nicht fremde Tracker. Code und Tabellen überschreiten die Inhaltsspalte nicht.
- Reduced Motion reduziert vorhandene Transitions/Animationen. Autosize, Tastatur und VisualViewport dürfen keinen window-Scroll verursachen.
- Automatisierte Prüfungen ergänzen explizite manuelle Schritte: VoiceOver/TalkBack, echte Bildschirmtastaturen, High Contrast und Browserzoom. Diese Schritte sind bis zur realen Prüfung NOT TESTED.
