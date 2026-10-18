"""Compare synthetic captures and DOM geometry without private reference pixels."""
import json
from pathlib import Path
from PIL import Image, ImageChops, ImageEnhance

root = Path(__file__).resolve().parent
before = json.loads((root / 'before/geometry.json').read_text())
after = json.loads((root / 'after/geometry.json').read_text())
reference = json.loads((root / 'reference-geometry.json').read_text())
rows = []
for current in after:
    original = next(row for row in before if all(row[key] == current[key] for key in ['width', 'height', 'theme', 'state']))
    changes = {}
    for name, result in current['elements'].items():
        previous = original['elements'].get(name)
        if not result or not previous:
            changes[name] = {'before': previous, 'after': result}
            continue
        changes[name] = {
            'before': previous, 'after': result,
            'rectDelta': {key: result['rect'][key] - previous['rect'][key] for key in ['x', 'y', 'width', 'height']},
        }
    target_deltas = None
    if current['width'] == 1920 and current['state'] == 'open':
        target_deltas = {
            name: {key: current['elements'][element]['rect'][key] - target[key] for key in keys}
            for name, element, keys in [
                ('rail', 'rail', ['x', 'width']), ('sidebar', 'sidebar', ['x', 'width']),
                ('chat', 'timeline', ['x', 'width']), ('composer', 'composer', ['x', 'y', 'width', 'height']),
            ] for target in [reference['rectangles'][name]]
        }
    rows.append({**{key: current[key] for key in ['width', 'height', 'theme', 'state', 'viewport']}, 'changes': changes, 'deltaFromRasterEstimate': target_deltas})
    filename = f"{current['width']}-{current['theme']}-{current['state']}.png"
    if current['state'] == 'open':
        old = Image.open(root / 'before' / filename).convert('RGB')
        new = Image.open(root / 'after' / filename).convert('RGB')
        # These are changes to Noris, not a claimed pixel diff against ChatGPT.
        difference = ImageEnhance.Contrast(ImageChops.difference(old, new)).enhance(3)
        difference.save(root / f"diff-{current['width']}-{current['theme']}.png")
(root / 'geometry.json').write_text(json.dumps({'reference': reference, 'comparisons': rows}, indent=2) + '\n')
for source, destination in [('before/1920-light-open.png', 'before.png'), ('after/1920-light-open.png', 'after.png'), ('diff-1920-light.png', 'diff.png')]:
    (root / destination).write_bytes((root / source).read_bytes())
