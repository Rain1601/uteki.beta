"""Offline candidate-evidence and archive contract smoke; no model or real adoption.

Only the committed v0.1 candidate and review excerpts are read. The real archive
Store is exercised in a disposable directory, with explicitly simulated review.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
# Direct execution works from any cwd and leaves no import caches in the checkout.
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))

from uteki.agents.research_archive import ArchiveError, Store
from uteki.domain.business_map import business_map_from_dict
from uteki.infrastructure.document_sources.sec import text_hash


INPUT_FILES = {
    "business_map": "benchmarks/alphabet_2025_business_map/v0.1-candidate/business_map.json",
    "claims": "benchmarks/alphabet_2025_business_map/v0.1-candidate/claims.json",
    "spans": "benchmarks/alphabet_2025_business_map/v0.1-candidate/evidence_spans.json",
    "manifest": "data/source_documents/alphabet_2025_10k/manifest.json",
    "excerpt": "data/source_documents/alphabet_2025_10k/review_excerpt.json",
}
LIMITATIONS = [
    "Offline contract smoke / 离线契约检查；不运行模型或访问网络。",
    "Simulated review and adoption only / 审核与采纳仅在临时归档中模拟，不代表真实人工批准。",
    "Candidate data, not frozen Gold / 使用候选数据，不发布 EvidenceBundle，也不修改 Gold。",
    "Checks excerpt integrity and exact English citations, not semantic support, numeric accuracy, translation quality or research completeness / 校验摘录完整性和英文引文，不证明研究结论正确。",
    "The complete SEC source is not committed; its manifest hash cannot be independently verified here / 完整 SEC 原文未提交，此处无法独立核验其整体哈希。",
    "Default scope is only alphabet-definition → e-overview → paragraph 55; use --strict-all to require every candidate chain to pass / 默认只验证一条明确选择的证据链；--strict-all 要求全集通过。",
]
SELECTED_CLAIM_ID = "alphabet-definition"


class SmokeError(ValueError):
    """A candidate-evidence or archive contract did not hold."""


def require(condition, message):
    # Unlike assert, checks must remain active under python -O.
    if not condition:
        raise SmokeError(message)


def unique_rows(rows, key, label):
    result = {}
    for row in rows:
        identity = row[key]
        require(identity not in result, f"Duplicate {label}: {identity}")
        result[identity] = row
    return result


def validate_candidate(root=ROOT, *, strict_all=False):
    """Validate stored references against freshly hashed excerpt text, read-only."""
    documents, fingerprints = {}, {}
    for name, relative in INPUT_FILES.items():
        raw = (Path(root) / relative).read_bytes()
        documents[name] = json.loads(raw)
        fingerprints[relative] = hashlib.sha256(raw).hexdigest()
    source = documents["manifest"]
    candidate = documents["business_map"]
    snapshot = source["source_snapshot_id"]
    for name in ("claims", "spans", "excerpt"):
        require(documents[name]["source_snapshot_id"] == snapshot, f"Source snapshot mismatch: {name}")
    require(candidate["metadata"]["source_snapshot_id"] == snapshot, "Business Map snapshot mismatch")
    require(candidate["document_id"] == source["document_id"], "Business Map document mismatch")
    require(candidate["metadata"].get("gold_status") == "not_frozen", "Expected an unfrozen candidate, not Gold")
    require(documents["claims"].get("status") == "candidate", "Claims must remain candidates")
    business_map = business_map_from_dict(candidate)
    business_ids = {business.id for business in business_map.businesses}
    all_evidence = unique_rows(candidate["evidence"], "id", "evidence")
    all_paragraphs = unique_rows(documents["excerpt"]["paragraphs"], "ordinal", "paragraph")
    all_claims = unique_rows(documents["claims"]["claims"], "id", "claim")
    require(SELECTED_CLAIM_ID in all_claims, f"Missing selected claim: {SELECTED_CLAIM_ID}")
    claims = all_claims if strict_all else {SELECTED_CLAIM_ID: all_claims[SELECTED_CLAIM_ID]}
    selected_ids = {identity for claim in claims.values() for identity in claim["evidence_ids"]}
    require(selected_ids <= all_evidence.keys(), f"Claim references missing evidence: {sorted(selected_ids - all_evidence.keys())}")
    evidence = all_evidence if strict_all else {identity: all_evidence[identity] for identity in selected_ids}
    selected_ordinals = {item["paragraph_ordinal"] for item in evidence.values()}
    require(selected_ordinals <= all_paragraphs.keys(),
            f"Missing excerpt paragraph for evidence: {sorted(selected_ordinals - all_paragraphs.keys())}")
    paragraphs = all_paragraphs if strict_all else {ordinal: all_paragraphs[ordinal] for ordinal in selected_ordinals}
    # Expose corruption outside the selected chain instead of silently hiding it.
    integrity_findings = [
        {"code": "excerpt_text_hash_mismatch", "paragraph_ordinal": ordinal,
         "stored_hash": paragraph["text_hash"], "recomputed_hash": text_hash(paragraph["text"]),
         "in_verified_scope": ordinal in paragraphs}
        for ordinal, paragraph in all_paragraphs.items()
        if text_hash(paragraph["text"]) != paragraph["text_hash"]
    ]
    require(bool(evidence and paragraphs and claims), "Candidate evidence, paragraphs and claims must be nonempty")

    for ordinal, paragraph in paragraphs.items():
        require(text_hash(paragraph["text"]) == paragraph["text_hash"],
                f"Excerpt text hash mismatch at paragraph {ordinal}")
    for identity, item in evidence.items():
        require(item["document_id"] == source["document_id"], f"Evidence document mismatch: {identity}")
        require(item["source_url"] == source["source_url"], f"Evidence source URL mismatch: {identity}")
        paragraph = paragraphs.get(item["paragraph_ordinal"])
        require(paragraph is not None, f"Missing excerpt paragraph for evidence: {identity}")
        require(text_hash(paragraph["text"]) == item["text_hash"], f"Evidence text hash mismatch: {identity}")

    spans = {}
    for span in documents["spans"]["spans"]:
        if not strict_all and span["claim_id"] not in claims:
            continue
        pair = span["claim_id"], span["evidence_id"]
        require(pair not in spans, f"Duplicate claim/evidence span: {pair}")
        require(pair[0] in claims, f"Span references missing claim: {pair[0]}")
        require(pair[1] in evidence, f"Span references missing evidence: {pair[1]}")
        require(pair[1] in claims[pair[0]]["evidence_ids"], f"Span is not cited by claim: {pair}")
        paragraph = paragraphs[evidence[pair[1]]["paragraph_ordinal"]]
        require(isinstance(span["quote_en"], str) and bool(span["quote_en"].strip())
                and span["quote_en"] in paragraph["text"], f"Quote is not an exact excerpt substring: {pair}")
        spans[pair] = span
    report_claims = []
    for identity, claim in claims.items():
        require(claim["business_id"] in business_ids, f"Claim references missing business: {identity}")
        require(bool(claim["evidence_ids"]), f"Claim has no evidence: {identity}")
        citations = []
        for evidence_id in claim["evidence_ids"]:
            require(evidence_id in evidence, f"Claim references missing evidence: {evidence_id}")
            require((identity, evidence_id) in spans, f"Missing claim/evidence span: {identity}, {evidence_id}")
            item = evidence[evidence_id]
            citations.append({
                "evidence_id": evidence_id, "source_snapshot_id": snapshot,
                "document_id": item["document_id"], "paragraph_ordinal": item["paragraph_ordinal"],
                "text_hash": item["text_hash"], "source_url": item["source_url"],
                "quote_en": spans[identity, evidence_id]["quote_en"],
            })
        report_claims.append({"claim_id": identity,
                              "text": f"{claim['label_en']}: {claim['value_en']}\n{claim['label_zh']}：{claim['value_zh']}",
                              "citations": citations})
    return {
        "source": source, "company_id": business_map.company_id,
        "input_sha256": fingerprints,
        "scope": {"mode": "all_candidate_chains" if strict_all else "selected_claim",
                  "claim_ids": list(claims), "evidence_ids": sorted(evidence),
                  "paragraph_ordinals": sorted(paragraphs)},
        "input_counts": {"businesses": len(business_ids), "claims": len(all_claims),
                         "evidence": len(all_evidence), "excerpt_paragraphs": len(all_paragraphs),
                         "quote_spans": len(documents["spans"]["spans"])},
        "integrity_findings": integrity_findings,
        "counts": {"claims": len(claims), "evidence": len(evidence),
                   "exact_quote_spans": len(spans), "rehashed_excerpt_paragraphs": len(paragraphs)},
        "answer": {"status": "candidate", "claims": report_claims, "limitations": list(LIMITATIONS)},
    }


def run_smoke(root=ROOT, *, strict_all=False):
    verified = validate_candidate(root, strict_all=strict_all)
    source = verified["source"]
    actor = "offline-smoke-simulated-reviewer"
    now = datetime.now(timezone.utc).isoformat()
    original = {
        "id": "offline-candidate-contract-smoke", "company_id": verified["company_id"],
        "researcher_id": "offline-contract-smoke", "scope": "candidate-evidence-contract",
        "primary_document_id": source["document_id"], "source_snapshot_id": source["source_snapshot_id"],
        "material_available_at": source["filed_at"], "knowledge_cutoff_at": source["filed_at"],
        "run_started_at": now, "created_at": now, "validation_status": "passed",
        "validation_method": "offline_excerpt_hash_and_exact_quote_only",
        "answer": deepcopy(verified["answer"]), "simulation_only": True,
    }
    with TemporaryDirectory(prefix="uteki-contract-smoke-") as temporary:
        archive_path = Path(temporary) / "archive.json"
        store = Store(archive_path)

        def context():
            return store.context(original["company_id"], original["scope"],
                                 datetime.now(timezone.utc).isoformat(), researcher_id=original["researcher_id"])

        candidate = store.seed([original])[0]
        require(candidate["status"] == "candidate", "Seed implicitly adopted the candidate")
        require(context()["baseline_snapshot_id"] is None, "Unadopted candidate entered baseline")
        edited_answer = deepcopy(original["answer"])
        edited_answer["limitations"].append("Simulated revision / 模拟修订：仅验证审核后显式采纳流程。")
        edited = store.act(candidate["id"], "edit", candidate["revision"], answer=edited_answer,
                           reason="Offline contract smoke: simulate an edit", actor=actor)["snapshot"]
        require(edited["id"] != candidate["id"] and edited["parent_snapshot_id"] == candidate["id"],
                "Edit did not create a separate candidate revision")
        before_rejection = archive_path.read_bytes()
        try:
            store.act(edited["id"], "adopt", edited["revision"], actor=actor)
        except ArchiveError as exc:
            require("Evidence validation must pass" in str(exc), "Adoption failed for an unexpected reason")
        else:
            raise SmokeError("Unreviewed revision was adopted")
        require(archive_path.read_bytes() == before_rejection, "Rejected adoption changed archive state")
        reviewed = store.act(edited["id"], "review", edited["revision"], actor=actor,
                             review_notes="SIMULATED REVIEW ONLY: offline contract, not human approval or semantic verification.")["snapshot"]
        require(reviewed["status"] == "candidate" and context()["baseline_snapshot_id"] is None,
                "Review implicitly adopted a candidate or loaded it as baseline")
        adopted = store.act(reviewed["id"], "adopt", reviewed["revision"], actor=actor,
                            expected_slot_revision=reviewed["slot_revision"],
                            reason="Explicit simulated adoption in disposable archive only")["snapshot"]
        require(adopted["status"] == "adopted", "Explicit simulated adoption did not succeed")
        store = Store(archive_path)
        history = {row["id"]: row for row in store.list()}
        require(history[candidate["id"]]["answer"] == original["answer"], "Original report changed")
        require(history[candidate["id"]]["status"] == "candidate", "Original candidate status changed")
        require(history[edited["id"]]["answer"] == edited_answer, "Edited report did not survive reload")
        require(context()["baseline_snapshot_ids"] == [edited["id"]], "Baseline differs from explicit adoption")
        lineage = [row["id"] for row in history[edited["id"]]["revision_lineage"]]
        require(lineage == [edited["id"], candidate["id"]], "Revision history lost its original report")
        events = json.loads(archive_path.read_text())["audit_events"]
        actions = [event["action"] for event in events]
        require(actions == ["seed", "edit", "review", "adopt"], "Archive audit history is incomplete")
        workflow = {
            "actions": actions, "snapshots_after_reload": len(history),
            "unreviewed_adoption_rejected_without_write": True,
            "candidate_and_reviewed_revision_excluded_from_baseline": True,
            "original_report_preserved": True, "revision_history_preserved": True,
            "baseline_requires_explicit_adoption": True, "simulation_only": True,
        }
    require(not archive_path.parent.exists(), "Temporary archive was not removed")
    return {
        "status": "passed", "check": "offline_research_workflow_contract",
        "source_snapshot_id": source["source_snapshot_id"], "document_id": source["document_id"],
        "source_url": source["source_url"], "counts": verified["counts"],
        "scope": verified["scope"], "input_counts": verified["input_counts"],
        "all_candidate_chains_validated": strict_all,
        "full_excerpt_hash_check": "failed" if verified["integrity_findings"] else "passed",
        "integrity_findings": verified["integrity_findings"],
        "input_sha256": verified["input_sha256"], "workflow": workflow,
        "temporary_archive_removed": True, "limitations": list(LIMITATIONS),
    }


def main(argv=None, *, root=ROOT):
    parser = argparse.ArgumentParser(description="Offline excerpt and disposable archive contract smoke; simulated review only")
    parser.add_argument("--strict-all", action="store_true", help="Require every committed candidate evidence chain to pass (known paragraph 90 integrity issue currently fails)")
    args = parser.parse_args(argv)
    try:
        result = run_smoke(root, strict_all=args.strict_all)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "failed", "check": "offline_research_workflow_contract",
                          "error_type": type(exc).__name__, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
