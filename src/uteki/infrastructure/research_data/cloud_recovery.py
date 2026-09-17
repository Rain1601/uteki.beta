"""A source-only Data-side recovery adapter; explicitly NOT general retrieval."""
import copy

from .cloud_spike import digest, encoded, extract

VERSION = "cloud-rule-source-recovery-v0.1"


def withhold_fact(snapshot, predicate="revenue", period="FY2025"):
    result = copy.deepcopy(snapshot)
    removed = [f for f in result["facts"] if f["predicate"] == predicate and f["period"] == period]
    if len(removed) != 1:
        raise ValueError("gap fixture must remove exactly one fact")
    result["facts"] = [f for f in result["facts"] if f not in removed]
    used = {e for f in result["facts"] for e in f["evidence_ids"]}
    result["evidence"] = {k: v for k, v in result["evidence"].items() if k in used}
    result["parent_snapshot_id"] = snapshot["snapshot_id"]
    result["coverage"]["status"] = "synthetic incomplete snapshot; not the approved original"
    result.pop("snapshot_id")
    result["snapshot_id"] = "gap-" + digest(encoded(result))[:16]
    return result


def recover_from_source(source_dir, source_sha256, predicate, period):
    scope = {"source_sha256": source_sha256, "adapter": VERSION,
             "sections": ["Part I Item 1", "Part II Item 8"],
             "method": "existing source-only deterministic Cloud extractor; fixed filing/metrics"}
    if predicate not in {"revenue", "operating_income"} or period not in {"FY2023", "FY2024", "FY2025"}:
        return {"status": "unsupported_scope", "results": [], "scope": scope,
                "reason": "No claim that the filing lacks this information"}
    # Re-read raw SEC HTML and verified index. Never load the approved/withheld answer.
    extracted = extract(source_dir)
    if extracted["source_sha256"] != source_sha256:
        raise ValueError("recovery source does not match the pinned filing")
    scope["index_id"] = extracted["index_id"]
    selected = [copy.deepcopy(f) for f in extracted["facts"] if f["predicate"] == predicate and f["period"] == period]
    if len(selected) != 1:
        return {"status": "not_found_in_supported_scope", "results": [], "scope": scope}
    fact = selected[0]
    fact["fact_id"] = "recovered-" + fact["fact_id"]
    fact["review_status"] = "pending"
    fact["retrieval_origin"] = "source_recovery"
    return {"status": "recovered_candidate", "results": [fact], "scope": scope,
            "evidence": {eid: extracted["evidence"][eid] for eid in fact["evidence_ids"]},
            "available_at": extracted["available_at"], "review_status": "pending"}
