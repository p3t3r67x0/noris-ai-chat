"""Compare unchanged, equally sized screenshots; requires Pillow locally."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("noris", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    reference = Image.open(args.reference).convert("RGB")
    noris = Image.open(args.noris).convert("RGB")
    if reference.size != noris.size:
        parser.error(f"Different dimensions: {reference.size} versus {noris.size}")
    args.output.mkdir(parents=True, exist_ok=True)
    width, height = reference.size
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
        "mean_absolute_rgb_difference": ImageStat.Stat(difference).mean,
        "interpretation": "Diagnostic only; no content masks, resizing or acceptance threshold.",
    }
    (args.output / "comparison.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata))


if __name__ == "__main__":
    main()
