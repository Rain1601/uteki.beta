import copy
import unittest

from uteki.infrastructure.research_data.adapters.evidence_provenance import classify_record_origin


class EvidenceProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.record = {"record_id": "sample-record", "source_snapshot_id": "source-a",
                       "record_type": "metric", "value_kind": "actual", "summary": "Normalized summary",
                       "origin": {"artifact": "inputs/financial.json", "record_index": 3,
                                  "raw_record": {"summary": "Original model wording", "evidence": [{"quote": "Quoted words"}]}}}
        self.manifest = {"model_calls": 0, "build_spec": {"inputs": [
            {"path": "inputs/financial.json", "source_snapshot_id": "source-a", "sha256": "a" * 64,
             "adapter": "alphabet-financial-v1"}]}}

    def test_deterministic_adapter_uses_exact_pinned_binding(self):
        result = classify_record_origin(self.record, self.manifest)
        self.assertEqual((result["origin_kind"], result["method_id"]), ("deterministic", "alphabet-financial-v1"))
        self.assertEqual((result["input_artifact"], result["input_sha256"]), ("inputs/financial.json", "a" * 64))
        self.assertIsNone(result["raw_model_extract"])

    def test_model_assisted_preserves_raw_record_without_relabeling_normalized_summary(self):
        self.manifest["build_spec"]["inputs"][0]["adapter"] = "alphabet-call-reviewed-v1"
        before = copy.deepcopy((self.record, self.manifest))
        result = classify_record_origin(self.record, self.manifest)
        self.assertEqual((result["origin_kind"], result["method_id"]), ("model_assisted", "alphabet-call-reviewed-v1"))
        self.assertEqual(result["record_index"], 3)
        self.assertEqual(result["raw_model_extract"]["summary"], "Original model wording")
        self.assertIn("Provider, model and prompt metadata are unavailable", " ".join(result["notes"]))
        result["raw_model_extract"]["evidence"][0]["quote"] = "Caller modification"
        self.assertEqual((self.record, self.manifest), before)

    def test_labels_ids_and_path_keywords_do_not_determine_origin(self):
        variants = [
            {"record_id": "qr-model-output", "record_type": "statement", "value_kind": "attributed_statement"},
            {"record_id": "obs-deterministic", "record_type": "metric", "value_kind": "actual"},
            {"summary": "Produced by a model or a deterministic extractor"},
        ]
        self.manifest["build_spec"]["inputs"][0]["adapter"] = "alphabet-call-reviewed-v1"
        for values in variants:
            with self.subTest(values=values):
                result = classify_record_origin({**self.record, **values}, self.manifest)
                self.assertEqual(result["origin_kind"], "model_assisted")
        self.manifest["build_spec"]["inputs"][0]["adapter"] = "unknown-model-adapter"
        result = classify_record_origin(self.record, self.manifest)
        self.assertEqual((result["origin_kind"], result["method_id"]), ("unknown", "unresolved"))
        self.assertIsNone(result["raw_model_extract"])

    def test_missing_wrong_source_partial_path_or_ambiguous_binding_is_unknown(self):
        cases = [
            {}, {"build_spec": {}}, {"build_spec": {"inputs": "not-a-list"}},
            {"build_spec": {"inputs": [{**self.manifest["build_spec"]["inputs"][0], "source_snapshot_id": "other-source"}]}},
            {"build_spec": {"inputs": [{**self.manifest["build_spec"]["inputs"][0], "path": "other/financial.json"}]}},
            {"build_spec": {"inputs": self.manifest["build_spec"]["inputs"] * 2}},
        ]
        for manifest in cases:
            with self.subTest(manifest=manifest):
                result = classify_record_origin(self.record, manifest)
                self.assertEqual((result["origin_kind"], result["method_id"]), ("unknown", "unresolved"))
                self.assertIsNone(result["input_sha256"])

    def test_missing_or_malformed_hash_does_not_establish_provenance(self):
        for value in (None, "", "a", "g" * 64, 123):
            with self.subTest(value=value):
                manifest = copy.deepcopy(self.manifest)
                manifest["build_spec"]["inputs"][0]["sha256"] = value
                result = classify_record_origin(self.record, manifest)
                self.assertEqual(result["origin_kind"], "unknown")
                self.assertIsNone(result["input_sha256"])

    def test_invalid_origin_fields_fail_closed_without_mutation(self):
        for origin in (None, [], {}, {"artifact": " "}, {"artifact": " inputs/financial.json"}):
            with self.subTest(origin=origin):
                result = classify_record_origin({**self.record, "origin": origin}, self.manifest)
                self.assertEqual(result["origin_kind"], "unknown")
        self.manifest["build_spec"]["inputs"][0]["adapter"] = "alphabet-call-reviewed-v1"
        for ordinal in (-1, True, "3", None):
            with self.subTest(ordinal=ordinal):
                record = {**self.record, "origin": {"artifact": "inputs/financial.json", "record_index": ordinal}}
                result = classify_record_origin(record, self.manifest)
                self.assertEqual(result["origin_kind"], "model_assisted")
                self.assertIsNone(result["record_index"])
                self.assertIsNone(result["raw_model_extract"])


if __name__ == "__main__":
    unittest.main()
