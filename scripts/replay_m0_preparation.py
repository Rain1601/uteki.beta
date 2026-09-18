#!/usr/bin/env python3
"""Replay the current R2-A source, index, and review package in a fresh directory.

Original research artifacts are read-only. A Python audit hook rejects reads of
the original data/ and benchmarks/ while the copied package is replayed, as well
as Python socket audit events. This is an in-process check, not an OS sandbox.
"""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import traceback


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]

from scripts.prepare_m0_review import prepare_review, verify_review
from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts
from uteki.infrastructure.document_sources.snapshots import import_snapshot, verify_snapshot


DEFAULT_PATHS = {
    "source": "data/source_documents/alphabet_2025_10k/r2a-20260918-candidate",
    "index": "data/source_documents/alphabet_2025_10k/indexes/r2a-20260918-candidate",
    "review": "data/evaluation/m0_r2a/2026-09-18-candidate",
}
LEGACY_PATHS = (
    "data/source_documents/alphabet_2025_10k/manifest.json",
    "data/source_documents/alphabet_2025_10k/review_excerpt.json",
    "benchmarks/alphabet_2025_business_map/v0.1-candidate/business_map.json",
    "benchmarks/alphabet_2025_business_map/v0.1-candidate/claims.json",
    "benchmarks/alphabet_2025_business_map/v0.1-candidate/evidence_spans.json",
    "data/evaluation/pilots/alphabet_2025_item1_business_map.json",
)
IMPLEMENTATION_PATHS = (
    "scripts/replay_m0_preparation.py",
    "scripts/prepare_m0_review.py",
    "src/uteki/infrastructure/document_sources/snapshots.py",
    "src/uteki/infrastructure/document_sources/sec.py",
    "src/uteki/infrastructure/document_sources/sec_index.py",
    "src/uteki/infrastructure/document_sources/index_artifacts.py",
)
INDEX_PARSER_VERSION = "sec-source-blocks-v0.1.5"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def inventory(folder: Path) -> dict[str, bytes]:
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError(f"expected a regular artifact directory: {folder}")
    files = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"artifact symlinks are not supported: {path}")
        if path.is_file():
            files[path.relative_to(folder).as_posix()] = path.read_bytes()
        elif not path.is_dir():
            raise ValueError(f"unexpected artifact entry: {path}")
    return files


def compare(expected: dict[str, bytes], folder: Path) -> dict:
    """Compare exact file sets and bytes, including each completion manifest."""
    actual = inventory(folder)
    rows = []
    for name in sorted(set(expected) | set(actual)):
        left, right = expected.get(name), actual.get(name)
        rows.append({
            "path": name, "present_in_reference": left is not None,
            "present_in_replay": right is not None,
            "expected_sha256": digest(left) if left is not None else None,
            "actual_sha256": digest(right) if right is not None else None,
            "expected_bytes": len(left) if left is not None else None,
            "actual_bytes": len(right) if right is not None else None,
            "byte_equal": left is not None and right is not None and left == right,
        })
    return {"status": "pass" if rows and all(row["byte_equal"] for row in rows) else "fail",
            "file_count": len(rows), "manifest_included": "manifest.json" in expected,
            "files": rows}


class ReplayAuditGuard:
    """A temporary policy within this Python process, not a security sandbox."""

    def __init__(self, root: Path):
        self.root = root
        self.active = False
        self.external_attempts = 0
        self.network_attempts = 0

    def audit(self, event, args):
        if not self.active:
            return
        if event.startswith("socket."):
            self.network_attempts += 1
            raise PermissionError("Python socket audit event prohibited during replay")
        if event != "open" or isinstance(args[0], int):
            return
        absolute = Path(os.path.abspath(os.fsdecode(args[0])))
        if any(absolute.is_relative_to(self.root / relative) for relative in ("data", "benchmarks")):
            self.external_attempts += 1
            raise PermissionError(f"original repository research input prohibited during replay: {absolute}")


def _replay_in_temporary_directory(paths, baseline, manifests, guard, checks):
    with tempfile.TemporaryDirectory(prefix="uteki-r2a-independent-replay-") as temporary:
        temp = Path(temporary)
        copied = temp / "copied-review"
        shutil.copytree(paths["review"], copied)
        checks["review_copy_exact"] = compare(baseline["review"], copied)
        original_cwd = Path.cwd()
        os.chdir(temp)
        guard.active = True
        try:
            copied_manifest = verify_review(copied)
            same_manifest = copied_manifest == manifests["review"]
            checks["review_verification_without_external_inputs"] = {
                "status": "pass" if same_manifest else "fail",
                "returned_manifest_equal": same_manifest,
                "repository_data_and_benchmarks_reads": "blocked_by_python_audit_hook",
                "blocked_external_read_attempts": guard.external_attempts,
                "working_directory": "fresh temporary directory",
            }
            rebuilt_review = temp / "rebuilt-review"
            prepare_review(copied / "source_snapshot", copied / "legacy_inputs",
                           copied / "legacy_inputs/review_excerpt.json", rebuilt_review,
                           prepared_at=copied_manifest["prepared_at"])
            checks["review_byte_replay"] = compare(baseline["review"], rebuilt_review)

            source_dir = copied / "source_snapshot"
            source_manifest = verify_snapshot(source_dir)
            raw_html = gzip.decompress((source_dir / "source.html.gz").read_bytes())
            assets = {row["filename"]: (source_dir / row["artifact_path"]).read_bytes()
                      for row in source_manifest["assets"]}
            rebuilt_source = temp / "base/r2a-20260918-candidate"
            imported = import_snapshot(
                raw_html, source_manifest=source_manifest["legacy_source_manifest"], assets=assets,
                output_dir=rebuilt_source, retrieved_at=source_manifest["retrieved_at"],
                retrieval=source_manifest["retrieval"],
            )
            verify_snapshot(rebuilt_source)
            checks["source_byte_replay"] = compare(baseline["source"], rebuilt_source)

            rebuilt_index = temp / "base/indexes/r2a-20260918-candidate"
            indexed = build_index_artifacts(rebuilt_source, rebuilt_index, parser_version=INDEX_PARSER_VERSION)
            checks["index_byte_replay"] = compare(baseline["index"], rebuilt_index)
            identities_match = imported == manifests["source"] and indexed == manifests["index"]
            checks["source_and_index_identity"] = {
                "status": "pass" if identities_match else "fail",
                "source_snapshot_id": imported["source_snapshot_id"], "index_id": indexed["index_id"],
            }
        finally:
            guard.active = False
            os.chdir(original_cwd)
        checks["temporary_review_unchanged_by_verification"] = compare(baseline["review"], copied)


def _legacy_check(root: Path, before: dict[str, bytes], committed: dict[str, bytes]) -> dict:
    rows = []
    for name, raw in before.items():
        after = (root / name).read_bytes()
        rows.append({"path": name, "before_sha256": digest(raw), "after_sha256": digest(after),
                     "git_head_sha256": digest(committed[name]),
                     "unchanged_during_replay": after == raw, "matches_git_head": after == committed[name]})
    passed = rows and all(row["unchanged_during_replay"] and row["matches_git_head"] for row in rows)
    return {"status": "pass" if passed else "fail", "files": rows}


def replay(root: Path = ROOT) -> dict:
    started = datetime.now(UTC).isoformat()
    paths = {name: root / relative for name, relative in DEFAULT_PATHS.items()}
    baseline, manifests, legacy_before, legacy_head, code_before = {}, {}, {}, {}, {}
    checks, errors = {}, []
    git_head = None
    guard = ReplayAuditGuard(root)
    sys.addaudithook(guard.audit)
    try:
        baseline = {name: inventory(path) for name, path in paths.items()}
        legacy_before = {name: (root / name).read_bytes() for name in LEGACY_PATHS}
        code_before = {name: (root / name).read_bytes() for name in IMPLEMENTATION_PATHS}
        git_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        legacy_head = {name: subprocess.check_output(["git", "show", f"HEAD:{name}"], cwd=root)
                       for name in LEGACY_PATHS}
        manifests = {name: json.loads(files["manifest.json"]) for name, files in baseline.items()}
        _replay_in_temporary_directory(paths, baseline, manifests, guard, checks)
    except Exception as error:
        errors.append({"phase": "replay", "type": type(error).__name__, "message": str(error),
                       "traceback": traceback.format_exc()})
    finally:
        guard.active = False

    # These checks run even when a regeneration fails, recording whether old
    # material or published candidates changed during the attempted replay.
    try:
        if legacy_before and legacy_head:
            checks["legacy_inputs_unchanged"] = _legacy_check(root, legacy_before, legacy_head)
        if baseline:
            artifacts = {name: compare(files, paths[name]) for name, files in baseline.items()}
            checks["published_artifacts_unchanged"] = {
                "status": "pass" if all(row["status"] == "pass" for row in artifacts.values()) else "fail",
                "artifacts": artifacts,
            }
        code_rows = {name: {"sha256": digest(raw), "unchanged_during_replay": (root / name).read_bytes() == raw}
                     for name, raw in code_before.items()}
        if code_rows:
            checks["implementation_unchanged_during_replay"] = {
                "status": "pass" if all(row["unchanged_during_replay"] for row in code_rows.values()) else "fail",
                "files": code_rows,
            }
    except Exception as error:
        code_rows = {}
        errors.append({"phase": "post_replay_integrity", "type": type(error).__name__, "message": str(error),
                       "traceback": traceback.format_exc()})

    source, index, review = (manifests.get(name, {}) for name in ("source", "index", "review"))
    evidence_counts = {}
    if "review" in baseline and "legacy_audit.json" in baseline["review"]:
        try:
            evidence_counts = json.loads(baseline["review"]["legacy_audit.json"])["counts"]
        except (ValueError, KeyError, TypeError):
            pass  # Failed verification already prevents a passing report.
    passed = bool(checks) and not errors and all(check["status"] == "pass" for check in checks.values())
    return {
        "schema_version": "m0-r2a-replay-report-v1", "status": "pass" if passed else "fail",
        "started_at": started, "completed_at": datetime.now(UTC).isoformat(),
        "scope": "deterministic source, index, and untouched human-review preparation artifacts",
        "reference_paths": DEFAULT_PATHS,
        "execution": {
            "command": shlex.join([sys.executable, *sys.argv]),
            "repository_root": str(root), "replay_working_directory": "new TemporaryDirectory; removed after checks",
            "python": sys.version, "platform": platform.platform(), "lxml": importlib.metadata.version("lxml"),
            "git_head": git_head, "implementation_fingerprints": code_rows,
            "network_activity": "no network calls; Python socket audit events rejected during replay",
            "external_input_isolation": "in-process Python audit hook rejects opens under original repository data/ and benchmarks/; not an OS security sandbox",
            "external_read_attempts": guard.external_attempts, "socket_audit_attempts": guard.network_attempts,
            "methods": [
                "Copy the review package to a fresh temporary directory; verify_review(copy) while original research-data opens are rejected.",
                "prepare_review(copy/source_snapshot, copy/legacy_inputs, copy/legacy_inputs/review_excerpt.json, new_output, prepared_at=original_prepared_at).",
                "Decompress copied source.html.gz and import_snapshot using embedded legacy_source_manifest, copied assets, original retrieved_at and retrieval.",
                "build_index_artifacts(temp/base/r2a-20260918-candidate, temp/base/indexes/r2a-20260918-candidate, parser_version=sec-source-blocks-v0.1.5).",
                "Compare exact file sets and every file byte, including each manifest.json, against pre-read reference bytes.",
                "Compare legacy inputs before/after and against git HEAD; compare published artifacts and implementation files before/after.",
            ],
        },
        "versions_and_identities": {
            "source_schema": source.get("schema_version"), "source_snapshot_id": source.get("source_snapshot_id"),
            "source_parser_version": source.get("parser_version"), "source_content_sha256": source.get("content_sha256"),
            "paragraph_contract_sha256": source.get("paragraph_contract_sha256"),
            "index_schema": index.get("schema_version"), "index_id": index.get("index_id"),
            "index_parser_version": index.get("parser_version"), "review_schema": review.get("schema_version"),
            "review_package_id": review.get("package_id"), "review_derivation_version": review.get("derivation_version"),
        },
        "counts": {
            "source_files_including_manifest": len(baseline.get("source", {})),
            "index_files_including_manifest": len(baseline.get("index", {})),
            "review_files_including_manifest": len(baseline.get("review", {})),
            "source_paragraphs": source.get("paragraph_count"), "source_assets": len(source.get("assets", [])),
            "excluded_tracking_image_references": source.get("excluded_image_reference_count"),
            "index": index.get("counts", {}), "review_evidence": evidence_counts,
        },
        "legacy_source_comparison": source.get("legacy_comparison"), "checks": checks, "errors": errors,
        "limitations": [
            "Replay uses a fresh directory and copied inputs on the same installed runtime, not a separate operating system or a clean dependency installation.",
            "The audit hook checks this Python process and specified file locations; it is not an OS security sandbox.",
            "No model calls, model-quality evaluation, human semantic review, Gold approval, adoption, or investment-result validation occurs.",
            "Historical full raw bytes remain unavailable. Newly retrieved raw SHA differs from the historical expected SHA while all 1311 legacy paragraph hashes match.",
            "One identified SEC Akamai noscript tracking pixel is excluded under the recorded policy; its reference remains in the unmodified HTML and no pixel request is made.",
            "The source, index, and review preparation remain candidates; human-review answers are left empty.",
        ],
    }


def _write_report(output: Path, raw: bytes) -> None:
    """Publish a complete report under a new name, never replacing any file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".m0-replay-report-", dir=output.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new report file; omission prints the full JSON report")
    args = parser.parse_args(argv)
    if args.output is not None and (args.output.exists() or args.output.is_symlink()):
        print(f"Replay report already exists; refusing to overwrite: {args.output}", file=sys.stderr)
        return 1
    report = replay()
    raw = (json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    if args.output is None:
        print(raw.decode(), end="")
    else:
        try:
            _write_report(args.output, raw)
        except OSError as error:
            print(f"Replay report could not be published: {error}", file=sys.stderr)
            return 1
        print(json.dumps({"status": report["status"], "report": str(args.output.resolve()),
                          "counts": report["counts"],
                          "checks": {name: check["status"] for name, check in report["checks"].items()},
                          "errors": report["errors"]}, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
