import copy
import json
import tempfile
import unittest
from pathlib import Path

from lxml import html

from uteki.infrastructure.research_data.financial_records import (
    FinancialRecordPort, cell_grid, compute_ytd_difference, extract_financial_records,
    parse_context as parse_issuer_context, parse_number, validate_table_headers,
)
from uteki.infrastructure.research_data.transcript_records import extract_transcript_records, guidance_context
from uteki.agents.document_reader import DocumentReader
from uteki.infrastructure.research_data.adapters.alphabet_financial import ALPHABET_FINANCIAL_MAPPING

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/source_documents/alphabet_2025_10k"
LIBRARY = ROOT / "data/document_library/alphabet/sources"


def context(start="2026-01-01", end="2026-06-30", dimension=""):
    return html.fromstring(f'<xbrli:context><xbrli:entity><xbrli:identifier>0001652044</xbrli:identifier>{dimension}</xbrli:entity>'
                           f'<xbrli:period><xbrli:startdate>{start}</xbrli:startdate><xbrli:enddate>{end}</xbrli:enddate></xbrli:period></xbrli:context>')


def parse_context(element):
    return parse_issuer_context(element, entity_identifier="0001652044")


class FinancialContextTests(unittest.TestCase):
    def test_context_issuer_is_explicit_and_not_alphabet_specific(self):
        element = context()
        element.xpath('.//*[local-name()="xbrli:identifier"]')[0].text = 'sample-issuer'
        parsed = parse_issuer_context(element, entity_identifier='sample-issuer')
        self.assertEqual(parsed['entity_identifier'], 'sample-issuer')
        with self.assertRaisesRegex(ValueError, 'unsupported_entity'):
            parse_issuer_context(element, entity_identifier='0001652044')
        with self.assertRaises(TypeError):
            parse_issuer_context(element)
    def test_distinguish_quarter_ytd_and_instant(self):
        self.assertEqual(parse_context(context())["period"]["kind"], "ytd")
        self.assertEqual(parse_context(context("2026-04-01"))["period"]["kind"], "quarter")
        first = parse_context(context(end="2026-03-31"))["period"]
        self.assertEqual((first["kind"], first["aliases"]), ("quarter", ["ytd"]))
        instant = html.fromstring('<context><identifier>0001652044</identifier><instant>2026-06-30</instant></context>')
        self.assertIsNone(parse_context(instant)["period"]["start"])

    def test_reject_unsupported_periods_and_dimensions(self):
        for a, b in [("2025-12-01", "2026-03-31"), ("2026-02-01", "2026-06-30"), ("2026-01-01", "2026-06-29")]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                parse_context(context(a, b))
        with self.assertRaises(ValueError):
            parse_context(context(dimension='<xbrldi:typedMember dimension="x">opaque</xbrldi:typedMember>'))
        with self.assertRaises(ValueError):
            parse_context(html.fromstring('<context><identifier>other</identifier></context>'))

    def test_numeric_scale_sign_and_transform(self):
        unit = html.fromstring('<unit><measure>iso4217:USD</measure></unit>')
        tag = html.fromstring('<ix:nonfraction scale="9" sign="-" format="ixt:num-dot-decimal">513.9</ix:nonfraction>')
        self.assertEqual(parse_number(tag, unit)["value_decimal"], "-513900000000.0")
        for attr, value in [("format", "unknown:num"), ("continuedat", "next"), ("xsi:nil", "true")]:
            bad = copy.deepcopy(tag); bad.set(attr, value)
            with self.subTest(attr=attr), self.assertRaises(ValueError):
                parse_number(bad, unit)
        with self.assertRaises(ValueError):
            parse_number(tag, html.fromstring('<unit><measure>iso4217:EUR</measure></unit>'))

    def test_rowspan_does_not_shift_column(self):
        table = html.fromstring('<table><tr><td rowspan="2">x</td><td colspan="2">y</td></tr><tr><td>12</td><td>34</td></tr></table>')
        grid = cell_grid(table)
        locations = {c["text"]: (c["row"], c["column"]) for c in grid.values()}
        self.assertEqual(locations["12"], (1, 1))
        self.assertEqual(locations["34"], (1, 2))

    def test_wrong_year_or_duration_header_rejected(self):
        block={'table':{'cells':[{'row':0,'column':1,'colspan':2,'text':'Three Months Ended'},
                                {'row':1,'column':1,'colspan':1,'text':'2026'}]}}
        cell={'row':2,'column':1}
        with self.assertRaisesRegex(ValueError,'duration_header'):
            validate_table_headers(block,cell,{'end':'2026-06-30','months':6})
        with self.assertRaisesRegex(ValueError,'year_header'):
            validate_table_headers(block,cell,{'end':'2025-06-30','months':3})


class FinancialSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annual = extract_financial_records(SOURCE, SOURCE / "indexes/v0.1", mapping=ALPHABET_FINANCIAL_MAPPING, metrics=["revenue", "operating_income"])
        cls.quarters = {}
        for key, name in [("q1", "alphabet-000165204426000048"), ("q2", "alphabet-000165204426000071")]:
            source = LIBRARY / name
            cls.quarters[key] = extract_financial_records(source, source / "indexes/v0.4-candidate", mapping=ALPHABET_FINANCIAL_MAPPING)

    def test_existing_annual_values_and_duplicate_occurrences(self):
        records = self.annual["records"]
        self.assertEqual(len(records), 6)
        r = next(r for r in records if r["metric"] == "revenue" and r["period"]["end"] == "2025-12-31")
        self.assertEqual(r["value_decimal"], "58705000000")
        self.assertEqual(len(r["evidence_ids"]), 2)
        self.assertEqual(self.annual["diagnostics"], [])
        self.assertEqual(self.annual["conflicts"], [])

    def test_quarterly_periods_and_per_metric_gap(self):
        records = self.quarters["q2"]["records"]
        p = FinancialRecordPort(records)
        args = dict(entity_id="google-cloud", metric="revenue", start="2026-04-01", end="2026-06-30", as_of="2026-07-23")
        q = p.query(**args)
        self.assertEqual(q["records"][0]["value_decimal"], "24768000000")
        args["start"] = "2026-01-01"
        ytd = p.query(**args)
        self.assertEqual(ytd["records"][0]["value_decimal"], "44796000000")
        self.assertNotEqual(q["records"][0]["series_key"], ytd["records"][0]["series_key"])
        args["metric"] = "gross_profit"
        self.assertEqual(p.query(**args)["status"], "missing")

    def test_cutoff_ambiguity_and_no_mutation(self):
        r = self.annual["records"][0]
        args = dict(entity_id=r["entity_id"], metric=r["metric"], start=r["period"]["start"], end=r["period"]["end"], as_of="2026-02-04")
        p = FinancialRecordPort([r]); self.assertEqual(p.query(**args)["status"], "missing")
        args["as_of"] = "2026-02-05"
        result = p.query(**args); result["records"][0]["value_decimal"] = "0"
        self.assertNotEqual(p.query(**args)["records"][0]["value_decimal"], "0")
        self.assertEqual(FinancialRecordPort([r,r]).query(**args)["status"], "ambiguous")
        with self.assertRaises(ValueError): p.query(**{**args,"as_of":"tomorrow"})

    def test_compact_iso_date_cannot_bypass_source_cutoff(self):
        row = self.annual['records'][0]
        args = dict(entity_id=row['entity_id'], metric=row['metric'], start=row['period']['start'],
                    end=row['period']['end'])
        port = FinancialRecordPort([row])
        self.assertEqual(port.query(**args, as_of='20260204')['status'], 'missing')
        self.assertEqual(port.query(**args, as_of='20260205')['status'], 'matched')

    def test_checked_cashflow_difference(self):
        def payment(key):
            return next(r for r in self.quarters[key]["records"] if r["metric"]=="capex_cash_payments" and r["period"]["start"]=="2026-01-01")
        current, previous = payment("q2"), payment("q1")
        calc = compute_ytd_difference(current, previous)
        self.assertEqual(calc["value_decimal"], "44924000000")
        self.assertEqual(calc["period"]["start"], "2026-04-01")
        for key,value in [("entity_id","google-cloud"),("unit","EUR"),("accounting_basis","adjusted")]:
            bad=copy.deepcopy(previous); bad[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):compute_ytd_difference(current,bad)
        with self.assertRaises(ValueError):compute_ytd_difference(previous,current)

    def test_mismatched_source_rejected_before_index_read(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)
            (source/'source.html.gz').write_bytes((SOURCE/'source.html.gz').read_bytes())
            (source/'manifest.json').write_text(json.dumps({'content_sha256':'0'*64}))
            with self.assertRaisesRegex(ValueError,'source_hash_mismatch'):
                extract_financial_records(source,source/'missing-index', mapping=ALPHABET_FINANCIAL_MAPPING)


class TranscriptRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=LIBRARY/'alphabet-2025q4-call'
        cls.index=cls.source/'indexes/v0.1-candidate'
        cls.before=extract_transcript_records(cls.source,cls.index,company_id="alphabet",fiscal_calendar="calendar")
        cls.after=extract_transcript_records(cls.source,cls.index,company_id="alphabet",fiscal_calendar="calendar",expanded_guidance=True)

    def test_guidance_range_and_attribution(self):
        guidance=[r for r in self.after['records'] if r['record_type']=='Guidance']
        self.assertEqual(len(guidance),2)
        for r in guidance:
            self.assertEqual(r['range'],{'low':'175000000000','high':'185000000000'})
            self.assertEqual(r['target_period']['end'],'2026-12-31')
        statements=[r for r in self.after['records'] if r['record_type']=='ManagementStatement']
        self.assertFalse(any(r['source_block_id']=='block-000243-6180ad20' for r in statements))

    def test_guidance_condition_and_topic_boundary(self):
        def find(data,bid):return next(r for r in data['records'] if r['record_type']=='Guidance' and r['source_block_id']==bid)
        before=find(self.before,'block-000151-be80bd28');after=find(self.after,'block-000151-be80bd28')
        self.assertEqual(before['condition_evidence_ids'],[])
        conditions=[self.after['evidence'][eid]['quote'] for eid in after['condition_evidence_ids']]
        self.assertTrue(any('timing of cash payments' in text for text in conditions))
        self.assertEqual(len(after['evidence_ids']),3)
        self.assertEqual(len(find(self.after,'block-000019-229fa8b5')['evidence_ids']),1)

    def test_full_qa_and_quote_identity(self):
        qa=next(r for r in self.after['records'] if r['record_type']=='QAExchange' and r['exchange_id']=='qa-06')
        reader=DocumentReader(self.index)
        expected=[b['block_id'] for b in reader.blocks if b.get('exchange_id')=='qa-06']
        self.assertEqual([self.after['evidence'][eid]['block_id'] for eid in qa['evidence_ids']],expected)
        for ev in self.after['evidence'].values():
            block=reader.blocks[reader.positions[ev['block_id']]]
            self.assertEqual(block['text'][ev['start']:ev['end']],ev['quote'])

    def test_context_cannot_cross_speaker_or_exceed_limit(self):
        reader=DocumentReader(self.index)
        last=next(b for b in reader.blocks if b.get('section')=='prepared' and b.get('speaker_role')=='management')
        with self.assertRaises(ValueError):guidance_context(reader,last,following=4)

    def test_missing_company_and_unsupported_calendar_rejected(self):
        with self.assertRaises(TypeError):
            extract_transcript_records(self.source, self.index)
        for company, calendar in ((" ", "calendar"), ("sample-company", "june-year-end")):
            with self.subTest(company=company), self.assertRaises(ValueError):
                extract_transcript_records(self.source, self.index, company_id=company, fiscal_calendar=calendar)


if __name__ == '__main__':
    unittest.main()
