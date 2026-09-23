"""Explicitly authorized small Opus probe. No retries; never logs credentials."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx2
from openai import OpenAI
from uteki.agents.runtime.local_credentials import load_provider_key

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent

def main():
    load_provider_key(ROOT, 'aihubmix')
    client = OpenAI(api_key=os.environ['AIHUBMIX_API_KEY'],
                    base_url='https://aihubmix.com/v1', timeout=45,
                    max_retries=0, http_client=httpx2.Client(follow_redirects=False, timeout=45))
    source = ROOT / 'data/evaluation/m0_r2a/2026-09-18-candidate/review_excerpt.json'
    paragraphs = [p for p in json.loads(source.read_text())['paragraphs']
                  if p['ordinal'] in (73, 76, 84, 88, 89, 90, 91)]
    tasks = [('hello', 'Hello, how are you?', 1024),
             ('extraction', '只依据下面原文，用中文输出 JSON：business_objects、revenue_categories、'
              'relationships、unknowns。每个提取项附 paragraph ordinal 和逐字 quote。'
              '区分业务对象与财务披露类别；没有披露的数值保持 null；不要引用外部知识。'
              '另说明这些段落能否确定 YouTube 全部收入与各产品收入。原文：\n'
              + json.dumps(paragraphs, ensure_ascii=False), 4096)]
    for name, prompt, limit in tasks:
        request = {'model': 'claude-opus-5-5', 'messages': [{'role': 'user', 'content': prompt}],
                   'max_tokens': limit, 'stream': False}
        (OUT / f'{name}.request.json').write_text(json.dumps(request, ensure_ascii=False, indent=2))
        record = {'started_at': datetime.now(timezone.utc).isoformat(), 'case': name,
                  'provider': 'aihubmix', 'requested_model': request['model'],
                  'max_retries': 0, 'cost_usd': None, 'pricing_status': 'unverified',
                  'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        try:
            response = client.chat.completions.create(**request)
            (OUT / f'{name}.response.json').write_text(response.model_dump_json(indent=2))
            record.update(status='success', returned_model=response.model,
                          usage=response.usage.model_dump() if response.usage else None)
        except Exception as exc:
            chain = []
            current = exc
            while current and len(chain) < 6:
                chain.append(type(current).__name__)
                current = current.__cause__
            record.update(status='failed', error_types=chain,
                          http_status=getattr(exc, 'status_code', None))
        record['finished_at'] = datetime.now(timezone.utc).isoformat()
        with (OUT / 'attempts.jsonl').open('a') as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + '\n')
        print(json.dumps(record, ensure_ascii=False), flush=True)
        if record['status'] != 'success':
            break
    client.close()

if __name__ == '__main__':
    main()
