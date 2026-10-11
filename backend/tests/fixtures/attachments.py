"""Generated documents only. Never load personal upload/reference files."""

from io import BytesIO

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def synthetic_png(width: int = 16, height: int = 16) -> bytes:
    output = BytesIO()
    Image.new("RGB", (width, height), "#517394").save(output, format="PNG")
    return output.getvalue()


def synthetic_pdf(
    text: str = "Synthetic attachment text",
    pages: int = 1,
    *,
    page_texts: list[str] | None = None,
    encrypted: bool = False,
    compressed: bool = False,
    size_bytes: int | None = None,
) -> bytes:
    writer = PdfWriter()
    writer.pdf_header = "%PDF-1.5"
    texts = page_texts if page_texts is not None else [text] * pages
    for text in texts:
        page = writer.add_blank_page(width=200, height=200)
        if text:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            page[NameObject("/Resources")] = DictionaryObject(
                {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
            )
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode("ascii"))
            page[NameObject("/Contents")] = stream.flate_encode() if compressed else stream
    if encrypted:
        writer.encrypt("fixture-password")
    padding = 0
    for _ in range(4):
        writer.add_metadata({"/FixturePadding": "x" * padding})
        output = BytesIO()
        writer.write(output)
        data = output.getvalue()
        if size_bytes is None or len(data) == size_bytes:
            return data
        padding += size_bytes - len(data)
        if padding < 0:
            raise ValueError("Fixture exceeds requested size")
    raise ValueError("Fixture padding did not converge")


def large_pdf_texts() -> list[str]:
    result: list[str] = []
    for page in range(1, 30):
        prefix = (
            "Anfangsklausel Einleitung. "
            if page == 1
            else "Schlussklausel Zielbetrag 98765 Euro. "
            if page == 29
            else f"Allgemeiner Abschnitt {page}. "
        )
        length = 1509 if page == 29 else 1493
        result.append((prefix + "synthetic filler " * 100)[:length])
    return result


def large_pdf() -> bytes:
    """Reproduce the reported PDF dimensions using entirely synthetic content."""
    return synthetic_pdf(page_texts=large_pdf_texts(), size_bytes=995_537)
