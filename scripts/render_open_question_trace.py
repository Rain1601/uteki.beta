"""Supplement the existing comparison with real actions and source links."""
import html
import json
import sys
from pathlib import Path
from uteki.agents.reading.document_reader import DocumentReader

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT/'experiments/analysis_comparison'/(sys.argv[1] if len(sys.argv)>1 else 'open-drivers-gpt54mini-v0.1')
e=html.escape
m=json.loads((RUN/'manifest.json').read_text())
docs={d['id']:d for d in m['documents']}
parts=[]
for mode in ('single','team'):
    folder=RUN/'open_drivers_risks'/mode
    rows=[]
    for file in sorted(folder.glob('tool-*.json')):
        c=json.loads(file.read_text())
        rows.append('<details><summary>'+e(file.stem+' · '+c['stage']+' · '+c['tool'])+'</summary><p>'+e(c['reason'])+'</p><pre>'+e(json.dumps(c['arguments'],ensure_ascii=False,indent=2))+'</pre><a href="'+str(file.relative_to(RUN))+'">完整工具返回</a></details>')
    citations=[]
    result=folder/'result.json'
    if result.exists():
        answer=json.loads(result.read_text())['answer']
        readers={}
        for claim in answer['claims']:
            links=[]
            for c in claim['citations']:
                doc=docs.get(c['document_id'])
                if not doc:continue
                if doc['id'] not in readers:readers[doc['id']]=DocumentReader(ROOT/doc['index_folder'])
                r=readers[doc['id']]
                b=next((b for b in r.blocks if b['block_id']==c['block_id']),None)
                if not b:
                    links.append('<p>未定位引用：'+e(c['block_id'])+'</p>');continue
                url=doc['source_url']+('#'+b['source_anchor'] if b.get('source_anchor') else '')
                links.append('<p><a target="_blank" href="'+e(url)+'">'+e(doc['title']+' · p.'+str(b['reported_page']))+'</a> · '+e(c['block_id'])+'</p><blockquote>'+e(c['quote'])+'</blockquote>')
            citations.append('<section><p>'+e(claim['text'])+'</p>'+''.join(links)+'</section>')
    parts.append('<h2>'+mode.upper()+'</h2><h3>回答与出处</h3>'+''.join(citations)+'<h3>真实操作顺序</h3>'+''.join(rows))
page='''<!doctype html><html lang="zh"><meta charset="utf-8"><title>自主分析 · 证据与调用路径</title><style>body{max-width:1200px;margin:24px auto;padding:0 24px;font:15px/1.7 system-ui;color:#20372b;background:#fafbf9}a{color:#167450}summary{cursor:pointer}details,section{border-top:1px solid #ddd;padding:12px 0}pre{white-space:pre-wrap}blockquote{border-left:3px solid #aaa;margin:8px 0;padding-left:12px}</style><h1>证据与真实操作记录</h1><p><a href="review.html">返回对比结果</a> · <a href="costs.html">逐次费用</a></p><p>操作原因由模型在工具调用时提交，是简短行动说明，不是内部思维链。SEC 链接使用原始锚点，可能只定位所在页。引用匹配不代表推断正确。</p>'''+''.join(parts)+'</html>'
with (RUN/'trace.html').open('x') as f:f.write(page)
review=RUN/'review.html'
review.write_text(review.read_text().replace('</h1>','</h1><p><a href="trace.html">查看真实操作路径与原文出处</a></p>',1))
