"""Compare the matching synthetic pending captures; never read private chats."""
from pathlib import Path
from PIL import Image, ImageChops

root = Path(__file__).resolve().parent
before = Image.open(root / "loading-before.png").convert("RGB")
after = Image.open(root / "loading-after.png").convert("RGB")
if before.size != after.size:
    raise ValueError(f"Mismatched raster sizes: {before.size} vs {after.size}")
ImageChops.difference(before, after).save(root / "loading-diff.png")
