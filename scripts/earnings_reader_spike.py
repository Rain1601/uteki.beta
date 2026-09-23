"""Exercise Analysis Agent tools without model calls; NOT an answer-quality eval."""
import argparse
import json
from pathlib import Path
from uteki.agents.reading.material_library import pin_materials
from uteki.agents.reading.tool_session import ToolSession
from uteki.agents.reading.document_reader import sha

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    manifest=pin_materials(ROOT,'2026-02-05',[
        'alphabet-000165204426000018','alphabet-2025q4-release','alphabet-2025q4-call'])
    manifest.update(mode='deterministic retrieval smoke; not model analysis or independent benchmark',
                    model_calls=0,model_cost_usd=0,review_status='pending')
    manifest['code_hashes']={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in [Path(__file__),
        ROOT/'src/uteki/agents/reading/document_reader.py',ROOT/'src/uteki/agents/reading/material_library.py',
        ROOT/'src/uteki/agents/reading/tool_session.py',ROOT/'src/uteki/agents/reading/reading_groups.py']}
    (args.output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    session=ToolSession(ROOT,manifest,args.output,max_calls=40,max_chars=350000)
    checks=[]
    for case,query in [('cloud_growth','Cloud'),('ai_investment','capital'),('analyst_questions','question')]:
        inventory=session.call(case,'documents','Inspect pinned materials',form='')
        matches=[]
        for doc in inventory:
            outline=session.call(case,'outline','Select document root',document_id=doc['id'])
            root=next(n['node_id'] for n in outline['nodes'] if n['parent_id'] is None)
            result=session.call(case,'search','Find a literal evidence candidate',document_id=doc['id'],node_id=root,query=query,limit=1)
            if result.get('hits'):
                read=session.call(case,'read','Read full surrounding context',document_id=doc['id'],node_id=root,start_block_id=result['hits'][0]['block_id'],count=1)
                if 'error' in read: raise ValueError(read)
                matches.append({'document_id':doc['id'],'blocks_read':len(read['blocks'])})
        checks.append({'case':case,'query':query,'matches':matches})
    (args.output/'checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'calls':session.calls,'characters':session.chars,'checks':checks},ensure_ascii=False,indent=2))


if __name__=='__main__': main()
