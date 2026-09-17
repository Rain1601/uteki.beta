from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts
from uteki.infrastructure.document_sources.sec import parse_sec_html
from uteki.infrastructure.document_sources.sec_index import build_legal_outline, parse_sec_source


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "data/source_documents/alphabet_2025_10k"
CANDIDATE = SNAPSHOT / "indexes/v0.1-candidate"
FROZEN = SNAPSHOT / "indexes/v0.1"


def fixture_html(*, href: str = "#item-1", duplicate_links: bool = False) -> bytes:
    second_link = f"<a href='{href}'>1</a>" if duplicate_links else "1"
    return f"""<!doctype html><html><body>
    <table><tr><td>PART I</td><td></td><td></td></tr>
      <tr><td>Item 1.</td><td><a href='{href}'>Business</a></td><td>{second_link}</td></tr></table>
    <div id='part-i'></div><div style='font-weight:700'>PART I</div>
    <div id='item-1'></div><div style='font-weight:700'>ITEM 1. BUSINESS</div>
    <div style='font-weight:700'>Data Center Segment</div>
    <div style='font-weight:700'>Data Center Market</div>
    <div style='text-align:center'>3</div>
    <table><tr><th rowspan='2'>Name</th><th colspan='2'>Value</th></tr><tr><td>A</td><td>B</td></tr></table>
    <div><img src='chart.jpg' alt='chart'></div>
    </body></html>""".encode()


class SecDocumentIndexUnitTests(unittest.TestCase):
    def test_toc_anchor_and_parent_child_ranges(self) -> None:
        parsed = parse_sec_source("filing", "https://example.test/report.htm", fixture_html())
        index = build_legal_outline(parsed)
        part = next(node for node in index.nodes if node.kind == "part")
        item = next(node for node in index.nodes if node.kind == "item")
        ordinals = {block.block_id: block.ordinal for block in parsed.blocks}
        self.assertEqual(item.source_anchor, "item-1")
        self.assertEqual(item.parent_id, part.node_id)
        self.assertLessEqual(ordinals[part.start_block_id], ordinals[item.start_block_id])
        self.assertLessEqual(ordinals[item.start_block_id], ordinals[item.end_block_id])

    def test_missing_anchor_uses_deterministic_heading_fallback(self) -> None:
        parsed = parse_sec_source("filing", "https://example.test/report.htm", fixture_html(href="#missing"))
        index = build_legal_outline(parsed)
        item = next(node for node in index.nodes if node.kind == "item")
        start = next(block for block in parsed.blocks if block.block_id == item.start_block_id)
        self.assertEqual(start.text, "ITEM 1. BUSINESS")
        self.assertIn("item_anchor_fallback", {item.code for item in index.diagnostics})

    def test_duplicate_links_in_one_toc_row_are_one_item(self) -> None:
        parsed = parse_sec_source("filing", "https://example.test/report.htm", fixture_html(duplicate_links=True))
        index = build_legal_outline(parsed)
        self.assertEqual(sum(node.kind == "item" for node in index.nodes), 1)
        self.assertNotIn("toc_row_anchor_conflict", {item.code for item in index.diagnostics})

    def test_same_style_business_titles_are_candidates_not_legal_nodes(self) -> None:
        parsed = parse_sec_source("filing", "https://example.test/report.htm", fixture_html())
        index = build_legal_outline(parsed)
        candidates = {block.text for block in parsed.blocks if block.type == "heading_candidate"}
        self.assertIn("Data Center Segment", candidates)
        self.assertIn("Data Center Market", candidates)
        self.assertEqual({node.kind for node in index.nodes}, {"document", "part", "item"})
        self.assertNotIn("Data Center Segment", {node.title for node in index.nodes})

    def test_tables_images_pages_and_merged_cells_remain_structured(self) -> None:
        parsed = parse_sec_source("filing", "https://example.test/report.htm", fixture_html())
        tables = [block for block in parsed.blocks if block.type == "table"]
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[-1].table.row_count, 2)
        self.assertEqual(tables[-1].table.column_count, 3)
        self.assertTrue(any(cell.rowspan == 2 for cell in tables[-1].table.cells))
        self.assertEqual(sum(block.type == "image" for block in parsed.blocks), 1)
        self.assertEqual(sum(block.type == "page_marker" for block in parsed.blocks), 1)
        self.assertEqual(parsed.assets[0].source_url, "https://example.test/chart.jpg")

    def test_reported_page_footer_labels_preceding_blocks(self) -> None:
        raw = b"""<html><body>
        <div>First page content</div><div style='text-align:center'>7.</div>
        <div>Second page content</div><div style='text-align:center'>8.</div>
        </body></html>"""
        parsed = parse_sec_source("filing", "https://example.test/report.htm", raw)
        content = {block.text: block.reported_page for block in parsed.blocks}
        self.assertEqual(content["First page content"], 7)
        self.assertEqual(content["Second page content"], 8)


class AlphabetDocumentIndexIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
        with gzip.open(SNAPSHOT / "source.html.gz", "rb") as source:
            cls.raw = source.read()
        cls.parsed = parse_sec_source(
            cls.manifest["document_id"],
            cls.manifest["source_url"],
            cls.raw,
            source_snapshot_id=cls.manifest["source_snapshot_id"],
            form_type=cls.manifest["form"],
        )
        cls.index = build_legal_outline(cls.parsed)

    def test_source_sha_and_legacy_paragraph_contract_are_unchanged(self) -> None:
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), self.manifest["content_sha256"])
        legacy = parse_sec_html(self.manifest["document_id"], self.manifest["source_url"], self.raw)
        contract = "".join(f"{item.ordinal}:{item.text_hash}\n" for item in legacy.paragraphs)
        self.assertEqual(len(legacy.paragraphs), 1311)
        self.assertEqual(hashlib.sha256(contract.encode()).hexdigest(), "001dc7f7c4b0c3224769711ceab27f97fb2b6cc6302d7ea863c45c74cc0a49ab")

    def test_every_toc_part_and_item_maps_once_to_a_valid_source_range(self) -> None:
        blocks = {block.block_id: block for block in self.parsed.blocks}
        legal_nodes = [node for node in self.index.nodes if node.kind != "document"]
        self.assertEqual(sum(node.kind == "part" for node in legal_nodes), 4)
        self.assertEqual(sum(node.kind == "item" for node in legal_nodes), 23)
        self.assertEqual(len({node.node_id for node in legal_nodes}), len(legal_nodes))
        for node in self.index.nodes:
            self.assertIn(node.start_block_id, blocks)
            self.assertIn(node.end_block_id, blocks)
            self.assertLessEqual(blocks[node.start_block_id].ordinal, blocks[node.end_block_id].ordinal)
            self.assertTrue(blocks[node.start_block_id].dom_path.startswith("/html/body/"))
        self.assertFalse([item for item in self.index.diagnostics if item.severity == "error"])

    def test_all_source_tables_and_images_are_represented(self) -> None:
        self.assertEqual(sum(block.type == "table" for block in self.parsed.blocks), 185)
        self.assertEqual(sum(block.type == "image" for block in self.parsed.blocks), 2)
        self.assertEqual(len(self.parsed.assets), 2)

    def test_artifact_generation_is_byte_stable(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            one = Path(first) / "v0.1-candidate"
            two = Path(second) / "v0.1-candidate"
            build_index_artifacts(SNAPSHOT, one)
            build_index_artifacts(SNAPSHOT, two)
            for filename in ("manifest.json", "index.json", "blocks.jsonl", "assets.json"):
                self.assertEqual((one / filename).read_bytes(), (two / filename).read_bytes())

    def test_frozen_v01_matches_the_approved_candidate(self) -> None:
        for filename in ("index.json", "blocks.jsonl", "assets.json"):
            self.assertEqual((CANDIDATE / filename).read_bytes(), (FROZEN / filename).read_bytes())
        candidate_manifest = json.loads((CANDIDATE / "manifest.json").read_text(encoding="utf-8"))
        frozen_manifest = json.loads((FROZEN / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(candidate_manifest["status"], "candidate")
        self.assertEqual(frozen_manifest["status"], "frozen")
        self.assertEqual(candidate_manifest["index_id"], frozen_manifest["index_id"])


if __name__ == "__main__":
    unittest.main()
