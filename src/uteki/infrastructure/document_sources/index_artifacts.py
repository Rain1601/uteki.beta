from __future__ import annotations

import gzip
import hashlib
import json
import mimetypes
import struct
from dataclasses import asdict
from pathlib import Path
from typing import Any

from uteki.domain.documents import ParsedDocument, SourceBlock
from uteki.infrastructure.document_sources.sec_index import build_legal_outline, parse_sec_source


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _block_payload(block: SourceBlock) -> dict[str, Any]:
    value = asdict(block)
    value["style_signature"] = dict(block.style_signature)
    return value


def _jpeg_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:2] != b"\xff\xd8":
        raise ValueError(f"unsupported image format: {path.name}")
    offset = 2
    while offset + 9 < len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
            return width, height
        offset += length
    raise ValueError(f"JPEG dimensions were not found: {path.name}")


def _asset_payloads(parsed: ParsedDocument, assets_dir: Path) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for reference in parsed.assets:
        filename = Path(reference.source_path).name
        asset_path = assets_dir / filename
        if not asset_path.is_file():
            raise FileNotFoundError(f"frozen source asset is missing: {asset_path}")
        raw = asset_path.read_bytes()
        width, height = _jpeg_size(asset_path)
        payloads.append(
            {
                **asdict(reference),
                "filename": filename,
                "local_path": f"../../assets/{filename}",
                "mime_type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
                "width": width,
                "height": height,
            }
        )
    return payloads


def build_index_artifacts(snapshot_dir: Path, output_dir: Path, *, parser_version: str | None = None) -> dict[str, Any]:
    source_manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    with gzip.open(snapshot_dir / "source.html.gz", "rb") as source:
        raw_html = source.read()
    if hashlib.sha256(raw_html).hexdigest() != source_manifest["content_sha256"]:
        raise ValueError("frozen SEC source does not match its manifest SHA")
    parsed = parse_sec_source(
        source_manifest["document_id"],
        source_manifest["source_url"],
        raw_html,
        source_snapshot_id=source_manifest["source_snapshot_id"],
        form_type=source_manifest["form"],
        **({"parser_version": parser_version} if parser_version else {}),
    )
    index = build_legal_outline(parsed)
    assets = _asset_payloads(parsed, snapshot_dir / "assets")
    index_payload = asdict(index)
    block_lines = b"".join(
        json.dumps(_block_payload(block), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        for block in parsed.blocks
    )
    assets_bytes = _json_bytes({"assets": assets})
    index_bytes = _json_bytes(index_payload)
    files = {
        "index.json": index_bytes,
        "blocks.jsonl": block_lines,
        "assets.json": assets_bytes,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (output_dir / filename).write_bytes(content)
    manifest = {
        "index_id": index.index_id,
        "index_version": output_dir.name,
        "status": "candidate" if output_dir.name.endswith("-candidate") else "frozen",
        "schema_version": index.schema_version,
        "parser_version": index.parser_version,
        "source_snapshot_id": index.source_snapshot_id,
        "source_sha256": parsed.content_hash,
        "form_type": index.form_type,
        "counts": {
            "blocks": len(parsed.blocks),
            "tables": sum(block.type == "table" for block in parsed.blocks),
            "images": len(parsed.assets),
            "parts": sum(node.kind == "part" for node in index.nodes),
            "items": sum(node.kind == "item" for node in index.nodes),
            "diagnostics": len(index.diagnostics),
        },
        "artifacts": {
            filename: {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)}
            for filename, content in files.items()
        },
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    return manifest
