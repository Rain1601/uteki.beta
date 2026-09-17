"""Download explicitly discovered official PDFs; never replace source indexes.

No model calls, no PDF authoring. Resumable originals, hashes, page/word inventory.
"""
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT/'data/reading_library/alphabet'
CDN = 'https://s206.q4cdn.com/479360582/files/doc_financials/'


def acquire(row):
    url = row.get('url') or CDN+row['cdn_path']
    folder = LIBRARY/'originals'/row['period'][:4]
    folder.mkdir(parents=True,exist_ok=True)
    target = folder/f"alphabet-{row['period']}-{row['kind']}.pdf"
    record = dict(period=row['period'],kind=row['kind'],url=url,
                  discovery_url=row.get('discovery_url') or 'https://abc.xyz/investor/earnings/',
                  discovered_on='2026-09-16',translation_status='not_started')
    try:
        if not target.exists():
            with tempfile.TemporaryDirectory(prefix='uteki-pdf-download-') as tmp:
                pending=Path(tmp)/'source.pdf'
                response=subprocess.run(['curl','-fsSL','--max-time','60',url,'-o',str(pending)],capture_output=True,text=True)
                if response.returncode:
                    raise ValueError(response.stderr.strip())
                raw=pending.read_bytes()
                if not raw.startswith(b'%PDF-'):
                    raise ValueError('Not a PDF; original not saved')
                with target.open('xb') as stream:
                    stream.write(raw)
        raw=target.read_bytes()
        if not raw.startswith(b'%PDF-'):
            raise ValueError('Existing original is not a PDF')
        info=subprocess.run(['pdfinfo',str(target)],capture_output=True,text=True,check=True).stdout
        text=subprocess.run(['pdftotext','-layout',str(target),'-'],capture_output=True,text=True,check=True).stdout
        match=re.search(r'^Pages:\s*(\d+)',info,re.M)
        record.update(status='downloaded',path=str(target.relative_to(LIBRARY)),
                      sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),pages=int(match[1]) if match else None,
                      extracted_words=len(re.findall(r'\S+',text)),extracted_chars=len(text),
                      extraction_note='Text layer only; charts and image text may require visual review')
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        record.update(status='failed',error=str(exc)[:500])
    print(f"{row['period']} {row['kind']}: {record['status']}",flush=True)
    return record


def main():
    with (LIBRARY/'pdf_sources.tsv').open() as stream:
        rows=list(csv.DictReader(stream,delimiter='\t'))
    transcripts=LIBRARY/'transcript_sources.json'
    if transcripts.exists():
        rows += json.loads(transcripts.read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        records=list(pool.map(acquire,rows))
    manifest=dict(company='Alphabet',scope='Fiscal 2022–2026 official earnings materials discovered so far',
                  checked_at=datetime.now(timezone.utc).isoformat(),documents=records,
                  total_pages=sum(r.get('pages') or 0 for r in records),
                  total_extracted_words=sum(r.get('extracted_words') or 0 for r in records),
                  downloaded=sum(r['status']=='downloaded' for r in records),failed=sum(r['status']=='failed' for r in records),
                  gaps=['Scope is fiscal 2022 through published 2026 quarters on the official earnings page, not every Alphabet publication.',
                        'No separate earnings slides were linked for 2022–2024 at discovery; do not infer that none exist elsewhere.',
                        'Annual-report editions overlap 10-K text; deduplicate before translation.'])
    (LIBRARY/'download_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    kinds=Counter(r['kind'] for r in records if r['status']=='downloaded')
    lines=['# Alphabet 原始材料阅读目录','',
           '范围：官方财报目录中的 FY2022–FY2025 全年，以及已发布的 2026 Q1/Q2。不是全部公司出版物。',
           '英文原件保持不变。中文翻译尚未启动，等待范围、对照方式和预算确认。','',
           f"已下载 {manifest['downloaded']} 份；失败 {manifest['failed']} 份；共 {manifest['total_pages']} 页。",'',
           ' | '.join(f'{k}: {v}' for k,v in sorted(kinds.items())), '',
           'Annual Report 与同年 10-K 存在重叠，翻译前需去重，原件仍分别保留。','',
           '| 材料 | 页数 | 英文原件 | 官方出处 |','|---|---:|---|---|']
    for r in sorted(records,key=lambda x:(x['period'],x['kind']),reverse=True):
        original=f"[打开 PDF]({r['path']})" if r['status']=='downloaded' else '下载失败'
        lines.append(f"| {r['period']} {r['kind']} | {r.get('pages','—')} | {original} | [来源]({r['url']}) |")
    lines += ['', '## 完整性与翻译说明',''] + ['- '+g for g in manifest['gaps']]
    lines += ['', '译文计划：保留源页码、发言人、段落、表格数字与单位；全文翻译，不用摘要代替；',
              '图表文字与扫描页单独标记复核。机器译文不是官方中文版本。',
              '下载目录不修改研究系统原有 Source Blocks、索引和分析报告。','']
    (LIBRARY/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('downloaded','failed','total_pages','total_extracted_words')},ensure_ascii=False))


if __name__=='__main__':
    main()
