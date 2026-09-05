from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Paragraph:
    ordinal: int
    text: str
    text_hash: str


@dataclass(frozen=True, slots=True)
class Document:
    id: str
    source_url: str
    content_hash: str
    paragraphs: tuple[Paragraph, ...]

