from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "evidence-bundle-v0.1"
SOURCE_POLICY_ID = "alphabet-fy2025-10k-only-v0.1"
QUERY_ID = "rdq-alphabet-2025-10k-business-map-v0.1"
METRIC_FIELDS = {"revenue_2025", "operating_income_2025", "operating_loss_2025"}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _metric_from_claim(claim: dict[str, Any]) -> dict[str, Any]:
    match = re.fullmatch(r"\$(\d+(?:\.\d+)?)B(?: loss)?", claim["value_en"])
    if match is None:
        raise ValueError(f"unsupported metric value: {claim['id']}={claim['value_en']}")
    value = round(float(match.group(1)) * 1000)
    if claim["field"].startswith("operating_loss"):
        value = -value
    metric = claim["field"].removesuffix("_2025")
    return {
        "metric_id": f"metric-{claim['business_id']}-{metric}",
        "claim_id": claim["id"],
        "business_id": claim["business_id"],
        "metric": metric,
        "period": "FY2025",
        "value": value,
        "unit": "USD millions",
        "reported_value_en": claim["value_en"],
        "reported_value_zh": claim["value_zh"],
        "evidence_ids": claim["evidence_ids"],
    }


def build_research_data_artifacts(
    benchmark_dir: Path,
    document_snapshot_dir: Path,
    output_dir: Path,
    *,
    generated_at: str,
) -> dict[str, Any]:
    business_map_path = benchmark_dir / "business_map.json"
    claims_path = benchmark_dir / "claims.json"
    spans_path = benchmark_dir / "evidence_spans.json"
    decisions_path = benchmark_dir / "review_decisions.json"
    index_manifest_path = document_snapshot_dir / "indexes/v0.1/manifest.json"
    source_manifest_path = document_snapshot_dir / "manifest.json"

    business_map = _read_json(business_map_path)
    claims_document = _read_json(claims_path)
    spans_document = _read_json(spans_path)
    decisions = _read_json(decisions_path)
    index_manifest = _read_json(index_manifest_path)
    source_manifest = _read_json(source_manifest_path)

    source_snapshot_id = source_manifest["source_snapshot_id"]
    if claims_document["source_snapshot_id"] != source_snapshot_id:
        raise ValueError("claims and source snapshot differ")
    if spans_document["source_snapshot_id"] != source_snapshot_id:
        raise ValueError("evidence spans and source snapshot differ")
    if business_map["metadata"]["source_snapshot_id"] != source_snapshot_id:
        raise ValueError("Business Map and source snapshot differ")

    evidence_by_id = {item["id"]: item for item in business_map["evidence"]}
    if len(evidence_by_id) != len(business_map["evidence"]):
        raise ValueError("Business Map evidence ids must be unique")

    claims = claims_document["claims"]
    spans = spans_document["spans"]
    span_pairs = [(item["claim_id"], item["evidence_id"]) for item in spans]
    if len(span_pairs) != len(set(span_pairs)):
        raise ValueError("claim-to-evidence span pairs must be unique")
    available_pairs = set(span_pairs)
    for claim in claims:
        missing = [item for item in claim["evidence_ids"] if (claim["id"], item) not in available_pairs]
        if missing:
            raise ValueError(f"claim {claim['id']} lacks exact spans for: {', '.join(missing)}")

    evidence_links: list[dict[str, Any]] = []
    quotes_by_evidence: dict[str, dict[str, list[str]]] = {}
    for span in spans:
        evidence = evidence_by_id[span["evidence_id"]]
        evidence_links.append(
            {
                "link_id": f"el-{span['claim_id']}--{span['evidence_id']}",
                "claim_id": span["claim_id"],
                "evidence_id": span["evidence_id"],
                "source_snapshot_id": source_snapshot_id,
                "document_id": evidence["document_id"],
                "section_path": evidence["section_path"],
                "paragraph_ordinal": evidence["paragraph_ordinal"],
                "text_hash": evidence["text_hash"],
                "source_url": evidence["source_url"],
                "support": evidence["support"],
                "quote_en": span["quote_en"],
                "quote_zh": span["quote_zh"],
            }
        )
        grouped = quotes_by_evidence.setdefault(span["evidence_id"], {"en": [], "zh": []})
        if span["quote_en"] not in grouped["en"]:
            grouped["en"].append(span["quote_en"])
        if span["quote_zh"] not in grouped["zh"]:
            grouped["zh"].append(span["quote_zh"])

    document_context = [
        {
            "evidence_id": evidence_id,
            "source_snapshot_id": source_snapshot_id,
            "document_id": evidence["document_id"],
            "section_path": evidence["section_path"],
            "paragraph_ordinal": evidence["paragraph_ordinal"],
            "text_hash": evidence["text_hash"],
            "source_url": evidence["source_url"],
            "support": evidence["support"],
            "quotes_en": quotes_by_evidence.get(evidence_id, {}).get("en", []),
            "quotes_zh": quotes_by_evidence.get(evidence_id, {}).get("zh", []),
        }
        for evidence_id, evidence in evidence_by_id.items()
    ]
    metrics = [_metric_from_claim(item) for item in claims if item["field"] in METRIC_FIELDS]

    diagnostics = [
        {
            "code": "business_map_candidate_not_frozen",
            "severity": "warning",
            "message": "The v0.2 Business Map is a candidate and must not be treated as Gold.",
        },
        {
            "code": "single_period_metrics_only",
            "severity": "info",
            "message": "This bundle contains FY2025 metric points and no cross-period change objects.",
        },
    ]
    pending_decisions = [
        item for item in decisions.get("decisions", []) if item.get("status") == "accepted_for_next_candidate"
    ]
    if pending_decisions:
        diagnostics.append(
            {
                "code": "pending_business_map_review_decisions",
                "severity": "warning",
                "message": f"{len(pending_decisions)} accepted review decision(s) target a later candidate.",
            }
        )

    input_hashes = {
        str(path.relative_to(benchmark_dir.parent.parent.parent)): _sha256(path.read_bytes())
        for path in (business_map_path, claims_path, spans_path, decisions_path)
    }
    input_hashes[str(index_manifest_path.relative_to(document_snapshot_dir.parent.parent.parent))] = _sha256(
        index_manifest_path.read_bytes()
    )
    snapshot_seed = _json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "source_snapshot_id": source_snapshot_id,
            "business_map_version": business_map["metadata"]["benchmark_version"],
            "input_hashes": input_hashes,
        }
    )
    data_snapshot_id = f"rds-{_sha256(snapshot_seed)[:16]}"

    core = {
        "schema_version": SCHEMA_VERSION,
        "query_id": QUERY_ID,
        "company_id": business_map["company_id"],
        "status": "candidate",
        "source_policy_id": SOURCE_POLICY_ID,
        "data_snapshot_id": data_snapshot_id,
        "source_snapshot_ids": [source_snapshot_id],
        "document_index_ids": [index_manifest["index_id"]],
        "business_map_version": business_map["metadata"]["benchmark_version"],
        "business_map_ref": "business_map.json",
        "source_as_of": source_manifest["filed_at"],
        "generated_at": generated_at,
        "claims": claims,
        "metrics": metrics,
        "changes": [],
        "evidence_links": evidence_links,
        "document_context": document_context,
        "unknowns": business_map["unknowns"],
        "quality_diagnostics": diagnostics,
    }
    bundle_id = f"eb-{_sha256(_json_bytes(core))[:16]}"
    bundle = {**core, "bundle_id": bundle_id}
    query = {
        "query_id": QUERY_ID,
        "company_id": business_map["company_id"],
        "question": "What business structure, factual claims, and disclosed FY2025 metrics are available for Alphabet?",
        "requested_data_types": ["business_map", "claims", "metrics", "evidence", "unknowns"],
        "periods": ["FY2025"],
        "source_policy_id": SOURCE_POLICY_ID,
        "related_research_ids": [],
        "minimum_evidence_level": "source_located",
        "created_at": generated_at,
    }

    files = {
        "business_map.json": _json_bytes(business_map),
        "evidence_bundle.json": _json_bytes(bundle),
        "query.json": _json_bytes(query),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        (output_dir / filename).write_bytes(content)

    manifest = {
        "schema_version": "research-data-manifest-v0.1",
        "release_version": output_dir.name,
        "status": "candidate",
        "company_id": business_map["company_id"],
        "source_policy_id": SOURCE_POLICY_ID,
        "data_snapshot_id": data_snapshot_id,
        "bundle_id": bundle_id,
        "business_map_version": business_map["metadata"]["benchmark_version"],
        "source_snapshot_ids": [source_snapshot_id],
        "document_index_ids": [index_manifest["index_id"]],
        "input_hashes": input_hashes,
        "counts": {
            "businesses": len(business_map["businesses"]),
            "claims": len(claims),
            "metrics": len(metrics),
            "changes": 0,
            "evidence_links": len(evidence_links),
            "document_contexts": len(document_context),
            "unknowns": len(business_map["unknowns"]),
            "quality_diagnostics": len(diagnostics),
        },
        "artifacts": {
            filename: {"sha256": _sha256(content), "bytes": len(content)}
            for filename, content in files.items()
        },
    }
    (output_dir / "manifest.json").write_bytes(_json_bytes(manifest))
    return manifest
