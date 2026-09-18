"""Import and verify local, immutable source candidates without network access.

The supplied legacy manifest expresses the caller's expected filing identity.
Matching it does not establish human approval or independently verify its claims.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import posixpath
import re
import shutil
import unicodedata
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit
from typing import Any

from uteki.domain.documents import Document
from uteki.infrastructure.document_sources.sec import parse_sec_html


SCHEMA_VERSION = "source-snapshot-v0.1"
PARSER_VERSION = "sec-visible-blocks-v1"
_METADATA_FIELDS = (
    "company", "company_id", "document_id", "source_url", "form",
    "period_end", "filed_at", "accession",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class SnapshotError(ValueError):
    """The source candidate or one of its integrity constraints is invalid."""


def _json_bytes(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as error:
        raise SnapshotError("snapshot metadata must be finite JSON data") from error


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _paragraph_contract(document: Document) -> str:
    value = "".join(f"{row.ordinal}:{row.text_hash}\n" for row in document.paragraphs)
    return _sha256(value.encode("utf-8"))


def _gzip(value: bytes) -> bytes:
    # GzipFile also fixes the OS header across supported Python versions.
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, filename="", mode="wb", mtime=0) as output:
        output.write(value)
    return stream.getvalue()


def _decoded_path(path: str) -> str:
    if re.search(r"%(?:2f|5c)", path, flags=re.IGNORECASE):
        raise SnapshotError("encoded path separators are not supported")
    try:
        decoded = unquote(path, encoding="utf-8", errors="strict")
    except UnicodeError as error:
        raise SnapshotError("invalid URL path encoding") from error
    if ("\\" in decoded or "%" in decoded or "\x00" in decoded
            or any(ord(char) < 32 or ord(char) == 127 for char in decoded)
            or ".." in decoded.split("/")):
        raise SnapshotError("unsafe or traversing source path")
    return posixpath.normpath(decoded)


def _https_url(value: str):
    if not isinstance(value, str) or not value or value != value.strip():
        raise SnapshotError("source URL must be a nonempty HTTPS URL")
    if any(char.isspace() or ord(char) < 32 for char in value) or "\\" in value:
        raise SnapshotError("unsafe source URL")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise SnapshotError("invalid source URL") from error
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or port not in (None, 443) or not parsed.path.startswith("/")
            or parsed.path.endswith("/")):
        raise SnapshotError("source URL must identify an HTTPS file without credentials or query")
    _decoded_path(parsed.path)
    return parsed


class _Images(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.sources: list[tuple[str, bool, list[tuple[str, str | None]]]] = []
        self._noscript_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "noscript":
            self._noscript_depth += 1
        if tag == "base" and any(key == "href" for key, _ in attrs):
            raise SnapshotError("HTML base URLs are not supported by source snapshots")
        if tag != "img":
            return
        if any(key == "srcset" for key, _ in attrs):
            raise SnapshotError("image srcset requires an explicit supported source policy")
        sources = [value for key, value in attrs if key == "src"]
        if len(sources) != 1 or not sources[0]:
            raise SnapshotError("each image must have exactly one nonempty src")
        self.sources.append((sources[0], self._noscript_depth > 0, attrs))

    def handle_endtag(self, tag: str) -> None:
        if tag == "noscript" and self._noscript_depth:
            self._noscript_depth -= 1


def _is_sec_tracking_pixel(reference, source, in_noscript: bool, attrs) -> bool:
    """Recognize only the observed SEC Akamai noscript tracking endpoint.

    Hidden images and noscript contents in general remain required assets. The
    exact host, endpoint, query shape, context, and positioning must all match.
    """
    try:
        port = reference.port
    except ValueError:
        return False
    if (not in_noscript or source.hostname.lower() != "www.sec.gov"
            or reference.scheme != "https" or reference.hostname != "www.sec.gov"
            or reference.username is not None or reference.password is not None
            or port not in (None, 443) or reference.fragment
            or reference.path != "/akam/13/pixel_3f5f58ec"
            or not re.fullmatch(r"a=[A-Za-z0-9+/]+={0,2}", reference.query)):
        return False
    styles = [value for key, value in attrs if key == "style"]
    if len(styles) != 1 or not isinstance(styles[0], str):
        return False
    declarations = [item.strip().lower() for item in styles[0].split(";") if item.strip()]
    pairs = [tuple(part.strip() for part in item.split(":", 1)) for item in declarations]
    return len(pairs) == 4 and all(len(pair) == 2 for pair in pairs) and dict(pairs) == {
        "visibility": "hidden", "position": "absolute", "left": "-999px", "top": "-999px",
    }


def _discover_assets(raw_html: bytes, source_url: str) -> tuple[list[dict], int, list[dict]]:
    source = _https_url(source_url)
    source_directory = posixpath.dirname(_decoded_path(source.path)) + "/"
    if source_directory == "//":
        source_directory = "/"
    parser = _Images()
    parser.feed(raw_html.decode("utf-8", errors="replace"))
    parser.close()
    assets: dict[str, dict] = {}
    filename_keys: dict[str, str] = {}
    excluded: list[dict] = []
    for ordinal, (reference, in_noscript, attrs) in enumerate(parser.sources, start=1):
        if (reference != reference.strip() or reference.startswith("//")
                or any(char.isspace() or ord(char) < 32 for char in reference)
                or "\\" in reference):
            raise SnapshotError("unsafe image reference")
        try:
            relative = urlsplit(reference)
        except ValueError as error:
            raise SnapshotError("invalid image URL") from error
        if _is_sec_tracking_pixel(relative, source, in_noscript, attrs):
            excluded.append({
                "image_reference_ordinal": ordinal,
                "source_path": reference,
                "reason": "sec_akamai_noscript_tracking_pixel",
                "policy_version": "sec-noscript-tracking-pixel-v1",
                "context": "noscript",
                "style": next(value for key, value in attrs if key == "style"),
            })
            continue
        if relative.query or relative.fragment or not relative.path:
            raise SnapshotError("image references must be unambiguous file paths")
        _decoded_path(relative.path)  # Check before urljoin can erase traversal.
        resolved = _https_url(urljoin(source_url, reference))
        if resolved.hostname.lower() != source.hostname.lower():
            raise SnapshotError("image URL has a different source origin")
        path = _decoded_path(resolved.path)
        if not path.startswith(source_directory):
            raise SnapshotError("image URL is outside the filing directory")
        filename = posixpath.basename(path)
        if filename in ("", ".", "..") or any(char in filename for char in (":", "?", "#")):
            raise SnapshotError("unsafe image filename")
        # Filesystem normalization must not silently merge two source assets.
        filename_key = unicodedata.normalize("NFC", filename).casefold()
        previous_name = filename_keys.setdefault(filename_key, filename)
        if previous_name != filename:
            raise SnapshotError("image filenames collide after filesystem normalization")
        canonical_url = urlunsplit(("https", source.hostname.lower(),
                                   quote(path, safe="/-._~"), "", ""))
        row = assets.get(filename)
        if row is not None and row["source_url"] != canonical_url:
            raise SnapshotError("different image URLs have the same filename")
        if row is None:
            row = {"filename": filename, "source_url": canonical_url,
                   "source_paths": [], "artifact_path": f"assets/{filename}"}
            assets[filename] = row
        if reference not in row["source_paths"]:
            row["source_paths"].append(reference)
    return [assets[name] for name in sorted(assets)], len(parser.sources), excluded


def _validate_metadata(source_manifest: dict, retrieved_at: str, retrieval: dict) -> dict:
    if not isinstance(source_manifest, dict) or not isinstance(retrieval, dict):
        raise SnapshotError("source_manifest and retrieval must be JSON objects")
    # Round-trip prevents caller mutations from changing the saved expectations.
    source_manifest = json.loads(_json_bytes(source_manifest))
    _json_bytes(retrieval)
    for key in ("document_id", "source_url"):
        if not isinstance(source_manifest.get(key), str) or not source_manifest[key].strip():
            raise SnapshotError(f"source_manifest.{key} must be nonempty")
    _https_url(source_manifest["source_url"])
    for key in _METADATA_FIELDS:
        if key in source_manifest and (not isinstance(source_manifest[key], str)
                                       or not source_manifest[key].strip()):
            raise SnapshotError(f"source_manifest.{key} must be a nonempty string")
    for key in ("content_sha256", "paragraph_contract_sha256", "expected_legacy_paragraph_contract_sha256"):
        if key in source_manifest and (not isinstance(source_manifest[key], str)
                                       or not _SHA256.fullmatch(source_manifest[key])):
            raise SnapshotError(f"source_manifest.{key} must be a SHA-256 digest")
    if ("paragraph_contract_sha256" in source_manifest
            and "expected_legacy_paragraph_contract_sha256" in source_manifest
            and source_manifest["paragraph_contract_sha256"]
            != source_manifest["expected_legacy_paragraph_contract_sha256"]):
        raise SnapshotError("legacy paragraph contract expectations disagree")
    if "paragraph_count" in source_manifest:
        count = source_manifest["paragraph_count"]
        if type(count) is not int or count < 0:
            raise SnapshotError("source_manifest.paragraph_count must be a nonnegative integer")
    for key in ("source_snapshot_id", "parser_version"):
        if key in source_manifest and (not isinstance(source_manifest[key], str)
                                       or not source_manifest[key].strip()):
            raise SnapshotError(f"source_manifest.{key} must be nonempty")
    try:
        timestamp = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise SnapshotError("retrieved_at must be an ISO timestamp with a timezone") from error
    if timestamp.utcoffset() is None:
        raise SnapshotError("retrieved_at must include a timezone")
    return source_manifest


def _prepare(raw_html: bytes, *, source_manifest: dict, assets: dict[str, bytes],
             retrieved_at: str, retrieval: dict, compressed: bytes | None = None):
    original = _validate_metadata(source_manifest, retrieved_at, retrieval)
    if not isinstance(raw_html, bytes) or not raw_html:
        raise SnapshotError("raw_html must contain nonempty source bytes")
    if not isinstance(assets, dict) or any(not isinstance(name, str) for name in assets):
        raise SnapshotError("assets must map original filenames to bytes")
    references, reference_count, excluded = _discover_assets(raw_html, original["source_url"])
    names = {row["filename"] for row in references}
    if names != set(assets):
        raise SnapshotError(f"image coverage mismatch: missing={sorted(names - set(assets))}, "
                            f"unexpected={sorted(set(assets) - names)}")
    if any(not isinstance(value, bytes) or not value for value in assets.values()):
        raise SnapshotError("source assets must contain nonempty bytes")
    document = parse_sec_html(original["document_id"], original["source_url"], raw_html)
    if not document.paragraphs:
        raise SnapshotError("source has no legacy visible paragraphs")
    contract = _paragraph_contract(document)
    payloads = {"source.html.gz": _gzip(raw_html) if compressed is None else compressed,
                "document.json": _json_bytes(asdict(document))}
    for row in references:
        raw_asset = assets[row["filename"]]
        row.update(sha256=_sha256(raw_asset), bytes=len(raw_asset))
        payloads[row["artifact_path"]] = raw_asset
    artifacts = {name: {"sha256": _sha256(raw), "bytes": len(raw)}
                 for name, raw in sorted(payloads.items())}
    metadata = {key: original[key] for key in _METADATA_FIELDS if key in original}
    # Identity depends on source content, attachments, parsing, and declared filing
    # metadata. Retrieval times and comparisons to earlier expectations are logs.
    identity = {**metadata, "content_sha256": document.content_hash,
                "parser_version": PARSER_VERSION,
                "paragraph_contract_sha256": contract, "assets": references,
                "excluded_image_references": excluded}
    snapshot_id = f"{document.id}-candidate-{_sha256(_json_bytes(identity))[:16]}"
    expected_sha = original.get("content_sha256")
    expected_count = original.get("paragraph_count")
    expected_contract = original.get("expected_legacy_paragraph_contract_sha256",
                                     original.get("paragraph_contract_sha256"))
    comparison = {
        "expected_content_sha256": expected_sha,
        "matches_legacy": None if expected_sha is None else expected_sha == document.content_hash,
        "expected_paragraph_count": expected_count,
        "paragraph_count_matches": None if expected_count is None else expected_count == len(document.paragraphs),
        "expected_paragraph_contract_sha256": expected_contract,
        "paragraph_contract_matches": None if expected_contract is None else expected_contract == contract,
        "expected_parser_version": original.get("parser_version"),
        "parser_version_matches": (None if "parser_version" not in original
                                   else original["parser_version"] == PARSER_VERSION),
    }
    manifest = {
        **metadata, "schema_version": SCHEMA_VERSION, "status": "candidate",
        "source_snapshot_id": snapshot_id,
        "legacy_source_snapshot_id": original.get("source_snapshot_id"),
        "legacy_source_manifest": original, "legacy_comparison": comparison,
        "identity_basis": "caller_declared_metadata; source_content_and_artifacts_verified",
        "content_sha256": document.content_hash, "parser_version": PARSER_VERSION,
        "paragraph_count": len(document.paragraphs), "paragraph_contract_sha256": contract,
        "image_reference_count": reference_count, "retrieved_at": retrieved_at,
        "excluded_image_reference_count": len(excluded), "excluded_image_references": excluded,
        "retrieval": json.loads(_json_bytes(retrieval)),
        "assets": references, "artifacts": artifacts,
    }
    return manifest, payloads, document


def _write_new(path: Path, raw: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(raw)


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise SnapshotError(f"missing or non-regular snapshot file: {path.name}")
    return path.read_bytes()


def _check_layout(snapshot_dir: Path, expected_files: set[str]) -> None:
    if snapshot_dir.is_symlink() or not snapshot_dir.is_dir():
        raise SnapshotError("snapshot must be a regular directory")
    actual = set()
    for path in snapshot_dir.rglob("*"):
        relative = path.relative_to(snapshot_dir).as_posix()
        if path.is_symlink():
            raise SnapshotError(f"snapshot symlinks are not supported: {relative}")
        if path.is_file():
            actual.add(relative)
        elif not path.is_dir() or relative != "assets":
            raise SnapshotError(f"unexpected snapshot entry: {relative}")
    if actual != expected_files:
        raise SnapshotError(f"snapshot file coverage mismatch: missing={sorted(expected_files - actual)}, "
                            f"unexpected={sorted(actual - expected_files)}")


def import_snapshot(raw_html: bytes, *, source_manifest: dict,
                    assets: dict[str, bytes], output_dir: Path,
                    retrieved_at: str, retrieval: dict) -> dict:
    """Create a new local candidate, refusing every already-existing directory.

    A different legacy SHA is recorded, not repaired. The manifest is published
    last; any failed write removes this call's new, incomplete directory.
    """
    output_dir = Path(output_dir)
    if output_dir.exists() or output_dir.is_symlink():
        raise FileExistsError(f"source snapshot output already exists: {output_dir}")
    manifest, payloads, _ = _prepare(raw_html, source_manifest=source_manifest, assets=assets,
                                    retrieved_at=retrieved_at, retrieval=retrieval)
    output_dir.mkdir(parents=True, exist_ok=False)
    try:
        if assets:
            (output_dir / "assets").mkdir()
        for name, raw in payloads.items():
            _write_new(output_dir / name, raw)
        _check_layout(output_dir, set(payloads))
        for name, raw in payloads.items():
            if _read_regular(output_dir / name) != raw:
                raise SnapshotError(f"source artifact write verification failed: {name}")
        temporary_manifest = output_dir / ".manifest.json.tmp"
        _write_new(temporary_manifest, _json_bytes(manifest))
        temporary_manifest.replace(output_dir / "manifest.json")
    except BaseException:
        # This directory was reserved by this call with exist_ok=False.
        shutil.rmtree(output_dir)
        raise
    return manifest


def _unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise SnapshotError(f"duplicate JSON key in snapshot manifest: {key}")
        result[key] = value
    return result


def _verify(snapshot_dir: Path) -> tuple[dict, Document]:
    snapshot_dir = Path(snapshot_dir)
    if snapshot_dir.is_symlink() or not snapshot_dir.is_dir():
        raise SnapshotError("snapshot must be a regular directory")
    try:
        manifest = json.loads(_read_regular(snapshot_dir / "manifest.json"),
                              object_pairs_hook=_unique_json_object)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SnapshotError("invalid snapshot manifest JSON") from error
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise SnapshotError("unsupported source snapshot manifest")
    original = _validate_metadata(manifest.get("legacy_source_manifest"),
                                  manifest.get("retrieved_at"), manifest.get("retrieval"))
    compressed = _read_regular(snapshot_dir / "source.html.gz")
    try:
        raw = gzip.decompress(compressed)
    except (OSError, EOFError) as error:
        raise SnapshotError("invalid compressed source artifact") from error
    if compressed[4:8] != b"\x00\x00\x00\x00":
        raise SnapshotError("source gzip must have a zero timestamp")
    references, _, _ = _discover_assets(raw, original["source_url"])
    paths = {"source.html.gz", "document.json", "manifest.json"}
    paths.update(row["artifact_path"] for row in references)
    _check_layout(snapshot_dir, paths)
    assets = {row["filename"]: _read_regular(snapshot_dir / row["artifact_path"])
              for row in references}
    expected, payloads, document = _prepare(
        raw, source_manifest=original, assets=assets,
        retrieved_at=manifest["retrieved_at"], retrieval=manifest["retrieval"],
        compressed=compressed,
    )
    if _read_regular(snapshot_dir / "document.json") != payloads["document.json"]:
        raise SnapshotError("document artifact differs from reparsed legacy source")
    if manifest != expected:
        raise SnapshotError("snapshot manifest metadata, identity, comparison, or artifact integrity mismatch")
    return manifest, document


def verify_snapshot(snapshot_dir: Path) -> dict:
    """Verify complete source bytes, attachment coverage, metadata, and parsing."""
    return _verify(Path(snapshot_dir))[0]


def load_snapshot_document(snapshot_dir: Path) -> Document:
    """Return the legacy Document only after the whole candidate verifies."""
    return _verify(Path(snapshot_dir))[1]
