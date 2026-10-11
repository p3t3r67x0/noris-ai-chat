"""Disposable parser process. No provider credentials or external requests.

Linux deployment limits CPU/address space before loading either parser.
Only a server-generated storage path and fixed processing limits are accepted.
"""

import base64
import hashlib
import io
import json
import os
import resource
import sys
import warnings
from pathlib import Path

from noris_ai.llm.vision import IMAGE_MAX_BYTES, IMAGE_MAX_EDGE


def extract(
    path: Path, mime: str, text_limit: int, page_limit: int, pixel_limit: int
) -> str | None:
    if mime in ("text/plain", "text/markdown"):
        text = path.read_bytes().decode("utf-8-sig", errors="strict")
        if any(ord(c) < 32 and c not in "\t\n\r" for c in text):
            raise ValueError("Binary content")
        if len(text) > text_limit:
            raise ValueError("Text limit")
        return text if text.strip() else None
    if mime == "application/pdf":
        from pypdf import PdfReader, filters

        filters.ZLIB_MAX_OUTPUT_LENGTH = 8_388_608
        if not path.read_bytes().startswith(b"%PDF-"):
            raise ValueError("PDF signature")
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or len(reader.pages) > page_limit:
            raise ValueError("PDF limit")
        parts: list[str] = []
        length = 0
        for page in reader.pages:
            content = page.get_contents()
            if content is not None and len(content.get_data()) > 8_388_608:
                raise ValueError("PDF decompression limit")
            text = page.extract_text() or ""
            length += len(text) + 1
            if length > text_limit:
                raise ValueError("Text limit")
            parts.append(text)
        text = "\n".join(parts)
        return text if text.strip() else None
    if mime in ("image/png", "image/jpeg"):
        from PIL import Image

        Image.MAX_IMAGE_PIXELS = pixel_limit
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        expected = "PNG" if mime == "image/png" else "JPEG"
        with Image.open(path, formats=[expected]) as image:
            if image.format != expected or image.width * image.height > pixel_limit:
                raise ValueError("Image limit")
            if max(image.size) > 8192 or getattr(image, "n_frames", 1) != 1:
                raise ValueError("Image dimensions")
            image.verify()
        with Image.open(path, formats=[expected]) as image:
            image.load()
        return None
    raise ValueError("Unsupported format")


def prepare_image(path: Path, mime: str, pixel_limit: int, size: int, sha256: str) -> str:
    """Revalidate original bytes, then produce a bounded metadata-free image."""
    from PIL import Image, ImageOps

    if mime not in ("image/png", "image/jpeg") or not 0 < size <= 20_971_520:
        raise ValueError("Invalid image")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        data = source.read(size + 1)
    if len(data) != size or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError("Storage integrity")
    Image.MAX_IMAGE_PIXELS = pixel_limit
    warnings.simplefilter("error", Image.DecompressionBombWarning)
    expected = "PNG" if mime == "image/png" else "JPEG"
    with Image.open(io.BytesIO(data), formats=[expected]) as original:
        if original.width * original.height > pixel_limit or max(original.size) > 8192:
            raise ValueError("Image limit")
        if getattr(original, "n_frames", 1) != 1:
            raise ValueError("Animated images are unsupported")
        original.load()
        oriented = ImageOps.exif_transpose(original)
        oriented.thumbnail((IMAGE_MAX_EDGE, IMAGE_MAX_EDGE), Image.Resampling.LANCZOS)
        # A fresh canvas strips EXIF/XMP/ICC and turns transparency into white.
        rgba = oriented.convert("RGBA")
        clean = Image.new("RGB", rgba.size, "white")
        clean.paste(rgba, mask=rgba.getchannel("A"))
        output = io.BytesIO()
        clean.save(output, format="JPEG", quality=80)
    encoded = output.getvalue()
    if len(encoded) > IMAGE_MAX_BYTES:
        raise ValueError("Normalized image limit")
    return "data:image/jpeg;base64," + base64.b64encode(encoded).decode("ascii")


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (268_435_456, 268_435_456))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    try:
        if len(sys.argv) > 6 and sys.argv[6] == "vision":
            image = prepare_image(
                Path(sys.argv[1]), sys.argv[2], int(sys.argv[5]), int(sys.argv[7]), sys.argv[8]
            )
            print(json.dumps({"data_url": image}, ensure_ascii=True))
        else:
            text = extract(Path(sys.argv[1]), sys.argv[2], *map(int, sys.argv[3:6]))
            print(json.dumps({"text": text}, ensure_ascii=True))
    except Exception:
        # Do not print parser exceptions, filenames, embedded text or metadata.
        sys.exit(1)


if __name__ == "__main__":
    main()
