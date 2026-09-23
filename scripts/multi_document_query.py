"""Pinned, read-only multi-document tool session; Codex chooses calls externally."""
import argparse
import json
from pathlib import Path
from uteki.agents.reading.document_reader import DocumentReader, sha

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/document_reader/multi-query-v0.1'


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('tool', choices=['init', 'documents', 'outline', 'search', 'read'])
    p.add_argument('--case', default='setup')
    p.add_argument('--args', default='{}')
    a = p.parse_args()
    params = json.loads(a.args)
    if a.tool == 'init':
        catalog = json.loads((ROOT / 'data/document_library/alphabet/catalog.json').read_text())
        docs = [d for d in catalog['documents'] if d.get('index_folder')]
        RUN.mkdir(parents=True, exist_ok=False)
        save(RUN / 'manifest.json', {'documents': docs, 'indexes': {d['id']: DocumentReader(ROOT / d['index_folder']).manifest for d in docs},
             'mode': 'Codex-directed, known-context demonstration; not independent blind evaluation',
             'checks': {
                 'q1': 'FY2025 competition: complete list with introduction; no invented names.',
                 'q2': 'FY2025 Other Bets: distinguish examples, organization, revenue sources.',
                 'q3': 'FY2022 vs FY2025 Cloud: cite both periods; no inference that first disclosure means business inception.',
                 'q4': 'FY2025 vs 2026 Q2 Cloud revenue sources: compare same disclosure topic; no invented revenue shares.',
                 'q5': 'FY2024 and FY2025 Cloud revenue and operating income: verify year headers, metric and USD millions; cross-check overlapping reports.',
                 'q6': '2026 Q2 earnings call explanation: inventory lacks transcript, so stop and report missing material.'},
             'review_status': 'pending', 'reference_status': 'criteria frozen; no independent gold answers',
             'code_hashes': {str(f.relative_to(ROOT)): sha(f.read_bytes()) for f in [Path(__file__), ROOT/'src/uteki/agents/reading/document_reader.py', ROOT/'src/uteki/agents/reading/reading_groups.py']}})
        print('initialized')
        return
    m = json.loads((RUN / 'manifest.json').read_text())
    for file, digest in m['code_hashes'].items():
        if sha((ROOT / file).read_bytes()) != digest:
            raise ValueError('Code changed; use a new run')
    if a.case not in m['checks']:
        raise ValueError('Unknown case')
    if a.tool == 'documents':
        result = [{k:d.get(k) for k in ('id','form','period_end','filed_at','title','status')} for d in m['documents']
                  if all(d.get(k) == v for k,v in params.items())]
    else:
        doc_id = params.pop('document_id')
        d = next(d for d in m['documents'] if d['id'] == doc_id)
        r = DocumentReader(ROOT / d['index_folder'])
        if r.manifest != m['indexes'][doc_id]:
            raise ValueError('Index changed')
        result = getattr(r, a.tool)(**params)
        result['document_id'] = doc_id
        params['document_id'] = doc_id
    seq = len(list(RUN.glob('call-*.json'))) + 1
    save(RUN / f'call-{seq:03}.json', {'case': a.case, 'tool': a.tool, 'arguments': params, 'result': result})
    # Full payload always in trace; terminal keeps locators/text and table cell structure.
    if isinstance(result, dict) and 'blocks' in result:
        result = dict(result, blocks=[{k:b[k] for k in ('block_id','text','type','reported_page','table')} for b in result['blocks']])
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
