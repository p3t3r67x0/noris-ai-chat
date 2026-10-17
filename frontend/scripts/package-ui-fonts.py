"""Package the measured UI fonts; no glyph or metric changes.

Maintenance tool: Python fonttools[woff] 4.61.1. The shipped app needs no
Python dependency or external font service. Source paths are explicit arguments.
"""
import argparse
import hashlib
import json
from pathlib import Path

from fontTools.ttLib import TTFont

parser = argparse.ArgumentParser()
parser.add_argument("--sans", type=Path, required=True)
parser.add_argument("--mono", type=Path, required=True)
parser.add_argument("--ofl-notice", type=Path, required=True)
args = parser.parse_args()
frontend = Path(__file__).resolve().parents[1]
output = frontend / "public/fonts"
output.mkdir(parents=True, exist_ok=True)
faces = []
rules = []
copyrights = set()
for family, directory, source_prefix, alias in [
    ("sans", args.sans, "NotoSans", "Noris Sans"),
    ("mono", args.mono, "LiberationMono", "Noris Mono"),
]:
    weights = [(400, "Regular"), (500, "Medium"), (600, "SemiBold"), (700, "Bold")] if family == "sans" else [(400, "Regular"), (700, "Bold")]
    for weight, cut in weights:
        for style in ["normal", "italic"]:
            source_cut = cut if style == "normal" else "Italic" if cut == "Regular" else f"{cut}Italic"
            source = directory / f"{source_prefix}-{source_cut}.ttf"
            font = TTFont(source, recalcTimestamp=False, recalcBBoxes=False)
            original = {"metrics": dict(font["hmtx"].metrics), "cmap": font.getBestCmap(), "unitsPerEm": font["head"].unitsPerEm}
            version = font["name"].getDebugName(5)
            copyrights.add(font["name"].getDebugName(0))
            # Respect reserved source font names after format conversion. Preserve
            # copyright/license records; only family/unique/PostScript names change.
            for name in font["name"].names:
                if name.nameID in {1, 3, 4, 6, 16, 17, 18, 21, 22}:
                    value = name.toUnicode().replace("Noto Sans", alias).replace("NotoSans", "NorisSans").replace("Liberation Mono", alias).replace("LiberationMono", "NorisMono")
                    name.string = value.encode(name.getEncoding())
            slug = source_cut.lower().replace("italic", "-italic").strip("-")
            destination = output / f"noris-{family}-{slug}.woff2"
            font.flavor = "woff2"
            font.save(destination)
            check = TTFont(destination)
            assert check["hmtx"].metrics == original["metrics"]
            assert check.getBestCmap() == original["cmap"]
            assert check["head"].unitsPerEm == original["unitsPerEm"]
            faces.append({"family": alias, "weight": weight, "style": style, "asset": destination.name,
                          "source": source.name, "sourceVersion": version,
                          "sourceSHA256": hashlib.sha256(source.read_bytes()).hexdigest(),
                          "assetSHA256": hashlib.sha256(destination.read_bytes()).hexdigest(),
                          "glyphCount": len(check.getGlyphOrder()), "metricsVerified": True})
            rules.append(f'@font-face {{\n  font-family: "{alias}";\n  font-style: {style};\n  font-weight: {weight};\n  font-display: swap;\n  src: url("/fonts/{destination.name}") format("woff2");\n}}\n')
            font.close()
            check.close()

notice = args.ofl_notice.read_text()
marker = "License: OFL-1.1\n"
start = notice.rindex(marker) + len(marker)
end = notice.find("\nLicense:", start)
text = notice[start:end if end >= 0 else None]
text = "\n".join("" if line.strip() == "." else line.removeprefix(" ") for line in text.splitlines())
credits = "\n\n".join(sorted(copyrights))
(output / "OFL.txt").write_text(credits + "\n\nOriginal Liberation fonts have Reserved Font Name Liberation.\nThe packaged fonts use the names Noris Sans / Noris Mono.\nGlyph outlines are not edited; horizontal metrics and cmap are verified.\n\n" + "SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007\n\n" + text + "\n")
(output / "manifest.json").write_text(json.dumps({"format": "WOFF2", "packager": "fonttools 4.61.1", "fonts": faces}, indent=2) + "\n")
(frontend / "app/assets/css/fonts.css").write_text("/* Self-hosted measured fonts; licenses and source hashes: /fonts/. */\n" + "\n".join(rules))
print(f"Packaged {len(faces)} faces; {sum((output / face['asset']).stat().st_size for face in faces):,} WOFF2 bytes.")
