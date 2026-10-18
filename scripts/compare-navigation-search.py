"""Compare synthetic before/after captures at identical CSS viewports and DPR."""
from pathlib import Path
import json
import shutil
import sys

from PIL import Image, ImageChops, ImageEnhance

ROOT = Path(__file__).resolve().parents[1] / 'docs'
for folder, sample in [('navigation-icons', '1440-light-open.png'), ('chat-search', '1440-light-5.png')]:
    if sys.argv[1:] and folder not in sys.argv[1:]:
        continue
    directory = ROOT / folder
    evidence = directory / 'evidence'
    if not (evidence / 'before').is_dir() or not (evidence / 'after').is_dir():
        continue
    destination = evidence / 'diff'
    destination.mkdir(exist_ok=True)
    comparisons = []
    for before in sorted((evidence / 'before').glob('*.png')):
        after = evidence / 'after' / before.name
        if not after.exists():
            continue
        original, current = Image.open(before).convert('RGB'), Image.open(after).convert('RGB')
        if original.size != current.size:
            raise ValueError(f'Unequal raster dimensions: {before.name}')
        difference = ImageChops.difference(original, current)
        ImageEnhance.Contrast(difference).enhance(3).save(destination / before.name)
        changed = sum(pixel != (0, 0, 0) for pixel in zip(*[iter(difference.tobytes())] * 3))
        comparisons.append({'scene': before.name, 'size': original.size, 'changedPixels': changed, 'changedFraction': changed / (original.width * original.height)})
    for name, source in [('before.png', evidence / 'before' / sample), ('after.png', evidence / 'after' / sample), ('diff.png', destination / sample)]:
        shutil.copyfile(source, directory / name)
    (directory / 'pixel-comparison.json').write_text(json.dumps(comparisons, indent=2) + '\n')
