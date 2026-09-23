"""Compatibility boundaries for the workbench package reorganization."""
import importlib
import unittest
from unittest.mock import patch

from apps.review_workbench.assets import asset_text
from apps.review_workbench.app import render_original_source_document


class WorkbenchStructureTests(unittest.TestCase):
    def test_legacy_patch_reaches_canonical_module(self):
        canonical = importlib.import_module('apps.review_workbench.pages.query_runs')
        legacy = importlib.import_module('apps.review_workbench.query_runs')
        self.assertIs(legacy, canonical)
        with patch('apps.review_workbench.query_runs.collections', return_value=['sentinel']):
            self.assertEqual(canonical.collections(None), ['sentinel'])

    def test_asset_lookup_rejects_paths_and_non_assets(self):
        self.assertIn('--paper:', asset_text('design_tokens.css'))
        for name in ('../app.py', '../static/css/design_tokens.css', '/tmp/file.js', 'app.py'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                asset_text(name)

    def test_source_bridge_preserves_escaped_data_and_script(self):
        html = render_original_source_document('<html><head></head><body></body></html>', {
            'paragraphs': [{'ordinal': 1, 'text': '</script> & source', 'translation_zh': '原文'}]})
        self.assertIn('<\\/script> & source', html)
        self.assertNotIn('__UTEKI_DATA_JSON__', html)
        self.assertIn('const UTEKI_BLOCKS=', html)
        self.assertIn("parent.postMessage({type:'uteki-source-ready'", html)
