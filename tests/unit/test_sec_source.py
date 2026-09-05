import unittest

from uteki.infrastructure.document_sources.sec import parse_sec_html, text_hash


class SecSourceTests(unittest.TestCase):
    def test_parses_visible_blocks_and_ignores_ix_header(self) -> None:
        raw = b"""<html><body><ix:header><div>hidden</div></ix:header>
        <div> First   paragraph. </div><div><span>Second</span> paragraph.</div>
        </body></html>"""
        document = parse_sec_html("filing", "https://example.test", raw)
        self.assertEqual([item.text for item in document.paragraphs], ["First paragraph.", "Second paragraph."])
        self.assertEqual(document.paragraphs[0].text_hash, text_hash("First paragraph."))


if __name__ == "__main__":
    unittest.main()
