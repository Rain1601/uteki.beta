from datetime import date
import unittest
from uteki.agents.hypothesis_contract import (Hypothesis, AnnualRevision, Assessment, ValidationRecord,
                                              Change, RevisionProposal, preview_revision, check_validation)


class HypothesisContractTests(unittest.TestCase):
    def setUp(self):
        self.h = Hypothesis(hypothesis_id='h-cloud',revision=1,statement='Conditional cloud thesis',
            business_scope='Cloud',horizon='3–5 years',conditions=('Search cash flow stays resilient',),
            observations=('Cloud margin',),reconsider_when='Sustained deterioration',support=(),opposition=())
        self.base = AnnualRevision(report_id='annual-25',revision_id='r1',company_id='alphabet',
            researcher_id='single-default',scope='drivers',primary_document_id='10k25',cutoff=date(2026,2,5),
            parent_revision_id=None,hypotheses=(self.h,),actor='model')
        self.record = ValidationRecord(validation_id='q1',report_id='annual-25',baseline_revision_id='r1',
            researcher_id='single-default',cutoff=date(2026,4,30),assessments=(Assessment(
                hypothesis_id='h-cloud',hypothesis_revision=1,verdict='insufficient',explanation='Not enough data',evidence=()),))
        self.change = Change(action='replace',hypothesis_id='h-cloud',expected_hypothesis_revision=1,
            replacement=self.h.model_copy(update=dict(revision=2,statement='Revised conditional thesis')),
            reason='Human revision after Q1',validation_ids=('q1',))
        self.proposal = RevisionProposal(proposal_id='p1',report_id='annual-25',baseline_revision_id='r1',
            researcher_id='single-default',cutoff=date(2026,4,30),changes=(self.change,))

    def test_revision_is_explicit_stable_and_does_not_mutate_original(self):
        revised=preview_revision(self.base,self.proposal,(self.record,),actor='user')
        self.assertEqual(self.base.hypotheses[0].revision,1)
        self.assertEqual(revised.hypotheses[0].hypothesis_id,'h-cloud')
        self.assertEqual(revised.hypotheses[0].revision,2)
        self.assertEqual(revised.parent_revision_id,'r1')
        self.assertEqual(revised.based_on_validation_ids,('q1',))
        self.assertEqual(revised,preview_revision(self.base,self.proposal,(self.record,),actor='user'))

    def test_wrong_researcher_and_stale_revision_rejected(self):
        for delta in [dict(researcher_id='team'),dict(baseline_revision_id='r2')]:
            with self.assertRaises(ValueError):
                preview_revision(self.base,self.proposal.model_copy(update=delta),(self.record,),actor='user')

    def test_validation_targets_exact_hypothesis_version(self):
        with self.assertRaises(ValueError):
            check_validation(self.base,self.record.model_copy(update=dict(assessments=(
                self.record.assessments[0].model_copy(update=dict(hypothesis_revision=2)),))))

    def test_absent_assessment_has_no_effect_and_cannot_justify_change(self):
        empty=self.record.model_copy(update=dict(assessments=()))
        check_validation(self.base,empty)
        with self.assertRaises(ValueError):
            preview_revision(self.base,self.proposal,(empty,),actor='user')

    def test_future_validation_and_duplicate_changes_rejected(self):
        with self.assertRaises(ValueError):
            preview_revision(self.base,self.proposal,(self.record.model_copy(update=dict(cutoff=date(2026,7,30))),),actor='user')
        with self.assertRaises(ValueError):
            preview_revision(self.base,self.proposal.model_copy(update=dict(changes=(self.change,self.change))),
                             (self.record,),actor='user')

    def test_withdrawal_keeps_history_identity(self):
        proposal=self.proposal.model_copy(update=dict(changes=(self.change.model_copy(update=dict(action='withdraw',replacement=None)),)))
        revised=preview_revision(self.base,proposal,(self.record,),actor='user')
        self.assertEqual(revised.hypotheses[0].status,'withdrawn')
        self.assertEqual(revised.hypotheses[0].statement,self.h.statement)

    def test_directional_verdict_without_evidence_rejected(self):
        with self.assertRaises(ValueError):
            Assessment(hypothesis_id='h-cloud',hypothesis_revision=1,verdict='supported',explanation='Assume',evidence=())


if __name__ == '__main__':
    unittest.main()
