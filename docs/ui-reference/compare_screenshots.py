"""Compare equally sized screenshots; source files remain unchanged. Requires Pillow."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("noris", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--redact-reference-sidebar", action="store_true",
        help="Mask only private title/account text in derived views of the supplied 1920x975 reference.",
    )
    args = parser.parse_args()
    reference = Image.open(args.reference).convert("RGB")
    noris = Image.open(args.noris).convert("RGB")
    if reference.size != noris.size:
        parser.error(f"Different dimensions: {reference.size} versus {noris.size}")
    masks = []
    if args.redact_reference_sidebar:
        if reference.size != (1920, 975):
            parser.error("Reference text redaction requires the measured 1920x975 source.")
        draw = ImageDraw.Draw(reference)
        title_rows = [(326, 339), (374, 387), (422, 435), (471, 483),
                      (519, 532), (567, 580), (615, 628), (664, 676),
                      (713, 725), (760, 773), (809, 821), (856, 869),
                      (906, 918), (954, 966)]
        for index, (top, bottom) in enumerate(title_rows):
            rectangle = [86, top - 5, 395, bottom + 5]
            color = "#efefef" if index == 0 else "#fcfcfc"
            draw.rectangle(rectangle, fill=color)
            masks.append({"rectangle": rectangle, "purpose": "private conversation title"})
        rectangle = [23, 935, 45, 949]
        draw.rectangle(rectangle, fill=reference.getpixel((25, 932)))
        masks.append({"rectangle": rectangle, "purpose": "account initials"})
    args.output.mkdir(parents=True, exist_ok=True)
    width, height = reference.size
    if masks:
        reference.save(args.output / "reference-layout-redacted.png")
    noris.save(args.output / "noris-reference.png")
    comparison = Image.new("RGB", (width * 2, height))
    comparison.paste(reference, (0, 0))
    comparison.paste(noris, (width, 0))
    comparison.save(args.output / "side-by-side.png")
    Image.blend(reference, noris, 0.5).save(args.output / "overlay.png")
    difference = ImageChops.difference(reference, noris)
    difference.save(args.output / "difference.png")
    metadata = {
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "noris_sha256": hashlib.sha256(args.noris.read_bytes()).hexdigest(),
        "dimensions": [width, height],
        "source_files_modified": False,
        "reference_content_masks": masks,
        "mean_absolute_rgb_difference": ImageStat.Stat(difference).mean,
        "interpretation": "Diagnostic only; private text masks are listed explicitly. No resizing or acceptance threshold.",
    }
    (args.output / "comparison.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
