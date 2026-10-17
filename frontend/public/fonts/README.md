# Measured, self-hosted UI fonts

Noris Sans packages Noto Sans 2.004; Noris Mono packages Liberation Mono 2.1.5.
Noris Symbols packages Arimo 1.33, the measured fallback for ↑ and ↓; Noto Sans
does not contain these glyphs. It follows Noris Sans in the font stack.
These are the faces Chromium actually used for the reference implementation on
the development host, measured with `CSS.getPlatformFontsForNode`, including
Noto Sans Medium (500) and SemiBold (600). `system-ui` alone selected different
installed fonts in other environments and is retained as a fallback.

WOFF2 files are generated from the installed source TTFs. Font names are changed
to Noris Sans / Noris Mono to respect reserved names after format conversion;
glyph outlines are not edited. Horizontal metrics, Unicode cmap and units per em
are checked against each source. Source versions and SHA256 hashes are recorded
in [manifest.json](manifest.json). All faces are licensed under SIL OFL 1.1;
original copyright notices and the full license are in [OFL.txt](OFL.txt).

No external font service, runtime Python package or model/API call is involved.
Normal 400/500/600 faces and the symbol fallback are preloaded; other weights/styles load when needed.
The existing composer autosizer waits for `document.fonts.ready`.

Regenerate using Python fonttools[woff] 4.61.1 and the matching source fonts:

```sh
python3 frontend/scripts/package-ui-fonts.py \
  --sans /usr/share/fonts/truetype/noto \
  --mono /usr/share/fonts/truetype/liberation \
  --symbols /usr/share/fonts/truetype/croscore \
  --ofl-notice /usr/share/doc/fonts-noto-core/copyright
```

Typography targets remain 16px/26px for messages, 16px/24px for the composer and
24/20/18px headings. The original ChatGPT font identity is not claimed.

Webfont shaping/rasterization can differ slightly from the host system-font path.
Baselines are reviewed and recaptured after embedding; font size, line height,
column width and screenshot tolerances are not changed for the new font path.
