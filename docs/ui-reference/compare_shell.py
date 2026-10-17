"""Compare the committed synthetic Noris captures, never the private reference.

Usage: python3 docs/ui-reference/compare_shell.py
Requires Pillow. This reports change magnitude, not reference pixel equality.
"""

import json
from pathlib import Path
from shutil import copyfile

from PIL import Image, ImageChops


def main() -> None:
    root = Path(__file__).parent / "october-2026"
    comparisons = []
    for before in sorted(root.glob("before-*.png")):
        after = root / before.name.replace("before-", "after-", 1)
        original = Image.open(before).convert("RGB")
        updated = Image.open(after).convert("RGB")
        if original.size != updated.size:
            raise ValueError(f"Different viewport sizes: {before.name}")
        difference = ImageChops.difference(original, updated)
        destination = root / before.name.replace("before-", "diff-", 1)
        difference.save(destination)
        changed = sum(pixel != (0, 0, 0) for pixel in difference.get_flattened_data())
        comparisons.append({
            "before": before.name, "after": after.name, "diff": destination.name,
            "width": original.width, "height": original.height,
            "changedPixels": changed,
            "changedRatio": changed / (original.width * original.height),
            "meaning": "Synthetic Noris before/after change, not a reference fidelity score",
        })
    for prefix in ("before", "after", "diff"):
        copyfile(root / f"{prefix}-1701-light.png", root / f"{prefix}.png")
    (root / "pixel-comparison.json").write_text(
        json.dumps(comparisons, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
