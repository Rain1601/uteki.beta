"""Build review from recorded reads only; verify numeric cell references."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / 'experiments/document_reader/multi-query-v0.1'
calls = [json.loads(p.read_text()) for p in sorted(RUN.glob('call-*.json'))]
answers = json.loads((RUN/'answers.json').read_text())
m = json.loads((RUN/'manifest.json').read_text())
docs = {d['id']:d for d in m['documents']}
read = {(c['result']['document_id'], b['block_id']): b for c in calls if c['tool']=='read' for b in c['result']['blocks']}
checks = []
for doc,block,row,column,year,expected in [
 ('alphabet-000165204425000014','block-000569-4a262e4f',9,15,'2024','43,229'),
 ('alphabet-000165204425000014','block-000631-b14e2c6d',13,15,'2024','6,112'),
 ('alphabet-000165204426000018','block-000511-f8791d57',9,3,'2024','43,229'),
 ('alphabet-000165204426000018','block-000511-f8791d57',9,9,'2025','58,705'),
 ('alphabet-000165204426000018','block-000562-00484160',13,3,'2024','6,112'),
 ('alphabet-000165204426000018','block-000562-00484160',13,9,'2025','13,910')]:
    cells = read[(doc,block)]['table']['cells']
    cell = next(c for c in cells if c['row']==row and c['column']==column)
    header = next(c for c in cells if c['row']==2 and c['column']==column)
    label = next(c for c in cells if c['row']==row and c['column']==0)
    assert cell['text']==expected and header['text']==year and label['text']=='Google Cloud'
    checks.append({'document_id':doc,'block_id':block,'cell':cell,'year_header':header,'row_label':label})
with (RUN/'financial-checks.json').open('x') as f:
    json.dump(checks,f,ensure_ascii=False,indent=2)
e=html.escape
parts=[]
for answer in answers:
    casecalls=[c for c in calls if c['case']==answer['id']]
    evidence={}
    for c in casecalls:
        if c['tool']=='read':
            for b in c['result']['blocks']:
                evidence[(c['result']['document_id'],b['block_id'])]=b
    entries=[]
    for (docid,bid),b in evidence.items():
        d=docs[docid]
        url=d['source_url'] + ('#'+b['source_anchor'] if b.get('source_anchor') else '')
        content=e(b['text'])
        if b.get('table'):
            rows={}
            for cell in b['table']['cells']:
                if cell['text'].strip():rows.setdefault(cell['row'],[]).append(cell['text'])
            content='<table>'+''.join('<tr>'+''.join('<td>'+e(t)+'</td>' for t in row)+'</tr>' for row in rows.values())+'</table>'
        entries.append(f'<details><summary>{e(d["title"])} · p.{b["reported_page"]} · {e(bid)}</summary><small>{e(m["indexes"][docid]["index_id"])}</small><div class="quote">{content}</div><a href="{e(url)}" target="_blank">SEC 原文（原始锚点，可能是所在页而非精确句子）</a></details>')
    parts.append(f'<section id="{answer["id"]}"><h2>{e(answer["id"].upper())} · {e(answer["question"])}</h2><p>{e(answer["answer"])}</p><p class="note">观察：{e(answer["observation"])}</p><small>{len(casecalls)} 次记录调用 · {len(evidence)} 个去重完整 Blocks · 人工审核待完成</small>'+''.join(entries)+'</section>')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>6 题跨文档验证</title><style>body{margin:0;background:#fafbf9;color:#22372e;font:15px/1.7 system-ui}header,main{padding:24px 5vw}header{border-bottom:1px solid #ccd7cd}h1{margin:0;font-size:25px}h2{font-size:19px}section{padding:20px 0;border-bottom:1px solid #ccd7cd}small,.note{color:#637168}summary{cursor:pointer;padding:9px 0}details{border-top:1px solid #e3e8e3}.quote{white-space:pre-wrap;background:white;padding:15px;font:14px/1.6 Georgia,serif}td{padding:4px 12px;border-bottom:1px solid #ddd}a{color:#16714d}nav a{margin-right:18px}</style><header><h1>Alphabet · 6 题检索验证</h1><p>固定 18 份材料 · 实际引用 4 份文档 · 候选结果 / 待人工审核</p><nav>'''+''.join(f'<a href="#{a["id"]}">{a["id"].upper()}</a>' for a in answers)+'''</nav><p>这是当前助手执行的可追溯演示，不是独立 Agent 盲测。运行前固定了检查标准，但没有独立人工标准答案，因此不报告准确率。目录调用在同一会话共享，并非每题独立运行。</p><a href="manifest.json">固定版本与检查项</a> · <a href="financial-checks.json">财务单元格核验</a></header><main>'''+''.join(parts)+'</main></html>'
with (RUN/'review.html').open('x') as f:f.write(page)
print(json.dumps({'calls':len(calls),'unique_read_blocks':len(read),'financial_cell_checks':len(checks),'review':'pending'}))
