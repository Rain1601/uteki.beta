import json
from pathlib import Path
import unittest
from uteki.agents.numeric_review import review_percentages, review_run


class PercentageReviewTests(unittest.TestCase):
    def test_numbers_are_scoped_to_citations_not_global_ledger(self):
        ref = dict(document_id='d', index_id='i', block_id='b')
        paragraph = dict(text='同比增长12.4%；预计50%。广告占70%。', citations=[dict(**ref,quote='70% of revenue')])
        report = dict(thesis=paragraph,sections=[])
        calc = dict(tool='calculate_table', result=dict(arithmetic_status='passed',value='12.39',
                                                       operands=[dict(reference=ref)]))
        result = review_percentages(report,[calc])
        self.assertEqual([f['text'] for f in result['findings'] if f['status']=='unresolved'], ['50%'])
        paragraph['citations'][0]['block_id']='different'
        self.assertEqual(len(review_percentages(report,[calc])['errors']),2)

    def test_failed_calculation_does_not_cover_number(self):
        report=dict(thesis=dict(text='利润率31.98%',citations=[]),sections=[])
        result=review_percentages(report,[dict(tool='calculate_table',result=dict(error='ValueError'))])
        self.assertEqual(result['status'],'unresolved')

    def test_actual_v04_regression(self):
        folder=Path(__file__).resolve().parents[2]/'experiments/analysis_comparison/annual-narrative-single-v0.4-a/run'
        if not (folder/'result.json').exists():
            self.skipTest('Local immutable experiment not distributed')
        report=json.loads((folder/'result.json').read_text())['report']
        review=review_run(report,folder)
        missing={f['text'] for f in review['findings'] if f['status']=='unresolved'}
        self.assertTrue({'31.98%', '35.96%', '23.68%'}.issubset(missing))


if __name__ == '__main__':
    unittest.main()
