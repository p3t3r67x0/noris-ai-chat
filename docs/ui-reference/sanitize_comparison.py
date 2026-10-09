"""Prepare local synthetic comparison views. Never uploads or modifies the sources.

Only explicitly reviewed static UI crops survive. History, account, conversation,
composer and status areas are drawn on a new opaque canvas with fixed demo data.
Pillow and the locally installed Arimo font are preparation tools, not app deps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from PIL import Image, ImageChops, ImageDraw, ImageFont

Kind = Literal["reference", "noris"]
Rectangle = tuple[int, int, int, int]
SIZE = (1920, 975)
ROOT = Path(__file__).resolve().parents[2]
LOCAL_ROOT = ROOT / "docs/ui-reference/local-comparison"
OUTPUT_NAMES = (
    "reference-layout-redacted.png",
    "noris-reference.png",
    "side-by-side.png",
    "overlay.png",
    "difference.png",
)

# These crops were individually inspected: generic navigation icons, product
# names/new-chat controls and static share/copy/edit controls. No message, draft,
# selected model, account, date, history row or project indicator is copied.
STATIC_CROPS: dict[Kind, tuple[Rectangle, ...]] = {
    "reference": ((0, 0, 68, 900), (68, 0, 444, 120), (1694, 0, 1920, 68)),
    "noris": (
        (0, 0, 68, 900),
        (68, 0, 444, 120),
        (460, 12, 494, 56),
        (1560, 80, 1683, 125),
    ),
}

# Freely invented; not paraphrases, hashes, aliases or length-preserving
# substitutions of private conversation data.
DEMO_HEADING = (
    "Ein fiktiver Tagesplan mit drei einfachen Schritten",
    "für eine neutrale Demonstration",
)
DEMO_PARAGRAPHS = (
    (
        251,
        (
            "Diese Darstellung verwendet ausschließlich erfundene Beispieldaten. Sie dient",
            "zur Prüfung von Lesebreite, Abständen und Bedienelementen.",
        ),
    ),
    (
        341,
        (
            "Der Plan besteht aus drei neutralen Schritten: einen Überblick erstellen,",
            "eine kleine Aufgabe auswählen und das Ergebnis kurz festhalten.",
            "Alle Inhalte gehören zu einer synthetischen Demonstration.",
        ),
    ),
    (
        497,
        (
            "1. Überblick: Notiere drei frei gewählte Tätigkeiten für den Tag.",
            "2. Aufgabe: Wähle eine Tätigkeit und plane einen kurzen Zeitraum.",
            "3. Rückblick: Halte fest, welche nächsten Schritte sinnvoll erscheinen.",
        ),
    ),
    (
        686,
        (
            "Die Bezeichnungen Beispiel 01 bis Beispiel 14 sind künstlich erzeugt.",
            "Es gibt keine echten Personen, Organisationen, Nachrichten oder Konten.",
            "Diese Bilddatei enthält keine privaten Gesprächsinhalte.",
        ),
    ),
)


@lru_cache(maxsize=16)
def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = "Arimo-Bold.ttf" if bold else "Arimo-Regular.ttf"
    return ImageFont.truetype(f"/usr/share/fonts/truetype/croscore/{name}", size)


def text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    value: str,
    size: int = 22,
    *,
    bold: bool = False,
    color: str = "#0d0d0d",
) -> None:
    draw.text((x, y), value, font=font(size, bold), fill=color)


def draw_sidebar(image: Image.Image, kind: Kind) -> None:
    bottom = 975 if kind == "reference" else 905
    history = Image.new("RGB", (376, bottom - 120), "#fcfcfc")
    draw = ImageDraw.Draw(history)
    group_y = 274 if kind == "reference" else 169
    text(draw, 21, group_y - 120, "Beispiele", 20, color="#676767")
    row_y = 309 if kind == "reference" else 199
    step = 48 if kind == "reference" else 53
    height = 47 if kind == "reference" else 51
    draw.rounded_rectangle(
        (8, row_y - 120, 368, row_y - 120 + height), radius=11, fill="#efefef"
    )
    for index in range(14):
        y = row_y + index * step
        text(draw, 21, y - 120 + 12, f"Beispiel {index + 1:02d}", 20)
        for dx in (-5, 0, 5):
            draw.ellipse(
                (337 + dx, y - 120 + 22, 339 + dx, y - 120 + 24), fill="#676767"
            )
    image.paste(history, (68, 120))
    draw = ImageDraw.Draw(image)
    draw.line((443, 0, 443, 974), fill="#e5e5e5")
    # A new neutral demo avatar replaces the whole original account surface.
    draw.ellipse((18, 926, 50, 958), fill="#efefef")
    text(draw, 27, 933, "D", 14, color="#676767")
    if kind == "noris":
        draw.rounded_rectangle(
            (80, 918, 180, 963), radius=10, fill="#fcfcfc", outline="#d6d6d6"
        )
        text(draw, 95, 929, "Demo", 16)


def draw_conversation(image: Image.Image, kind: Kind) -> None:
    draw = ImageDraw.Draw(image)
    top, bottom = (-66, 61) if kind == "reference" else (14, 75)
    draw.rounded_rectangle((982, top, 1682, bottom), radius=28, fill="#000000")
    if kind == "reference":
        text(
            draw,
            1004,
            -16,
            "Zeige einen einfachen Tagesplan mit drei Schritten.",
            color="#ffffff",
        )
        text(
            draw,
            1004,
            18,
            "Verwende ausschließlich frei erfundene Angaben.",
            color="#ffffff",
        )
    else:
        # Fixed flow header occludes the same synthetic bubble, as in the real UI.
        draw.rectangle((982, 0, 1682, 67), fill="#fcfcfc")
        text(draw, 522, 22, "Demo-Modell", 16, color="#676767")
        text(draw, 1808, 25, "Demo", 12, color="#676767")
    text(draw, 1704, 92, "Synthetische Vergleichsansicht", 12, color="#676767")
    if kind == "reference":
        text(draw, 682, 120, "Synthetisches Beispiel", 20, color="#676767")
    for index, line in enumerate(DEMO_HEADING):
        text(draw, 682, 152 + index * 42, line, 32, bold=True)
    for y, lines in DEMO_PARAGRAPHS:
        for index, line in enumerate(lines):
            text(draw, 682, y + index * 34, line)
    text(draw, 682, 844, "1. Drei neutrale Schritte", 26, bold=True)


def draw_composer(image: Image.Image, kind: Kind) -> None:
    draw = ImageDraw.Draw(image)
    x = 680 if kind == "reference" else 682
    right = 1683 if kind == "reference" else 1682
    draw.rounded_rectangle((x - 2, 875, right + 2, 950), radius=37, fill="#f4f4f4")
    if kind == "noris":
        draw.rounded_rectangle(
            (x - 2, 874, right + 2, 948),
            radius=37,
            fill="#fcfcfc",
            outline="#0d0d0d",
            width=2,
        )
    draw.rounded_rectangle(
        (x, 876, right, 946), radius=35, fill="#ffffff", outline="#e5e5e5", width=1
    )
    plus_x = 714 if kind == "reference" else 709
    draw.line((plus_x - 9, 911, plus_x + 9, 911), fill="#0d0d0d", width=2)
    draw.line((plus_x, 902, plus_x, 920), fill="#0d0d0d", width=2)
    text(draw, 750, 896, "Demo-Nachricht eingeben", color="#676767")
    text(draw, 1430, 897, "Demo-Modell", 20, color="#676767")
    draw.line((1567, 905, 1573, 911, 1579, 905), fill="#676767", width=2)
    if kind == "reference":
        draw.rounded_rectangle(
            (1585, 900, 1597, 916), radius=6, outline="#676767", width=2
        )
        draw.line((1591, 916, 1591, 922), fill="#676767", width=2)
    draw.ellipse((1625, 887, 1673, 935), fill="#000000")
    if kind == "reference":
        draw.rounded_rectangle((1642, 904, 1656, 918), radius=2, fill="#ffffff")
    else:
        draw.rounded_rectangle(
            (1642, 904, 1656, 918), radius=2, outline="#ffffff", width=2
        )
    if kind == "noris":
        text(
            draw,
            1052,
            955,
            "Synthetische Demo ohne echte Kontodaten.",
            11,
            color="#676767",
        )


def sanitize_image(source: Image.Image, kind: Kind) -> Image.Image:
    if source.size != SIZE:
        raise ValueError("Only the reviewed 1920 x 975 sources are supported")
    if kind not in STATIC_CROPS:
        raise ValueError("Unknown source kind")
    # A new opaque image has no original metadata or hidden alpha layers.
    image = Image.new("RGB", SIZE, "#fcfcfc")
    ImageDraw.Draw(image).rectangle((0, 0, 67, 974), fill="#f9f9f9")
    for rectangle in STATIC_CROPS[kind]:
        image.paste(source.crop(rectangle).convert("RGB"), rectangle[:2])
    draw_sidebar(image, kind)
    draw_conversation(image, kind)
    draw_composer(image, kind)
    return image


def prepare_views(reference: Image.Image, noris: Image.Image) -> dict[str, Image.Image]:
    safe_reference = sanitize_image(reference, "reference")
    safe_noris = sanitize_image(noris, "noris")
    side_by_side = Image.new("RGB", (3840, 975))
    side_by_side.paste(safe_reference, (0, 0))
    side_by_side.paste(safe_noris, (1920, 0))
    return dict(
        zip(
            OUTPUT_NAMES,
            (
                safe_reference,
                safe_noris,
                side_by_side,
                Image.blend(safe_reference, safe_noris, 0.5),
                ImageChops.difference(safe_reference, safe_noris),
            ),
        )
    )


def validate_output_directory(output: Path) -> None:
    if not output.resolve().is_relative_to(LOCAL_ROOT.resolve()):
        raise ValueError(
            "Output must stay inside the Git-excluded local-comparison directory"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("noris", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate_output_directory(args.output)
    output_paths = [(args.output / name).resolve() for name in OUTPUT_NAMES]
    if any(source.resolve() in output_paths for source in (args.reference, args.noris)):
        parser.error("Output must not overwrite an input")
    args.output.mkdir(parents=True, exist_ok=True)
    with Image.open(args.reference) as reference, Image.open(args.noris) as noris:
        views = prepare_views(reference, noris)
    files = []
    for name, image in views.items():
        output = args.output / name
        image.save(output, format="PNG", compress_level=9)
        files.append(
            {
                "file": name,
                "dimensions": image.size,
                "mode": image.mode,
                "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "status": "LOCAL_ONLY_AWAITING_USER_APPROVAL",
        "kind": "synthetic anonymized comparison derivatives, not unmodified browser captures",
        "source_pixels": "only the individually reviewed static UI crops listed below",
        "static_crops": STATIC_CROPS,
        "removed": [
            "entire conversation",
            "entire history and project area",
            "account surface",
            "composer and selected model",
            "status/time/source/link information",
        ],
        "derived_views": "side-by-side, overlay and difference use only the two sanitized sources",
        "files": files,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )
    print(json.dumps({"status": manifest["status"], "images": len(files)}))


if __name__ == "__main__":
    main()
