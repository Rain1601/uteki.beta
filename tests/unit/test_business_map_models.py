import json
import unittest
from pathlib import Path

from uteki.domain.business_map import (
    Business,
    BusinessKind,
    BusinessMap,
    Evidence,
    RelationshipKind,
    business_map_from_dict,
)


class BusinessMapModelTests(unittest.TestCase):
    def test_rejects_unknown_evidence_reference(self) -> None:
        business = Business(
            id="cloud",
            name="Cloud",
            kind=BusinessKind.REPORTABLE_SEGMENT,
            description="Cloud services",
            evidence_ids=("missing",),
        )
        with self.assertRaisesRegex(ValueError, "unknown ids"):
            BusinessMap("0.1", "alphabet", "filing", "summary", (business,), (), (), ())

    def test_accepts_consistent_map(self) -> None:
        evidence = Evidence("e1", "filing", ("Item 1",), 1, "abc", "https://example.test", "support")
        business = Business(
            id="cloud",
            name="Cloud",
            kind=BusinessKind.REPORTABLE_SEGMENT,
            description="Cloud services",
            evidence_ids=("e1",),
        )
        result = BusinessMap("0.1", "alphabet", "filing", "summary", (business,), (), (), (evidence,))
        self.assertEqual(result.to_dict()["businesses"][0]["kind"], BusinessKind.REPORTABLE_SEGMENT)

    def test_pilot_matches_domain_contract(self) -> None:
        path = Path("data/evaluation/pilots/alphabet_2025_item1_business_map.json")
        result = business_map_from_dict(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(result.company_id, "alphabet")
        self.assertEqual(len(result.businesses), 5)

    def test_benchmark_candidate_matches_domain_contract(self) -> None:
        path = Path("benchmarks/alphabet_2025_business_map/v0.1-candidate/business_map.json")
        result = business_map_from_dict(json.loads(path.read_text(encoding="utf-8")))
        self.assertEqual(result.company_id, "alphabet")
        self.assertEqual(len(result.businesses), 9)
        self.assertEqual(len(result.relationships), 8)
        self.assertEqual(len(result.evidence), 22)

    def test_layered_benchmark_candidate_matches_domain_contract(self) -> None:
        root = Path("benchmarks/alphabet_2025_business_map/v0.2-candidate")
        result = business_map_from_dict(json.loads((root / "business_map.json").read_text(encoding="utf-8")))
        policy = json.loads((root / "benchmark_policy.json").read_text(encoding="utf-8"))
        required = {item["business_id"] for item in policy["node_policy"] if item["requirement"] == "required"}

        self.assertEqual(result.company_id, "alphabet")
        self.assertEqual(len(result.businesses), 12)
        self.assertEqual(len(result.relationships), 11)
        self.assertEqual(len(result.evidence), 22)
        self.assertEqual(required, {item.id for item in result.businesses})
        self.assertEqual(
            {item.id for item in result.businesses if item.kind == BusinessKind.REVENUE_LINE},
            {"google-search-other", "youtube-ads", "google-network"},
        )

    def test_dual_structure_candidate_separates_business_and_financial_views(self) -> None:
        root = Path("benchmarks/alphabet_2025_business_map/v0.3-candidate")
        result = business_map_from_dict(json.loads((root / "business_map.json").read_text(encoding="utf-8")))
        policy = json.loads((root / "benchmark_policy.json").read_text(encoding="utf-8"))
        required = {item["business_id"] for item in policy["node_policy"] if item["requirement"] == "required"}

        self.assertEqual(len(result.businesses), 15)
        self.assertEqual(len(result.relationships), 17)
        self.assertNotIn("google-spd", {item.id for item in result.businesses})
        self.assertEqual(
            {"google-subscriptions", "google-platforms", "google-devices"},
            {item.id for item in result.businesses if item.id in {"google-subscriptions", "google-platforms", "google-devices"}},
        )
        revenue_lines = {item.id for item in result.businesses if item.kind == BusinessKind.REVENUE_LINE}
        self.assertIn("google-spd-revenue", revenue_lines)
        self.assertEqual(required, {item.id for item in result.businesses})
        supports = [item for item in result.relationships if item.kind == RelationshipKind.SUPPORTS]
        self.assertEqual(len(supports), 3)
        self.assertEqual({item.target_id for item in supports}, {"google-spd-revenue"})
        disclosed_48b = {
            item.id
            for item in result.businesses
            if "2025 revenue: $48.030B" in item.importance_signals
        }
        self.assertEqual(disclosed_48b, {"google-spd-revenue"})
