#!/usr/bin/env python3
"""Audit legacy M0 evidence against a verified source and prepare human review."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uteki.domain.documents import Document
from uteki.domain.business_map import business_map_from_dict
from uteki.infrastructure.document_sources.sec import text_hash
from uteki.infrastructure.document_sources.snapshots import load_snapshot_document, verify_snapshot


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def fingerprint(path: str, raw: bytes) -> dict:
    """All references in a review package resolve relative to the package."""
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def audit_evidence(document: Document, candidate: dict, excerpt: dict, claims: dict, spans: dict) -> dict:
    """Measure exact source integrity; this does not judge semantic support."""
    paragraphs = {p.ordinal: p for p in document.paragraphs}
    issues = []
    if candidate["document_id"] != document.id:
        issues.append({"kind": "candidate_document_mismatch", "blocks_rebinding": True})
    evidence_by_id = {}
    verified_evidence = 0
    for item in candidate["evidence"]:
        if item["id"] in evidence_by_id:
            issues.append({"kind": "duplicate_evidence_id", "evidence_id": item["id"], "blocks_rebinding": True})
        evidence_by_id[item["id"]] = item
        paragraph = paragraphs.get(item["paragraph_ordinal"])
        matches = bool(paragraph and paragraph.text_hash == item["text_hash"]
                       and item["document_id"] == document.id and item["source_url"] == document.source_url)
        verified_evidence += int(matches)
        if not matches:
            issues.append({"kind": "evidence_source_mismatch", "evidence_id": item["id"],
                           "paragraph_ordinal": item["paragraph_ordinal"], "blocks_rebinding": True})
    excerpt_matches = 0
    seen_ordinals = set()
    for item in excerpt["paragraphs"]:
        ordinal = item["ordinal"]
        if ordinal in seen_ordinals:
            issues.append({"kind": "duplicate_excerpt_ordinal", "paragraph_ordinal": ordinal, "blocks_rebinding": True})
        seen_ordinals.add(ordinal)
        paragraph = paragraphs.get(ordinal)
        if paragraph is None:
            issues.append({"kind": "missing_source_paragraph", "paragraph_ordinal": ordinal, "blocks_rebinding": True})
            continue
        internal_match = text_hash(item["text"]) == item["text_hash"]
        text_match = item["text"] == paragraph.text
        stored_match = item["text_hash"] == paragraph.text_hash
        excerpt_matches += int(internal_match and text_match and stored_match)
        if not (internal_match and text_match and stored_match):
            affected = [e["id"] for e in candidate["evidence"] if e["paragraph_ordinal"] == ordinal]
            issues.append({
                "kind": "legacy_excerpt_difference", "paragraph_ordinal": ordinal,
                "legacy_text": item["text"], "source_text": paragraph.text,
                "legacy_stored_hash": item["text_hash"], "legacy_computed_hash": text_hash(item["text"]),
                "source_text_hash": paragraph.text_hash, "stored_hash_matches_source": stored_match,
                "affected_evidence_ids": affected,
                "affected_claim_ids": [c["id"] for c in claims["claims"] if set(c["evidence_ids"]) & set(affected)],
                "blocks_rebinding": not stored_match,
            })
    claim_by_id = {c["id"]: c for c in claims["claims"]}
    if len(claim_by_id) != len(claims["claims"]):
        issues.append({"kind": "duplicate_claim_id", "blocks_rebinding": True})
    for claim in claims["claims"]:
        if not claim["evidence_ids"] or any(e not in evidence_by_id for e in claim["evidence_ids"]):
            issues.append({"kind": "claim_evidence_missing", "claim_id": claim["id"], "blocks_rebinding": True})
    verified_spans = 0
    span_pairs = set()
    for span in spans["spans"]:
        pair = (span["claim_id"], span["evidence_id"])
        if pair in span_pairs:
            issues.append({"kind": "duplicate_claim_evidence_span", "claim_id": pair[0],
                           "evidence_id": pair[1], "blocks_rebinding": True})
        span_pairs.add(pair)
        evidence = evidence_by_id.get(span["evidence_id"])
        paragraph = paragraphs.get(evidence["paragraph_ordinal"]) if evidence else None
        claim = claim_by_id.get(span["claim_id"])
        linked = bool(claim and span["evidence_id"] in claim["evidence_ids"])
        matches = bool(paragraph and span["quote_en"] and span["quote_en"] in paragraph.text and linked)
        verified_spans += int(matches)
        if not matches:
            issues.append({"kind": "span_source_mismatch", "claim_id": span["claim_id"],
                           "evidence_id": span["evidence_id"], "quote_en": span["quote_en"], "blocks_rebinding": True})
    for claim in claims["claims"]:
        for evidence_id in claim["evidence_ids"]:
            if (claim["id"], evidence_id) not in span_pairs:
                issues.append({"kind": "claim_evidence_span_missing", "claim_id": claim["id"],
                               "evidence_id": evidence_id, "blocks_rebinding": True})
    return {
        "document_id": document.id, "source_content_sha256": document.content_hash,
        "counts": {"paragraphs": len(document.paragraphs), "evidence": len(candidate["evidence"]),
                   "verified_evidence": verified_evidence, "excerpt_paragraphs": len(excerpt["paragraphs"]),
                   "matching_legacy_excerpts": excerpt_matches, "claims": len(claims["claims"]),
                   "spans": len(spans["spans"]), "verified_spans": verified_spans},
        "issues": issues, "can_rebind_source": not any(i["blocks_rebinding"] for i in issues),
        "semantic_review": "pending_human_review", "gold_status": "not_frozen",
    }


PACKAGE_SCHEMA = "m0-review-package-v1"
DERIVATION_VERSION = "m0-source-rebinding-v1"
SOURCE_DIRECTORY = "source_snapshot"
LEGACY_DIRECTORY = "legacy_inputs"
LEGACY_FILES = ("business_map.json", "claims.json", "evidence_spans.json", "review_excerpt.json")
M0_IDENTITY = {
    "document_id": "sec-0001652044-26-000018", "form": "10-K",
    "period_end": "2025-12-31", "filed_at": "2026-02-05", "accession": "0001652044-26-000018",
    "source_url": "https://www.sec.gov/Archives/edgar/data/1652044/000165204426000018/goog-20251231.htm",
}
_CLAIM_FIELDS = ("id", "business_id", "field", "label_en", "label_zh", "value_en",
                 "value_zh", "basis", "evidence_ids")
_SPAN_FIELDS = ("claim_id", "evidence_id", "quote_en", "quote_zh")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(raw: bytes) -> dict:
    value = json.loads(raw, object_pairs_hook=_unique_object)
    if not isinstance(value, dict):
        raise ValueError("review input must be a JSON object")
    encoded(value)  # Reject non-finite JSON values.
    return value


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or non-regular review file: {path}")
    return path.read_bytes()


def _validate_prepared_at(value: str) -> None:
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError("prepared_at must be an ISO timestamp with timezone") from error
    if stamp.utcoffset() is None:
        raise ValueError("prepared_at must include a timezone")


def _review_questions(source_snapshot_id: str, candidate_id: str) -> dict:
    return {
        "schema_version": "m0-g0-review-v1", "status": "pending_human_review",
        "candidate_id": candidate_id, "source_snapshot_id": source_snapshot_id,
        "reviewer": None, "reviewed_at": None,
        "pilot_paragraphs": [88, 89, 90, 91],
        "questions": [
            {"id": "G0-P1", "question": "Google Services 下的订阅、平台、设备，应如何表达为业务节点与收入类别，才能有用且不重复？", "answer": None},
            {"id": "G0-P2", "question": "Google Play、Google One、YouTube 与 Pixel 在本段应作为产品/服务，哪些有足够依据提升为独立业务节点？", "answer": None},
            {"id": "G0-P3", "question": "本段仅披露收入来源，是否同意把各类收入占比、利润率和独立性保留为未知，并要求每项推导写明规则？", "answer": None},
            {"id": "G0-P4", "question": "是否确认采用新来源快照及第 90 段原文，旧摘录和旧审核身份继续保留？", "answer": None},
        ],
        "full_gold_review": "not_started", "independent_omission_check": "not_started",
    }


def _review_markdown(document: Document, source_snapshot_id: str, audit: dict, review: dict) -> bytes:
    body = ["# M0 G0 人工试标包", "", "状态：待人工审阅；这是新候选，不是 Gold 或已采纳研究。", "",
            f"固定来源：[{document.id}]({document.source_url})", "",
            f"新来源快照：`{source_snapshot_id}`", "",
            "## 来源核查", "", "完整来源的全部段落参与校验；以下计数仅表示来源一致性，不表示主张语义正确。", "",
            f"- 旧证据定位：{audit['counts']['verified_evidence']}/{audit['counts']['evidence']}。",
            f"- 旧精确英文引文：{audit['counts']['verified_spans']}/{audit['counts']['spans']}。",
            f"- 旧摘录逐段一致：{audit['counts']['matching_legacy_excerpts']}/{audit['counts']['excerpt_paragraphs']}。", "",
            "旧文件均未覆盖。差异、前后文本、输入指纹见 `legacy_audit.json`；新的 `review_excerpt.json` 直接来自已校验完整来源。", "",
            "完整来源及附件保存在 `source_snapshot/`，原候选输入按原字节保存在 `legacy_inputs/`。本包可复制到其他目录独立校验，无须原工作区资料。", "",
            "## 小节试标：Google Services 的非广告收入", ""]
    by_ordinal = {p.ordinal: p for p in document.paragraphs}
    for ordinal in review["pilot_paragraphs"]:
        p = by_ordinal.get(ordinal)
        if p is None:
            raise ValueError(f"pilot paragraph {ordinal} is missing")
        body += [f"### 第 {ordinal} 段", "", p.text, "", f"文本指纹：`{p.text_hash}`", ""]
    body += ["## 请记录研究判断", "", "以下是待裁决的问题，不是已批准的标注规则。可直接在讨论中回答，由执行者据实记录为新的审核版本；本准备包保持不可变。", ""]
    for q in review["questions"]:
        body += [f"- **{q['id']}**：{q['question']}"]
    body += ["", "完整候选也已附在本目录。一次小节试标不替代完整 Gold 的逐项审核与独立遗漏搜索。", "",
             "## 下一步", "", "人工试用规则后更新 G0；再冻结来源/运行契约与 baseline 设计，进入完整 Gold。付费 baseline 的模型及预算尚未确定。", ""]
    return "\n".join(body).encode()


def _derive_package(snapshot: Path, legacy: dict[str, bytes], prepared_at: str) -> tuple[dict, dict[str, bytes]]:
    """Deterministic derivation shared by preparation and independent replay."""
    _validate_prepared_at(prepared_at)
    manifest = verify_snapshot(snapshot)
    document = load_snapshot_document(snapshot)
    if any(manifest.get(key) != expected for key, expected in M0_IDENTITY.items()):
        raise ValueError("this review pilot is scoped to the fixed Alphabet FY2025 10-K")
    values = {name: _json(legacy[name]) for name in LEGACY_FILES}
    candidate, claims, spans, excerpt = (values[name] for name in LEGACY_FILES)
    model = business_map_from_dict(candidate)
    if candidate["company_id"] != "alphabet":
        raise ValueError("the candidate must belong to Alphabet")
    legacy_id = manifest.get("legacy_source_snapshot_id")
    identities = [candidate.get("metadata", {}).get("source_snapshot_id"),
                  claims.get("source_snapshot_id"), spans.get("source_snapshot_id"),
                  excerpt.get("source_snapshot_id")]
    if not legacy_id or any(identity != legacy_id for identity in identities):
        raise ValueError("legacy candidate, claims, spans, excerpt, and source expectations must share one identity")
    if not model.businesses or not model.evidence or not claims["claims"] or not spans["spans"]:
        raise ValueError("a review package requires nonempty businesses, evidence, claims, and exact spans")
    business_ids = {row.id for row in model.businesses}
    for claim in claims["claims"]:
        if any(key not in claim for key in _CLAIM_FIELDS):
            raise ValueError(f"claim lacks required review content: {claim.get('id')}")
        if claim.get("business_id") not in business_ids:
            raise ValueError(f"claim references an unknown business: {claim.get('id')}")
        if len(set(claim["evidence_ids"])) != len(claim["evidence_ids"]):
            raise ValueError(f"claim repeats evidence identities: {claim['id']}")
        if claim.get("basis") != "explicit":
            raise ValueError("mechanical rebinding currently supports explicit claims only; derived claims need rule review")
    for span in spans["spans"]:
        if any(key not in span for key in _SPAN_FIELDS):
            raise ValueError("an evidence span lacks required bilingual review content")
    audit = audit_evidence(document, candidate, excerpt, claims, spans)
    files = {f"{LEGACY_DIRECTORY}/{name}": legacy[name] for name in LEGACY_FILES}
    for name in ["manifest.json", *manifest["artifacts"]]:
        files[f"{SOURCE_DIRECTORY}/{name}"] = _read_regular(snapshot / name)
    input_paths = {name: f"{LEGACY_DIRECTORY}/{name}" for name in LEGACY_FILES[:-1]}
    input_paths.update(legacy_excerpt=f"{LEGACY_DIRECTORY}/review_excerpt.json",
                       new_source_manifest=f"{SOURCE_DIRECTORY}/manifest.json")
    audit["inputs"] = {name: fingerprint(path, files[path]) for name, path in input_paths.items()}
    if not audit["can_rebind_source"]:
        blocking = [issue for issue in audit["issues"] if issue["blocks_rebinding"]]
        raise ValueError("legacy references require manual investigation: " + json.dumps(blocking, ensure_ascii=False))
    seed = {"schema_version": PACKAGE_SCHEMA, "derivation_version": DERIVATION_VERSION,
            "inputs": audit["inputs"]}
    candidate_id = "m0-review-candidate-" + hashlib.sha256(encoded(seed)).hexdigest()[:16]

    # Project through the domain schema instead of copying arbitrary approval
    # extensions. Prior decisions survive only inside the immutable legacy inputs.
    fresh = model.to_dict()
    fresh["schema_version"] = "m0-review-business-map-v1"
    fresh["metadata"] = {"status": "candidate", "gold_status": "not_frozen",
                         "candidate_id": candidate_id, "benchmark_version": candidate_id,
                         "source_snapshot_id": manifest["source_snapshot_id"],
                         "authoring_method": "mechanical source rebinding; semantic review pending",
                         "derived_from_sha256": audit["inputs"]["business_map.json"]["sha256"]}
    if "financial_values_unit" in candidate.get("metadata", {}):
        fresh["metadata"]["financial_values_unit"] = candidate["metadata"]["financial_values_unit"]
    for item in (*fresh["businesses"], *fresh["relationships"]):
        item["review_status"] = "candidate"
    fresh_claims = {"schema_version": "m0-review-claims-v1", "benchmark_id": candidate_id,
                    "source_snapshot_id": manifest["source_snapshot_id"], "status": "candidate",
                    "claims": [{key: deepcopy(row[key]) for key in _CLAIM_FIELDS if key in row}
                               for row in claims["claims"]]}
    fresh_spans = {"schema_version": "m0-review-evidence-spans-v1", "candidate_id": candidate_id,
                   "source_snapshot_id": manifest["source_snapshot_id"], "status": "candidate",
                   "spans": [{key: deepcopy(row[key]) for key in _SPAN_FIELDS if key in row}
                             for row in spans["spans"]]}
    selected_ordinals = {e["paragraph_ordinal"] for e in fresh["evidence"]}
    source_excerpt = {"source_snapshot_id": manifest["source_snapshot_id"],
                      "purpose": "Exact source paragraphs for a new candidate; no translation or approval is inherited.",
                      "paragraphs": [asdict(p) for p in document.paragraphs if p.ordinal in selected_ordinals]}
    review = _review_questions(manifest["source_snapshot_id"], candidate_id)
    files.update({"legacy_audit.json": encoded(audit), "business_map.json": encoded(fresh),
                  "claims.json": encoded(fresh_claims), "evidence_spans.json": encoded(fresh_spans),
                  "review_excerpt.json": encoded(source_excerpt), "review_questions.json": encoded(review),
                  "REVIEW.zh-CN.md": _review_markdown(document, manifest["source_snapshot_id"], audit, review)})
    package = {"schema_version": PACKAGE_SCHEMA, "derivation_version": DERIVATION_VERSION,
               "package_id": candidate_id, "status": "candidate_pending_human_review",
               "prepared_at": prepared_at, "source_snapshot_id": manifest["source_snapshot_id"],
               "source_snapshot_path": SOURCE_DIRECTORY, "legacy_input_directory": LEGACY_DIRECTORY,
               "source_manifest_sha256": audit["inputs"]["new_source_manifest"]["sha256"],
               "automatic_adoption": False, "gold_status": "not_frozen",
               "artifacts": {name: fingerprint(name, raw) for name, raw in sorted(files.items())}}
    return package, files


def _verify_review(package_dir: Path, package: dict, *, has_manifest: bool) -> dict:
    if package_dir.is_symlink() or not package_dir.is_dir():
        raise ValueError("review package must be a regular directory")
    if package.get("schema_version") != PACKAGE_SCHEMA or not isinstance(package.get("artifacts"), dict):
        raise ValueError("unsupported review package manifest")
    artifacts = package["artifacts"]
    for name, record in artifacts.items():
        if (not isinstance(name, str) or not name or "\\" in name
                or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or PurePosixPath(name).as_posix() != name or name == "manifest.json"):
            raise ValueError("review artifact path must be a normalized path inside the package")
        if (not isinstance(record, dict) or record.get("path") != name
                or type(record.get("bytes")) is not int or record["bytes"] < 0
                or not isinstance(record.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])):
            raise ValueError(f"invalid artifact record: {name}")
    actual_files = set()
    expected_directories = {str(parent) for name in artifacts
                            for parent in PurePosixPath(name).parents if str(parent) != "."}
    for path in package_dir.rglob("*"):
        relative = path.relative_to(package_dir).as_posix()
        if path.is_symlink():
            raise ValueError(f"review package contains a symlink: {relative}")
        if path.is_file():
            actual_files.add(relative)
        elif not path.is_dir() or relative not in expected_directories:
            raise ValueError(f"unexpected review entry: {relative}")
    expected_files = set(artifacts) | ({"manifest.json"} if has_manifest else set())
    if actual_files != expected_files:
        raise ValueError("review package file coverage does not match its manifest")
    for name, record in artifacts.items():
        if fingerprint(name, _read_regular(package_dir / name)) != record:
            raise ValueError(f"review artifact integrity mismatch: {name}")
    legacy = {name: _read_regular(package_dir / LEGACY_DIRECTORY / name) for name in LEGACY_FILES}
    replayed, files = _derive_package(package_dir / SOURCE_DIRECTORY, legacy, package.get("prepared_at"))
    if package != replayed:
        raise ValueError("review manifest does not match independent source and input replay")
    for name, expected in files.items():
        if _read_regular(package_dir / name) != expected:
            raise ValueError(f"review artifact differs from independent replay: {name}")
    return package


def verify_review(package_dir: Path) -> dict:
    """Read-only verification and replay using only the package's own inputs.

    This checks the untouched preparation package. Human answers belong in a
    later review version and are never inferred from this package's status.
    """
    package_dir = Path(package_dir)
    package = _json(_read_regular(package_dir / "manifest.json"))
    return _verify_review(package_dir, package, has_manifest=True)


def _write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def prepare_review(snapshot: Path, candidate_dir: Path, excerpt_path: Path, output: Path,
                   *, prepared_at: str | None = None) -> dict:
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"review output already exists: {output}")
    legacy = {name: _read_regular(Path(candidate_dir) / name) for name in LEGACY_FILES[:-1]}
    legacy["review_excerpt.json"] = _read_regular(Path(excerpt_path))
    package, files = _derive_package(Path(snapshot), legacy, prepared_at or datetime.now(UTC).isoformat())
    output.mkdir(parents=True, exist_ok=False)
    try:
        for name, raw in files.items():
            _write_new(output / name, raw)
        _verify_review(output, package, has_manifest=False)
        temporary = output / ".manifest.json.tmp"
        manifest_bytes = encoded(package)
        _write_new(temporary, manifest_bytes)
        if _read_regular(temporary) != manifest_bytes:
            raise ValueError("review manifest write verification failed")
        temporary.replace(output / "manifest.json")
    except BaseException:
        shutil.rmtree(output)
        raise
    return package


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", type=Path)
    mode.add_argument("--verify", type=Path, metavar="REVIEW_PACKAGE")
    parser.add_argument("--candidate", type=Path, default=ROOT / "benchmarks/alphabet_2025_business_map/v0.1-candidate")
    parser.add_argument("--excerpt", type=Path, default=ROOT / "data/source_documents/alphabet_2025_10k/review_excerpt.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.snapshot is not None and args.output is None:
        parser.error("--output is required when preparing a review package")
    if args.verify is not None and args.output is not None:
        parser.error("--output does not apply to read-only verification")
    try:
        package = (verify_review(args.verify) if args.verify is not None
                   else prepare_review(args.snapshot, args.candidate, args.excerpt, args.output))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Review preparation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(package, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
