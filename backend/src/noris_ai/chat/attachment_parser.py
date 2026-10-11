"""Disposable parser process. No provider credentials or external requests.

Linux deployment limits CPU/address space before loading either parser.
Only a server-generated storage path and fixed processing limits are accepted.
"""

import json
import resource
import sys
import warnings
from pathlib import Path


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


def main() -> None:
    resource.setrlimit(resource.RLIMIT_AS, (268_435_456, 268_435_456))
    resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    try:
        text = extract(Path(sys.argv[1]), sys.argv[2], *map(int, sys.argv[3:6]))
        print(json.dumps({"text": text}, ensure_ascii=True))
    except Exception:
        # Do not print parser exceptions, filenames, embedded text or metadata.
        sys.exit(1)


if __name__ == "__main__":
    main()
