import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.review_workbench.app import (
    DEFAULT_DATA,
    SOURCE_EXCERPT,
    load_json,
    render_annotation_page,
    render_result_page,
    save_review,
)


class ReviewWorkbenchTests(unittest.TestCase):
    def test_every_candidate_evidence_resolves_to_the_source_excerpt(self) -> None:
        data = load_json(DEFAULT_DATA)
        excerpt = load_json(SOURCE_EXCERPT)
        source_hashes = {item["ordinal"]: item["text_hash"] for item in excerpt["paragraphs"]}
        for evidence in data["evidence"]:
            self.assertEqual(
                source_hashes.get(evidence["paragraph_ordinal"]),
                evidence["text_hash"],
                evidence["id"],
            )

    def test_result_page_keeps_extraction_and_source_together(self) -> None:
        data = load_json(DEFAULT_DATA)
        page = render_result_page(data, load_json(SOURCE_EXCERPT))
        self.assertIn("Extracted business map", page)
        self.assertIn("提取业务结构", page)
        self.assertIn("Alphabet is a collection of businesses", page)
        self.assertIn("Google Advertising", page)
        self.assertIn("Google Cloud", page)
        self.assertIn("Google Cloud Platform", page)
        self.assertIn("data-paragraph='55'", page)
        self.assertNotIn("问题标签", page)

    def test_annotation_page_is_a_separate_structured_workbench(self) -> None:
        data = load_json(DEFAULT_DATA)
        page = render_annotation_page(data, {})
        self.assertIn("Business hierarchy", page)
        self.assertIn("业务层级目录", page)
        self.assertIn("遗漏节点", page)
        self.assertIn("财务数字错误", page)
        self.assertIn("Save &amp; next", page)
        self.assertIn("保存并查看下一项", page)
        self.assertNotIn("Alphabet is a collection of businesses", page)

    def test_saves_review_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "review.json"
            with patch("apps.review_workbench.app.REVIEW_FILE", target):
                save_review(
                    "google-cloud",
                    "edited",
                    "verified",
                    ("wrong_parent", "wrong_evidence"),
                    {"corrected_name": "Google Cloud", "corrected_parent": "google"},
                )
            value = load_json(target)
            review = value["businesses"]["google-cloud"]
            self.assertEqual(review["status"], "edited")
            self.assertEqual(review["issues"], ["wrong_parent", "wrong_evidence"])
            self.assertEqual(review["corrected_parent"], "google")


if __name__ == "__main__":
    unittest.main()
