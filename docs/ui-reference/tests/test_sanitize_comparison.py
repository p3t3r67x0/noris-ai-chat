"""Local privacy checks; these tests do not publish any files."""

from __future__ import annotations

import importlib.util
import io
import struct
import subprocess
import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, PngImagePlugin

SCRIPT = Path(__file__).resolve().parents[1] / "sanitize_comparison.py"
spec = importlib.util.spec_from_file_location("sanitize_comparison", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def encoded(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=9)
    return buffer.getvalue()


class PrivacyChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        # Self-contained inputs: no private screenshot is required in a checkout.
        inputs = []
        for kind in ("reference", "noris"):
            source = Image.new("RGB", module.SIZE, "#fff4e5")
            draw = ImageDraw.Draw(source)
            for index, rectangle in enumerate(module.STATIC_CROPS[kind]):
                x0, y0, x1, y1 = rectangle
                draw.rectangle(
                    (x0, y0, x1 - 1, y1 - 1), fill=(220 + index * 5, 230, 240)
                )
                draw.text((x0 + 12, y0 + 12), "SYNTHETIC_UI", fill="#111111")
            draw.text((800, 320), "PRIVATE_INPUT_CANARY", fill="#ff0000")
            inputs.append(source)
        cls.reference, cls.noris = inputs
        cls.views = module.prepare_views(cls.reference, cls.noris)

    def test_any_change_outside_reviewed_static_crops_cannot_reach_output(self) -> None:
        for kind, source in (("reference", self.reference), ("noris", self.noris)):
            with self.subTest(kind=kind):
                alternate = Image.new("RGB", source.size, "#f017a9")
                for rectangle in module.STATIC_CROPS[kind]:
                    alternate.paste(source.crop(rectangle), rectangle[:2])
                self.assertEqual(
                    encoded(module.sanitize_image(source, kind)),
                    encoded(module.sanitize_image(alternate, kind)),
                )

    def test_sensitive_zone_canaries_do_not_change_the_clean_views(self) -> None:
        for kind, source in (("reference", self.reference), ("noris", self.noris)):
            with self.subTest(kind=kind):
                alternate = source.copy()
                draw = ImageDraw.Draw(alternate)
                # Invented markers in content, history, avatar, model and draft.
                for x, y in (
                    (1000, 2),
                    (90, 350),
                    (20, 940),
                    (690, 260),
                    (760, 910),
                    (1440, 902),
                    (522, 23),
                ):
                    draw.text((x, y), "PRIVATE_CANARY", fill="#ff0000")
                self.assertEqual(
                    encoded(module.sanitize_image(source, kind)),
                    encoded(module.sanitize_image(alternate, kind)),
                )

    def test_reviewed_static_ui_is_retained_as_a_positive_control(self) -> None:
        alternate = self.reference.copy()
        ImageDraw.Draw(alternate).rectangle((12, 12, 50, 50), fill="#ff0000")
        self.assertNotEqual(
            encoded(module.sanitize_image(self.reference, "reference")),
            encoded(module.sanitize_image(alternate, "reference")),
        )

    def test_private_changes_cannot_reach_any_of_the_five_derived_files(self) -> None:
        changed = []
        for kind, source in (("reference", self.reference), ("noris", self.noris)):
            alternate = Image.new("RGB", source.size, "#0000ff")
            for rectangle in module.STATIC_CROPS[kind]:
                alternate.paste(source.crop(rectangle), rectangle[:2])
            changed.append(alternate)
        alternate_views = module.prepare_views(*changed)
        for name in module.OUTPUT_NAMES:
            with self.subTest(file=name):
                self.assertEqual(
                    encoded(alternate_views[name]), encoded(self.views[name])
                )

    def test_original_png_metadata_is_discarded(self) -> None:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Comment", "PRIVATE_METADATA_CANARY")
        buffer = io.BytesIO()
        self.reference.save(buffer, format="PNG", pnginfo=metadata)
        buffer.seek(0)
        source = Image.open(buffer)
        output = encoded(module.sanitize_image(source, "reference"))
        self.assertNotIn(b"PRIVATE_METADATA_CANARY", output)
        self.assertEqual(output, encoded(self.views["reference-layout-redacted.png"]))

    def test_all_five_pngs_are_opaque_and_have_no_metadata_chunks(self) -> None:
        self.assertEqual(tuple(self.views), module.OUTPUT_NAMES)
        for name, image in self.views.items():
            with self.subTest(file=name):
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.info, {})
                data = encoded(image)
                offset = 8
                types = []
                while offset < len(data):
                    length = struct.unpack(">I", data[offset : offset + 4])[0]
                    types.append(data[offset + 4 : offset + 8])
                    offset += 12 + length
                self.assertEqual(offset, len(data))
                self.assertEqual(set(types), {b"IHDR", b"IDAT", b"IEND"})
                self.assertEqual(types[-1], b"IEND")

    def test_three_derived_views_use_only_sanitized_sources(self) -> None:
        reference = self.views["reference-layout-redacted.png"]
        noris = self.views["noris-reference.png"]
        side = self.views["side-by-side.png"]
        self.assertEqual(side.crop((0, 0, 1920, 975)).tobytes(), reference.tobytes())
        self.assertEqual(side.crop((1920, 0, 3840, 975)).tobytes(), noris.tobytes())
        self.assertEqual(
            self.views["overlay.png"].tobytes(),
            Image.blend(reference, noris, 0.5).tobytes(),
        )
        self.assertEqual(
            self.views["difference.png"].tobytes(),
            ImageChops.difference(reference, noris).tobytes(),
        )

    def test_overlay_inverse_only_reconstructs_the_sanitized_reference(self) -> None:
        reference = self.views["reference-layout-redacted.png"].tobytes()
        noris = self.views["noris-reference.png"].tobytes()
        overlay = self.views["overlay.png"].tobytes()
        maximum_error = max(
            abs(max(0, min(255, 2 * v - n)) - r)
            for r, n, v in zip(reference, noris, overlay)
        )
        self.assertLessEqual(maximum_error, 1)

    def test_export_outside_the_local_excluded_directory_is_rejected(self) -> None:
        module.validate_output_directory(module.LOCAL_ROOT / "sanitized")
        with self.assertRaises(ValueError):
            module.validate_output_directory(module.ROOT / "docs/ui-reference/evidence")

    def test_unreviewed_dimensions_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            module.sanitize_image(Image.new("RGB", (390, 844)), "reference")

    def test_old_partial_masking_tool_refuses_a_git_visible_export(self) -> None:
        # The guard must reject the output before even reading the inputs.
        source = module.LOCAL_ROOT / "nonexistent-synthetic-inputs"
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT.parent / "compare_screenshots.py"),
                str(source / "reference-layout-redacted.png"),
                str(source / "noris-reference.png"),
                str(module.ROOT / "docs/ui-reference/evidence"),
                "--redact-reference-sidebar",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("Private comparisons must stay", result.stderr)


if __name__ == "__main__":
    unittest.main()
