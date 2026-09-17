"""Annual context is a selection contract, never an instruction to call a model."""
from pathlib import Path
import tempfile
import unittest

from uteki.agents.research_archive import Store, ArchiveError
from uteki.agents.research_archive_context import build_context, freeze_context, read_history


class AnnualContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'state.json')
        self.docs = {}
        for year in (2021, 2022, 2023, 2024):
            self.add(str(year), f'{year}-12-31')
        self.add('quarter', '2025-03-31', form='10-Q')
        self.add('team', '2024-12-31', researcher='team-a')

    def add(self, key, period, form='10-K', researcher='single-default'):
        year = int(period[:4]) + (1 if form == '10-K' else 0)
        published = f'{year}-05-01'
        self.docs[key] = dict(id=key, company_id='alphabet', form=form, period_end=period,
                              filed_at=published, index_folder='/private/not-model-input')
        self.store.seed([dict(id=key, company_id='alphabet', researcher_id=researcher,
                             scope='company-drivers', primary_document_id=key,
                             material_available_at=published, knowledge_cutoff_at=published,
                             run_started_at=published, validation_status='passed', answer='Answer '+key)])
        self.store.act(key, 'adopt', 1)

    def context(self, form='10-K', period='2025-12-31', **kwargs):
        material = dict(id='current', form=form, company_id='alphabet',
                        period_end=period, published_at='2026-02-01')
        material.update(kwargs.pop('material_overrides', {}))
        return build_context(self.store, 'alphabet', 'company-drivers',
                             kwargs.pop('cutoff', '2026-03-01'), researcher_id='single-default',
                             material=material, document_metadata=self.docs, **kwargs)

    def test_exact_prior_two_years_no_quarter_or_team(self):
        ctx = self.context()
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2024','2023'])
        self.assertEqual(ctx['history_snapshot_ids'], ['2022','2021'])
        self.assertEqual(ctx['analysis_objective'], 'annual_research')
        self.assertEqual(ctx['baseline_status'], 'ready')
        self.assertNotIn('content', ctx['baseline'])  # no duplicate answer payload
        self.assertEqual([b['content']['answer'] for b in ctx['baselines']], ['Answer 2024','Answer 2023'])
        self.assertNotIn('index_folder', str(ctx['document_metadata']))

    def test_missing_year_is_not_replaced_by_older_year(self):
        self.store.act('2023', 'archive', 2)
        ctx = self.context()
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2024'])
        self.assertEqual(ctx['missing_baseline_years'], [2023])
        self.assertEqual(ctx['baseline_status'], 'partial')

    def test_supplemental_materials_use_annual_not_quarter(self):
        for form in ('10-Q','earnings_call','earnings_release','competitor_report'):
            ctx = self.context(form=form)
            self.assertEqual(ctx['baseline_snapshot_ids'], ['2024'])
            self.assertEqual(ctx['analysis_objective'], 'hypothesis_validation')
            self.assertTrue(ctx['baseline_is_hypothesis_not_fact'])

    def test_foreign_company_annual_is_validation(self):
        ctx = self.context(material_overrides={'company_id':'microsoft'})
        self.assertEqual(ctx['context_policy'], 'latest_prior_10k')
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2024'])

    def test_same_period_call_can_use_published_annual(self):
        ctx = self.context(form='earnings_call',period='2024-12-31')
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2024'])

    def test_time_gate_and_unpublished_material(self):
        with self.assertRaises(ArchiveError):
            self.context(cutoff='2025-01-01')
        ctx = self.context(cutoff='2025-01-01', material_overrides={'published_at':'2025-01-01'})
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2023'])
        self.assertEqual(ctx['missing_baseline_years'], [2024])

    def test_frozen_context_and_second_baseline_opinions(self):
        self.store.act('2023','comment',2,text='Check cloud economics',carry_forward=True)
        ctx = self.context(strict=False)
        self.assertEqual(ctx['opinions'][0]['review_status'],'pending')
        frozen = freeze_context(ctx, self.root/'run')
        self.assertTrue(frozen.exists())
        self.assertEqual(read_history(ctx,self.store,'2022')['content']['answer'],'Answer 2022')
        self.store.seed([dict(id='child',company_id='alphabet',researcher_id='single-default',
                             scope='company-drivers',primary_document_id='child-doc',
                             material_available_at='2026-02-01',knowledge_cutoff_at='2026-02-01',
                             run_started_at='2026-02-01',baseline_snapshot_ids=['2024','2023'])])
        self.store.act('2023','archive',3)
        child=next(r for r in self.store.list() if r['id']=='child')
        self.assertTrue(child['inheritance_review_required'])
        self.assertEqual(ctx['baseline_snapshot_ids'], ['2024','2023'])

    def test_no_baseline_is_explicit(self):
        for year in ('2024','2023','2022','2021'):
            self.store.act(year,'archive',2)
        ctx = self.context(form='10-Q')
        self.assertEqual(ctx['baseline_status'],'missing')
        self.assertEqual(ctx['baselines'],[])
