"""Evidence-preserving transcript records for a bounded guidance experiment.

Uses existing speaker/Q&A parsing. Topic matches are navigation tags, never an
exhaustive semantic classifier; quantitative guidance supports explicit ranges.
"""
import json
import re
from decimal import Decimal
from pathlib import Path

from uteki.agents.reading.document_reader import DocumentReader
from uteki.infrastructure.research_data.financial_records import digest

VERSION = "transcript-records-v0.2"
TOPIC = re.compile(r"\bcapex\b|capital expenditures|\bcloud\b", re.I)
RANGE = re.compile(r"\bCapEx\b.*?\brange\s+of\s+\$(\d+(?:\.\d+)?)\s+(billion|million)\s+to\s+\$(\d+(?:\.\d+)?)\s+(billion|million)", re.I)
YEAR = re.compile(r"\b(20\d{2})\b")
CONDITION = re.compile(r"keep in mind|subject to|depend|variability|provided that", re.I)
TOPIC_BOUNDARY = re.compile(r"^(?:In terms of expenses|Turning to|Moving to|Next,|Now,|First,|Today, I.{0,12}(?:provide|discuss))", re.I)


def guidance_context(reader, block, following=3):
    """Opt-in local overlay: same speaker/turn, explicit boundary, no index edits."""
    if not 0 <= following <= 3:
        raise ValueError("guidance_context_limit")
    baseline = reader.read("document", block["block_id"], 1)
    if block.get("exchange_id"):
        return baseline["blocks"]
    result = [block]
    pos = reader.positions[block["block_id"]]
    for candidate in reader.blocks[pos + 1:pos + 1 + following]:
        if (candidate.get("turn_id") != block.get("turn_id")
                or candidate.get("speaker") != block.get("speaker")
                or candidate.get("section") != block.get("section")
                or TOPIC_BOUNDARY.search(candidate["text"])):
            break
        result.append(candidate)
    return result


def extract_transcript_records(source_dir, index_dir, *, company_id, fiscal_calendar, expanded_guidance=False):
    if not isinstance(company_id, str) or not company_id.strip():
        raise ValueError("explicit company_id is required")
    if fiscal_calendar != "calendar":
        raise ValueError("unsupported fiscal calendar; do not infer calendar dates")
    source_dir = Path(source_dir)
    manifest = json.loads((source_dir / "manifest.json").read_text())
    source_sha = digest((source_dir / "source.pdf").read_bytes())
    if source_sha != manifest["content_sha256"]:
        raise ValueError("source_hash_mismatch")
    if manifest.get("company_id", company_id) != company_id:
        raise ValueError("source company differs from explicit company_id")
    reader = DocumentReader(index_dir)
    if reader.manifest["source_sha256"] != source_sha:
        raise ValueError("source_index_mismatch")
    evidence, records, excluded = {}, [], []

    def cite(block):
        eid = "tev-" + digest([manifest["source_snapshot_id"], block["block_id"]])[:20]
        evidence[eid] = {"evidence_id": eid, "source_snapshot_id": manifest["source_snapshot_id"],
                         "source_sha256": source_sha, "document_id": manifest["document_id"],
                         "index_id": reader.index["index_id"], "block_id": block["block_id"],
                         "text_hash": block["text_hash"], "quote": block["text"],
                         "start": 0, "end": len(block["text"]), "speaker": block.get("speaker"),
                         "speaker_role": block.get("speaker_role"), "turn_id": block.get("turn_id"),
                         "exchange_id": block.get("exchange_id"), "pdf_page": block.get("pdf_page"),
                         "bbox": block.get("bbox"), "source_url": manifest["source_url"]}
        return eid

    for block in reader.blocks:
        if not TOPIC.search(block["text"]):
            continue
        if block.get("speaker_role") != "management":
            excluded.append({"block_id": block["block_id"], "role": block.get("speaker_role"),
                             "reason": "not_a_management_statement; retained in full exchange"})
            continue
        eid = cite(block)
        record = {"record_type": "ManagementStatement", "source_block_id": block["block_id"],
                  "source_snapshot_id": manifest["source_snapshot_id"], "quote": block["text"],
                  "speaker": block.get("speaker"), "speaker_role": "management", "section": block.get("section"),
                  "exchange_id": block.get("exchange_id"), "evidence_ids": [eid],
                  "available_at": manifest["published_at"], "assertion_status": "attributed_statement_not_verified_fact",
                  "semantic_review": "pending", "topic_selection": "literal_capex_or_cloud"}
        record["record_id"] = "statement-" + digest([record["source_snapshot_id"], block["block_id"]])[:20]
        records.append(record)
        match = RANGE.search(block["text"])
        if not match:
            continue
        years = YEAR.findall(block["text"][:match.start()])
        if len(set(years)) != 1:
            excluded.append({"block_id": block["block_id"], "reason": "guidance_target_year_ambiguous"})
            continue
        low, low_unit, high, high_unit = match.groups()
        lo = Decimal(low) * (10 ** (9 if low_unit.lower() == "billion" else 6))
        hi = Decimal(high) * (10 ** (9 if high_unit.lower() == "billion" else 6))
        if lo > hi:
            raise ValueError("reversed_guidance_range")
        context = guidance_context(reader, block) if expanded_guidance else reader.read("document", block["block_id"], 1)["blocks"]
        condition_blocks = [b for b in context if CONDITION.search(b["text"])]
        year = int(years[0])
        guidance = {"record_type": "Guidance", "source_block_id": block["block_id"],
                    "source_snapshot_id": manifest["source_snapshot_id"], "entity_id": company_id,
                    "metric": "management_capex_guidance", "value_kind": "management_guidance",
                    "unit": "USD", "range": {"low": str(lo), "high": str(hi)},
                    "target_period": {"kind": "year", "start": f"{year}-01-01", "end": f"{year}-12-31"},
                    "issued_at": manifest["published_at"], "speaker": block.get("speaker"),
                    "quote": block["text"], "evidence_ids": [cite(b) for b in context],
                    "condition_evidence_ids": [cite(b) for b in condition_blocks],
                    "context_policy": "same_turn_next_3_until_topic_boundary_v2" if expanded_guidance else "existing_reader_one_block",
                    "qualifier_coverage": "bounded_context_requires_review" if expanded_guidance else "outside_anchor_not_checked",
                    "definition": "Management CapEx terminology; equivalence to GAAP cash-payments metric not assumed",
                    "semantic_review": "pending"}
        guidance["record_id"] = "guidance-" + digest(guidance)[:20]
        records.append(guidance)
    exchanges = sorted({r.get("exchange_id") for r in records if r.get("exchange_id")})
    for exchange in exchanges:
        blocks = [b for b in reader.blocks if b.get("exchange_id") == exchange]
        records.append({"record_type": "QAExchange", "record_id": "qa-" + digest([source_sha, exchange])[:20],
                        "source_snapshot_id": manifest["source_snapshot_id"], "exchange_id": exchange,
                        "evidence_ids": [cite(b) for b in blocks],
                        "question_refs": [cite(b) for b in blocks if b.get("speaker_role") == "analyst"],
                        "answer_refs": [cite(b) for b in blocks if b.get("speaker_role") == "management"],
                        "context_policy": "complete_existing_exchange"})
    return {"schema_version": VERSION, "expanded_guidance": expanded_guidance,
            "source_snapshot_id": manifest["source_snapshot_id"], "records": records, "evidence": evidence,
            "coverage": {"total_blocks": len(reader.blocks), "topic_matched_blocks": sum(bool(TOPIC.search(b["text"])) for b in reader.blocks),
                         "excluded": excluded, "scope": "literal capital-expenditure/Cloud topic selection; no semantic recall claim"},
            "limits": ["Existing source speaker parsing retained", "Explicit CapEx range and year only",
                       "Management explanation not established causality", "Qualitative statements preserved as quotes, not numeric guidance"]}
