"""Bounded query-plan compiler, SQL reader, evidence reader and Decimal formulas.

The caller supplies a resolved plan using discover_data/get_schema. Free-form
questions are trace context, never silently interpreted as executable SQL.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import json
from pathlib import Path
import threading

import duckdb

from uteki.agents.document_reader import DocumentReader
from uteki.domain.research_data.query_contract import DataQuery, RecordRequest, ResearchRecord, QueryResult, VERSION
from .financial_records import digest
from .query_dataset import contained, load


class QueryDataPort:
    def __init__(self, dataset: Path):
        self.dataset = dataset.resolve()
        self.manifest = load(self.dataset / "manifest.json")
        if self.manifest["schema_version"] != VERSION:
            raise ValueError(f"unsupported dataset schema version: {self.manifest['schema_version']}; "
                             f"expected {VERSION}. Build a new dataset; preserve the historical snapshot.")
        for relative, expected in self.manifest["files"].items():
            if digest(contained(self.dataset, relative).read_bytes()) != expected:
                raise ValueError("dataset integrity failure: " + relative)
        self.sources = load(self.dataset / "sources.json")
        self.metrics = load(self.dataset / "metrics.json")
        self._readers = {}
        self._db = duckdb.connect(str(self.dataset / "research.duckdb"), read_only=True, config={
            "enable_external_access": "false", "autoinstall_known_extensions": "false",
            "autoload_known_extensions": "false", "threads": "1", "memory_limit": "128MB",
        })
        try:
            entities = {s["company_id"]: {"entity_id": s["company_id"], "company_id": s["company_id"],
                                         "accounting_bases": set()} for s in self.sources}
            for entity, company, basis in self._db.execute(
                    "SELECT DISTINCT o.entity_id, s.company_id, o.accounting_basis "
                    "FROM observations o JOIN sources s USING (source_snapshot_id)").fetchall():
                if entity in entities and entities[entity]["company_id"] != company:
                    raise ValueError("entity belongs to multiple companies; use qualified entity IDs")
                entry = entities.setdefault(entity, {"entity_id": entity, "company_id": company, "accounting_bases": set()})
                entry["accounting_bases"].add(basis)
            self.entities = {key: {**value, "accounting_bases": sorted(value["accounting_bases"])}
                             for key, value in sorted(entities.items())}
        except Exception:
            self._db.close()
            raise

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @property
    def snapshot_id(self):
        return self.manifest["snapshot_id"]

    def _sql(self, sql, parameters, trace):
        # Only source-controlled SQL reaches this method. Each connection is used serially.
        timer = threading.Timer(10, self._db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            rows = self._db.execute(sql, parameters).fetchall()
        finally:
            timer.cancel()
            timer.join()
        trace.append({"tool": "sql", "sql": sql, "parameters": [str(x) if isinstance(x, date) else x for x in parameters],
                      "returned_rows": len(rows), "snapshot_id": self.snapshot_id})
        return rows

    def get_schema(self, metric_ids=()):
        unknown = set(metric_ids) - self.metrics.keys()
        if unknown:
            raise ValueError("unknown metric IDs: " + ", ".join(sorted(unknown)))
        return {"snapshot_id": self.snapshot_id, "schema_version": VERSION, "query": load(self.dataset / "schemas/query.schema.json"),
                "record": load(self.dataset / "schemas/record.schema.json"), "result": load(self.dataset / "schemas/result.schema.json"),
                "metrics": {k:v for k,v in self.metrics.items() if not metric_ids or k in metric_ids},
                "entities": list(self.entities.values()),
                "physical_tables": {name: [{"name": row[1], "type": row[2], "not_null": row[3], "primary_key": row[5]}
                    for row in self._db.execute(f"PRAGMA table_info('{name}')").fetchall()]
                    for name in ("observations", "sources", "evidence", "metric_definitions")},
                "capabilities": ["compiled_parameterized_select", "decimal_calculations", "literal_document_search", "read_complete_context"],
                "unsupported": ["free_form_NL_planner", "arbitrary_SQL", "OCR", "web_search", "automatic_acquisition"],
                "notes": ["All rows are candidates; include_candidates must be explicitly true.",
                          "period=null requests records with no typed period; period_resolution distinguishes unresolved/not_applicable. It is not a wildcard.",
                          "question is context; only the typed plan is executed.",
                          "No implicit SUM or joins that multiply disclosure occurrences."]}

    def discover_data(self, *, knowledge_cutoff: str, include_candidates=False):
        cutoff = date.fromisoformat(knowledge_cutoff)
        visible = [s for s in self.sources if date.fromisoformat(s["available_at"]) <= cutoff]
        rows = self._db.execute("SELECT entity_id, metric_id, period_kind, period_start, period_end, value_kind, count(*) "
                                "FROM observations WHERE available_at <= ? GROUP BY ALL ORDER BY entity_id, metric_id, period_end", [cutoff]).fetchall()
        return {"snapshot_id": self.snapshot_id, "source_policy_id": self.manifest["source_policy_id"],
                "status": "candidate", "knowledge_cutoff": knowledge_cutoff,
                "sources": [{**s, "queryable": include_candidates} for s in visible],
                "coverage": [{"entity_id": r[0], "metric_id": r[1], "period_kind": r[2],
                              "period_start": str(r[3]) if r[3] else None, "period_end": str(r[4]) if r[4] else None,
                              "value_kind": r[5], "occurrence_count": r[6],
                              "status": "available_candidate" if include_candidates else "quality_filtered"} for r in rows],
                "limits": self.manifest["limits"], "not_disclosed_inference": "never inferred from a missing row"}

    def _reader(self, source):
        sid = source["source_snapshot_id"]
        if sid not in self._readers:
            self._readers[sid] = DocumentReader(contained(self.dataset, source["index_folder"]))
        return self._readers[sid]

    @staticmethod
    def _document_node(reader):
        roots = [n["node_id"] for n in reader.index["nodes"] if n["kind"] == "document"]
        if len(roots) != 1:
            raise ValueError("source index must declare exactly one document node")
        return roots[0]

    def get_evidence(self, evidence_ids, *, snapshot_id, knowledge_cutoff, include_candidates=False):
        if snapshot_id != self.snapshot_id:
            raise ValueError("snapshot mismatch")
        if not include_candidates:
            raise PermissionError("candidate evidence requires explicit candidate access")
        if not 1 <= len(evidence_ids) <= 256:
            raise ValueError("evidence request must contain 1..256 IDs")
        cutoff = date.fromisoformat(knowledge_cutoff)
        found = {}
        for eid in dict.fromkeys(evidence_ids):
            row = self._db.execute("SELECT e.payload FROM evidence e JOIN sources s USING(source_snapshot_id) "
                                   "WHERE e.evidence_id = ? AND s.available_at <= ?", [eid, cutoff]).fetchone()
            if row is None:
                raise KeyError("evidence unavailable at requested cutoff: " + eid)
            found[eid] = json.loads(row[0])
        return {"snapshot_id": self.snapshot_id, "evidence": found}

    @staticmethod
    def _key(request):
        return digest(request.model_dump(mode="json"))[:24]

    def _lookup(self, request, query, trace):
        plan = request.model_dump(mode="json")
        base = {"request": plan, "selection_id": self._key(request), "record_ids": []}
        if request.metric_id not in self.metrics or request.entity_id not in self.entities:
            return {**base, "status": "unsupported", "reason": "unknown_entity_or_metric"}, []
        if not query.include_candidates:
            return {**base, "status": "quality_filtered", "reason": "dataset_contains_candidates_only"}, []
        sql = "SELECT payload FROM observations WHERE entity_id = ? AND metric_id = ? AND value_kind = ?"
        args = [request.entity_id, request.metric_id, request.value_kind]
        if request.period:
            sql += " AND period_kind = ? AND period_start IS NOT DISTINCT FROM ? AND period_end = ?"
            args += [request.period.kind, request.period.start, request.period.end]
        else:
            sql += " AND period_kind IS NULL"
        sql += " AND available_at <= ? AND status = 'candidate' ORDER BY record_id LIMIT 257"
        rows = [json.loads(r[0]) for r in self._sql(sql, args + [query.knowledge_cutoff], trace)]
        if len(rows) > 256:
            return {**base, "status": "limited", "reason": "narrow_query_before_consuming_records"}, []
        base["record_ids"] = [r["record_id"] for r in rows]
        if not rows:
            uncapped = self._db.execute(sql, args + [date.max]).fetchall()
            if uncapped:
                return {**base, "status": "not_available_at_cutoff", "reason": "later_source_exists_in_snapshot"}, []
            company = self.entities[request.entity_id]["company_id"]
            eligible_sources = {s["source_snapshot_id"] for s in self.sources
                                if s["company_id"] == company and s["available_at"] <= str(query.knowledge_cutoff)
                                and (request.value_kind != "actual" or s["form"] in ("10-K", "10-Q"))}
            matching_periods = {s["source_snapshot_id"] for s in self.sources if s["source_snapshot_id"] in eligible_sources
                                and request.period and s["period_end"] == str(request.period.end)}
            if request.period:
                matching_periods.update(r[0] for r in self._db.execute(
                    "SELECT DISTINCT source_snapshot_id FROM observations WHERE entity_id = ? AND period_kind = ? "
                    "AND period_start IS NOT DISTINCT FROM ? AND period_end = ? AND available_at <= ?",
                    [request.entity_id, request.period.kind, request.period.start, request.period.end,
                     query.knowledge_cutoff]).fetchall() if r[0] in eligible_sources)
            return {**base, "status": "source_present_unprocessed" if matching_periods else "source_missing",
                    "reason": "not_structured_in_this_pilot; not a not-disclosed finding"}, []
        if all(r["value_relation"] == "qualitative" for r in rows):
            return {**base, "status": "listed", "reason": "qualitative_statements_are_not_numeric_observations"}, rows
        signatures = {json.dumps([r[k] for k in ("record_type", "value_decimal", "upper_decimal", "value_relation", "unit",
                      "accounting_basis", "dimensions", "denominator", "modality")]
                      + [r["available_at"] if r["value_kind"] == "management_guidance" else None], sort_keys=True) for r in rows}
        return {**base, "status": "matched" if len(signatures) == 1 else "ambiguous",
                "reason": "equivalent_numeric_disclosures_retained" if len(rows) > 1 and len(signatures) == 1 else "one_or_conflicting_observations",
                "occurrence_count": len(rows)}, rows

    def _documents(self, request, query, trace):
        spec = request.model_dump(mode="json")
        sources = [s for s in self.sources if s["company_id"] == request.company_id and s["form"] == request.form
                   and s["period_end"] == str(request.period_end)]
        if not query.include_candidates:
            return {"request": spec, "status": "quality_filtered", "contexts": []}
        visible = [s for s in sources if s["available_at"] <= str(query.knowledge_cutoff)]
        if not visible:
            return {"request": spec, "status": "not_available_at_cutoff" if sources else "source_missing", "contexts": []}
        contexts, hits, remaining, seen = [], 0, request.limit, set()
        for source in visible:
            reader = self._reader(source)
            node_id = self._document_node(reader)
            result = reader.search(node_id, request.phrase, limit=request.limit)
            hits += result["total"]
            trace.append({"tool": "document_search", "source_snapshot_id": source["source_snapshot_id"],
                          "phrase": request.phrase, "total_hits": result["total"], "mode": "literal_source_order"})
            for hit in result["hits"]:
                if remaining == 0:
                    break
                anchor = reader.blocks[reader.positions[hit["block_id"]]]
                start = reader.positions[hit["block_id"]]
                if anchor.get("speaker") and not anchor.get("exchange_id"):
                    for previous in reader.blocks[max(0, start - 2):start][::-1]:
                        if previous.get("turn_id") != anchor.get("turn_id") or previous.get("speaker") != anchor.get("speaker"):
                            break
                        start -= 1
                context = reader.read(node_id, reader.blocks[start]["block_id"], count=reader.positions[hit["block_id"]] - start + 1)
                block_ids = tuple(b["block_id"] for b in context["blocks"])
                key = (source["source_snapshot_id"], block_ids)
                if key in seen:
                    continue
                seen.add(key)
                chars = sum(len(b["text"]) for b in context["blocks"])
                payload = {"source_snapshot_id": source["source_snapshot_id"], "index_id": source["index_id"],
                           "source_url": source["source_url"], "source_sha256": source["source_sha256"],
                           "anchor_block_id": hit["block_id"], "block_ids": block_ids, "context_characters": chars,
                           "source_period_end": source["period_end"], "available_at": source["available_at"]}
                if chars > 80000:
                    contexts.append({**payload, "status": "context_too_large", "blocks": [],
                                     "continuation": {"source_snapshot_id": source["source_snapshot_id"], "block_id": hit["block_id"]}})
                else:
                    contexts.append({**payload, "status": "read", "blocks": context["blocks"]})
                remaining -= 1
                trace.append({"tool": "document_read", **{k:v for k,v in payload.items() if k != "source_url"}})
        status = "no_literal_match" if not hits else "limited" if hits > request.limit or any(c["status"] != "read" for c in contexts) else "matched"
        return {"request": spec, "status": status, "total_literal_hits": hits, "contexts": contexts,
                "coverage": "bounded literal retrieval; not exhaustive semantic recall", "not_disclosed": False}

    def read_context(self, *, source_snapshot_id, block_id, snapshot_id, knowledge_cutoff, include_candidates=False):
        if snapshot_id != self.snapshot_id:
            raise ValueError("snapshot mismatch")
        if not include_candidates:
            raise PermissionError("candidate access must be explicit")
        cutoff = date.fromisoformat(knowledge_cutoff)
        source = next((s for s in self.sources if s["source_snapshot_id"] == source_snapshot_id and date.fromisoformat(s["available_at"]) <= cutoff), None)
        if source is None:
            raise KeyError("source unavailable at cutoff")
        reader = self._reader(source)
        result = reader.read(self._document_node(reader), block_id, count=1)
        return {"snapshot_id": self.snapshot_id, "source_snapshot_id": source_snapshot_id, "source_sha256": source["source_sha256"],
                "source_url": source["source_url"], **result}

    @staticmethod
    def _dependencies(calculation):
        metrics = ("revenue", "operating_income") if calculation.formula_id in ("operating_margin", "operating_margin_delta_pp") else (calculation.formula_id.removesuffix("_yoy"),)
        return [RecordRequest(entity_id=calculation.entity_id, metric_id=m, period=p, value_kind="actual")
                for p in calculation.periods for m in metrics]

    def _calculate(self, calculation, selections, records):
        deps = self._dependencies(calculation)
        used, values = [], []
        for dep in deps:
            selection = selections[self._key(dep)]
            if selection["status"] != "matched":
                raise ValueError("operand_missing_or_ambiguous")
            members = [records[rid] for rid in selection["record_ids"]]
            r = members[0]
            if r["value_relation"] != "eq" or r["value_kind"] != "actual" or r["record_type"] != "metric":
                raise ValueError("operand_not_exact_actual")
            used.extend(selection["record_ids"])
            values.append(r)
        signature = lambda r: json.dumps([r[k] for k in ("entity_id", "unit", "accounting_basis", "dimensions")], sort_keys=True)
        if len({signature(r) for r in values}) != 1:
            raise ValueError("incompatible_unit_basis_or_dimensions")
        periods = calculation.periods
        if len(periods) == 2:
            a, b = periods
            months = lambda p: (p.end.year - p.start.year) * 12 + p.end.month - p.start.month + 1 if p.start else None
            if a.end >= b.end or a.kind != b.kind or months(a) != months(b):
                raise ValueError("incomparable_periods")
            if calculation.formula_id.endswith("_yoy") and (b.end.year != a.end.year + 1 or
                    (a.end.month, a.end.day) != (b.end.month, b.end.day) or a.start is None or b.start is None or
                    (a.start.month, a.start.day) != (b.start.month, b.start.day)):
                raise ValueError("not_year_over_year_periods")
        with localcontext() as context:
            context.prec = 50
            decimals = [Decimal(r["value_decimal"]) for r in values]
            if calculation.formula_id in ("operating_margin", "operating_margin_delta_pp"):
                if any(x <= 0 for x in decimals[::2]):
                    raise ValueError("nonpositive_revenue_denominator")
                margins = [decimals[i+1] / decimals[i] * 100 for i in range(0, len(decimals), 2)]
                value = margins[0] if len(margins) == 1 else margins[1] - margins[0]
            else:
                if decimals[0] <= 0:
                    raise ValueError("nonpositive_yoy_base")
                value = (decimals[1] / decimals[0] - 1) * 100
            exact = str(value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))
            display = str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
        result = {"formula_id": calculation.formula_id + "-v1", "entity_id": calculation.entity_id,
                  "periods": [p.model_dump(mode="json") for p in periods], "operand_record_ids": used,
                  "value_decimal": exact, "display_decimal": display,
                  "unit": "percentage_points" if calculation.formula_id.endswith("_pp") else "percent",
                  "rounding": "Decimal precision 50; HALF_EVEN 6 output decimals / 2 display decimals",
                  "snapshot_id": self.snapshot_id}
        return {"computed_id": "calc-" + digest(result)[:24], **result}

    def query_data(self, request):
        query = request if isinstance(request, DataQuery) else DataQuery.model_validate(request)
        if query.snapshot_id != self.snapshot_id:
            raise ValueError("snapshot mismatch")
        if query.source_policy_id != self.manifest["source_policy_id"]:
            raise PermissionError("source policy mismatch")
        trace, selections, all_records, gaps = [], {}, {}, []
        needs = list(query.records)
        for calc in query.calculations:
            needs.extend(self._dependencies(calc))
        for need in needs:
            key = self._key(need)
            if key in selections:
                continue
            selection, rows = self._lookup(need, query, trace)
            selections[key] = selection
            all_records.update({r["record_id"]:r for r in rows})
            if selection["status"] not in ("matched", "listed"):
                gaps.append({"scope": "record", "selection_id": key, "reason": selection["status"], "request": selection["request"]})
            elif any(r["period_resolution"] == "unresolved" for r in rows):
                gaps.append({"scope": "semantics", "selection_id": key, "reason": "target_period_unresolved"})
        computed = []
        for calc in query.calculations:
            try:
                result = self._calculate(calc, selections, all_records)
                computed.append(result)
                trace.append({"tool": "registered_calculation", "computed_id": result["computed_id"], "formula_id": result["formula_id"]})
            except ValueError as error:
                gaps.append({"scope": "calculation", "formula_id": calc.formula_id, "reason": str(error)})
        documents = [self._documents(d, query, trace) for d in query.documents]
        gaps.extend({"scope": "document", "request": d["request"], "reason": d["status"]} for d in documents if d["status"] != "matched")
        evidence_ids = sorted({eid for r in all_records.values() for name in ("evidence_ids", "qualifier_evidence_ids", "question_evidence_ids") for eid in r[name]})
        evidence = {}
        for offset in range(0, len(evidence_ids), 256):
            evidence.update(self.get_evidence(evidence_ids[offset:offset + 256], snapshot_id=self.snapshot_id,
                            knowledge_cutoff=str(query.knowledge_cutoff),
                            include_candidates=query.include_candidates)["evidence"])
        has_content = bool(all_records or computed or any(d["contexts"] for d in documents))
        status = "ambiguous" if any(g["reason"] == "ambiguous" for g in gaps) else "partial" if gaps and has_content else "unanswerable" if gaps else "complete"
        return QueryResult(query_id=query.query_id, snapshot_id=self.snapshot_id, source_policy_id=query.source_policy_id,
                           knowledge_cutoff=query.knowledge_cutoff, candidate_data=query.include_candidates, status=status,
                           completion_scope="Resolved typed plan only; document match does not establish semantic completeness of the natural-language question.",
                           records=tuple(ResearchRecord.model_validate(r) for r in all_records.values()),
                           selections=tuple(selections.values()), computed_facts=tuple(computed), documents=tuple(documents),
                           evidence=evidence, gaps=tuple(gaps), trace=tuple(trace)).model_dump(mode="json")
