"""Pure evidence package contracts; no files, providers or retrieval side effects."""
import copy
import unittest

from pydantic import ValidationError

from uteki.domain.research_data.evidence_package import (
    ComputedScalar, EvidenceArtifact, EvidencePackage, ImageReference, PACKAGE_VERSION,
    SourceLocator, SourceQuote, SourceTable, SourceText,
)


def locator(block_id="b1"):
    return {"source_snapshot_id": "acme-annual", "source_sha256": "a" * 64,
            "source_url": "https://example.invalid/annual", "available_at": "2032-02-01",
            "index_id": "index-acme", "block_id": block_id, "reported_page": None}


def provenance(method, verification="snapshot_verified"):
    return {"method": method, "method_id": method + "-v1", "verification": verification}


def artifact(aid, kind, payload, parents=(), method="source_read", locators=None):
    return {"artifact_id": aid, "kind": kind, "source_snapshot_ids": ["acme-annual"],
            "locators": [locator()] if locators is None else locators,
            "derived_from": list(parents), "provenance": provenance(method), "payload": payload}


def fixture():
    text = artifact("text", "source_text", {"text": "Revenue was 100.",
        "block": {"block_id": "b1", "type": "paragraph", "text": "Revenue was 100."}})
    table_data = {"rows": [[{"text": "Revenue"}, {"text": "100"}]]}
    table = artifact("table", "source_table", {"text": "Revenue 100", "table": table_data,
        "block": {"block_id": "b2", "type": "table", "text": "Revenue 100", "table": table_data}},
        locators=[locator("b2")])
    quote = artifact("quote", "source_quote", {"text": "100", "evidence": {"quote": "100"}},
                     parents=("text",), method="source_quote")
    record = {"record_id": "rev", "record_type": "metric", "entity_id": "acme-services", "metric_id": "revenue",
        "period": {"kind": "year", "start": "2031-01-01", "end": "2031-12-31"},
        "value_kind": "actual", "value_decimal": "100", "value_relation": "eq", "unit": "USD",
        "accounting_basis": "reported_segment", "available_at": "2032-02-01", "source_snapshot_id": "acme-annual",
        "evidence_ids": ["ev-1"], "summary": "Synthetic fact", "origin": {}}
    normalized = artifact("normalized", "normalized_record", {"record": record, "origin_kind": "deterministic"},
                          parents=("quote",), method="normalization")
    computed = artifact("computed", "computed_scalar", {"fact": {"computed_id": "calc-1", "operand_record_ids": ["rev"],
        "value_decimal": "100.000000", "display_decimal": "100.00"}}, parents=("normalized",), method="registered_calculation", locators=[])
    model = artifact("extracted", "model_extract", {"extraction": {"statement": "Synthetic model extraction"}},
                     parents=("text",), method="model", locators=[])
    summary = artifact("summary", "model_summary", {"text": "Synthetic summary, not original wording."},
                       parents=("extracted",), method="model", locators=[])
    image = artifact("image", "image_reference", {"alt_text": "Source-provided alt text", "image_asset_id": "img-1",
        "asset_metadata": {"filename": "figure.png"}, "bytes_status": "metadata_only"}, locators=[locator("b3")])
    return {"schema_version": PACKAGE_VERSION, "bundle_id": "bundle-test",
        "scope": {"snapshot_id": "synthetic-snapshot", "company_ids": ["acme"], "source_snapshot_ids": ["acme-annual"],
                  "source_policy_id": "local-frozen-v1", "knowledge_cutoff": "2032-03-01", "include_candidates": True},
        "source_companies": {"acme-annual": "acme"},
        "artifacts": [text, table, quote, normalized, computed, model, summary, image],
        "bindings": {"context:ctx-1": ["text", "table", "image"], "record:rev": ["normalized"], "evidence:ev-1": ["quote"]},
        "coverage": [{"source_snapshot_id": "acme-annual", "node_id": "business", "block_ids": ["b1", "b2"], "mode": "body_returned"},
                     {"source_snapshot_id": "acme-annual", "block_ids": ["b3"], "mode": "image_reference_only"}], "gaps": []}


class EvidencePackageContractTests(unittest.TestCase):
    def test_typed_roundtrip_preserves_originals_and_does_not_claim_semantic_completeness(self):
        package = EvidencePackage.model_validate(fixture())
        self.assertEqual(package.schema_version, PACKAGE_VERSION)
        self.assertEqual(package.semantic_completeness, "not_evaluated")
        self.assertEqual(package.artifacts[0].payload.block["text"], "Revenue was 100.")
        self.assertIsInstance(package.artifacts[0].payload, SourceText)
        self.assertIsInstance(package.artifacts[1].payload, SourceTable)
        self.assertEqual(EvidencePackage.model_validate_json(package.model_dump_json()), package)
        self.assertIsNone(package.artifacts[0].locators[0].reported_page)
        self.assertEqual(package.artifacts[-1].payload.ocr_status, "not_run")
        self.assertEqual(package.artifacts[-1].payload.vision_status, "not_run")

    def test_source_payloads_cannot_conflict_or_disguise_an_image_as_text(self):
        for update in ({"text": "rewritten"}, {"block": {"type": "image", "text": "Revenue was 100."}},
                       {"block": {"type": "table", "text": "Revenue was 100."}}):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                SourceText.model_validate({**fixture()["artifacts"][0]["payload"], **update})
        table = fixture()["artifacts"][1]["payload"]
        with self.assertRaises(ValidationError):
            SourceTable.model_validate({**table, "table": {"rewritten": True}})
        with self.assertRaises(ValidationError):
            EvidenceArtifact.model_validate({**fixture()["artifacts"][0], "kind": "source_table"})

    def test_scope_mapping_is_exact_and_sources_never_inferred_from_ids(self):
        for mapping in ({}, {"acme-annual": "other"}, {"acme-annual": "acme", "extra": "acme"}):
            with self.subTest(mapping=mapping), self.assertRaises(ValidationError):
                EvidencePackage.model_validate({**fixture(), "source_companies": mapping})
        data = fixture()
        data["artifacts"][0]["source_snapshot_ids"] = ["other-annual"]
        with self.assertRaises(ValidationError):
            EvidencePackage.model_validate(data)
        data = fixture()
        data["artifacts"][0]["locators"][0]["source_snapshot_id"] = "other-annual"
        with self.assertRaises(ValidationError):
            EvidencePackage.model_validate(data)

    def test_candidate_access_and_future_dates_cannot_be_overridden_by_evidence(self):
        data = fixture()
        data["scope"]["include_candidates"] = False
        with self.assertRaises(ValidationError):
            EvidencePackage.model_validate(data)
        empty = {**data, "artifacts": [], "bindings": {}, "coverage": []}
        self.assertEqual(EvidencePackage.model_validate(empty).artifacts, ())
        for place in ("locator", "record"):
            data = fixture()
            target = data["artifacts"][0]["locators"][0] if place == "locator" else data["artifacts"][3]["payload"]["record"]
            target["available_at"] = "2033-01-01"
            with self.subTest(place=place), self.assertRaises(ValidationError):
                EvidencePackage.model_validate(data)

    def test_bindings_gaps_and_artifact_ids_must_resolve_uniquely(self):
        invalid = []
        duplicate = fixture()
        duplicate["artifacts"].append(copy.deepcopy(duplicate["artifacts"][0]))
        invalid.append(duplicate)
        unknown_binding = fixture()
        unknown_binding["bindings"]["context:wrong"] = ["missing"]
        invalid.append(unknown_binding)
        unknown_gap = fixture()
        unknown_gap["gaps"] = [{"gap_id": "g", "reason": "missing", "artifact_ids": ["wrong"], "detail": "Invalid reference"}]
        invalid.append(unknown_gap)
        duplicate_gap = fixture()
        duplicate_gap["gaps"] = [{"gap_id": "g", "reason": "known", "detail": "Gap"}] * 2
        invalid.append(duplicate_gap)
        for data in invalid:
            with self.subTest(data=data["bindings"]), self.assertRaises(ValidationError):
                EvidencePackage.model_validate(data)

    def test_derivation_requires_real_parents_and_an_acyclic_graph(self):
        missing = fixture()
        missing["artifacts"][5]["derived_from"] = ["missing-parent"]
        with self.assertRaisesRegex(ValidationError, "missing parent"):
            EvidencePackage.model_validate(missing)
        cyclic = fixture()
        cyclic["artifacts"][5]["derived_from"] = ["summary"]
        with self.assertRaisesRegex(ValidationError, "acyclic"):
            EvidencePackage.model_validate(cyclic)
        root = fixture()["artifacts"][0]
        with self.assertRaisesRegex(ValidationError, "source roots"):
            EvidenceArtifact.model_validate({**root, "derived_from": ["summary"]})

    def test_model_outputs_must_remain_distinct_and_reference_parents(self):
        model = fixture()["artifacts"][5]
        for changes in ({"derived_from": []}, {"provenance": provenance("source_read")}, {"kind": "source_text"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                EvidenceArtifact.model_validate({**model, **changes})

    def test_computed_values_are_finite_and_operands_are_normalized_parents(self):
        fact = fixture()["artifacts"][4]["payload"]["fact"]
        for value in ("NaN", "Infinity", "-Infinity", "not-a-number", 100):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                ComputedScalar(fact={**fact, "value_decimal": value})
        for operands in ([], ["rev", "rev"], [" "]):
            with self.subTest(operands=operands), self.assertRaises(ValidationError):
                ComputedScalar(fact={**fact, "operand_record_ids": operands})
        wrong = fixture()
        wrong["artifacts"][4]["derived_from"] = ["text"]
        with self.assertRaisesRegex(ValidationError, "normalized records"):
            EvidencePackage.model_validate(wrong)
        wrong = fixture()
        wrong["artifacts"][4]["payload"]["fact"]["operand_record_ids"] = ["other-record"]
        with self.assertRaisesRegex(ValidationError, "operand IDs"):
            EvidencePackage.model_validate(wrong)

    def test_detached_quote_requires_snapshot_verification_and_explicit_gap(self):
        data = fixture()
        quote = data["artifacts"][2]
        quote["derived_from"] = []
        with self.assertRaisesRegex(ValidationError, "quote_without_read_parent"):
            EvidencePackage.model_validate(data)
        data["gaps"] = [{"gap_id": "quote-gap", "reason": "quote_without_read_parent", "artifact_ids": ["quote"],
                         "detail": "Snapshot quote retained; original surrounding blocks were not returned."}]
        EvidencePackage.model_validate(data)
        quote["provenance"]["verification"] = "source_verified"
        with self.assertRaises(ValidationError):
            EvidencePackage.model_validate(data)

    def test_quote_display_cannot_disagree_with_retained_evidence_or_parent_text(self):
        with self.assertRaisesRegex(ValidationError, "retained evidence quote"):
            SourceQuote(text="Rewritten quote", evidence={"quote": "Original quote"})
        data = fixture()
        data["artifacts"][2]["payload"] = {"text": "Invented claim", "evidence": {"quote": "Invented claim"}}
        with self.assertRaisesRegex(ValidationError, "corresponding original parent block"):
            EvidencePackage.model_validate(data)

    def test_quote_locator_cannot_borrow_the_text_from_another_block_or_source(self):
        for changes in ({"block_id": "b2"}, {"index_id": "another-index"}, {"source_sha256": "b" * 64},
                        {"char_start": 0, "char_end": 3}):
            data = fixture()
            data["artifacts"][2]["locators"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValidationError, "corresponding original parent block"):
                EvidencePackage.model_validate(data)
        for evidence in ({"quote": "100", "source_snapshot_id": "other-annual"}, {"quote": "100", "block_id": "b2"}):
            data = fixture()
            data["artifacts"][2]["payload"]["evidence"] = evidence
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValidationError, "conflicts"):
                EvidencePackage.model_validate(data)
        # The actual anchor can coexist with additional context parents.
        data = fixture()
        data["artifacts"][2]["derived_from"] = ["text", "table"]
        data["artifacts"][2]["locators"][0].update(char_start=12, char_end=15)
        EvidencePackage.model_validate(data)

    def test_missing_source_metadata_is_kept_unknown_with_explicit_gap(self):
        data = fixture()
        data["artifacts"][0]["locators"][0]["source_sha256"] = None
        with self.assertRaisesRegex(ValidationError, "source_metadata_incomplete"):
            EvidencePackage.model_validate(data)
        data["gaps"] = [{"gap_id": "source-gap", "reason": "source_metadata_incomplete",
                         "source_snapshot_ids": ["acme-annual"], "detail": "Source hash was not supplied."}]
        result = EvidencePackage.model_validate(data)
        self.assertIsNone(result.artifacts[0].locators[0].source_sha256)

    def test_locations_need_explicit_coordinate_systems_and_ordered_ranges(self):
        for changes in ({"char_start": 1}, {"char_start": 4, "char_end": 4}, {"cell": {"row": 1}},
                        {"bbox": [0, 0, 1, 1]}, {"bbox": [2, 0, 1, 1], "region_coordinate_system": "pixels"},
                        {"bbox": [0, 0, float("inf"), 1], "region_coordinate_system": "pixels"}, {"reported_page": " "}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                SourceLocator.model_validate({**locator(), **changes})
        valid = SourceLocator.model_validate({**locator(), "char_start": 0, "char_end": 4,
                    "cell": {"row": 0, "column": 1}, "bbox": [0, 0, 100, 200], "region_coordinate_system": "pixels"})
        self.assertEqual(valid.char_start, 0)

    def test_image_bytes_and_ocr_claims_cannot_be_invented(self):
        ImageReference(bytes_status="metadata_only")
        ImageReference(bytes_status="verified_local", image_asset_id="image-1", bytes_sha256="b" * 64)
        for changes in ({"bytes_status": "verified_local"}, {"bytes_status": "metadata_only", "bytes_sha256": "b" * 64},
                        {"bytes_status": "metadata_only", "ocr_status": "completed"},
                        {"bytes_status": "metadata_only", "vision_status": "completed"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ImageReference.model_validate(changes)

    def test_coverage_cannot_claim_unreturned_body_or_image_understanding(self):
        for changes in ({"block_ids": ["missing"]}, {"block_ids": ["b3"]}, {"semantic_completeness": "complete"}):
            data = fixture()
            data["coverage"][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                EvidencePackage.model_validate(data)
        with self.assertRaises(ValidationError):
            EvidencePackage.model_validate({**fixture(), "semantic_completeness": "complete"})


if __name__ == "__main__":
    unittest.main()
