"""Local evidence reader for a Codex-authored, sequential retrospective MVP.

This is not an autonomous SDK runner or a blind historical backtest.
Only the current stage's documents are visible; freezing unlocks the next stage.
"""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from uteki.agents.document_reader import DocumentReader
from uteki.agents.material_library import pin_materials

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'experiments/analysis_comparison/codex-hypothesis-2025-2026-v0.1'
STAGES = [
    ('annual', '2026-02-05', 'alphabet-000165204426000018'),
    ('q1', '2026-04-30', 'alphabet-000165204426000048'),
    ('q2', '2026-07-23', 'alphabet-000165204426000071'),
]


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as f:
        f.write(encoded(value))


def stage_material(stage):
    i = [s[0] for s in STAGES].index(stage)
    for previous, _, _ in STAGES[:i]:
        seal = json.loads((OUT / previous / 'frozen.json').read_text())
        if digest((OUT / previous / 'answer.json').read_bytes()) != seal['answer_sha256']:
            raise ValueError('Previous answer changed after freeze')
        for name, expected in seal['read_hashes'].items():
            if digest((OUT / previous / 'reads' / name).read_bytes()) != expected:
                raise ValueError('Previous read changed after freeze')
    key, cutoff, docid = STAGES[i]
    manifest_path = OUT / key / 'materials.json'
    if not manifest_path.exists():
        save_new(manifest_path, pin_materials(ROOT, cutoff, [s[2] for s in STAGES[:i + 1]]))
    manifest = json.loads(manifest_path.read_text())
    doc = next(d for d in manifest['documents'] if d['id'] == docid)
    reader = DocumentReader(ROOT / doc['index_folder'])
    if reader.manifest != manifest['indexes'][docid]:
        raise ValueError('Pinned index changed')
    return doc, reader


def record(stage, operation, arguments, result):
    folder = OUT / stage / 'reads'
    folder.mkdir(parents=True, exist_ok=True)
    number = len(list(folder.glob('*.json'))) + 1
    save_new(folder / f'{number:03d}.json', {
        'at': datetime.now(timezone.utc).isoformat(), 'operation': operation,
        'arguments': arguments, 'result': result,
    })


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=[s[0] for s in STAGES])
    p.add_argument('operation', choices=['outline', 'search', 'read', 'freeze'])
    p.add_argument('--query')
    p.add_argument('--block')
    p.add_argument('--count', type=int, default=1)
    p.add_argument('--offset', type=int, default=0)
    args = p.parse_args()
    if (OUT / args.stage / 'frozen.json').exists():
        raise ValueError('Stage is frozen; create a new experiment for revisions')
    doc, reader = stage_material(args.stage)
    root_id = next(n['node_id'] for n in reader.index['nodes'] if n['kind'] == 'document')
    if args.operation == 'outline':
        result = reader.outline()
    elif args.operation == 'search':
        result = reader.search(root_id, args.query, offset=args.offset, limit=20)
    elif args.operation == 'read':
        result = reader.read(root_id, args.block, args.count)
    else:
        answer_path = OUT / args.stage / 'answer.json'
        answer = json.loads(answer_path.read_text())
        read_blocks = {}
        read_files = {}
        for log in (OUT / args.stage / 'reads').glob('*.json'):
            read_files[log.name] = digest(log.read_bytes())
            entry = json.loads(log.read_text())
            for b in entry['result'].get('blocks', []):
                read_blocks[b['block_id']] = b
        evidence = answer['evidence']
        if not evidence:
            raise ValueError('Evidence required')
        for e in evidence:
            b = read_blocks[e['block_id']]
            if not e['quote'] or e['quote'] not in b['text']:
                raise ValueError('Quote not in read block: ' + e['id'])
            e.update(document_id=doc['id'], index_id=reader.index['index_id'],
                     reported_page=b['reported_page'], source_anchor=b.get('source_anchor'),
                     dom_path=b.get('dom_path'), text_hash=b['text_hash'])
        save_new(OUT / args.stage / 'evidence.json', evidence)
        result = {'answer_sha256': digest(answer_path.read_bytes()),
                  'read_hashes': read_files, 'evidence_count': len(evidence),
                  'frozen_at': datetime.now(timezone.utc).isoformat(),
                  'validation': 'Quotes occur in blocks actually read; not semantic correctness approval.',
                  'author': 'Codex in this conversation; model identity and token billing unavailable',
                  'experiment_type': 'retrospective_sequential_not_blind',
                  'review_status': 'pending_human_review',
                  'external_model_calls': 0, 'codex_cost_usd': None,
                  'cost_note': 'No external API calls. Codex subscription usage/cost unavailable, not zero.'}
        save_new(OUT / args.stage / 'frozen.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    record(args.stage, args.operation, vars(args), result)
    # Printed read view excludes HTML/cell metadata; the log preserves full blocks.
    if args.operation == 'read':
        result = {'blocks': [{k: b.get(k) for k in ('block_id', 'type', 'reported_page', 'text')}
                             for b in result['blocks']], 'next_block_id': result['next_block_id']}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
