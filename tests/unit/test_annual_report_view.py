import sys
import unittest
import tempfile
import shutil
from unittest.mock import patch
from pathlib import Path
from lxml import html

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from render_hypothesis_mvp import validate, render
import render_hypothesis_mvp


class AnnualReportViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(directory.cleanup)
        output = Path(directory.name) / 'annual-report'
        shutil.copytree(render_hypothesis_mvp.OUT, output)
        override = patch.object(render_hypothesis_mvp, 'OUT', output)
        override.start()
        cls.addClassCleanup(override.stop)
        cls.stages, cls.metrics, cls.validation = validate()

    def test_initial_view_contains_only_annual_sources_and_no_quarter_results(self):
        original = self.stages[0]['title']
        page = html.fromstring(render(self.stages, self.metrics, self.validation, annual_only=True))
        self.assertFalse(page.xpath('//*[@id="q1" or @id="q2" or @id="review"]'))
        self.assertEqual(page.xpath('//table/thead/tr/th/text()'), ['指标', '2025 10-K'])
        self.assertTrue(all(a.get('data-evidence').startswith('A') for a in page.xpath('//*[@data-evidence]')))
        self.assertEqual(len(page.xpath('//table//a[contains(@class,"hm-positive")]')), 5)
        self.assertIn('其中：Search & other', page.text_content())
        self.assertEqual(self.stages[0]['title'], original)

    def test_comparison_retains_negative_colors(self):
        page = html.fromstring(render(self.stages, self.metrics, self.validation))
        self.assertEqual(len(page.xpath('//table//a[contains(@class,"hm-negative")]')), 2)

    def test_editorial_has_five_sections_with_optional_verification_details(self):
        page = html.fromstring(render(self.stages, self.metrics, self.validation, annual_only=True))
        for key in ('business', 'industry', 'earnings', 'price', 'watch'):
            self.assertEqual(len(page.xpath(f'//section[@id="{key}"]')), 1)
        self.assertFalse(page.xpath('//*[contains(@class,"hm-hypothesis")]'))
        self.assertEqual(len(page.xpath('//section[@id="watch"]//article/details')), 3)
        self.assertTrue(all(not d.get('open') for d in page.xpath('//section[@id="watch"]//details')))
        self.assertIn('目前不能判断', page.xpath('//section[@id="price"]')[0].text_content())
        for anchor in page.xpath('//nav[@aria-label="报告目录"]/a'):
            self.assertEqual(len(page.xpath(f'//*[@id="{anchor.get("href")[1:]}"]')), 1)


if __name__ == '__main__':
    unittest.main()
