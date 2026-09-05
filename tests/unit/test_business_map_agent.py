import json
import unittest
from pathlib import Path

from uteki.agents.business_map import AgentConfig, BusinessMapAgent, BusinessMapRequest
from uteki.agents.business_map.model_port import ModelResponse
from uteki.domain.documents import Document, Paragraph
from uteki.infrastructure.document_sources.sec import text_hash


class FakeModel:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def generate_json(self, **kwargs) -> ModelResponse:
        return ModelResponse(self.payload, kwargs["model"], input_tokens=100, output_tokens=50)


class BusinessMapAgentTests(unittest.TestCase):
    def _document(self) -> Document:
        texts = ("ITEM 1. BUSINESS", "Alphabet business paragraph.", "ITEM 1A. RISK FACTORS")
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

    def test_runs_through_public_contract(self) -> None:
        result = BusinessMapAgent(FakeModel(self._payload())).run(
            BusinessMapRequest(self._document()), AgentConfig(model="fake/model")
        )
        self.assertEqual(result.candidate.company_id, "alphabet")
        self.assertEqual(result.run.input_tokens, 100)

    def test_rejects_evidence_hash_not_in_source(self) -> None:
        payload = self._payload()
        payload["evidence"][0]["text_hash"] = "wrong"
        with self.assertRaisesRegex(ValueError, "does not match source"):
            BusinessMapAgent(FakeModel(payload)).run(
                BusinessMapRequest(self._document()), AgentConfig(model="fake/model")
            )


if __name__ == "__main__":
    unittest.main()
