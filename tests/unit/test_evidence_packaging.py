"""Evidence assembly regressions over frozen sources and independent synthetic data."""
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.verify_scoped_retrieval import ReplayPlanner
from uteki.agents.data_query_agent import DataQueryAgent
from uteki.domain.research_data.evidence_package import EvidencePackage, PACKAGE_VERSION
from uteki.infrastructure.research_data.evidence_packaging import build_evidence_package
from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_cli import main as query_main
from uteki.infrastructure.research_data.query_service import QueryDataPort
from tests.unit import test_query_scope
from tests.unit.test_scoped_data_query_agent import ScriptedPlanner, scoped_request


ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "experiments/data_agent_query/2026-09-22-pilot-04/dataset"
HISTORICAL = ROOT / "experiments/data_agent_query/source-scope-v1/offline-01"


def read_json(path):
    return json.loads(path.read_text())


def artifact_for(package, kind, legacy_id):
    ids = package["bindings"][f"{kind}:{legacy_id}"]
    artifacts = {a["artifact_id"]: a for a in package["artifacts"]}
    return [artifacts[aid] for aid in ids]


def result_without_evidence(result):
    empty = copy.deepcopy(result)
    for field in ("records", "computed_facts", "contexts", "gaps", "answer_parts"):
        empty[field] = []
    empty["evidence"] = {}
    empty["status"] = "limited"
    return empty


class FrozenEvidencePackagingTests(unittest.TestCase):
    def setUp(self):
        self.port = QueryDataPort(PILOT)
        self.addCleanup(self.port.close)
        self.result = read_json(HISTORICAL / "session/result.json")
        self.scoped = self.port.scoped(self.result["request"]["scope"])
        self.source = self.scoped.sources[0]
        self.blocks = {b["block_id"]: b for b in (
            json.loads(line) for line in (PILOT / self.source["index_folder"] / "blocks.jsonl").read_text().splitlines())}

    def test_real_seven_step_result_preserves_full_blocks_quotes_and_derivation_graph(self):
        original = copy.deepcopy(self.result)
        package = build_evidence_package(self.scoped, self.result)
        EvidencePackage.model_validate(package)
        self.assertEqual(self.result, original)
        self.assertEqual(package["schema_version"], PACKAGE_VERSION)
        self.assertEqual(package["scope"], self.result["request"]["scope"])
        self.assertEqual(package["source_companies"], {self.source["source_snapshot_id"]: "alphabet"})
        self.assertEqual(package["semantic_completeness"], "not_evaluated")
        artifacts = {a["artifact_id"]: a for a in package["artifacts"]}

        for context in self.result["contexts"]:
            returned = artifact_for(package, "context", context["context_id"])
            self.assertEqual({a["payload"]["block"]["block_id"] for a in returned}, set(context["block_ids"]))
            for artifact in returned:
                block = artifact["payload"]["block"]
                self.assertEqual(block, self.blocks[block["block_id"]])
                self.assertEqual(artifact["payload"]["text"], block["text"])
                self.assertEqual(artifact["provenance"]["method"], "source_read")
                self.assertEqual(artifact["derived_from"], [])

        for eid, evidence in self.result["evidence"].items():
            quotes = artifact_for(package, "evidence", eid)
            self.assertEqual(len(quotes), 1)
            quote = quotes[0]
            self.assertEqual(quote["kind"], "source_quote")
            self.assertEqual(quote["payload"], {"text": evidence["quote"], "evidence": evidence})
            self.assertEqual(quote["provenance"]["verification"], "source_verified")
            self.assertTrue(quote["derived_from"])
            quoted_tables = []
            for parent_id in quote["derived_from"]:
                parent = artifacts[parent_id]
                self.assertIn(parent["kind"], ("source_text", "source_table"))
                block = parent["payload"]["block"]
                self.assertEqual(block, self.blocks[block["block_id"]])
                if parent["kind"] == "source_table":
                    self.assertEqual(parent["payload"]["table"], block["table"])
                    if block["block_id"] == evidence["block_id"]:
                        quoted_tables.append(parent)
            self.assertEqual(len(quoted_tables), 1)

        for record in self.result["records"]:
            normalized = artifact_for(package, "record", record["record_id"])
            self.assertEqual(len(normalized), 1)
            self.assertEqual(normalized[0]["kind"], "normalized_record")
            self.assertEqual(normalized[0]["payload"]["record"], record)
            self.assertEqual(normalized[0]["payload"]["origin_kind"], "deterministic")
            self.assertEqual(set(normalized[0]["derived_from"]), {
                artifact_for(package, "evidence", eid)[0]["artifact_id"] for eid in record["evidence_ids"]})

        for computed in self.result["computed_facts"]:
            derived = artifact_for(package, "computed", computed["computed_id"])
            self.assertEqual(len(derived), 1)
            self.assertEqual(derived[0]["payload"]["fact"], computed)
            self.assertEqual(derived[0]["kind"], "computed_scalar")
            self.assertEqual({artifacts[aid]["payload"]["record"]["record_id"]
                              for aid in derived[0]["derived_from"]}, set(computed["operand_record_ids"]))
        self.assertFalse({"model_summary", "model_extract"} & {a["kind"] for a in package["artifacts"]})

    def test_navigation_previews_never_become_source_body_or_read_coverage(self):
        navigation_only = result_without_evidence(self.result)
        search = next(n for n in navigation_only["navigation"] if n["tool"] == "search_source")
        search["hits"][0]["preview"] = "Preview-only words are not a source paragraph."
        package = build_evidence_package(self.scoped, navigation_only)
        self.assertEqual(package["artifacts"], [])
        self.assertEqual(package["bindings"], {})
        self.assertTrue(package["coverage"])
        self.assertEqual({c["mode"] for c in package["coverage"]}, {"navigation_only"})
        self.assertNotIn("Preview-only words", json.dumps(package))

    def test_wrong_scope_and_cross_source_or_company_are_rejected(self):
        mutations = []
        wrong_scope = copy.deepcopy(self.result)
        wrong_scope["request"]["scope"]["source_snapshot_ids"] = ["alphabet-000165204426000048-2ff47ad2"]
        mutations.append(("scope", wrong_scope))
        cross_source = copy.deepcopy(self.result)
        cross_source["contexts"][0]["source_snapshot_id"] = "alphabet-000165204426000048-2ff47ad2"
        mutations.append(("source", cross_source))
        cross_company = copy.deepcopy(self.result)
        cross_company["contexts"][0]["company_id"] = "other-company"
        mutations.append(("company", cross_company))
        for label, value in mutations:
            with self.subTest(mutation=label), self.assertRaises(ValueError):
                build_evidence_package(self.scoped, value)

    def test_rewritten_original_text_table_quote_record_and_calculation_are_rejected(self):
        mutations = []
        text = copy.deepcopy(self.result)
        text["contexts"][0]["blocks"][0]["text"] = "Fabricated source sentence"
        mutations.append(("body", text))
        quote = copy.deepcopy(self.result)
        eid = next(iter(quote["evidence"]))
        quote["evidence"][eid]["quote"] = "999,999"
        mutations.append(("quote", quote))
        evidence_metadata = copy.deepcopy(self.result)
        evidence_metadata["evidence"][eid]["number_metadata"]["scale"] = 3
        mutations.append(("evidence metadata", evidence_metadata))
        record = copy.deepcopy(self.result)
        record["records"][0]["value_decimal"] = "1"
        mutations.append(("record", record))
        computed = copy.deepcopy(self.result)
        computed["computed_facts"][0]["display_decimal"] = "99.99"
        mutations.append(("calculation", computed))
        table = copy.deepcopy(self.result)
        context = self.scoped.read_context(source_snapshot_id=self.source["source_snapshot_id"],
            block_id=self.result["evidence"][eid]["block_id"])
        context["context_id"] = "ctx-extra-table-read"
        table["contexts"].append(context)
        build_evidence_package(self.scoped, table)
        next(b for b in table["contexts"][-1]["blocks"] if b["type"] == "table")["table"] = {"rows": []}
        mutations.append(("table cells", table))
        for label, value in mutations:
            with self.subTest(mutation=label), self.assertRaises(ValueError):
                build_evidence_package(self.scoped, value)

    def test_real_image_keeps_metadata_without_borrowing_missing_bytes_or_running_ocr(self):
        image = next(b for b in self.blocks.values() if b["type"] == "image")
        outline = self.scoped.outline_source({"source_snapshot_id": self.source["source_snapshot_id"]})
        document = next(n for n in outline["nodes"] if n["kind"] == "document")
        request = {**copy.deepcopy(self.result["request"]), "question": "Read the selected image reference."}

        def finish(packet):
            context = packet["history"][-1]["result"]
            return {"action": "finish", "answer_parts": [{"requested_information": "Image reference",
                "context_ids": [context["context_id"]]}]}

        planner = ScriptedPlanner([{"action": "read_source", "read": {
            "source_snapshot_id": self.source["source_snapshot_id"], "node_id": document["node_id"],
            "start_block_id": image["block_id"], "count": 1}}, finish])
        with tempfile.TemporaryDirectory() as tmp:
            result = asyncio.run(DataQueryAgent(self.port, planner).run_scoped(request, output=Path(tmp) / "session"))
            package = read_json(Path(tmp) / "session/evidence-package.json")
        self.assertEqual(result["status"], "answered")
        images = [a for a in package["artifacts"] if a["kind"] == "image_reference"]
        self.assertEqual(len(images), 1)
        payload = images[0]["payload"]
        asset = next(a for a in read_json(PILOT / self.source["index_folder"] / "assets.json")["assets"]
                     if a["asset_id"] == image["image_asset_id"])
        self.assertEqual(payload["image_asset_id"], asset["asset_id"])
        self.assertEqual(payload["asset_metadata"], asset)
        self.assertEqual(payload["alt_text"], asset["alt"])
        self.assertEqual(payload["bytes_status"], "metadata_only")
        self.assertIsNone(payload["bytes_sha256"])
        self.assertEqual(payload["ocr_status"], "not_run")
        self.assertEqual(payload["vision_status"], "not_run")
        self.assertTrue(any(c["mode"] == "image_reference_only" and image["block_id"] in c["block_ids"]
                            for c in package["coverage"]))
        self.assertFalse(any(c["mode"] == "body_returned" and image["block_id"] in c["block_ids"]
                             for c in package["coverage"]))
        self.assertFalse(any(a["kind"] in ("source_text", "model_extract", "model_summary") for a in package["artifacts"]))

    def test_candidate_permission_cannot_be_removed_while_reusing_candidate_evidence(self):
        value = copy.deepcopy(self.result)
        value["request"]["scope"]["include_candidates"] = False
        blocked_port = self.port.scoped(value["request"]["scope"])
        with self.assertRaises(ValueError):
            build_evidence_package(blocked_port, value)

    def test_historical_call_model_extract_retains_raw_record_without_invented_model_metadata(self):
        source = next(s for s in self.port.sources if s["form"] == "EARNINGS_CALL"
                      and s["company_id"] == "alphabet" and s["period_end"] == "2025-12-31")
        request = scoped_request(self.port, companies=["alphabet"], sources=[source["source_snapshot_id"]],
            question="FY2026 CapEx guidance", cutoff="2026-09-22")

        def finish(packet):
            value = packet["history"][-1]["result"]
            return {"action": "finish", "answer_parts": [{"requested_information": "CapEx guidance",
                "record_ids": [record["record_id"] for record in value["records"]]}]}

        planner = ScriptedPlanner([{"action": "query", "plan": {"records": [{
            "entity_id": "alphabet", "metric_id": "capex_guidance", "value_kind": "management_guidance",
            "period": {"kind": "year", "start": "2026-01-01", "end": "2026-12-31"}}]}}, finish])
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session"
            result = asyncio.run(DataQueryAgent(self.port, planner).run_scoped(request, output=session))
            package = read_json(session / "evidence-package.json")
        self.assertEqual(result["status"], "answered")
        self.assertTrue(result["records"])
        self.assertIn("model_metadata_unavailable", {g["reason"] for g in package["gaps"]})
        by_id = {a["artifact_id"]: a for a in package["artifacts"]}
        for record in result["records"]:
            normalized = artifact_for(package, "record", record["record_id"])[0]
            self.assertEqual(normalized["payload"]["origin_kind"], "model_assisted")
            model_parents = [by_id[aid] for aid in normalized["derived_from"] if by_id[aid]["kind"] == "model_extract"]
            self.assertEqual(len(model_parents), 1)
            model = model_parents[0]
            self.assertEqual(model["payload"]["extraction"], record["origin"]["raw_record"])
            self.assertEqual(model["provenance"]["method"], "model")
            self.assertEqual(model["provenance"]["verification"], "snapshot_verified")
            self.assertTrue(model["derived_from"])
            for key in ("provider", "model", "prompt_sha256"):
                self.assertIsNone(model["provenance"][key])
        self.assertFalse(any(a["kind"] == "model_summary" for a in package["artifacts"]))

    def test_packaging_is_deterministic_and_preserves_historical_session_and_storage_schemas(self):
        paths = [p for p in HISTORICAL.rglob("*") if p.is_file()]
        paths += [PILOT / "manifest.json", *(PILOT / "schemas").glob("*.json")]
        before = {p: digest(p.read_bytes()) for p in paths}
        first = build_evidence_package(self.scoped, self.result)
        second = build_evidence_package(self.scoped, copy.deepcopy(self.result))
        self.assertEqual(first, second)
        self.assertEqual(before, {p: digest(p.read_bytes()) for p in paths})

    def test_new_scoped_session_saves_bundle_and_schema_in_manifest_without_model_context_duplication(self):
        spec = read_json(HISTORICAL / "spec.json")

        class InspectableReplay(ReplayPlanner):
            def __init__(self, steps):
                super().__init__(steps)
                self.packets = []

            async def decide(self, packet):
                self.packets.append(copy.deepcopy(packet))
                return await super().decide(packet)

        planner = InspectableReplay(spec["steps"])
        with tempfile.TemporaryDirectory() as tmp:
            session = Path(tmp) / "session"
            result = asyncio.run(DataQueryAgent(self.port, planner, max_steps=7, max_packet_bytes=400000).run_scoped(
                spec["request"], output=session))
            package = read_json(session / "evidence-package.json")
            self.assertEqual(result["evidence_package"], {"schema_version": PACKAGE_VERSION,
                "bundle_id": package["bundle_id"], "path": "evidence-package.json"})
            self.assertEqual(read_json(session / "evidence-package.schema.json"), EvidencePackage.model_json_schema())
            self.assertEqual(read_json(session / "result.json"), result)
            manifest = read_json(session / "manifest.json")
            for name in ("evidence-package.json", "evidence-package.schema.json", "result.json"):
                self.assertEqual(manifest["files"][name], digest((session / name).read_bytes()))
            EvidencePackage.model_validate(package)
        self.assertEqual(result["status"], "answered")
        self.assertEqual(len(planner.packets), 7)
        for packet in planner.packets:
            self.assertNotIn("evidence_package", packet)
            for turn in packet["history"]:
                self.assertNotIn("evidence_package", turn["result"])
                self.assertNotIn("artifacts", turn["result"])

    def test_cli_exposes_package_schema_and_packages_historical_result_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scope = root / "scope.json"
            scope.write_text(json.dumps(self.result["request"]["scope"]))
            schema_output = io.StringIO()
            with redirect_stdout(schema_output):
                status = query_main(["scoped-schema", "--dataset", str(PILOT), "--scope", str(scope)])
            self.assertEqual(status, 0)
            self.assertEqual(json.loads(schema_output.getvalue())["output_contracts"]["evidence_package"],
                             EvidencePackage.model_json_schema())
            output = root / "evidence-package.json"
            status = query_main(["--out", str(output), "scoped-package", "--dataset", str(PILOT),
                "--scope", str(scope), "--request", str(HISTORICAL / "session/result.json")])
            self.assertEqual(status, 0)
            package = read_json(output)
            EvidencePackage.model_validate(package)
            self.assertEqual(package, build_evidence_package(self.scoped, self.result))


class SyntheticEvidencePackagingTests(unittest.TestCase):
    def setUp(self):
        fixture = test_query_scope.QueryScopeTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.port = fixture.port
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.output = Path(temporary.name) / "session"
        self.request = scoped_request(self.port, companies=["acme"], sources=["acme-2031"],
            question="Acme Services operating margin for 2031 Q2", cutoff="2031-07-21")

    def test_agent_and_packaging_cli_cannot_write_inside_selected_dataset(self):
        before = {str(p.relative_to(self.port.dataset)): digest(p.read_bytes())
                  for p in self.port.dataset.rglob("*") if p.is_file()}
        planner = ScriptedPlanner([])
        forbidden_session = self.port.dataset / "forbidden-session"
        with self.assertRaises(ValueError):
            asyncio.run(DataQueryAgent(self.port, planner).run_scoped(self.request, output=forbidden_session))
        self.assertFalse(forbidden_session.exists())
        self.assertEqual(planner.packets, [])
        scope_file = self.output.parent / "scope.json"
        scope_file.write_text(json.dumps(self.request["scope"]))
        result_file = self.output.parent / "empty-result.json"
        result_file.write_text(json.dumps({"request": self.request, "records": [], "computed_facts": [],
            "evidence": {}, "contexts": [], "navigation": [], "gaps": [], "answer_parts": []}))
        forbidden_package = self.port.dataset / "forbidden-package.json"
        with redirect_stderr(io.StringIO()):
            status = query_main(["--out", str(forbidden_package), "scoped-package", "--dataset", str(self.port.dataset),
                "--scope", str(scope_file), "--request", str(result_file)])
        self.assertEqual(status, 2)
        self.assertFalse(forbidden_package.exists())
        self.assertEqual(before, {str(p.relative_to(self.port.dataset)): digest(p.read_bytes())
                                 for p in self.port.dataset.rglob("*") if p.is_file()})

    def test_missing_source_metadata_and_quote_locators_are_explicit_gaps_with_namespaced_bindings(self):
        def finish(packet):
            value = packet["history"][-1]["result"]
            return {"action": "finish", "answer_parts": [{"requested_information": "Operating margin",
                "computed_ids": [fact["computed_id"] for fact in value["computed_facts"]]}]}

        planner = ScriptedPlanner([{"action": "query", "plan": {"calculations": [{
            "formula_id": "operating_margin", "entity_id": "acme-services", "periods": [{
                "kind": "quarter", "start": "2031-04-01", "end": "2031-06-30"}]}]}}, finish])
        result = asyncio.run(DataQueryAgent(self.port, planner).run_scoped(self.request, output=self.output))
        self.assertEqual(result["status"], "answered")
        package = read_json(self.output / "evidence-package.json")
        EvidencePackage.model_validate(package)
        self.assertTrue({"quote_without_read_parent", "source_metadata_incomplete"}
                        <= {g["reason"] for g in package["gaps"]})
        self.assertEqual(package["source_companies"], {"acme-2031": "acme"})
        quotes = [a for a in package["artifacts"] if a["kind"] == "source_quote"]
        self.assertEqual(len(quotes), 2)
        for quote in quotes:
            self.assertEqual(quote["derived_from"], [])
            self.assertEqual(quote["provenance"]["verification"], "snapshot_verified")
            self.assertIsNone(quote["locators"][0]["block_id"])
            self.assertIsNone(quote["locators"][0]["source_sha256"])
            self.assertIsNone(quote["locators"][0]["source_url"])
        self.assertNotEqual(package["bindings"]["record:revenue"], package["bindings"]["evidence:revenue"])
        self.assertEqual(artifact_for(package, "record", "revenue")[0]["payload"]["record"]["value_decimal"], "900")
        self.assertFalse(any(a["kind"] in ("source_text", "source_table") for a in package["artifacts"]))


if __name__ == "__main__":
    unittest.main()
