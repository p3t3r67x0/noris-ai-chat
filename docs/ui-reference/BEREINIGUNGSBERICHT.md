# Bereinigung der fünf Vergleichsbilder für PR #18

## Nachträglicher Integrationsstand

Die fünf Bildhashes und deren damalige Prüfung bleiben unverändert. Zusätzlich wurden später die private Referenz-Fixture, ihre Golden und die aktiven PR-18-/PR-20-Historien nach gesonderter Freigabe bereinigt. Alle 17 freigegebenen alten Browserartefakte sind gelöscht. Der Auftraggeber genehmigte anschließend die Integration der bereinigten PRs #18 und #19 trotz des ausdrücklich offenen GitHub-Support-Takedowns. [HISTORIENBEREINIGUNG](HISTORIENBEREINIGUNG.md) beschreibt den aktuellen Stand; nachfolgende ursprüngliche Befunde bleiben als historische Nachweise nachvollziehbar.

Stand: 2026-10-09. **Die abschließende Freigabe des Auftraggebers wurde erteilt.** Dieser PR veröffentlicht ausschließlich die fünf nachfolgend benannten, vollständig bereinigten Dateien mit den geprüften SHA256-Werten sowie diesen Bericht. Die Freigabe umfasst weder private Originale noch alte Vergleichsdateien, eine Historienumschreibung oder einen Merge.

## Ergebnis

Die fünf bisherigen Kandidaten waren **nicht vollständig bereinigt**. Die frühere Maskierung entfernte Sidebar-Titel und Kontobuchstaben, ließ aber den privaten Gesprächsinhalt stehen. Auch die Noris-Referenzszene enthält aus der privaten Vorlage übernommene Texte. Diese Inhalte wurden unabhängig davon, ob sie Namen oder Zugangsdaten enthalten, als nicht zur Veröffentlichung freigegeben behandelt.

Die fünf neuen Dateien enthalten feste, frei erfundene Gesprächsinhalte und neutrale Demo-Kontodarstellungen. Alle fünf wurden visuell in Originalauflösung geprüft. Es wurden darin keine personenbezogenen, vertraulichen oder nicht freigegebenen Gesprächsinhalte festgestellt. Ergänzende lokale Tests prüfen die Unabhängigkeit von privaten Bildbereichen und die ausschließlich bereinigten Quellen der abgeleiteten Ansichten. Zur Veröffentlichung wurden die freigegebenen PNG-Bytes unverändert kopiert, nicht neu gerendert.

**Offener Zusatzbefund:** Das ursprüngliche private Bild ist aus dem aktuellen Git-Dateibaum ausgeschlossen, befindet sich aber bereits in einem früheren Commit. Die neuen Bildversionen beseitigen diesen historischen Bestand nicht. Der gesamte PR kann deshalb durch diese Bildprüfung nicht pauschal als frei von privaten Referenzdaten bezeichnet werden; siehe „Git-Prüfung“.

## Prüfung der bisherigen fünf Kandidaten

Die alten Dateien liegen unverändert und im Git ausgeschlossen unter `local-comparison/quarantine/previous/`. Sie sind ausdrücklich keine Veröffentlichungskandidaten. Ihre SHA256-Werte sind lokal in `local-comparison/quarantine/input-audit.json` festgehalten.

| Datei | Befund vor der vollständigen Bereinigung | Entscheidung |
| --- | --- | --- |
| `reference-layout-redacted.png` | Sidebar und Initialen maskiert; Nutzernachricht, Antwort und Kontext weiterhin lesbar | FAIL, lokale Quarantäne |
| `noris-reference.png` | Mock-Verlauf, aber aus der privaten Referenz übernommene Antwort und thematisch zuordenbarer Titel | FAIL, lokale Quarantäne |
| `side-by-side.png` | Beide unzureichend bereinigten Bilder direkt lesbar; mathematisch identisch mit den beiden nebeneinander gesetzten Quellen | FAIL, vollständig neu erzeugt |
| `overlay.png` | Private Gesprächsinhalte lesbar; eine Quelle bei bekannter anderer Quelle nahezu vollständig rekonstruierbar | FAIL, vollständig neu erzeugt |
| `difference.png` | Textkonturen und Teile der privaten Inhalte lesbar; keine verlässliche Anonymisierung | FAIL, vollständig neu erzeugt |

Es wurden in den bisherigen PNGs keine zusätzlichen Text-/EXIF-Metadaten oder Alphaebenen gefunden. Das machte die sichtbaren Inhalte nicht veröffentlichungsfähig. Originaltexte, Chat-Titel und Kontobuchstaben werden in diesem Bericht nicht erneut wiedergegeben.

## Ersetzte Inhalte

| Bereich | Vollständiger Ersatz |
| --- | --- |
| Nutzerfrage einschließlich oben angeschnittener Textzeilen | Erfundene Bitte um einen neutralen Tagesplan mit drei Schritten |
| Assistant-Antwort einschließlich Überschriften, Absätzen und Formatierung | Neu formulierter synthetischer Tagesplan; keine Paraphrase oder Kürzung des privaten Gesprächs |
| Gesprächstitel, Gruppierung, Projektbereich, Verlauf und Statusmarker | Feste Bezeichnungen `Beispiel 01` bis `Beispiel 14`, Gruppe `Beispiele`; keine Zuordnung zu tatsächlichen Chats oder deren Anzahl |
| Profil-/Kontodarstellung | Vollständig neu gezeichnete graue Demo-Fläche mit `D`; ursprüngliche Initialen und Profilfarbe nicht übernommen |
| Composer einschließlich möglicher Entwürfe und Modellauswahl | Neu gezeichnete Fläche mit `Demo-Nachricht eingeben` und `Demo-Modell` |
| Header-Modell und Konto-/Statusbeschriftungen | Generische Demo-Beschriftungen |
| Denkzeit, Projektstatus, Quellenchips, Links und kontextbezogene Angaben | Entfernt; bei Bedarf generischer Hinweis auf die synthetische Darstellung |
| Personen, Organisationen, Kontaktdaten, URLs, IDs, Pfade und Zugangsdaten im Gespräch | Kein Inhalt aus diesen Bereichen übernommen; synthetische Texte enthalten keine solchen Angaben |

Nur einzeln visuell geprüfte **statische UI-Bereiche** bleiben als Rasterausschnitte erhalten: allgemeine Navigationsicons, Produktnamen, Neuer-Chat-Steuerung sowie statische Teilen-/Kopieren-/Bearbeiten-Icons. Die bekannten Produktbezeichnungen sind öffentliches UI-Chrome, keine Kontodaten. Die genauen Rechtecke stehen im [freigegebenen Manifest](evidence/sanitized/manifest.json) und in [sanitize_comparison.py](sanitize_comparison.py).

Alle anderen Bereiche werden auf einer neuen, vollständig deckenden RGB-Fläche gezeichnet. Die Methode verwendet keine Unschärfe, Pixelierung, transparente Abdeckung oder generative Rekonstruktion privater Texte. Originale und bisherige Kandidaten bleiben unverändert erhalten. Die neuen Ansichten tragen die Kennzeichnung „Synthetische Vergleichsansicht“.

## Rekonstruktionsprüfung

Beim alten 50-Prozent-Overlay lässt sich die Referenz mit `2 × Overlay − Noris` rekonstruieren. Der gemessene maximale Fehler beträgt **eine RGB-Stufe** durch Rundung. Die damals nur teilweise bereinigte Referenz enthielt weiterhin Gesprächsinhalte. Ein Overlay schützt diese Daten somit nicht.

Eine absolute Differenz ist ohne zusätzliche Information nicht eindeutig invertierbar, weil das Vorzeichen fehlt. Sie zeigt dennoch Textkonturen und lesbare Inhalte; eine bekannte zweite Quelle schränkt die möglichen Originalwerte weiter ein. Auch sie ist kein Ersatz für vorherige Bereinigung.

Die neuen Side-by-side-, Overlay- und Differenzbilder werden **ausschließlich aus den zwei vollständig bereinigten Ausgangsbildern** erzeugt. Die Quellgleichheit wurde pixelweise geprüft. Eine Rückrechnung des neuen Overlays liefert ausschließlich die synthetische Referenz samt geprüftem statischem UI-Chrome, wieder mit höchstens einer RGB-Stufe Rundungsfehler. Es werden keine privaten Pixelbereiche zum Erstellen dieser drei Bilder verwendet.

## Fünf freigegebene Vergleichsbilder

Die folgenden Dateien sind unter `evidence/sanitized/` veröffentlicht. Eine byteidentische lokale Kopie bleibt unter dem Git-ausgeschlossenen Verzeichnis `local-comparison/sanitized/`. Ausschließlich diese fünf Hashes wurden zur Veröffentlichung freigegeben. Alte Kandidaten, Originale und private Vergleichsdateien gehören nicht dazu.

| Datei | Auflösung | SHA256 |
| --- | --- | --- |
| [Bereinigte Referenz](evidence/sanitized/reference-layout-redacted.png) | 1920 × 975 | `d25571e65223c54be898203aa5206a154469b4c7228db3643e7534d1d664b790` |
| [Bereinigte Noris-Ansicht](evidence/sanitized/noris-reference.png) | 1920 × 975 | `8bb368e991323165a6c569cf64b9d6562ec53b89c81dbbdc89defeabdd432eb7` |
| [Side-by-side](evidence/sanitized/side-by-side.png) | 3840 × 975 | `c0ec93ecef9f7a2bfa0e5c6e216c32aaff440f17142c84b05c2c720e0433489a` |
| [Overlay](evidence/sanitized/overlay.png) | 1920 × 975 | `6563363dc11162bc63b73257cee5f303984aed62ba145c252b31542f21f92a38` |
| [Differenzbild](evidence/sanitized/difference.png) | 1920 × 975 | `f790305f89bed895084dd784ba2c6e71169ebad5b6aeffffb605ff28673717c5` |

Alle fünf Dateien haben den Modus **RGB ohne Alpha**, keine PNG-Text-/EXIF-Metadaten und ausschließlich die Chunks `IHDR`, `IDAT`, `IEND`. Es gibt keine angehängten Daten hinter `IEND`. Die Dateien sind deckend neu exportiert; Dateinamen und das Manifest enthalten keine privaten Kontodaten oder persönlichen Quellpfade.

## Lokale Prüfnachweise

**PASS:** elf Tests in [test_sanitize_comparison.py](tests/test_sanitize_comparison.py), ohne Skip:

- Änderungen sämtlicher Pixel außerhalb der geprüften statischen Ausschnitte ändern die bereinigten Ausgangsbilder nicht.
- Auch alle fünf resultierenden Dateien bleiben bei solchen Änderungen identisch.
- Künstliche Geheimtext-Marker in Nachricht, Verlauf, Profil, Modell und Eingabe gelangen nicht in die Ergebnisse.
- Eine Änderung am erlaubten statischen UI-Ausschnitt verändert das Ergebnis als positive Kontrolle.
- Eingangsmetadaten werden verworfen; alle fünf Exporte enthalten keine Alpha- oder Metadatenebenen.
- Die drei abgeleiteten Ansichten verwenden pixelgenau ausschließlich die beiden bereinigten Quellen.
- Die Overlay-Rückrechnung rekonstruiert ausschließlich die bereinigte Referenz.
- Exporte in Git-sichtbare Verzeichnisse sowie ungeprüfte Bildgrößen werden abgelehnt.
- Das frühere Werkzeug für reine Sidebar-Maskierung verweigert ebenfalls Git-sichtbare Exporte.

**PASS:** visuelle Einzelprüfung aller fünf neuen Bilder, SHA256-Abgleich aller fünf Exporte und ihrer Veröffentlichungskopien, unveränderte Bytes der fünf alten Kandidaten, `git check-ignore` für sämtliche lokalen Vergleichsdateien und das Original. Nur die fünf bereinigten Veröffentlichungskopien sind Git-sichtbar. Der Ausgangsscreenshot wurde in dieser Prüfung nicht verändert.

**PASS vor Veröffentlichung:** elf Tests mit vollständig synthetischen Eingangsfixtures erneut ausgeführt (8,702 s, kein Skip); Ruff-Lint und Formatprüfung für Bereinigungswerkzeug, Vergleichswerkzeug und Datenschutztests bestanden. Die Veröffentlichungs-Allowlist umfasst exakt fünf PNGs; ursprüngliche Referenz, Quarantäne und sonstige lokale Vergleiche sind nicht Bestandteil des Folgecommits.

**NOT RUN:** automatische OCR, da lokal kein OCR-Werkzeug installiert ist. Es wird keine OCR-Erkennung behauptet. Die Bildprüfung verbindet direkte Sichtung, geprüfte statische Ausschnitte und reproduzierbare Datenfluss-/Rekonstruktionsprüfungen.

Die App, ihre Golden-Baselines und die bestehenden Frontend-/Backend-Tests wurden für diese Bildprüfung nicht verändert. Die elf Prüfungen verwenden vollständig synthetische Eingangsfixtures und benötigen keine privaten Screenshots. Sie sind separate lokal ausgeführte Datenschutzprüfungen; sie werden nicht als zusätzliche bereits bestandene GitHub-CI-Fälle ausgegeben. Pillow und die Schrift Arimo sind lokale Vorbereitungsvoraussetzungen, keine neuen App-Abhängigkeiten.

## Historische Git-Prüfung vor der separat genehmigten Historienbereinigung

Geprüfter PR-Head vor der Veröffentlichung: `23faceb58d0f15a8c29f02c4e8de507af26b651a`. PR #18 bleibt Draft; die Bildfreigabe ist keine vollständige UX-Abnahme.

- **PASS aktueller Dateibaum:** Die ursprüngliche private Datei `docs/ui-reference/evidence/reference-chatgpt.png` fehlt; die Ausschlussregel ist aktiv. Sämtliche alten/neuen lokalen Vergleiche sind ebenfalls ausgeschlossen. Während der Vorbereitung bis zur Freigabe wurde kein Bild hochgeladen. Der anschließende Veröffentlichungscommit nimmt ausschließlich die fünf oben genannten bereinigten PNG-Kopien auf.
- **FAIL, damalige Historie:** Commit `58d57b2` enthält die ursprüngliche private Datei als Blob `3d50917c0d895af92dceffcc8cda7c9c64819e5f`. Der SHA256-Abgleich bestätigt, dass es sich um das ursprüngliche Bild handelt. Seine spätere Entfernung in `dba475b` beseitigt diesen historischen Bestand nicht. Die frühere Aufnahme war ein Fehler.
- **Zusatzbefund:** Die bestehende Funktion `referenceChat()` in `frontend/tests/e2e/chat-fixtures.ts` und die bereits veröffentlichte Baseline `reference-reference-light.png` enthalten übernommene Referenztexte. Diese fünf neuen Bildversionen ersetzen diese Texte vollständig, bereinigen aber nicht rückwirkend die vorhandene Fixture/Baseline oder Git-Historie.

Eine vollständige Bereinigung des bestehenden Repository-Bestands benötigt einen eigenen Schritt für die Historie und die übernommenen Referenztexte. Die Veröffentlichung fügt einen regulären Folgecommit hinzu; sie schreibt keine Historie um und führt keinen Merge aus. Die Anforderung „Originale nicht in Git“ ist für neue Änderungen erfüllt, aber wegen des dokumentierten Altbestands noch nicht für die gesamte Historie.

## Verwendung und Freigabe

Die bereinigten Dateien sind **synthetisch bearbeitete Vergleichsansichten**, keine unveränderten Browseraufnahmen. Ihre neugeschriebenen Text-/Composer-Flächen dürfen nicht als Beleg für pixelgenaue Originaltypografie oder unverändertes Laufzeitverhalten benutzt werden. Unveränderte private Messungen bleiben getrennt und lokal.

Die Ausschnitt-Allowlist gilt nur für die fünf konkret geprüften Quellen. Andere Screenshots benötigen eine neue visuelle Prüfung der statischen Bereiche.

Lokale Reproduktion:

```sh
python3 docs/ui-reference/sanitize_comparison.py \
  docs/ui-reference/local-comparison/quarantine/previous/reference-layout-redacted.png \
  docs/ui-reference/local-comparison/quarantine/previous/noris-reference.png \
  docs/ui-reference/local-comparison/sanitized
python3 -m unittest discover -s docs/ui-reference/tests -p 'test_sanitize_comparison.py' -v
```

**Veröffentlichungsstatus: VOM AUFTRAGGEBER FREIGEGEBEN, fünf bereinigte Dateien in PR #18.** Die Freigabe vom 2026-10-09 ist an die oben dokumentierten SHA256-Werte gebunden. Eine Neugenerierung, andere Bildquellen oder weitere Dateien benötigen eine neue Prüfung und Freigabe; das Vorbereitungswerkzeug setzt neu erzeugte Kandidaten deshalb weiterhin auf `LOCAL_ONLY_AWAITING_USER_APPROVAL`.
