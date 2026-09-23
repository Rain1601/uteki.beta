"""Deterministic regression replay of known queries, not autonomous agent evaluation."""
import json
from pathlib import Path
from uteki.agents.reading.document_reader import DocumentReader, sha
from uteki.infrastructure.document_sources.index_artifacts import build_index_artifacts

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'experiments/document_reader/multi-query-v0.1'
OUT = ROOT / 'experiments/document_reader/multi-query-v0.2'


def write(path, data):
    with path.open('x') as f: json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    old = json.loads((OLD / 'manifest.json').read_text())
    OUT.mkdir(parents=True, exist_ok=False)
    docs = old['documents']
    readers = {}
    changes = []
    for doc in docs:
        previous = DocumentReader(ROOT / doc['index_folder'])
        if doc['form'] == '10-K':
            target = ROOT / doc['folder'] / 'indexes/v0.5-candidate'
            if target.exists(): raise ValueError('Refusing overwrite: '+str(target))
            new = build_index_artifacts(ROOT / doc['folder'], target, parser_version='sec-source-blocks-v0.1.5')
            # Preserve table/image inventory and legal outline before using a candidate.
            for key in ('tables','images','parts','items'):
                assert new['counts'][key] == previous.manifest['counts'][key], (doc['id'],key)
            changes.append({'document':doc['id'],'old':previous.manifest,'new':new})
            (target / 'CHANGELOG.md').write_text('# v0.5 Candidate\n\nUnwrap annual DOM/XBRL containers with the existing nested parser. No source changes, LLM or semantic inference. Old evidence stays pinned to old indexes. See multi-query-v0.2 for regression results.\n\n使用递归 DOM 解析展开年度报告复合容器；不覆盖旧索引、不调用 LLM。仍需人工审核。\n')
            doc['index_folder'] = str(target.relative_to(ROOT))
            doc['status'] = 'indexed_candidate'
        readers[doc['id']] = DocumentReader(ROOT / doc['index_folder'])
    write(OUT / 'manifest.json', {'documents':docs,'indexes':{d:r.manifest for d,r in readers.items()},
          'mode':'known-query deterministic regression replay, not fresh agent run',
          'review_status':'pending','checks':old['checks'],'changes':changes,
          'code_hashes':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [Path(__file__),ROOT/'src/uteki/agents/reading/document_reader.py',ROOT/'src/uteki/agents/reading/reading_groups.py',ROOT/'src/uteki/infrastructure/document_sources/sec_index.py']}})
    metrics=[]
    for path in sorted(OLD.glob('call-*.json')):
        call=json.loads(path.read_text()); args=dict(call['arguments']); tool=call['tool']
        if tool=='documents':
            result=[{k:d.get(k) for k in ('id','form','period_end','filed_at','title','status')} for d in docs if all(d.get(k)==v for k,v in args.items())]
        else:
            docid=args.pop('document_id'); r=readers[docid]
            if 'node_id' in args:
                suffix=args['node_id'].split('-part-',1)[1]
                args['node_id']=r.index['index_id']+'-part-'+suffix
            if tool=='read':
                oldblock=next(b for b in call['result']['blocks'] if b['block_id']==args['start_block_id'])
                matches=[b for b in r.blocks if b['text']==oldblock['text']]
                lo,hi=r._range(args['node_id'])
                matches=[b for b in matches if lo<=r.positions[b['block_id']]<hi]
                if oldblock['block_id']=='block-000770-2374b36c':
                    matches=[b for b in r.blocks[lo:hi] if b['text']=='Google Cloud revenues consist of revenues from:']
                if len(matches)!=1: raise ValueError(('Ambiguous replay mapping',path.name,len(matches)))
                args['start_block_id']=matches[0]['block_id']
            result=getattr(r,tool)(**args)
            result['document_id']=docid;args['document_id']=docid
        write(OUT/path.name,{'case':call['case'],'tool':tool,'arguments':args,'result':result,'replay_of':path.name})
        if tool=='read':metrics.append({'case':call['case'],'call':path.name,
             'old_blocks':len(call['result']['blocks']),'new_blocks':len(result['blocks']),
             'old_text_chars':sum(len(b['text']) for b in call['result']['blocks']),
             'new_text_chars':sum(len(b['text']) for b in result['blocks'])})
    write(OUT/'comparison.json',metrics)
    print(json.dumps({'replayed':len(list(OUT.glob('call-*.json'))),'annual_candidates':len(changes),'reads':metrics},ensure_ascii=False))


if __name__=='__main__':main()
