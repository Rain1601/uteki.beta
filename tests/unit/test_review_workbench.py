import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.review_workbench.app import render_page, save_review


class ReviewWorkbenchTests(unittest.TestCase):
    def test_renders_pilot(self) -> None:
        data = json.loads(Path("data/evaluation/pilots/alphabet_2025_item1_business_map.json").read_text())
        page = render_page(data, {})
        self.assertIn("Parsed source data", page)
        self.assertIn("解析原始数据", page)
        self.assertIn("Analysis result &amp; annotation", page)
        self.assertIn("分析结果与标注", page)
        self.assertIn("Alphabet is a collection of businesses", page)
        self.assertIn("Google Cloud", page)
        self.assertIn("Which businesses constitute the complete Other Bets portfolio?", page)
        self.assertIn("Other Bets 完整包含哪些业务？", page)

    def test_saves_review_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "review.json"
            with patch("apps.review_workbench.app.REVIEW_FILE", target):
                save_review("google-cloud", "accepted", "verified")
            value = json.loads(target.read_text())
            self.assertEqual(value["businesses"]["google-cloud"]["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
