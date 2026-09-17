from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uteki.domain.research_data import ResearchDataRequest, evidence_bundle_from_dict
from uteki.infrastructure.research_data import LocalResearchDataPort, ResearchDataIntegrityError
from uteki.infrastructure.research_data.artifacts import SOURCE_POLICY_ID, build_research_data_artifacts


ROOT = Path(__file__).resolve().parents[2]
LEGACY_BENCHMARK = ROOT / "benchmarks/alphabet_2025_business_map/v0.2-candidate"
BENCHMARK = ROOT / "benchmarks/alphabet_2025_business_map/v0.3-candidate"
DOCUMENT = ROOT / "data/source_documents/alphabet_2025_10k"
LEGACY_RELEASE = ROOT / "data/research_data/alphabet_2025_10k/v0.1-candidate"
RELEASE = ROOT / "data/research_data/alphabet_2025_10k/v0.2-candidate"
LEGACY_GENERATED_AT = "2026-09-13T01:16:56+08:00"
GENERATED_AT = "2026-09-13T01:34:55+08:00"


class EvidenceBundleTests(unittest.TestCase):
    def test_previous_candidate_bundle_remains_unchanged(self) -> None:
        payload = json.loads((LEGACY_RELEASE / "evidence_bundle.json").read_text(encoding="utf-8"))
        bundle = evidence_bundle_from_dict(payload)

        self.assertEqual(len(bundle.claims), 51)
        self.assertEqual(len(bundle.evidence_links), 74)
        self.assertIn(
            "pending_business_map_review_decisions",
            {item.code for item in bundle.quality_diagnostics},
        )

    def test_current_candidate_bundle_separates_business_and_financial_views(self) -> None:
        payload = json.loads((RELEASE / "evidence_bundle.json").read_text(encoding="utf-8"))
        bundle = evidence_bundle_from_dict(payload)

        self.assertEqual(bundle.company_id, "alphabet")
        self.assertEqual(bundle.status, "candidate")
        self.assertEqual(bundle.business_map_version, "v0.3-candidate")
        self.assertEqual(len(bundle.claims), 57)
        self.assertEqual(len(bundle.metrics), 13)
        self.assertEqual(len(bundle.evidence_links), 80)
        self.assertEqual(len(bundle.document_context), 22)
        self.assertEqual(len(bundle.unknowns), 2)
        self.assertEqual(bundle.changes, ())
        self.assertNotIn(
            "pending_business_map_review_decisions",
            {item.code for item in bundle.quality_diagnostics},
        )

    def test_artifact_generation_is_byte_stable_for_pinned_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = Path(first) / "v0.2-candidate"
            two = Path(second) / "v0.2-candidate"
            build_research_data_artifacts(BENCHMARK, DOCUMENT, one, generated_at=GENERATED_AT)
            build_research_data_artifacts(BENCHMARK, DOCUMENT, two, generated_at=GENERATED_AT)
            for filename in ("manifest.json", "query.json", "business_map.json", "evidence_bundle.json"):
                self.assertEqual((one / filename).read_bytes(), (two / filename).read_bytes())
                self.assertEqual((one / filename).read_bytes(), (RELEASE / filename).read_bytes())

        with tempfile.TemporaryDirectory() as temporary:
            legacy = Path(temporary) / "v0.1-candidate"
            build_research_data_artifacts(
                LEGACY_BENCHMARK,
                DOCUMENT,
                legacy,
                generated_at=LEGACY_GENERATED_AT,
            )
            for filename in ("manifest.json", "query.json", "business_map.json", "evidence_bundle.json"):
                self.assertEqual((legacy / filename).read_bytes(), (LEGACY_RELEASE / filename).read_bytes())


class LocalResearchDataPortTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.port = LocalResearchDataPort(RELEASE, request_dir=Path(self.temporary.name) / "requests")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_business_map_search_and_evidence_are_source_resolvable(self) -> None:
        business_map = self.port.get_business_map("alphabet", "v0.3-candidate")
        claims = self.port.search_research_data("alphabet", "Google Cloud revenue", SOURCE_POLICY_ID)

        self.assertEqual(len(business_map.businesses), 15)
        self.assertIn("cloud-revenue-2025", {item.id for item in claims})
        links = self.port.get_claim_evidence("cloud-revenue-2025")
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].source_snapshot_id, "alphabet-2025-10k-c2f63010")
        contexts = self.port.get_document_context(tuple(item.evidence_id for item in links))
        self.assertEqual(contexts[0].paragraph_ordinal, links[0].paragraph_ordinal)
        self.assertTrue(contexts[0].quotes_en)

    def test_metric_and_period_queries_preserve_missing_periods(self) -> None:
        points = self.port.get_metric_series("metric-google-cloud-revenue", ("FY2025",))
        comparison = self.port.compare_periods(
            "alphabet", ("FY2024", "FY2025"), ("revenue",)
        )

        self.assertEqual(points[0].value, 58_705)
        self.assertEqual(points[0].unit, "USD millions")
        self.assertEqual(len(comparison.metrics), 9)
        self.assertEqual(comparison.missing_periods, ("FY2024",))

    def test_missing_data_request_is_idempotent_but_not_overwritable(self) -> None:
        request = ResearchDataRequest(
            request_id="rdr-cloud-2024",
            research_question="How did Cloud revenue change?",
            missing_information="FY2024 Cloud revenue",
            why_material="Needed for a period comparison",
            suggested_source_types=("10-K",),
            company_id="alphabet",
            periods=("FY2024",),
            related_driver_or_risk_ids=(),
            priority="normal",
        )
        self.assertEqual(self.port.request_missing_data(request), request)
        self.assertEqual(self.port.request_missing_data(request), request)

        changed = ResearchDataRequest(
            request_id=request.request_id,
            research_question=request.research_question,
            missing_information="different",
            why_material=request.why_material,
            suggested_source_types=request.suggested_source_types,
            company_id=request.company_id,
            periods=request.periods,
            related_driver_or_risk_ids=(),
            priority=request.priority,
        )
        with self.assertRaises(FileExistsError):
            self.port.request_missing_data(changed)

    def test_manifest_integrity_failure_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            release = Path(temporary) / "v0.1-candidate"
            build_research_data_artifacts(BENCHMARK, DOCUMENT, release, generated_at=GENERATED_AT)
            with (release / "query.json").open("a", encoding="utf-8") as target:
                target.write(" ")
            with self.assertRaisesRegex(ResearchDataIntegrityError, "integrity check"):
                LocalResearchDataPort(release)


if __name__ == "__main__":
    unittest.main()
