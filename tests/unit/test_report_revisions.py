import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from apps.review_workbench.report_text import render_report, text_changes
from apps.review_workbench.archive_navigation import revision_history
from apps.review_workbench.research_archive_ui import bi, render_archive
from uteki.agents.research_archive import Store, ArchiveError, ConflictError
from tests.unit.test_research_archive import sample


class ReportRevisionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.store = Store(self.path/'state.json')
        self.store.seed([sample(answer={'report_markdown':'# Report\n\nOriginal'}, author='Codex', editor_type='agent')])
        self.artifact = self.path/'agent.json'
        self.artifact.write_text(json.dumps({'answer':{'report_markdown':'# Report\n\nAgent update'}}))

    def agent_edit(self, expected=1):
        return self.store.record_agent_revision('a', expected, answer={'report_markdown':'# Report\n\nAgent update'},
            reason='Recheck cash flow', agent_id='research-agent', model='test-model', run_id='run-1',
            artifact_path=self.artifact, artifact_sha256=hashlib.sha256(self.artifact.read_bytes()).hexdigest())['snapshot']

    def test_agent_then_human_preserves_content_identity_and_history_after_reload(self):
        agent = self.agent_edit()
        human = self.store.act(agent['id'], 'edit', 1, answer={'report_markdown':'# Report\n\nHuman correction'},human_notes='Clarify the period')['snapshot']
        rows = {r['id']:r for r in Store(self.path/'state.json').list()}
        self.assertEqual(rows['a']['answer']['report_markdown'], '# Report\n\nOriginal')
        self.assertEqual(rows[agent['id']]['answer']['report_markdown'], '# Report\n\nAgent update')
        self.assertEqual(human['editor_type'], 'human')
        self.assertNotIn('agent_provenance', human)
        self.assertEqual(agent['agent_provenance']['model'], 'test-model')
        self.assertEqual([r['id'] for r in human['revision_lineage']], [human['id'],agent['id'],'a'])
        self.assertEqual(agent['validation_status'], 'pending')
        self.assertEqual(human['validation_status'], 'pending')
        history = revision_history(human, bi)
        self.assertIn('Human correction', history)
        self.assertIn('Agent update', history)
        self.assertIn('Agent 修订', history)
        self.assertIn('Clarify the period', history)

    def test_stale_agent_result_conflicts_without_overwriting_human_edit(self):
        self.store.act('a', 'edit', 1, human_notes='A concurrent opinion')
        before = (self.path/'state.json').read_bytes()
        with self.assertRaises(ConflictError):
            self.agent_edit()
        self.assertEqual((self.path/'state.json').read_bytes(), before)
        self.assertTrue(self.artifact.exists())

    def test_missing_artifact_or_invalid_markdown_cannot_mutate(self):
        with self.assertRaises(ArchiveError):
            self.store.record_agent_revision('a',1,answer={'report_markdown':'new'},reason='why',agent_id='agent',
                model='test',run_id='1',artifact_path=self.artifact,artifact_sha256='bad')
        with self.assertRaises(ArchiveError):
            self.store.act('a','edit',1,answer={'report_markdown':''})
        with self.assertRaises(ArchiveError):
            self.store.act('a','edit',1,answer={'report_markdown':'# Report\n\nOriginal'})
        self.assertEqual(len(self.store.list()),1)

    def test_agent_review_does_not_adopt_or_bypass_failed_parent(self):
        agent = self.agent_edit()
        with self.assertRaises(ArchiveError):
            self.store.act(agent['id'],'adopt',1)
        reviewed = self.store.act(agent['id'],'review',1,review_notes='Read the original evidence')['snapshot']
        self.assertEqual(reviewed['status'],'candidate')
        self.assertEqual(reviewed['reviewed_by'],'user')

    def test_report_render_and_diff_escape_untrusted_content(self):
        html = render_report('# Report\n\n<script>alert(1)</script>\n\n[x](javascript:alert)\n\n| A | B |\n|---|---|\n|1|2|')
        self.assertNotIn('<script>',html)
        self.assertNotIn('href="javascript:',html)
        self.assertIn('<table>',html)
        diff = text_changes('before <img>', 'after <script>', bi)
        self.assertNotIn('<script>',diff)
        self.assertIn('修改前',diff)


if __name__ == '__main__':
    unittest.main()
