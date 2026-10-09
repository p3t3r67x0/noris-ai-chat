"""Measure the supplied original without changing it; requires Pillow locally."""

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    image = Image.open(args.reference).convert("RGB")
    if image.size != (1920, 975):
        parser.error("Sample rectangles refer to the supplied 1920x975 original.")
    rectangles = {
        "rail": (0, 0, 68, 975),
        "sidebar": (68, 0, 443, 975),
        "workspace": (445, 65, 1919, 875),
        "composer": (690, 890, 1600, 930),
        "active_conversation": (76, 310, 436, 355),
    }
    samples = {}
    for name, rectangle in rectangles.items():
        crop = image.crop(rectangle)
        colors = crop.getcolors(crop.width * crop.height)
        count, color = max(colors, key=lambda entry: entry[0])
        samples[name] = {"rectangle": rectangle, "dominant_rgb": color, "pixel_count": count}
    heading = []
    for top, bottom in [(152, 199), (199, 238)]:
        points = [(x, y) for y in range(top, bottom) for x in range(680, 1684)
                  if max(image.getpixel((x, y))) < 90]
        heading.append({"sample_rows": [top, bottom], "dark_pixel_bounds":
                        [min(x for x, _ in points), min(y for _, y in points),
                         max(x for x, _ in points), max(y for _, y in points)]})
    result = {
        "dimensions": image.size,
        "sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "method": "Original image pixels; dominant RGB in listed rectangles. Font CSS size/DPR remain estimates.",
        "samples": samples,
        "heading_glyph_bounds": heading,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
