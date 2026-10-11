"""Bounded parser output shared by the existing upload and PDF context paths."""

from pydantic import BaseModel, ConfigDict, Field

PDF_SECTION_CHARS = 2000


class PDFSection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    page: int = Field(ge=1, le=100)
    text: str = Field(min_length=1, max_length=PDF_SECTION_CHARS)


class ExtractedAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str | None = Field(default=None, max_length=32_000)
    sections: list[PDFSection] = Field(default_factory=list[PDFSection], max_length=600)
    page_count: int | None = Field(default=None, ge=1, le=100)

    @property
    def has_text(self) -> bool:
        return bool(self.text or self.sections)


class ExtractionError(ValueError):
    """Only a fixed, non-sensitive code crosses the parser process boundary."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
