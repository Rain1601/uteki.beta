import json
from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from scripts.inspect_evidence_package import main, render_package
from tests.unit.test_evidence_package_contract import fixture


class EvidencePackageReportTests(unittest.TestCase):
    def test_report_keeps_original_model_normalization_and_image_status_distinct(self):
        data = fixture()
        text = render_package(data)
        for phrase in ("原始文本", "原始表格", "模型原始提取输出", "模型原输出与归一化分开查看",
                       "摘要（非原文引语）", "确定性计算", "父记录 ID", "metadata_only", "not_run",
                       "body_returned", "provenance_only", "navigation_only", "image_reference_only",
                       "**语义完整性：未评估。**", "Provider | 未知", "Prompt 哈希 | 未知"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text.replace("\\_", "_"))
        self.assertIn("> Revenue was 100.", text)
        self.assertIn("Synthetic model extraction", text)
        self.assertIn("Synthetic fact", text)
        self.assertNotIn("```json", text)
        self.assertIn("来源父产物", text)
        self.assertNotIn("已读父产物", text)

    def test_source_strings_are_escaped_without_truncating_complete_examples(self):
        data = fixture()
        paragraph = "Revenue was 100. A | B <script>alert(1)</script> [link](javascript:bad)\n" + "尾部完整" * 250
        data["artifacts"][0]["payload"]["text"] = paragraph
        data["artifacts"][0]["payload"]["block"]["text"] = paragraph
        text = render_package(data)
        self.assertIn("A \\| B &lt;script&gt;", text)
        self.assertNotIn("<script>", text)
        self.assertNotIn("[link](javascript:bad)", text)
        self.assertIn("尾部完整" * 250, text)
        self.assertIn("未展示的正文、表格单元格和完整元数据仍保留在输入证据包中", text)

    def test_report_uses_input_scope_and_renders_gaps(self):
        data = fixture()
        data["gaps"] = [{"gap_id": "gap-review", "reason": "coverage_not_evaluated", "source_snapshot_ids": ["acme-annual"],
                         "detail": "尚未检查全篇遗漏。"}]
        text = render_package(data)
        self.assertIn("acme-annual", text)
        self.assertIn("2032-03-01", text)
        self.assertIn("尚未检查全篇遗漏。", text)
        self.assertNotIn("Alphabet", text)

    def test_cli_writes_once_and_preserves_package_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            package = folder / "package.json"
            package.write_text(json.dumps(fixture()), encoding="utf-8")
            original = package.read_bytes()
            output = folder / "report.md"
            self.assertEqual(main(["--package", str(package), "--output", str(output)]), 0)
            report = output.read_bytes()
            with self.assertRaises(FileExistsError):
                main(["--package", str(package), "--output", str(output)])
            self.assertEqual(output.read_bytes(), report)
            self.assertEqual(package.read_bytes(), original)

    def test_invalid_package_never_creates_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            package = folder / "invalid.json"
            data = fixture()
            data["artifacts"][0]["payload"]["text"] = "Changed source content"
            package.write_text(json.dumps(data), encoding="utf-8")
            output = folder / "report.md"
            with self.assertRaises(ValidationError):
                main(["--package", str(package), "--output", str(output)])
        self.assertFalse(output.exists())

    def test_value_relation_is_explicit_for_bounds_and_approximations(self):
        for relation, value_text in (("eq", "100 / USD"), ("gt", "&gt; 100 / USD"), ("approx", "约 100 / USD")):
            data = fixture()
            data["artifacts"][3]["payload"]["record"]["value_relation"] = relation
            text = render_package(data)
            with self.subTest(relation=relation):
                self.assertIn("value_relation", text)
                self.assertIn(f"| {relation} |", text)
                self.assertIn(value_text, text)


if __name__ == "__main__":
    unittest.main()
