import unittest
from pathlib import Path
from lxml import html
from apps.review_workbench.visual_system import theme_html


class VisualSystemTest(unittest.TestCase):
    def test_explicit_body_keeps_attributes_scripts_and_content(self):
        raw = '<html><head><style>p{color:red}</style></head><body class="zh"><script>const x="<test>";</script><p>Evidence</p></body></html>'
        themed = theme_html(raw, 'research')
        tree = html.fromstring(themed)
        self.assertEqual(tree.xpath('//body')[0].get('class'), 'zh')
        self.assertEqual(tree.xpath('//body')[0].get('data-workbench'), 'research')
        self.assertIn('<script>const x="<test>";</script>', themed)
        self.assertEqual(theme_html(themed, 'research'), themed)
        self.assertEqual(len(tree.xpath('//style[@id="uteki-visual-system"]')), 1)

    def test_implicit_body_data_and_experiment_pages(self):
        for raw in ('<html><meta charset="utf-8"><style>a{color:blue}</style><header>Data</header><main>Inventory</main></html>',
                    '<!doctype html><meta charset="utf-8"><h1>Experiments</h1>'):
            tree = html.fromstring(theme_html(raw, 'data'))
            self.assertEqual(tree.xpath('//body')[0].get('data-workbench'), 'data')

    def test_theme_is_scoped_and_reduced_motion_is_supported(self):
        css = (Path(__file__).resolve().parents[1] / 'apps/review_workbench/visual_system.css').read_text()
        self.assertIn('body[data-workbench]', css)
        self.assertIn('prefers-reduced-motion:reduce', css)
        self.assertIn('focus-visible', css)
        with self.assertRaises(ValueError):
            theme_html('<body></body>', '"invalid')

    def test_source_renderers_are_not_decorated(self):
        from apps.review_workbench.app import render_original_source_document
        from apps.review_workbench.document_index import render_index_source_document
        self.assertFalse(hasattr(render_original_source_document, '__wrapped__'))
        self.assertFalse(hasattr(render_index_source_document, '__wrapped__'))
