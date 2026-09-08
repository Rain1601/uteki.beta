import copy
import unittest

from apps.review_workbench.app import (
    CLAIMS_DATA,
    DEFAULT_DATA,
    SPANS_DATA,
    SOURCE_EXCERPT,
    load_json,
    render_result_page,
    validate_claims,
)


class ReviewWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.data = load_json(DEFAULT_DATA)
        self.claims = load_json(CLAIMS_DATA)
        self.spans = load_json(SPANS_DATA)
        self.excerpt = load_json(SOURCE_EXCERPT)

    def test_every_claim_resolves_to_fixed_source_evidence(self) -> None:
        validate_claims(self.data, self.claims, self.excerpt, self.spans)
        self.assertEqual(len(self.claims["claims"]), 42)
        self.assertEqual(len(self.spans["spans"]), 65)
        self.assertTrue(all(item.get("translation_zh") for item in self.excerpt["paragraphs"]))

    def test_rejects_claim_with_unknown_evidence(self) -> None:
        claims = copy.deepcopy(self.claims)
        claims["claims"][0]["evidence_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown evidence"):
            validate_claims(self.data, claims, self.excerpt)

    def test_result_page_renders_field_level_knowledge_and_evidence_previews(self) -> None:
        page = render_result_page(self.data, self.excerpt, "google-advertising", self.claims)
        self.assertIn("Alphabet business knowledge", page)
        self.assertIn("Alphabet 业务知识", page)
        self.assertIn("data-claim='advertising-definition'", page)
        self.assertIn("data-ordinal='773'", page)
        self.assertIn("<b>4 <span data-lang='en'>sources</span><span data-lang='zh'>条证据</span>", page)
        self.assertIn("Google Search &amp; other · YouTube ads · Google Network", page)
        self.assertIn("1/4", page)
        self.assertIn("4/4", page)

    def test_chinese_mode_keeps_translation_and_sec_original(self) -> None:
        page = render_result_page(self.data, self.excerpt, claims_data=self.claims)
        self.assertIn("中文为忠实翻译候选", page)
        self.assertIn("就报告目的而言，Google 由 Google Services", page)
        self.assertIn("SEC 英文原文", page)
        self.assertIn("For reporting purposes Google comprises two segments", page)

    def test_source_is_honestly_presented_as_selected_evidence(self) -> None:
        page = render_result_page(self.data, self.excerpt, claims_data=self.claims)
        self.assertIn("仅展示当前知识条目对应的出处，不伪装成连续全文。", page)
        self.assertIn("data-paragraph='55'", page)
        self.assertIn("data-paragraph='792'", page)


if __name__ == "__main__":
    unittest.main()
