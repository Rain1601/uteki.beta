"""Decimal arithmetic from explicitly selected, already-read table cells.

Checks identity, row label and year-column alignment. It does not infer units,
business hierarchy, fiscal comparability or whether a ratio supports a thesis.
"""
from decimal import Decimal, ROUND_HALF_UP
import re


def number(text):
    text = text.strip()
    negative = text.startswith('(') and text.endswith(')')
    if negative:
        text = text[1:-1]
    if not re.fullmatch(r'-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?', text):
        raise ValueError('Expected a complete numeric cell; no guessed currency, dash or footnote')
    value = Decimal(text.replace(',', ''))
    return -value if negative else value


def operand(session, ref):
    key = (ref['document_id'],ref['index_id'],ref['block_id'])
    if key not in session.evidence:
        raise ValueError('Arithmetic requires an actually read block')
    reader = session.reader(ref['document_id'])
    block = reader.blocks[reader.positions[ref['block_id']]]
    if block['text'] != session.evidence[key]:
        raise ValueError('Read evidence changed')
    cells = (block.get('table') or {}).get('cells', [])
    cell = next((c for c in cells if (c['row'],c['column']) == (ref['row'],ref['column'])), None)
    if cell is None:
        raise ValueError('Cell not present')
    labels = [c['text'] for c in cells if c['row'] == ref['row'] and c['column'] < ref['column']]
    if ref['row_label'] not in labels:
        raise ValueError('Row label mismatch')
    headers = [c for c in cells if c['row'] < ref['row'] and c['text'] == str(ref['year'])
               and c['column'] <= cell['column'] < c['column'] + c.get('colspan',1)]
    if not headers:
        raise ValueError('Year header does not cover selected value column')
    return {'reference':dict(ref),'source_text':cell['text'], 'value':str(number(cell['text']))}


def calculate(session, operation, first, second, decimals=2):
    if type(decimals) is not int or not 0 <= decimals <= 6:
        raise ValueError('Precision must be 0..6')
    a, b = operand(session, first), operand(session, second)
    x, y = Decimal(a['value']), Decimal(b['value'])
    if operation == 'growth_pct':
        if first['row_label'] != second['row_label'] or first['year'] <= second['year']:
            raise ValueError('Growth needs the same metric, current then earlier year')
        if y <= 0:
            raise ValueError('Growth from a nonpositive base needs separate interpretation')
        result, formula = (x/y-1)*100, '(current/prior - 1)*100'
    elif operation == 'ratio_pct':
        if first['year'] != second['year'] or y == 0:
            raise ValueError('Ratio requires matching years and nonzero denominator')
        result, formula = x/y*100, '(numerator/denominator)*100'
    else:
        raise ValueError('Unsupported arithmetic operation')
    rounded = result.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    return {'operation':operation,'formula':formula,'operands':[a,b], 'value':str(rounded),
            'unit':'percent','arithmetic_status':'passed',
            'interpretation_status':'not_checked',
            'limitations':['Caller must verify units, row section and fiscal comparability.',
                           'Arithmetic correctness does not establish semantic support.']}
