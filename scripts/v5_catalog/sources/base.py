"""What every source hands to the parsers: lines of text with a locator."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Line:
    text: str
    book: str | None = None  # book_id, for PDF lines
    page: int | None = None  # printed page
    page_pdf: int | None = None
    url: str | None = None  # for online lines
    revision: int | None = None
    height: float | None = None  # PDF line height in points (headings differ from body text)
    x: float | None = None

    def locator(self) -> dict:
        if self.url:
            return {"url": self.url, "revision": self.revision}
        return {"book": self.book, "page": self.page, "page_pdf": self.page_pdf}
