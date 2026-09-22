"""Render-level contracts: no browser or model calls."""
import unittest

from apps.review_workbench.research_archive_ui import render_archive, _claims, _material_label, _citation_excerpt


class ResearchArchiveUITest(unittest.TestCase):
    def snapshot(self, **overrides):
        row = {
            "id": "snapshot-first", "company_id": "alphabet", "researcher_id": "single-default", "scope": "company-drivers",
            "status": "candidate", "validation_status": "passed", "revision": 1,
            "primary_document_id": "doc-2025", "primary_title": "FY2025 10-K",
            "material_available_at": "2026-02-04T00:00:00Z",
            "run_started_at": "2026-09-13T02:03:00Z", "mode": "single",
            "answer": {"claims": [{"text": "A conditional hypothesis", "citations": []}]},
        }
        row.update(overrides)
        return row

    def test_empty_has_no_model_action(self):
        page = render_archive({"id": "alphabet", "name": "Alphabet"}, [])
        self.assertIn("No model call is started automatically", page)
        self.assertIn('/companies/alphabet/data', page)

    def test_materials_have_an_independent_right_rail(self):
        from lxml import html
        dom = html.fromstring(render_archive({'id':'alphabet'}, [self.snapshot()]))
        self.assertEqual(dom.xpath('//main/*/@class'), ['report-list-rail', 'detail', 'material-rail'])
        self.assertEqual(len(dom.xpath('//main/aside//select[@id="researcher-filter"]')), 1)
        self.assertEqual(len(dom.xpath('//main/aside//a[contains(@class,"report-choice")]')), 1)
        self.assertEqual(dom.xpath('//main/aside//a[contains(@class,"version-row")]'), [])
        self.assertEqual(len(dom.xpath('//details[@class="archive-options"]//a[contains(@class,"version-row")]')), 1)
        self.assertIn('原始材料快照', dom.xpath('//main/div[@class="material-rail"]')[0].text_content())
        self.assertEqual(dom.xpath('//*[@id="edit-dialog"]'), [])
        self.assertEqual(len(dom.xpath('//*[@data-editor-version="inline-v2"]')), 1)
        self.assertEqual(dom.xpath('//*[@id="answer-editor"]'), [])
        self.assertEqual(dom.xpath('//dialog[@id="edit-dialog"]'), [])
        self.assertEqual(dom.xpath('//main/div[@class="detail"]//details[@class="version-history"]'), [])
        self.assertNotIn('Pending candidates', html.tostring(dom).decode())
        self.assertEqual(dom.xpath('//main/div[@class="detail"]//div[@class="material-list"]'), [])

    def test_failed_candidate_cannot_adopt(self):
        page = render_archive({"id": "alphabet"}, [self.snapshot(validation_status="failed")])
        self.assertIn('data-action="adopt" disabled', page)
        self.assertIn("No baseline was recorded", page)

    def test_adopted_can_derive_revision(self):
        page = render_archive({"id": "alphabet"}, [self.snapshot(status="adopted")])
        self.assertNotIn('data-open="inline-report"', page)
        self.assertIn('startBlockEdit', page)
        self.assertIn('block-progress', page)
        self.assertIn('data-action="archive"', page)
        self.assertNotIn('data-action="delete"', page)

    def test_source_sort_precedes_run_time(self):
        old = self.snapshot(id="old", primary_document_id="old-material", material_available_at="2025-01-01T00:00:00Z", run_started_at="2026-09-14T00:00:00Z")
        new = self.snapshot(id="new")
        page = render_archive({"id": "alphabet"}, [old, new])
        self.assertLess(page.index('snapshot=new'), page.index('snapshot=old'))
        self.assertIn('2026-09-13 10:03', page)

    def test_content_and_citation_urls_are_safe(self):
        row = self.snapshot(answer={"claims": [{"text": "<script>bad()</script>", "citations": [{"block_id": "b1", "url": "javascript:alert(1)", "quote": "<img src=x>"}]}]}, human_notes="</script><script>bad()</script>")
        page = render_archive({"id": "alphabet"}, [row])
        self.assertNotIn('<script>bad()', page)
        self.assertNotIn('href="javascript:', page)
        self.assertIn('&lt;script&gt;', page)
        self.assertIn('Link unavailable', page)

    def test_comments_withdraw_and_restore(self):
        row = self.snapshot(comments=[{"comment_id": "comment1", "text": "Review", "kind": "preference", "carry_forward": True, "review_status": "pending"}])
        page = render_archive({"id": "alphabet"}, [row])
        self.assertIn('data-opinion="comment1"', page)
        self.assertIn('Carry-forward requested', page)
        page = render_archive({"id": "alphabet"}, [self.snapshot(status="deleted")], "snapshot-first")
        self.assertIn('data-action="restore"', page)
        self.assertNotIn('id="opinion-form"', page)

    def test_review_revision_requires_valid_parent(self):
        original = self.snapshot(status="archived")
        revision = self.snapshot(id="human-revision", edit_kind="human_revision", validation_status="pending", parent_snapshot_id=original["id"])
        page = render_archive({"id": "alphabet"}, [original, revision], revision["id"])
        self.assertIn('data-action="review"', page)
        self.assertIn("'X-Uteki-Request':'1'", page)
        original["validation_status"] = "failed"
        page = render_archive({"id": "alphabet"}, [original, revision], revision["id"])
        self.assertNotIn('data-action="review"', page)

    def test_inheritance_warning_and_lazy_source_drawer(self):
        row = self.snapshot(inheritance_review_required=True, answer={"claims": [{"text": "Read this evidence", "citations": [{"block_id": "block-1", "url": "/companies/alphabet/documents/doc/source#block-1"}]}]})
        page = render_archive({"id": "alphabet"}, [row])
        self.assertIn("Inherited sources or opinions changed", page)
        self.assertIn('data-source="/companies/alphabet/documents/doc/source#block-1"', page)
        self.assertIn('id="source-drawer" role="dialog"', page)
        self.assertIn('id="source-excerpt"', page)
        self.assertNotIn('<iframe', page)
        self.assertIn('id="source-new-tab"', page)

    def test_citation_contents_and_distinct_document_labels(self):
        citations = [
            {'document_id': 'annual', 'block_id': 'opaque-1', 'url': '/annual/source#opaque-1', 'quote': 'Google Cloud revenue increased.'},
            {'document_id': 'quarter', 'block_id': 'opaque-2', 'url': '/quarter/source#opaque-2', 'quote': 'Capital expenditure rose.'}]
        docs = {'annual': {'period_end': '2025-12-31', 'form': '10-K', 'filed_at': '2026-02-05'},
                'quarter': {'period_end': '2026-06-30', 'form': '10-Q'}}
        page = _claims({'claims': [{'text': 'A claim', 'citations': citations}]}, docs)
        self.assertIn('>Google Cloud revenue increased.</a>', page)
        self.assertIn('[2025 10-K]', page)
        self.assertIn('[2026 Q2 10-Q]', page)
        self.assertNotIn('[2026 10-K]', page)
        self.assertNotIn('>opaque-1<', page)
        self.assertNotIn('Source 1', page)
        self.assertIn('data-source="/annual/source#opaque-1"', page)

    def test_missing_excerpt_image_and_truncation_are_explicit(self):
        self.assertIn('no text excerpt', _citation_excerpt({'type': 'image'}))
        self.assertIn('Excerpt unavailable', _citation_excerpt({}))
        self.assertIn('Source unidentified', _material_label({}, {}))
        self.assertTrue(_citation_excerpt({'quote': 'Revenue is not attributable to AI. ' * 20}).endswith('…'))
        self.assertIn('not attributable', _citation_excerpt({'quote': 'Revenue is not attributable to AI. ' * 20}))

    def test_identical_citations_collapse_only_in_display(self):
        citation = {'document_id': 'd', 'block_id': 'b', 'url': '/source#b', 'quote': 'Revenue grew'}
        answer = {'claims': [{'text': 'Test', 'citations': [citation, citation]}]}
        page = _claims(answer)
        self.assertEqual(page.count('class="evidence-text"'), 1)
        self.assertEqual(len(answer['claims'][0]['citations']), 2)

    def test_compact_excerpt_retains_full_quote_for_preview(self):
        from lxml import html
        quote = 'Alphabet is a collection of businesses. ' * 20
        tree = html.fromstring(_claims({'claims': [{'citations': [{'url': '/source#b', 'quote': quote}]}]}))
        link = tree.xpath('//a')[0]
        self.assertLessEqual(len(link.text), 65)
        self.assertTrue(link.text.endswith('…'))
        self.assertEqual(link.get('title'), quote)
        self.assertEqual(link.get('data-source'), '/source#b')

    def test_chinese_citation_is_presentation_only_and_exact_matched(self):
        from lxml import html
        from apps.review_workbench.citation_translations import translated_quote
        citation = {'quote': '“increases in search queries”', 'url': '/source#b'}
        before = dict(citation)
        tree = html.fromstring(_claims({'claims': [{'citations': [citation]}]}))
        link = tree.xpath('//a')[0]
        self.assertEqual(link.xpath('./span[@lang="zh"]')[0].text, '搜索查询量增加')
        self.assertEqual(link.xpath('./span[@lang="en"]')[0].text, 'increases in search queries')
        self.assertEqual(link.get('data-quote-zh'), '搜索查询量增加')
        self.assertEqual(link.get('title'), before['quote'])
        self.assertEqual(citation, before)
        self.assertEqual(translated_quote({'quote': 'no increases in search queries'}), '')
        self.assertIn('待译', _claims({'claims': [{'citations': [{'quote': 'new unmatched text'}]}]}))

    def test_translation_does_not_repair_incomplete_or_conditional_evidence(self):
        from apps.review_workbench.citation_translations import translated_quote
        self.assertIn('截断', translated_quote({'quote': 'could face signif'}))
        self.assertIn('可能', translated_quote({'quote': 'we may monetize differently'}))
        self.assertIn('78 亿美元', translated_quote({'quote': 'Google Cloud operating income increased $7.8 billion'}))

    def test_more_than_three_citations_are_collapsed_and_keep_ellipsis(self):
        from lxml import html
        citations = [{'document_id': 'd', 'block_id': str(i), 'url': f'/source#{i}',
                      'quote': f'Citation {i} ' + 'long evidence text ' * 30} for i in range(5)]
        answer = {'claims': [{'text': 'Test', 'citations': citations}]}
        tree = html.fromstring(_claims(answer))
        extra = tree.xpath('//span[@class="extra-citations"]')[0]
        self.assertIn('hidden', extra.attrib)
        self.assertEqual(len(extra.xpath('.//a')), 2)
        self.assertEqual(len(tree.xpath('//a[not(ancestor::span[@class="extra-citations"])]')), 3)
        button = tree.xpath('//button[@class="citation-toggle"]')[0]
        self.assertEqual(button.get('aria-expanded'), 'false')
        self.assertEqual(button.get('aria-controls'), extra.get('id'))
        self.assertTrue(all(a.text.endswith('…') for a in tree.xpath('//a')))
        self.assertEqual(len(answer['claims'][0]['citations']), 5)
        for count in (0, 1, 3):
            self.assertNotIn('citation-toggle', _claims({'claims': [{'citations': citations[:count]}]}))

    def test_date_only_metadata_does_not_fabricate_hours(self):
        row = self.snapshot(material_time_precision="date", knowledge_cutoff_at="2026-02-04T23:59:59+00:00", question="What might drive future value?")
        page = render_archive({"id": "alphabet"}, [row])
        self.assertIn('Publication date · exact time unknown', page)
        self.assertIn('Material date boundary · date only', page)
        self.assertNotIn('2026-02-04 08:00', page)
        self.assertNotIn('2026-02-05 07:59', page)
        self.assertIn('<h1>What might drive future value?</h1>', page)
        self.assertIn('<span class="badge">single</span>', page)


if __name__ == '__main__':
    unittest.main()
