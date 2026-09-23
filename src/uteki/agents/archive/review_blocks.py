"""Source-bound content approval units. These do not adopt a report as a baseline."""
import hashlib
import json
import re

def review_blocks(answer):
    result = {}
    if not isinstance(answer, dict): return result
    def add(key, value):
        result[key] = hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    if 'report_markdown' in answer:
        for i,line in enumerate(answer['report_markdown'].splitlines()):
            line=line.strip()
            if not line: continue
            if line.startswith('|'):
                cells=[c.strip() for c in line.strip('|').split('|')]
                if all(re.fullmatch(r'[:\- ]+',c or '-') for c in cells): continue
                for k,c in enumerate(cells): add(f'md:{i}:{k}',c)
            else: add(f'md:{i}',line)
    else:
        for i,c in enumerate(answer.get('claims',[])): add(f'claim:{i}',c)
    return result

def valid_decisions(row):
    blocks=review_blocks(row.get('answer'))
    return {k:v for k,v in row.get('block_decisions',{}).items() if k in blocks and v.get('hash')==blocks[k]}
