import json
import unittest
from pathlib import Path

from uteki.domain.business_map import Business, BusinessKind, BusinessMap, Evidence, business_map_from_dict


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
