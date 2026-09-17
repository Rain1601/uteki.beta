import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from run_annual_report_spike import Report, Paragraph, Section, Citation, SECTIONS, compile_sources, validate_report
from uteki.agents.analysis_comparison import ToolSession


class AnnualNarrativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.session=ToolSession(self.temp.name,{},self.temp.name)
        self.session.calls=1
        self.session.evidence={('doc','index','block'):'Original source text'}
        cited=Paragraph(text='A conditional inference',kind='inference',citations=[Citation(document_id='doc',index_id='index',block_id='block',quote='')])
        self.report=Report(title='Report',thesis=cited,sections=[Section(key=k,title=k,paragraphs=[cited.model_copy(deep=True)]) for k in SECTIONS],limitations=['Not blind'],stop_reason='Enough evidence')

    def test_compilation_preserves_raw_output(self):
        resolved=compile_sources(self.report,self.session)
        self.assertEqual(self.report.thesis.citations[0].quote,'')
        self.assertEqual(resolved.thesis.citations[0].quote,'Original source text')
        self.assertEqual(validate_report(resolved,self.session),[])

    def test_duplicate_sections_and_unread_sources_fail(self):
        self.report.sections[1].key='business'
        self.report.thesis.citations[0].document_id='future-document'
        errors=validate_report(compile_sources(self.report,self.session),self.session)
        self.assertTrue(any('distinct' in e for e in errors))
        self.assertTrue(any('Unread' in e for e in errors))

    def test_facts_require_citations_but_unknown_can_explain_missing_material(self):
        self.report.sections[3].paragraphs=[Paragraph(text='No price supplied',kind='unknown',citations=[])]
        self.assertEqual(validate_report(compile_sources(self.report,self.session),self.session),[])
        self.report.thesis.citations=[]
        self.assertTrue(any('Uncited' in e for e in validate_report(compile_sources(self.report,self.session),self.session)))


if __name__=='__main__':
    unittest.main()
