"""Source-only Google Cloud rule baseline and bounded retrieval spike.

This deliberately narrow extractor is not a general business or LLM extractor.
It never reads a benchmark. References are evaluated in a separate process.
"""
from __future__ import annotations

import copy
import gzip
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from lxml import html
from .adapters.legacy_alphabet import require_legacy_alphabet_source

VERSION = "cloud-source-rules-v0.1"


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encoded(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def extract(source_dir: Path) -> dict:
    manifest = json.loads((source_dir / "manifest.json").read_text())
    raw = gzip.decompress((source_dir / "source.html.gz").read_bytes())
    if digest(raw) != manifest["content_sha256"]:
        raise ValueError("source hash mismatch")
    require_legacy_alphabet_source(manifest)
    index_dir = source_dir / "indexes/v0.1"
    index_manifest = json.loads((index_dir / "manifest.json").read_text())
    for name, expected in index_manifest["artifacts"].items():
        if digest((index_dir / name).read_bytes()) != expected["sha256"]:
            raise ValueError("index artifact hash mismatch")
    index = json.loads((index_dir / "index.json").read_text())
    if index_manifest["source_sha256"] != digest(raw):
        raise ValueError("index/source mismatch")
    blocks = [json.loads(line) for line in (index_dir / "blocks.jsonl").read_text().splitlines()]
    by_id = {b["block_id"]: b for b in blocks}
    tree = html.document_fromstring(raw, parser=html.HTMLParser(encoding="utf-8"))
    nodes = [n for n in index["nodes"] if n["kind"] == "item" and
             (n["part_number"], n["item_number"]) in {("I", "1"), ("II", "8")}]
    if len(nodes) != 2:
        raise ValueError("required legal sections unavailable")
    selected = [b for b in blocks if any(by_id[n["start_block_id"]]["ordinal"] <= b["ordinal"] <=
                 by_id[n["end_block_id"]]["ordinal"] for n in nodes)]
    facts, evidence = [], {}

    def cite(block, cell=None, year_cell=None):
        eid = block["block_id"] + (f"-r{cell['row']}-c{cell['column']}" if cell else "")
        evidence[eid] = {"evidence_id": eid, "block_id": block["block_id"],
                         "dom_path": block["dom_path"], "reported_page": block["reported_page"],
                         "text_hash": block["text_hash"], "quote": cell["text"] if cell else block["text"],
                         "cell": cell, "year_cell": year_cell}
        return eid

    # Preserve the reported offering names, without inferring an internal hierarchy.
    matches = [(b, re.search(r"Through our (.+?) and (.+?) offerings, Google Cloud generates", b["text"]))
               for b in selected if b["type"] == "paragraph"]
    matches = [(b, m) for b, m in matches if m]
    if len(matches) != 1:
        raise ValueError("offering sentence missing or ambiguous")
    block, match = matches[0]
    facts.append({"fact_id": "google-cloud-offerings", "subject_id": "google-cloud",
                  "predicate": "offerings", "period": None, "value": list(match.groups()),
                  "unit": None, "basis": "explicit", "evidence_ids": [cite(block)]})

    # Require one segment table with explicit metric section labels.
    tables = [b for b in selected if b["type"] == "table" and
              all(t in b["text"] for t in ("Revenues:", "Operating income (loss):", "Google Cloud"))]
    if len(tables) != 1:
        raise ValueError("segment table missing or ambiguous")
    block = tables[0]
    cells = block["table"]["cells"]
    years = [c for c in cells if re.fullmatch(r"20\d{2}", c["text"])]
    if len({c["text"] for c in years}) != len(years) or not years:
        raise ValueError("ambiguous year headers")
    xpath = re.sub(r"([\w-]+:[\w-]+)", r"*[name()='\1']", block["dom_path"])
    elements = tree.xpath(xpath)
    if len(elements) != 1:
        raise ValueError("table DOM location invalid")
    table = elements[0]
    if table.tag != "table":
        tables_dom = table.xpath(".//table")
        if len(tables_dom) != 1:
            raise ValueError("table DOM ambiguous")
        table = tables_dom[0]
    rows_dom = table.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")
    metric = None
    for row in range(block["table"]["row_count"]):
        row_cells = [c for c in cells if c["row"] == row]
        labels = [c["text"] for c in row_cells]
        if "Revenues:" in labels:
            metric = "revenue"
        elif "Operating income (loss):" in labels:
            metric = "operating_income"
        elif "Supplemental information about segment expenses:" in labels:
            metric = None
        if "Google Cloud" not in labels or metric is None:
            continue
        for year in years:
            values = [c for c in row_cells if year["column"] <= c["column"] < year["column"] + year["colspan"]
                      and re.fullmatch(r"\(?[\d,]+\)?", c["text"])]
            if len(values) != 1:
                raise ValueError("numeric cell missing or ambiguous")
            cell = values[0]
            # Bind the visible number to its Inline XBRL unit, scale and period.
            column = 0
            target = None
            for td in rows_dom[row].xpath("./td|./th"):
                if column == cell["column"]:
                    target = td
                column += int(td.get("colspan", "1"))
            tags = [] if target is None else [e for e in target.iter() if e.get("contextref")]
            if len(tags) != 1 or tags[0].get("scale") != "6":
                raise ValueError("unverified XBRL scale")
            tag = tags[0]
            units = tree.xpath("//*[@id=$id]", id=tag.get("unitref"))
            contexts = tree.xpath("//*[@id=$id]", id=tag.get("contextref"))
            if len(units) != 1 or "iso4217:USD" not in units[0].text_content() or len(contexts) != 1:
                raise ValueError("unverified XBRL unit/context")
            context = contexts[0].text_content()
            y = year["text"]
            if f"{y}-01-01" not in context or f"{y}-12-31" not in context:
                raise ValueError("period/header mismatch")
            if "Cloud" not in context:
                raise ValueError("segment/context mismatch")
            number = int(cell["text"].replace(",", "").strip("()")) * (-1 if "(" in cell["text"] else 1)
            eid = cite(block, cell, year)
            evidence[eid]["xbrl"] = {"name": tag.get("name"), "context": tag.get("contextref"),
                                      "unit": tag.get("unitref"), "scale": 6}
            facts.append({"fact_id": f"google-cloud-{metric}-{y}", "subject_id": "google-cloud",
                          "predicate": metric, "period": f"FY{y}", "value": number,
                          "unit": "USD millions", "basis": "explicit", "evidence_ids": [eid]})
    if {f["predicate"] for f in facts} != {"offerings", "revenue", "operating_income"}:
        raise ValueError("required fields missing")
    result = {"schema_version": "cloud-spike-v0.1", "extractor_version": VERSION,
              "company_id": "alphabet", "source_snapshot_id": manifest["source_snapshot_id"],
              "available_at": manifest["filed_at"], "availability_precision": "date",
              "availability_policy": "source filing date; earliest prior disclosure not established",
              "source_url": manifest["source_url"], "index_id": index["index_id"],
              "source_sha256": digest(raw), "selected_node_ids": [n["node_id"] for n in nodes],
              "facts": facts, "evidence": evidence,
              "coverage": {"subject_ids": ["google-cloud"],
                           "predicates": ["offerings", "revenue", "operating_income"],
                           "periods": sorted({f["period"] for f in facts if f["period"]}),
                           "status": "candidate; extraction completeness requires review"}}
    result["snapshot_id"] = "cloud-" + digest(encoded(result))[:16]
    return result


class CloudReader:
    """A pinned, bounded tool surface. Trace contains exactly the returned payloads."""
    def __init__(self, snapshot: dict, *, as_of: str):
        if date.fromisoformat(as_of) < date.fromisoformat(snapshot["available_at"]):
            raise PermissionError("source was not available at the requested date")
        self._data = copy.deepcopy(snapshot)
        self.trace = []

    def _record(self, tool, args, response):
        response = {"snapshot_id": self._data["snapshot_id"], **response}
        self.trace.append({"step": len(self.trace) + 1, "tool": tool, "arguments": args,
                           "response": copy.deepcopy(response)})
        return copy.deepcopy(response)

    def manifest(self):
        return self._record("manifest", {}, {"coverage": self._data["coverage"],
                            "available_at": self._data["available_at"],
                            "tools": ["facts", "evidence", "request_missing"]})

    def facts(self, *, predicate: str, period: str | None = None, offset=0, limit=2):
        if offset < 0 or not 1 <= limit <= 20:
            raise ValueError("invalid pagination")
        matches = [f for f in self._data["facts"] if f["predicate"] == predicate
                   and (period is None or f["period"] == period)]
        supported = predicate in self._data["coverage"]["predicates"]
        return self._record("facts", {"predicate": predicate, "period": period, "offset": offset, "limit": limit},
                            {"status": "matched" if matches else "not_extracted" if supported else "unsupported",
                             "results": matches[offset:offset + limit], "total": len(matches),
                             "next_offset": offset + limit if offset + limit < len(matches) else None,
                             "search_scope": "stored Google Cloud facts in this snapshot"})

    def evidence(self, fact_id: str):
        fact = next((f for f in self._data["facts"] if f["fact_id"] == fact_id), None)
        if fact is None:
            raise KeyError(fact_id)
        return self._record("evidence", {"fact_id": fact_id},
                            {"results": [self._data["evidence"][eid] for eid in fact["evidence_ids"]]})

    def request_missing(self, predicate: str, period: str):
        return self._record("request_missing", {"predicate": predicate, "period": period},
                            {"status": "recorded_only", "reason": "No acquisition worker in this spike"})


def simulate(reader: CloudReader):
    reader.manifest()
    for predicate in ("offerings", "revenue", "operating_income"):
        offset = 0
        while True:
            response = reader.facts(predicate=predicate, offset=offset)
            for fact in response["results"]:
                reader.evidence(fact["fact_id"])
            offset = response["next_offset"]
            if offset is None:
                break
    missing = reader.facts(predicate="revenue", period="Q1-2025")
    if missing["status"] == "not_extracted":
        reader.request_missing("revenue", "Q1-2025")
    return reader.trace
