"""Offline review for the three explicitly selected canary questions.

Expected values stay in this evaluation folder and never enter planner inputs.
Run after both live runs. Refuses to overwrite the recorded review.
"""
import json
from decimal import Decimal
from pathlib import Path

from uteki.infrastructure.research_data.financial_records import digest
from uteki.infrastructure.research_data.query_service import QueryDataPort

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def read(path):
    return json.loads(path.read_text())


def review():
    config = read(HERE / 'refinement-config.json')
    reference = read(HERE / 'review-reference.json')
    dataset = ROOT / config['dataset']
    pilot = read(dataset.parent / 'run-manifest.json')
    unchanged = all(digest((dataset.parent / name).read_bytes()) == expected
                    for name, expected in pilot['files'].items())
    assert unchanged, 'historical pilot artifacts changed'
    sources = {s['source_snapshot_id']: s for s in read(dataset / 'sources.json')}
    blocks = {sid: {b['block_id']: b for b in map(json.loads,
               (dataset / s['index_folder'] / 'blocks.jsonl').read_text().splitlines())}
              for sid, s in sources.items()}
    rows = []
    for run in ('live-01', 'live-02'):
        for case in config['cases']:
            name = case['id']
            folder = HERE / run / name
            result = read(folder / 'session/result.json')
            costs = read(folder / 'costs.json')
            manifest = read(folder / 'session/manifest.json')
            assert all(digest((folder / 'session' / p).read_bytes()) == h for p, h in manifest['files'].items())
            evidence = result['evidence']
            checked_evidence = []
            for eid, value in evidence.items():
                sid, bid = value['source_snapshot_id'], value['block_id']
                assert value['quote'] in blocks[sid][bid]['text'], eid
                assert value['source_sha256'] == sources[sid]['source_sha256'], eid
                checked_evidence.append(eid)
            for ctx in result['contexts']:
                for block in ctx['blocks']:
                    assert block == blocks[ctx['source_snapshot_id']][block['block_id']]
            checks = {'evidence_quotes_match_frozen_blocks': True, 'context_blocks_match_frozen_index': True}
            if name == 'q1-margin':
                expected = reference[name]
                checks['requested_observations_match'] = all(
                    any(all(record[k] == item[k] for k in item) for record in result['records'])
                    for item in expected['observations'])
                checks['formula_and_operands_match'] = result['computed_facts'] == expected['computed']
                checks['status_matches'] = result['status'] == 'answered'
            elif name == 'capex-conditions':
                expected = reference[name]
                selected_ids = {rid for part in result['answer_parts'] for rid in part['record_ids']}
                selected = [r for r in result['records'] if r['record_id'] in selected_ids]
                guidance = [r for r in selected if r['metric_id'] == 'capex_guidance']
                checks['range_and_target_period_match'] = bool(guidance) and all(
                    r['value_decimal'] == expected['low_usd'] and r['upper_decimal'] == expected['high_usd']
                    and r['unit'] == 'USD' and r['value_kind'] == 'management_guidance'
                    and r['period']['kind'] == 'year' and r['period']['start'] == expected['guidance_year'] + '-01-01'
                    and r['period']['end'] == expected['guidance_year'] + '-12-31'
                    and sources[r['source_snapshot_id']]['period_end'] == expected['source_period_end']
                    for r in guidance)
                cited_text = '\n'.join(evidence[eid]['quote'] for r in selected
                                      for field in ('evidence_ids', 'qualifier_evidence_ids') for eid in r[field])
                checks['all_three_conditions_in_cited_evidence'] = all(q in cited_text for q in expected['required_conditions'])
                checks['no_unresolved_gap'] = not result['gaps']
                checks['status_matches'] = result['status'] == 'answered'
            else:
                checks['clarifies_without_selecting_period'] = (
                    result['status'] == 'needs_clarification' and not result['records'] and not result['computed_facts'])
            rows.append({'run': run, 'case': name, 'status': result['status'], 'checks': checks,
                         'checked_evidence_ids': checked_evidence,
                         'requests': costs['requests'], 'estimated_usd': costs['known_estimated_usd'],
                         'unknown_cost_requests': costs['unknown_cost_requests'],
                         'steps': result['trace'], 'gaps': result['gaps'],
                         'result': str((folder / 'session/result.json').relative_to(ROOT))})
    # Execute the original failing filing plan with the repaired reader, offline.
    original = HERE / 'live-01/q1-margin/session'
    request = read(original / 'request.json')
    plan = read(original / 'turn-01/decision.json')['plan']
    with QueryDataPort(dataset) as port:
        replay = port.query_data({'query_id': 'offline-original-plan-replay',
                                  **{k: v for k, v in request.items() if k != 'company_ids'}, **plan})
    assert replay['documents'][0]['contexts']
    assert replay['computed_facts'] == reference['q1-margin']['computed']
    with (HERE / 'offline-original-plan-replay.json').open('x') as stream:
        json.dump(replay, stream, ensure_ascii=False, indent=2)
    report = {'scope': 'Known canary cases; fixture checks plus source review, not a blind or general evaluation.',
              'historical_pilot_files_unchanged': unchanged, 'historical_pilot_file_count': len(pilot['files']),
              'rows': rows, 'requests': sum(r['requests'] for r in rows),
              'estimated_usd': str(sum((Decimal(r['estimated_usd']) for r in rows), Decimal(0))),
              'unknown_cost_requests': sum(r['unknown_cost_requests'] for r in rows),
              'offline_original_plan_replay': {'no_exception': True, 'retrieved_document_contexts': True,
                                               'formula_and_operands_match': True},
              'manual_findings': [
                  'CapEx answer references the required amounts and qualifiers, but both runs over-query unrelated metrics and keep incidental gaps.',
                  'Second-run clarification correctly requests a period, but its prose wrongly implies continuous quarter coverage and suggests YTD despite the restricted NL period parser.',
                  'Semantic subquestion completeness and retrieval relevance are not host-validated.'
              ],
              'expansion_gate': 'not_passed'}
    with (HERE / 'review.json').open('x') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('rows', 'manual_findings')}, ensure_ascii=False))


if __name__ == '__main__':
    review()
