import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result


class StepExperimentTests(unittest.TestCase):
    def test_offline_steps_and_fair_packet_preparation(self):
        runner=module('run_research_data_steps')
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'run'
            result=runner.run(output)
            self.assertEqual(result['numeric_reference_agreement'],{'matched':24,'total':24})
            self.assertTrue(result['annual_numeric_unchanged'])
            self.assertEqual(result['query_statuses'],['matched','matched','missing','missing'])
            self.assertEqual(result['model_calls'],0)
            for case in ('A1','A2'):
                before=json.loads((output/'step-05'/case/'before-input.json').read_text())
                after=json.loads((output/'step-05'/case/'after-input.json').read_text())
                self.assertEqual(before['blocks'],after['blocks'])
                if case == 'A1':
                    self.assertTrue(any('in millions' in b['text'] for b in before['blocks']))
                self.assertNotIn('records',before)
                self.assertTrue(after['records'])
                self.assertLess(len(json.dumps(after,ensure_ascii=False,separators=(',',':'))),65000)
            with self.assertRaises(FileExistsError):runner.run(output)
            manifest=json.loads((output/'manifest.json').read_text())
            for path,expected in manifest['files'].items():
                self.assertEqual(runner.digest((output/path).read_bytes()),expected)

    def test_consumer_citation_validation(self):
        runner=module('run_research_data_consumer_comparison')
        packet={'blocks':[{'document_id':'d','index_id':'i','block_id':'b','text':'Expected source quote.'}]}
        citation={'document_id':'d','index_id':'i','block_id':'b','quote':'source quote'}
        answer={'claims':[{'text':'A claim','citations':[citation]}]}
        self.assertEqual(runner.validate_citations(answer,packet),[])
        citation['quote']='fabricated'
        self.assertTrue(runner.validate_citations(answer,packet))
        citation['quote']='source quote';citation['block_id']='unread'
        self.assertTrue(runner.validate_citations(answer,packet))


if __name__=='__main__':unittest.main()
