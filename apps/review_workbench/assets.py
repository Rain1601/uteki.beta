"""Read local presentation assets; embedded output preserves existing page behavior."""
from pathlib import Path

_STATIC = Path(__file__).with_name("static")


def asset_text(name: str) -> str:
    """Resolve a fixed asset filename, never an arbitrary filesystem path."""
    path = Path(name)
    if path.name != name or path.suffix not in {".css", ".js"}:
        raise ValueError("Expected a CSS or JavaScript asset filename")
    return (_STATIC / path.suffix[1:] / name).read_text(encoding="utf-8")
