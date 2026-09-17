import copy
import json
import unittest
from collections import Counter
from pathlib import Path

from apps.review_workbench.company_universe import (
    render_company_universe_page,
    validate_company_universe,
)


DATA = Path("data/company_universe/v0.1-candidate/companies.json")


class CompanyUniverseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = json.loads(DATA.read_text(encoding="utf-8"))

    def test_candidate_has_fifty_sp500_companies_and_five_per_theme(self) -> None:
        validate_company_universe(self.data)
        self.assertEqual(len(self.data["companies"]), 50)
        self.assertTrue(all("sp500" in item["indices"] for item in self.data["companies"]))
        self.assertEqual(set(Counter(item["theme_id"] for item in self.data["companies"]).values()), {5})

    def test_holding_state_is_not_invented(self) -> None:
        self.assertTrue(all(item["holding"] == "unknown" for item in self.data["companies"]))

    def test_rejects_unknown_theme(self) -> None:
        data = copy.deepcopy(self.data)
        data["companies"][0]["theme_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown theme"):
            validate_company_universe(data)

    def test_page_renders_filters_bilingual_copy_and_alphabet_link(self) -> None:
        page = render_company_universe_page(self.data)
        self.assertIn("公司观察池", page)
        self.assertIn("Landmark companies", page)
        self.assertIn("data-value='nasdaq100'", page)
        self.assertIn("data-value='core'", page)
        self.assertIn("value='unknown'", page)
        self.assertIn("data-value='ai-compute'", page)
        self.assertNotIn("href='/result'", page)
        self.assertNotIn("href='/document-index'", page)
        self.assertEqual(page.count("class='company-row'"), 50)
        self.assertNotIn("theme-divider", page)
        self.assertIn("id='page-size'", page)
        self.assertIn("id='previous'", page)
        self.assertIn("id='next'", page)


if __name__ == "__main__":
    unittest.main()
