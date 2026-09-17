"""Answer-first review for real Single/Team runs (not simulated answers)."""
import argparse
import html
import json
from pathlib import Path

p=argparse.ArgumentParser();p.add_argument('run',type=Path);args=p.parse_args()
run=args.run;m=json.loads((run/'manifest.json').read_text());e=html.escape
sections=[];summary=[]
for case,question in m['cases'].items():
    columns=[]
    for mode in ('single','team'):
        folder=run/case/mode
        path=folder/'result.json'
        if not path.exists():
            failure=json.loads((folder/'failure.json').read_text()) if (folder/'failure.json').exists() else {'status':'running'}
            columns.append('<div><h3>'+mode+'</h3><pre>'+e(json.dumps(failure,ensure_ascii=False,indent=2))+'</pre></div>')
            summary.append({'case':case,'mode':mode,**failure});continue
        r=json.loads(path.read_text());a=r['answer']
        content=''
        for claim in a['claims']:
            refs=''.join('<details><summary>'+e(c['document_id']+' / '+c['block_id'])+'</summary><blockquote>'+e(c['quote'])+'</blockquote><small>'+e(c['index_id'])+'</small></details>' for c in claim['citations'])
            content+='<p>'+e(claim['text'])+'</p>'+refs
        for name in ('limitations','findings'):
            if a[name]:content+='<h4>'+('限制 / 材料缺失' if name=='limitations' else '核查与修订说明')+'</h4><ul>'+''.join('<li>'+e(s)+'</li>' for s in a[name])+'</ul>'
        content+='<p>停止原因：'+e(a['stop_reason'])+'</p>'
        stages=''.join('<p><a href="'+str(f.relative_to(run))+'">'+e(f.stem)+'</a></p>' for f in sorted(folder.glob('*-output.json')))
        tools=''.join('<p><a href="'+str(f.relative_to(run))+'">'+e(f.stem)+'</a></p>' for f in sorted(folder.glob('tool-*.json')))
        columns.append(f'<div><h3>{mode.upper()} · {e(a["status"])}</h3><small>{r["tool_calls"]} 次工具调用 · {r["elapsed_seconds"]:.1f}s · 输入 {r["input_tokens"]:,} / 输出 {r["output_tokens"]:,} tokens</small><p class="status">{e(r["status"])} · 引用格式错误 {len(r["citation_errors"])}</p>'+content+'<details><summary>阶段结果与操作记录</summary>'+stages+tools+'</details></div>')
        summary.append({'case':case,'mode':mode,**{k:r[k] for k in ('status','tool_calls','elapsed_seconds','input_tokens','output_tokens','citation_errors')}})
    sections.append('<section><h2>'+e(question)+'</h2><div class="columns">'+''.join(columns)+'</div></section>')
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>Single / Team 实测对比</title><style>body{margin:0;padding:24px 4vw;background:#fafbf9;color:#20372b;font:15px/1.7 system-ui}.columns{display:grid;grid-template-columns:1fr 1fr;gap:32px}.columns>div{min-width:0}section{border-top:1px solid #d0d9d1;margin-top:24px;padding-top:12px}h1{font-size:26px}h2{font-size:21px}h3{font-size:17px}small,.status{color:#637769}summary{cursor:pointer;font-size:12px;padding:5px 0;overflow-wrap:anywhere}blockquote{margin:8px 0;border-left:3px solid #92b89c;padding-left:12px}a{color:#167450}pre{white-space:pre-wrap}@media(max-width:800px){.columns{grid-template-columns:1fr}}</style><h1>Single / Agent Team · 真实模型对比</h1><p>'''+e(m['provider']+' / '+m['model'])+'''</p><p>两组模型上下文隔离；Team 为分析→独立核查→修订。候选结果，仍需人工判断正确性。引用校验只验证已读取和逐字匹配，不等于事实正确。AIHubMix 上游路由未锁定，Team 的模型调用预算高于 Single。</p>'''+''.join(sections)+'</html>'
if (run/'costs.html').exists():
    page=page.replace('</h1>', '</h1><p><a href="costs.html">逐次调用费用与汇总 / Call costs</a></p>', 1)
if (run/'REVIEW.md').exists():
    assessment=(run/'REVIEW.md').read_text()
    page=page.replace(''.join(sections), '<section><h2>实测复核 · 非人工验收</h2><pre>'+e(assessment)+'</pre><a href="REVIEW.md">打开复核记录</a></section>'+''.join(sections))
with (run/'review.html').open('x') as f:f.write(page)
with (run/'summary.json').open('x') as f:json.dump(summary,f,ensure_ascii=False,indent=2)
print(json.dumps(summary,ensure_ascii=False))
