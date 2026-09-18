import json
import unittest
from copy import deepcopy
import hashlib
from dataclasses import asdict, replace

from uteki.agents.business_map import AgentConfig, BusinessMapAgent, BusinessMapRequest, BusinessMapRunError
from uteki.agents.business_map.model_port import ModelGenerationError, ModelResponse
from uteki.domain.documents import Document, Paragraph
from uteki.domain.runs import RunStatus
from uteki.infrastructure.document_sources.sec import text_hash


class FakeModel:
    def __init__(self, payload, *, error: Exception | None = None, raw_output=None, response_overrides=None) -> None:
        self.payload = payload
        self.error = error
        self.raw_output = raw_output
        self.response_overrides = response_overrides or {}
        self.calls = []

    def generate_json(self, **kwargs) -> ModelResponse:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return ModelResponse(**{
            "payload": self.payload, "model": "fake/resolved-model", "input_tokens": 100, "output_tokens": 50,
            "cost_usd": 0.005, "metadata": {"provider_request_id": "fixture-1"}, "raw_output": self.raw_output,
            **self.response_overrides,
        })


class BusinessMapAgentTests(unittest.TestCase):
    def _document(self) -> Document:
        texts = (
            "ITEM 1. BUSINESS", "Alphabet business paragraph.", "ITEM 1A. RISK FACTORS",
            "Risk paragraph outside the supplied section.",
        )
        paragraphs = tuple(Paragraph(i + 1, text, text_hash(text)) for i, text in enumerate(texts))
        return Document("sec-0001652044-26-000018", "https://example.test", "content", paragraphs)

    def _payload(self) -> dict:
        return {
            "schema_version": "0.1",
            "company_id": "alphabet",
            "document_id": "sec-0001652044-26-000018",
            "summary": "summary",
            "businesses": [{
                "id": "alphabet", "name": "Alphabet", "kind": "company",
                "description": "description", "evidence_ids": ["e1"]
            }],
            "relationships": [], "unknowns": [],
            "evidence": [{
                "id": "e1", "document_id": "sec-0001652044-26-000018",
                "section_path": ["ITEM 1. BUSINESS"], "paragraph_ordinal": 2,
                "text_hash": text_hash("Alphabet business paragraph."),
                "source_url": "https://example.test", "support": "supports"
            }]
        }

    def _run(self, model=None, *, document=None, config=None):
        return BusinessMapAgent(model or FakeModel(self._payload())).run(
            BusinessMapRequest(document or self._document()), config or AgentConfig(model="fake/requested-model"),
        )

    def test_runs_through_public_contract(self) -> None:
        model = FakeModel(self._payload())
        result = self._run(model)
        self.assertEqual(result.candidate.company_id, "alphabet")
        self.assertEqual(result.candidate.businesses[0].review_status, "candidate")
        self.assertEqual(result.run.status, RunStatus.SUCCEEDED)
        self.assertEqual(result.run.input_tokens, 100)
        self.assertEqual(result.run.model, "fake/resolved-model")
        self.assertEqual(result.run.configuration["requested_model"], "fake/requested-model")
        self.assertEqual(result.run.configuration["model_metadata"]["provider_request_id"], "fixture-1")
        self.assertEqual(result.run.prompt_version, "business-map-v0.1")
        self.assertEqual(result.run.configuration["temperature"], model.calls[0]["temperature"])
        self.assertIsNone(result.run.error_stage)
        self.assertNotIn("Risk paragraph", model.calls[0]["user"])
        json.dumps(asdict(result.run), allow_nan=False)

    def test_records_exact_input_and_section_boundaries(self) -> None:
        result = self._run()
        manifest = result.run.input_manifest
        self.assertEqual(manifest["document_id"], self._document().id)
        self.assertEqual(manifest["source_url"], self._document().source_url)
        self.assertEqual(manifest["source_content_hash"], "content")
        self.assertEqual(manifest["selection_mode"], "section")
        self.assertEqual(manifest["paragraph_count"], 2)
        self.assertEqual(manifest["start_ordinal"], 1)
        self.assertEqual(manifest["end_ordinal_exclusive"], 3)
        self.assertEqual([item["ordinal"] for item in manifest["paragraphs"]], [1, 2])
        self.assertEqual(manifest["paragraphs"][1]["text"], "Alphabet business paragraph.")
        replay = self._run()
        self.assertEqual(result.run.input_hash, replay.run.input_hash)
        self.assertEqual(result.run.prompt_hash, replay.run.prompt_hash)

    def test_actual_input_change_changes_fingerprints_even_with_same_declared_content_hash(self) -> None:
        initial = self._run()
        document = self._document()
        changed_text = "Changed Alphabet business paragraph."
        changed_paragraph = Paragraph(2, changed_text, text_hash(changed_text))
        changed_document = replace(document, paragraphs=(document.paragraphs[0], changed_paragraph, *document.paragraphs[2:]))
        payload = self._payload()
        payload["evidence"][0]["text_hash"] = changed_paragraph.text_hash
        changed = self._run(FakeModel(payload), document=changed_document)
        self.assertNotEqual(initial.run.input_hash, changed.run.input_hash)
        self.assertNotEqual(initial.run.prompt_hash, changed.run.prompt_hash)

    def test_unknown_prompt_version_cannot_be_mislabelled_as_a_run(self) -> None:
        model = FakeModel(self._payload())
        with self.assertRaisesRegex(BusinessMapRunError, "unsupported prompt_version") as caught:
            self._run(model, config=AgentConfig(model="fake/model", prompt_version="invented-v9"))
        self.assertEqual(model.calls, [])
        self.assertEqual(caught.exception.run.status, RunStatus.FAILED)
        self.assertEqual(caught.exception.run.prompt_version, "")
        self.assertEqual(caught.exception.run.prompt_hash, "")
        self.assertEqual(caught.exception.run.configuration["requested_prompt_version"], "invented-v9")

    def test_missing_section_is_recorded_without_calling_model(self) -> None:
        model = FakeModel(self._payload())
        with self.assertRaisesRegex(BusinessMapRunError, "section start not found") as caught:
            BusinessMapAgent(model).run(
                BusinessMapRequest(self._document(), section_start="MISSING"), AgentConfig(model="fake/model"),
            )
        self.assertEqual(model.calls, [])
        self.assertEqual(caught.exception.run.error_stage, "input")

    def test_rejects_corrupt_input_hash_before_model_call(self) -> None:
        document = self._document()
        paragraphs = list(document.paragraphs)
        paragraphs[1] = replace(paragraphs[1], text_hash="wrong")
        model = FakeModel(self._payload())
        with self.assertRaisesRegex(BusinessMapRunError, "paragraph 2 text hash") as caught:
            self._run(model, document=replace(document, paragraphs=tuple(paragraphs)))
        self.assertEqual(model.calls, [])
        self.assertEqual(caught.exception.run.error_stage, "input")

    def test_rejects_duplicate_ordinal_before_model_call(self) -> None:
        document = self._document()
        paragraphs = (*document.paragraphs, document.paragraphs[1])
        model = FakeModel(self._payload())
        with self.assertRaisesRegex(BusinessMapRunError, "duplicate paragraph ordinal"):
            self._run(model, document=replace(document, paragraphs=paragraphs))
        self.assertEqual(model.calls, [])

    def test_paragraph_hash_uses_source_whitespace_normalization(self) -> None:
        document = self._document()
        paragraphs = list(document.paragraphs)
        paragraphs[1] = replace(paragraphs[1], text=" Alphabet\n business   paragraph. ")
        self.assertEqual(self._run(document=replace(document, paragraphs=tuple(paragraphs))).run.status, RunStatus.SUCCEEDED)

    def test_rejects_evidence_hash_not_in_source(self) -> None:
        payload = self._payload()
        payload["evidence"][0]["text_hash"] = "wrong"
        with self.assertRaisesRegex(ValueError, "does not match source") as caught:
            self._run(FakeModel(payload))
        failure = caught.exception
        self.assertIsInstance(failure, BusinessMapRunError)
        self.assertEqual(failure.run.status, RunStatus.FAILED)
        self.assertEqual(failure.run.error_stage, "evidence")
        self.assertEqual(failure.run.output_tokens, 50)
        self.assertEqual(failure.run.cost_usd, 0.005)
        self.assertEqual(failure.raw_output, payload)
        self.assertIsNotNone(failure.run.input_hash)

    def test_rejects_valid_document_evidence_outside_model_input(self) -> None:
        for ordinal in (3, 4):
            with self.subTest(ordinal=ordinal):
                payload = self._payload()
                paragraph = self._document().paragraphs[ordinal - 1]
                payload["evidence"][0].update(paragraph_ordinal=ordinal, text_hash=paragraph.text_hash)
                with self.assertRaisesRegex(BusinessMapRunError, "not supplied to the model") as caught:
                    self._run(FakeModel(payload))
                self.assertEqual(caught.exception.raw_output, payload)

    def test_rejects_other_source_url(self) -> None:
        payload = self._payload()
        payload["evidence"][0]["source_url"] = "https://different.example.test"
        with self.assertRaisesRegex(BusinessMapRunError, "source_url does not match"):
            self._run(FakeModel(payload))

    def test_rejects_other_document_ids(self) -> None:
        for location in ("candidate", "evidence"):
            with self.subTest(location=location):
                payload = self._payload()
                target = payload if location == "candidate" else payload["evidence"][0]
                target["document_id"] = "different-document"
                with self.assertRaises(BusinessMapRunError) as caught:
                    self._run(FakeModel(payload))
                self.assertEqual(caught.exception.run.error_stage, "evidence")

    def test_invalid_schema_retains_raw_output_and_failure(self) -> None:
        invalid_payloads = [
            [], {"summary": "incomplete"}, {**self._payload(), "businesses": "not an array"},
            {**self._payload(), "schema_version": "unsupported-v9"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(BusinessMapRunError) as caught:
                    self._run(FakeModel(payload))
                self.assertEqual(caught.exception.run.error_stage, "schema")
                self.assertEqual(caught.exception.raw_output, payload)
                self.assertEqual(caught.exception.run.status, RunStatus.FAILED)

    def test_rejects_types_that_the_stored_map_parser_would_coerce(self) -> None:
        payloads = []
        for collection, field, value in (
            ("businesses", "evidence_ids", "e1"),
            ("businesses", "description", 123),
            ("evidence", "section_path", "ITEM 1. BUSINESS"),
            ("evidence", "paragraph_ordinal", True),
        ):
            payload = self._payload()
            payload[collection][0][field] = value
            payloads.append(payload)
        for payload in payloads:
            with self.subTest(payload=payload):
                with self.assertRaises(BusinessMapRunError) as caught:
                    self._run(FakeModel(payload))
                self.assertEqual(caught.exception.run.error_stage, "schema")

    def test_model_cannot_set_human_review_status(self) -> None:
        for collection in ("businesses", "relationships"):
            for status in ("accepted", "edited", "rejected", "ambiguous"):
                with self.subTest(collection=collection, status=status):
                    payload = self._payload()
                    if collection == "relationships":
                        payload[collection] = [{
                            "source_id": "alphabet", "target_id": "alphabet", "kind": "supports",
                            "description": "relationship", "evidence_ids": ["e1"],
                        }]
                    payload[collection][0]["review_status"] = status
                    with self.assertRaisesRegex(BusinessMapRunError, "must remain candidate") as caught:
                        self._run(FakeModel(payload))
                    self.assertEqual(caught.exception.raw_output, payload)

    def test_model_cannot_add_evaluation_or_adoption_metadata(self) -> None:
        for extra in ({"metadata": {"adopted": True}}, {"evaluation": {"passed": True}}, {"review_status": "accepted"}):
            with self.subTest(extra=extra):
                payload = {**self._payload(), **extra}
                with self.assertRaises(BusinessMapRunError):
                    self._run(FakeModel(payload))

    def test_model_exception_is_an_auditable_failed_run(self) -> None:
        error = RuntimeError("provider unavailable")
        with self.assertRaisesRegex(BusinessMapRunError, "provider unavailable") as caught:
            self._run(FakeModel(None, error=error))
        failure = caught.exception
        self.assertEqual(failure.run.error_stage, "model")
        self.assertEqual(failure.run.error_type, "RuntimeError")
        self.assertEqual(failure.run.status, RunStatus.FAILED)
        self.assertIsNone(failure.run.cost_usd)
        self.assertIsNone(failure.raw_output)
        self.assertIs(failure.__cause__, error)
        self.assertTrue(failure.run.prompt_hash)

    def test_adapter_failure_preserves_available_output_and_usage(self) -> None:
        error = ModelGenerationError(
            "invalid JSON", raw_output='{"unfinished":', model="fake/provider-model",
            input_tokens=123, output_tokens=7, cost_usd=0.001,
        )
        with self.assertRaises(BusinessMapRunError) as caught:
            self._run(FakeModel(None, error=error))
        failure = caught.exception
        self.assertEqual(failure.raw_output, '{"unfinished":')
        self.assertEqual(failure.run.model, "fake/provider-model")
        self.assertEqual(failure.run.input_tokens, 123)
        self.assertEqual(failure.run.cost_usd, 0.001)

    def test_json_decoder_failure_retains_original_text(self) -> None:
        with self.assertRaises(BusinessMapRunError) as caught:
            self._run(FakeModel(None, error=json.JSONDecodeError("invalid", "{broken", 1)))
        self.assertEqual(caught.exception.raw_output, "{broken")

    def test_invalid_response_retains_provider_text_when_available(self) -> None:
        with self.assertRaises(BusinessMapRunError) as caught:
            self._run(FakeModel([], raw_output="[]"))
        self.assertEqual(caught.exception.raw_output, "[]")

    def test_invalid_provider_return_value_is_retained(self) -> None:
        class InvalidResponseModel:
            def generate_json(self, **kwargs):
                return {"bad": "provider envelope"}

        with self.assertRaisesRegex(BusinessMapRunError, "must return ModelResponse") as caught:
            self._run(InvalidResponseModel())
        self.assertEqual(caught.exception.run.error_stage, "model")
        self.assertEqual(caught.exception.raw_output, {"bad": "provider envelope"})

    def test_complete_candidate_keeps_domain_fields_and_candidate_status(self) -> None:
        payload = self._payload()
        payload["businesses"][0].update(
            products_services=["service"], customers=["customer"], importance_signals=["signal"],
            monetization=[{"description": "fees", "basis": "explicit", "evidence_ids": ["e1"]}],
        )
        payload["businesses"].append({
            "id": "service", "name": "Service", "kind": "business", "description": "service",
            "evidence_ids": ["e1"], "review_status": "candidate",
        })
        payload["relationships"] = [{
            "source_id": "service", "target_id": "alphabet", "kind": "part_of",
            "description": "part of company", "evidence_ids": ["e1"], "review_status": "candidate",
        }]
        payload["unknowns"] = [{
            "id": "unknown", "question": "What is unknown?", "materiality": "material",
            "related_business_ids": ["service"], "reason_unanswered": "not disclosed", "evidence_ids": [],
        }]
        result = self._run(FakeModel(payload))
        self.assertEqual(result.candidate.relationships[0].review_status, "candidate")
        self.assertEqual(result.candidate.businesses[0].monetization[0].description, "fees")
        self.assertEqual(result.candidate.unknowns[0].related_business_ids, ("service",))

    def test_returned_results_do_not_share_provider_payload(self) -> None:
        payload = self._payload()
        payload["metadata"] = {}
        result = self._run(FakeModel(payload))
        frozen_raw = deepcopy(result.raw_output)
        payload["businesses"][0]["description"] = "changed after return"
        payload["metadata"]["adopted"] = True
        self.assertEqual(result.raw_output, frozen_raw)
        self.assertEqual(result.candidate.businesses[0].description, "description")
        self.assertEqual(result.candidate.metadata, {})

    def test_default_v01_retains_its_original_prompt_bytes(self) -> None:
        model = FakeModel(self._payload())
        result = self._run(model)
        self.assertEqual(result.run.prompt_version, "business-map-v0.1")
        self.assertEqual(hashlib.sha256(model.calls[0]["system"].encode()).hexdigest(),
                         "71b2601e1fa49881175c699ab4d015ce8030e44ddd21e7ced83555ae68c78951")
        self.assertEqual(hashlib.sha256(model.calls[0]["user"].encode()).hexdigest(),
                         "64048102690c81749cde5bef80e6cbd1cbbb847fde5eb62200aabf7bb04c48d3")

    def test_v02_supplies_complete_nested_contract_and_current_domain_kinds(self) -> None:
        from uteki.domain.business_map import BusinessKind, RelationshipKind

        payload = self._payload()
        payload["businesses"].append({
            "id": "revenue", "name": "Revenue line", "kind": "revenue_line",
            "description": "disclosed revenue", "evidence_ids": ["e1"],
        })
        payload["relationships"] = [{
            "source_id": "revenue", "target_id": "alphabet", "kind": "revenue_component_of",
            "description": "component", "evidence_ids": ["e1"],
        }]
        model = FakeModel(payload)
        result = self._run(model, config=AgentConfig(model="fake/model", prompt_version="business-map-v0.2"))
        self.assertEqual(result.run.prompt_version, "business-map-v0.2")
        prompt = model.calls[0]["user"]
        schema = json.loads(prompt.split("OUTPUT JSON SCHEMA\n", 1)[1].split("\n\nSOURCE PARAGRAPHS\n", 1)[0])
        self.assertEqual(schema["properties"]["schema_version"], {"const": "0.1"})
        self.assertEqual(set(schema["required"]), set(self._payload()))
        self.assertFalse(schema["additionalProperties"])
        definitions = schema["$defs"]
        self.assertEqual(set(definitions["business"]["properties"]["kind"]["enum"]), set(BusinessKind))
        self.assertEqual(set(definitions["relationship"]["properties"]["kind"]["enum"]), set(RelationshipKind))
        self.assertEqual(set(definitions["evidence"]["required"]), set(payload["evidence"][0]))
        self.assertIn("reason_unanswered", definitions["unknown"]["required"])
        self.assertEqual(set(definitions["monetization"]["required"]), {"description", "basis", "evidence_ids"})
        self.assertEqual(definitions["monetization"]["properties"]["basis"]["enum"], ["explicit", "unknown"])
        for definition in definitions.values():
            self.assertFalse(definition["additionalProperties"])
        self.assertEqual(definitions["business"]["properties"]["review_status"], {"const": "candidate"})
        self.assertEqual(schema["properties"]["metadata"]["maxProperties"], 0)
        self.assertNotIn("Risk paragraph", prompt)
        self.assertNotEqual(result.run.prompt_hash, self._run().run.prompt_hash)

    def test_v02_rejects_unapproved_derived_statement_and_retains_raw_failure(self) -> None:
        payload = self._payload()
        payload["businesses"][0]["monetization"] = [{
            "description": "inferred economics", "basis": "derived", "evidence_ids": ["e1"],
        }]
        raw = "\n" + json.dumps(payload, indent=1) + "\n"
        with self.assertRaisesRegex(BusinessMapRunError, "no approved deterministic derivation rules") as caught:
            self._run(FakeModel(payload, raw_output=raw),
                      config=AgentConfig(model="fake/model", prompt_version="business-map-v0.2"))
        self.assertEqual(caught.exception.raw_output, raw)
        self.assertEqual(caught.exception.run.error_stage, "schema")
        self.assertEqual(caught.exception.run.prompt_version, "business-map-v0.2")
        json.dumps(asdict(caught.exception.run), allow_nan=False)
        # Historical prompt configurations retain their original domain contract.
        legacy = self._run(FakeModel(payload), config=AgentConfig(model="fake/model", prompt_version="business-map-v0.1"))
        self.assertEqual(legacy.candidate.businesses[0].monetization[0].basis, "derived")

    def test_full_document_requires_explicit_paired_none_and_covers_later_evidence(self) -> None:
        document = self._document()
        payload = self._payload()
        payload["evidence"][0].update(paragraph_ordinal=4, text_hash=document.paragraphs[3].text_hash)
        model = FakeModel(payload)
        result = BusinessMapAgent(model).run(
            BusinessMapRequest(document, section_start=None, section_end=None),
            AgentConfig(model="fake/model", prompt_version="business-map-v0.2"),
        )
        manifest = result.run.input_manifest
        self.assertEqual(manifest["selection_mode"], "full_document")
        self.assertEqual((manifest["start_ordinal"], manifest["end_ordinal_exclusive"]), (1, 5))
        self.assertEqual(manifest["paragraph_count"], 4)
        self.assertIsNone(manifest["section_start"])
        self.assertIsNone(manifest["section_end"])
        self.assertEqual([paragraph["ordinal"] for paragraph in manifest["paragraphs"]], [1, 2, 3, 4])
        self.assertIn(document.paragraphs[3].text, model.calls[0]["user"])
        self.assertNotEqual(result.run.input_hash, self._run().run.input_hash)
        payload["evidence"][0]["paragraph_ordinal"] = 5
        with self.assertRaisesRegex(BusinessMapRunError, "not supplied to the model"):
            BusinessMapAgent(FakeModel(payload)).run(
                BusinessMapRequest(document, None, None), AgentConfig(model="fake/model"),
            )

    def test_mixed_or_empty_full_document_selection_fails_before_model_call(self) -> None:
        requests = [
            BusinessMapRequest(self._document(), None, "ITEM 1A. RISK FACTORS"),
            BusinessMapRequest(self._document(), "ITEM 1. BUSINESS", None),
            BusinessMapRequest(replace(self._document(), paragraphs=()), None, None),
        ]
        for request in requests:
            with self.subTest(request=request):
                model = FakeModel(self._payload())
                with self.assertRaises(BusinessMapRunError) as caught:
                    BusinessMapAgent(model).run(request, AgentConfig(model="fake/model"))
                self.assertEqual(model.calls, [])
                self.assertEqual(caught.exception.run.error_stage, "input")
                json.dumps(asdict(caught.exception.run), allow_nan=False)

    def test_explicit_section_boundaries_keep_their_selected_scope(self) -> None:
        document = self._document()
        model = FakeModel(self._payload())
        result = BusinessMapAgent(model).run(
            BusinessMapRequest(document, document.paragraphs[1].text, document.paragraphs[3].text),
            AgentConfig(model="fake/model", prompt_version="business-map-v0.2"),
        )
        manifest = result.run.input_manifest
        self.assertEqual(manifest["selection_mode"], "section")
        self.assertEqual([row["ordinal"] for row in manifest["paragraphs"]], [2, 3])
        self.assertEqual((manifest["start_ordinal"], manifest["end_ordinal_exclusive"]), (2, 4))
        self.assertNotIn(document.paragraphs[3].text, model.calls[0]["user"])

    def test_nonfinite_configuration_retains_json_safe_failure_details(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                model = FakeModel(self._payload())
                with self.assertRaisesRegex(BusinessMapRunError, "temperature must be a finite number") as caught:
                    self._run(model, config=AgentConfig(model="fake/model", temperature=value))
                self.assertEqual(model.calls, [])
                run = caught.exception.run
                self.assertEqual(run.error_stage, "configuration")
                self.assertEqual(run.configuration["temperature"],
                                 {"invalid_type": "float", "representation": repr(value)})
                json.dumps(asdict(run), allow_nan=False)

    def test_invalid_response_metadata_cannot_make_the_failure_record_unwritable(self) -> None:
        circular = {}
        circular["self"] = circular
        values = [[], {"nested": [float("nan")]}, {"score": float("inf")},
                  {1: "not a JSON key"}, {"unsupported": object()}, circular]
        for metadata in values:
            with self.subTest(metadata=repr(metadata)):
                model = FakeModel(self._payload(), response_overrides={"metadata": metadata})
                with self.assertRaisesRegex(BusinessMapRunError, "ModelResponse.metadata") as caught:
                    self._run(model)
                run = caught.exception.run
                self.assertEqual(run.error_stage, "model")
                self.assertEqual(run.input_tokens, 100)
                self.assertEqual(run.cost_usd, 0.005)
                self.assertEqual(caught.exception.raw_output, self._payload())
                json.dumps(asdict(run), allow_nan=False)

    def test_invalid_response_usage_is_rejected_and_preserved_as_invalid(self) -> None:
        for field, value in (("input_tokens", -1), ("input_tokens", True), ("input_tokens", "100"),
                             ("output_tokens", 1.5), ("output_tokens", float("nan")),
                             ("cost_usd", -0.01), ("cost_usd", float("inf")), ("cost_usd", True)):
            with self.subTest(field=field, value=value):
                model = FakeModel(self._payload(), response_overrides={field: value})
                with self.assertRaisesRegex(BusinessMapRunError, "invalid ModelResponse usage") as caught:
                    self._run(model)
                run = caught.exception.run
                self.assertEqual(run.error_stage, "model")
                self.assertIsNone(getattr(run, field))
                self.assertIn(field, run.configuration["invalid_usage"])
                self.assertIn("reason", run.configuration["invalid_usage"][field])
                json.dumps(asdict(run), allow_nan=False)

    def test_adapter_exception_with_invalid_usage_keeps_original_reason_and_known_usage(self) -> None:
        error = ModelGenerationError("provider failed", raw_output="partial output", input_tokens=42,
                                     output_tokens=float("nan"), cost_usd=float("inf"))
        with self.assertRaisesRegex(BusinessMapRunError, "provider failed") as caught:
            self._run(FakeModel(None, error=error))
        run = caught.exception.run
        self.assertEqual(run.input_tokens, 42)
        self.assertIsNone(run.output_tokens)
        self.assertIsNone(run.cost_usd)
        self.assertEqual(set(run.configuration["invalid_usage"]), {"output_tokens", "cost_usd"})
        self.assertEqual(caught.exception.raw_output, "partial output")
        json.dumps(asdict(run), allow_nan=False)

    def test_success_preserves_exact_adapter_text_and_accepts_zero_or_unknown_usage(self) -> None:
        payload = self._payload()
        raw = " \n" + json.dumps(payload, indent=3) + "\n "
        model = FakeModel(payload, raw_output=raw, response_overrides={
            "input_tokens": 0, "output_tokens": None, "cost_usd": 0,
            "metadata": {"nested": [None, False, 0, 0.5, {"request_id": "fixture"}]},
        })
        result = self._run(model)
        self.assertEqual(result.raw_output, raw)
        self.assertEqual(result.candidate.company_id, "alphabet")
        self.assertEqual(result.run.input_tokens, 0)
        self.assertIsNone(result.run.output_tokens)
        json.dumps(asdict(result.run), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
