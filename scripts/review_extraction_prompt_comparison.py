"""Post-run mechanical checks only; semantic review remains explicit."""
import argparse
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from uteki.infrastructure.research_data.financial_records import digest
from run_research_data_consumer_comparison import save


def review(prepared, run, output):
    expected_hash = json.loads((prepared/'evaluation-freeze.json').read_text())['reference_sha256']
    reference_file = prepared/'evaluation-reference.json'
    if digest(reference_file.read_bytes()) != expected_hash:
        raise ValueError('Evaluation reference changed')
    reference = json.loads(reference_file.read_text())
    manifest = json.loads((run/'result.json').read_text())
    rows = []
    for row in manifest['runs']:
        folder = run/row['folder']
        costs = json.loads((folder/'costs.json').read_text())
        responses = costs['records']
        data = json.loads((folder/'output.json').read_text()) if (folder/'output.json').exists() else None
        numeric_checks = []
        if row['case'] == 'F1':
            for metric, period, value in reference['F1']['targets']:
                matches = [r for r in (data or {}).get('records', [])
                           if (r['entity'], r['metric'], r['period']) == ('google-cloud', metric, period)]
                matched = len(matches) == 1
                if matched:
                    record = matches[0]
                    try:
                        matched = (record['kind'] == 'financial' and record['unit'] == 'USD_millions'
                                   and Decimal(record['value']) == Decimal(value) and record['upper'] is None)
                    except (InvalidOperation, TypeError):
                        matched = False
                numeric_checks.append({'metric': metric, 'period': period, 'expected_value': value,
                                       'matches': len(matches), 'correct': matched})
        rows.append({**row, 'numeric_checks': numeric_checks,
                     'input_tokens': sum((r.get('usage') or {}).get('input_tokens', 0) for r in responses),
                     'output_tokens': sum((r.get('usage') or {}).get('output_tokens', 0) for r in responses),
                     'elapsed_seconds': sum(r['elapsed_seconds'] for r in responses),
                     'estimated_usd': costs['known_estimated_usd'],
                     'unknown_cost_requests': costs['unknown_cost_requests'],
                     'actual_models': sorted({r['actual_upstream_model'] for r in responses if r.get('actual_upstream_model')})})
    save(output, {'reference_sha256': expected_hash, 'rows': rows, 'budget': manifest['budget'],
                  'semantic_review': 'Not performed by this script. Exact quotes do not establish semantic validity.'})


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--prepared', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    review(args.prepared, args.run, args.output)
