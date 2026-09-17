"""Conservative percentage coverage gate, NOT a semantic or full numeric audit.

A percentage needs an exact disclosure in a cited, read block or a successful
calculation whose operands are cited in the same paragraph. Matching the number
does not prove that its metric, period, units or interpretation are correct.
"""
from decimal import Decimal, ROUND_HALF_UP
import json
import re


PERCENT = re.compile(r'(?<![\d.])([+-]?\d+(?:\.\d+)?)\s*[%％]')


def identity(ref):
    return tuple(ref.get(k) for k in ('document_id', 'index_id', 'block_id'))


def review_percentages(report, tool_records):
    calculations = [r['result'] for r in tool_records
                    if r.get('tool') == 'calculate_table'
                    and r.get('result', {}).get('arithmetic_status') == 'passed']
    paragraphs = [('thesis', report['thesis'])]
    for section in report['sections']:
        paragraphs.extend((f"{section['key']}/{i}", p) for i, p in enumerate(section['paragraphs']))
    findings = []
    for location, paragraph in paragraphs:
        refs = paragraph.get('citations', [])
        keys = {identity(c) for c in refs}
        disclosed = {Decimal(m[1]) for c in refs for m in PERCENT.finditer(c.get('quote', ''))}
        for match in PERCENT.finditer(paragraph['text']):
            raw = match[1]
            value = Decimal(raw)
            precision = len(raw.partition('.')[2])
            candidates = [c for c in calculations
                          if all(identity(o['reference']) in keys for o in c['operands'])
                          and Decimal(c['value']).quantize(Decimal(1).scaleb(-precision),
                                                         rounding=ROUND_HALF_UP) == value]
            findings.append(dict(location=location, text=match[0],
                                 status='covered_not_verified' if value in disclosed or candidates else 'unresolved',
                                 basis='source_percentage' if value in disclosed else 'calculation' if candidates else None))
    unresolved = [f for f in findings if f['status'] == 'unresolved']
    return dict(status='unresolved' if unresolved else 'coverage_only_pending_semantic_review',
                findings=findings, errors=[f"Unverified percentage at {f['location']}: {f['text']}" for f in unresolved],
                limitations=['Only percentage expressions are checked; other numbers still require review.',
                             'Number matching does not verify metric, period, units or economic meaning.',
                             'Unmatched forecast percentages also require explicit human review.'])


def review_run(report, folder):
    records = [json.loads(p.read_text()) for p in sorted(folder.glob('tool-*.json'))]
    return review_percentages(report, records)
