import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from uteki.agents.evidence_math import number, calculate


class EvidenceMathTests(unittest.TestCase):
    def test_numeric_cells_not_permissive_text(self):
        self.assertEqual(str(number('(1,234.5)')), '-1234.5')
        for value in ('—', '$23', '23 footnote', '1,23', ''):
            with self.assertRaises(ValueError):
                number(value)

    def test_real_alphabet_revenue_and_cloud_growth(self):
        root = Path(__file__).resolve().parents[2]
        blocks = [json.loads(line) for line in (root/'data/source_documents/alphabet_2025_10k/indexes/v0.1/blocks.jsonl').read_text().splitlines()]
        block = next(b for b in blocks if b['ordinal']==914)
        reader = SimpleNamespace(blocks=[block],positions={block['block_id']:0})
        session = SimpleNamespace(evidence={('doc','idx',block['block_id']):block['text']},reader=lambda _:reader)
        def ref(row,col,year,label):
            return dict(document_id='doc',index_id='idx',block_id=block['block_id'],row=row,column=col,year=year,row_label=label)
        cloud = calculate(session,'growth_pct',ref(5,15,2025,'Google Cloud'),ref(5,9,2024,'Google Cloud'))
        self.assertEqual(cloud['value'],'35.80')
        revenue = calculate(session,'growth_pct',ref(8,16,2025,'Total revenues'),ref(8,10,2024,'Total revenues'),1)
        self.assertEqual(revenue['value'],'15.1')
        with self.assertRaises(ValueError):
            calculate(session,'growth_pct',ref(5,15,2024,'Google Cloud'),ref(5,9,2023,'Google Cloud'))
        session.evidence = {}
        with self.assertRaises(ValueError):
            calculate(session,'growth_pct',ref(5,15,2025,'Google Cloud'),ref(5,9,2024,'Google Cloud'))
