"""Answer-first comparison. Answers are reviewed carry-forwards, not new model output."""
import html
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'experiments/document_reader/multi-query-v0.1'
NEW=ROOT/'experiments/document_reader/multi-query-v0.2'
e=html.escape
answers=json.loads((OLD/'answers.json').read_text())
changes=json.loads((NEW/'comparison.json').read_text())
observations={
'q1':'11 项竞争来源及引导段完整保留，正文无变化。',
'q2':'Other Bets 原文及答案依据无变化。',
'q3':'从任一列表条目读取，现在带上前页标题与引导句；Gemini 两个子项显式归属于 Agents。该已知路径本来从标题读取，所以总文本量不变。',
'q4':'年报读取由 7,969 字符的混杂内容，变为 651 字符的 Cloud 专属上下文（5 Blocks）。候选答案不变，但依据更干净。',
'q5':'四张表的读取均自动附带单位说明；两张营业利润表同时带上紧邻的标记注释。旧路径里的额外查单位步骤因此冗余，但本次保留以便对比，未声称调用次数下降。',
'q6':'仍无已索引电话会材料，继续返回不足，不生成替代解释。'}
sections=[]
for a in answers:
    cols=[]
    for folder,label in ((OLD,'旧版'),(NEW,'新版')):
        evidence={}
        for p in sorted(folder.glob('call-*.json')):
            c=json.loads(p.read_text())
            if c['case']==a['id'] and c['tool']=='read':
                for b in c['result']['blocks']: evidence[(c['result']['document_id'],b['block_id'])]=b
        entries=[]
        for (doc,bid),b in evidence.items():
            entries.append(f'<details><summary>{e(doc)} · p.{b["reported_page"]} · {e(bid)}</summary><p class="quote">{e(b["text"])}</p></details>')
        cols.append(f'<div><h3>{label}证据 · {len(evidence)} Blocks</h3>'+''.join(entries)+'</div>')
    metrics=[x for x in changes if x['case']==a['id']]
    rows=''.join(f'<tr><td>{x["call"]}</td><td>{x["old_blocks"]} → {x["new_blocks"]}</td><td>{x["old_text_chars"]} → {x["new_text_chars"]}</td></tr>' for x in metrics)
    sections.append(f'<section id="{a["id"]}"><h2>{e(a["question"])}</h2><h3>候选回答（本轮核对后沿用）</h3><p>{e(a["answer"])}</p><p class="note">{e(observations[a["id"]])}</p><details><summary>读取量对比</summary><table><tr><th>调用</th><th>Blocks：旧 → 新</th><th>正文字符：旧 → 新</th></tr>{rows}</table></details><div class="columns">'+''.join(cols)+'</div></section>')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>读取修复 · 六题新旧对比</title><style>body{margin:0;background:#fafbf9;color:#20382c;font:15px/1.65 system-ui}header,main{padding:24px 4vw}h1{font-size:26px}h2{font-size:21px}h3{font-size:15px}section{border-top:1px solid #cdd8d0;padding:24px 0}.columns{display:grid;grid-template-columns:1fr 1fr;gap:24px}summary{cursor:pointer;padding:8px 0;font-size:12px;overflow-wrap:anywhere}.quote{white-space:pre-wrap;background:white;padding:12px;font-size:13px}.note{color:#286247;border-left:3px solid #86b69b;padding-left:12px}td,th{text-align:left;padding:6px 14px}a{color:#246648;margin-right:18px}@media(max-width:800px){.columns{grid-template-columns:1fr}}</style><header><h1>读取修复 · 六题新旧对比</h1><p>reading-groups v0.2 · 年报 v0.5-candidate · 待人工审核</p><p>同一已知路径的工程回归，不是新的独立 Agent 运行。答案核对后沿用，先看回答，再展开新旧证据。没有独立 gold answer，不报告准确率。</p>'''+''.join(f'<a href="#{a["id"]}">{a["id"].upper()}</a>' for a in answers)+'</header><main>'+''.join(sections)+'</main></html>'
with (NEW/'review.html').open('x') as f:f.write(page)
with (NEW/'answers.json').open('x') as f:json.dump([dict(a,observation=observations[a['id']],status='carried_forward_checked_against_replay_pending_human') for a in answers],f,ensure_ascii=False,indent=2)
print('review.html created')
