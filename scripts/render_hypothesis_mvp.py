"""Verify frozen Codex research and render an answer-first review artifact."""
import gzip
import hashlib
import json
import re
from html import escape as esc
from pathlib import Path
from urllib.parse import quote
from lxml import html

from codex_hypothesis_mvp import ROOT, OUT, STAGES, encoded, digest


def load(path):
    return json.loads(path.read_text())


def rows(block):
    result = {}
    for c in block['table']['cells']:
        result.setdefault(c['row'], []).append(c)
    return [[c['text'] for c in sorted(cs, key=lambda c: c['column']) if c['text'].strip()]
            for _, cs in sorted(result.items())]


def numbers(block, label, occurrence=0):
    row = [r for r in rows(block) if r and r[0] == label][occurrence]
    values = []
    for cell in row[1:]:
        s = cell.replace(',', '').replace('$', '').strip()
        if re.fullmatch(r'\(?-?\d+(\.\d+)?\)?', s):
            values.append(float(s.replace('(', '-').replace(')', '')))
    return values


def dom_element(root, path):
    current = root
    steps = path.strip('/').split('/')
    for step in steps[1:]:
        m = re.fullmatch(r'([^\[]+)(?:\[(\d+)\])?', step)
        current = [c for c in current if isinstance(c.tag, str) and c.tag.lower() == m[1]][int(m[2] or 1) - 1]
    return current


def validate():
    stages, checks, metrics = [], [], []
    last_time = ''
    for i, (key, cutoff, docid) in enumerate(STAGES):
        folder = OUT / key
        a, seal, materials = (load(folder / n) for n in ('answer.json', 'frozen.json', 'materials.json'))
        assert digest((folder / 'answer.json').read_bytes()) == seal['answer_sha256']
        assert seal['frozen_at'] > last_time
        last_time = seal['frozen_at']
        assert materials['material_cutoff'] == cutoff == a['cutoff']
        assert [d['id'] for d in materials['documents']] == [s[2] for s in STAGES[:i+1]]
        assert all(d['filed_at'] <= cutoff for d in materials['documents'])
        assert [h['id'] for h in a['hypotheses']] == ['H1', 'H2', 'H3']
        blocks, logs = {}, []
        assert set(seal['read_hashes']) == {p.name for p in (folder/'reads').glob('*.json')}
        for name, sha in sorted(seal['read_hashes'].items()):
            p = folder / 'reads' / name
            assert digest(p.read_bytes()) == sha
            entry = load(p)
            assert entry['at'] < seal['frozen_at']
            if i:
                assert entry['at'] > load(OUT / STAGES[i-1][0] / 'frozen.json')['frozen_at']
            blocks.update({b['block_id']: b for b in entry['result'].get('blocks', [])})
            logs.append((name, entry))
        doc = next(d for d in materials['documents'] if d['id'] == docid)
        raw = gzip.decompress((ROOT / doc['folder'] / 'source.html.gz').read_bytes())
        assert digest(raw) == materials['indexes'][docid]['source_sha256']
        tree = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
        evidence = load(folder / 'evidence.json')
        byid = {e['id']: e for e in evidence}
        assert len(evidence) == len(a['evidence'])
        for e, original in zip(evidence, a['evidence']):
            assert all(e[k] == v for k, v in original.items())
            b = blocks[e['block_id']]
            assert e['quote'] in b['text']
            assert e['text_hash'] == b['text_hash']
            target = dom_element(tree, b['dom_path'])
            norm = lambda s: re.sub(r'\s+', '', s).casefold()
            assert norm(e['quote']) in norm(target.text_content()), e['id']
        for h in a['hypotheses']:
            assert all(s in byid for s in h['sources'])
        a.update(_doc=doc, _blocks=blocks, _evidence=evidence, _logs=logs, _seal=seal)
        stages.append(a)
        checks.append({'stage': key, 'cutoff': cutoff, 'reads': len(logs),
                       'citations': len(evidence), 'source_sha_verified': True,
                       'quotes_in_original_dom': True, 'frozen_answer_and_read_hashes': True})
    notes = load(OUT/'review-notes.json')
    supplement = notes['supplemental_source']
    supplemental_block = stages[2]['_blocks'][supplement['block_id']]
    assert supplement['quote'] in supplemental_block['text']
    for a in stages:
        prefix = {'annual':'A', 'q1':'B', 'q2':'C'}[a['stage']]
        ev = {e['id']: a['_blocks'][e['block_id']] for e in a['_evidence']}
        rev = ev[prefix + '1']
        seg = ev[prefix + '2']
        cloud, services, search = (numbers(rev, label)[:2] for label in ('Google Cloud','Google Services total','Google Search & other'))
        profit = numbers(seg, 'Google Cloud', 0 if prefix == 'A' else 1)[:2]
        cash = ev[prefix + '8']
        cfo = numbers(cash, 'Net cash provided by operating activities')
        capex = [abs(n) for n in numbers(cash, 'Purchases of property and equipment')]
        if prefix == 'A':
            cfo, capex = cfo[-2:], capex[-2:]
        fcf = [x-y for x,y in zip(cfo,capex)]
        metrics.append({'stage': a['stage'], 'unit': 'USD million',
            'revenue_period': 'FY2024 / FY2025' if prefix=='A' else ('Q1 2025 / Q1 2026' if prefix=='B' else 'Q2 2025 / Q2 2026'),
            'cash_period': 'FY2024 / FY2025' if prefix=='A' else ('Q1 2025 / Q1 2026' if prefix=='B' else 'H1 2025 / H1 2026'),
            'cloud_revenue': cloud, 'services_revenue': services, 'search_revenue': search,
            'cloud_profit': profit, 'operating_cash': cfo, 'purchases_of_ppe':capex, 'simplified_fcf':fcf,
            'cloud_growth_pct':(cloud[1]/cloud[0]-1)*100,
            'services_growth_pct':(services[1]/services[0]-1)*100,
            'search_growth_pct':(search[1]/search[0]-1)*100,
            'cloud_margin_pct':[p/r*100 for p,r in zip(profit,cloud)],
            'fcf_growth_pct':(fcf[1]/fcf[0]-1)*100,
            'formulas': {'growth':'(current / prior - 1) * 100', 'margin':'segment operating profit / segment revenue * 100', 'simplified_fcf':'operating cash - purchases of property and equipment'},
            'sources':[prefix+'1',prefix+'2',prefix+'8']})
    validation = {'status':'mechanical_checks_passed_not_research_approval', 'stages':checks,
                  'precision_corrections': notes['notes'], 'supplemental_read_citation': supplement,
                  'external_api_calls':0,'codex_cost_usd':None,
                  'limitations':['No independent judge','No price or valuation result','Not blind','No product Agent reproducibility claim']}
    (OUT/'metrics.json').write_bytes(encoded(metrics))
    (OUT/'validation.json').write_bytes(encoded(validation))
    return stages, metrics, validation


def source_link(a, e):
    d = a['_doc']
    version = Path(d['index_folder']).name
    return f"/companies/alphabet/documents/{d['accession']}/indexes/{version}/source#{quote(e['block_id'])}"


def render(stages, metrics, validation, annual_only=False):
    if annual_only:
        stages = [dict(a) for a in stages if a['stage'] == 'annual']
        metrics = [m for m in metrics if m['stage'] == 'annual']
        stages[0]['title'] = '核心判断：Cloud 有望增加利润贡献，但仍依赖搜索业务保持盈利能力'
        stages[0]['summary'] = ('基于 2025 年报，我们的初步判断是：Google Cloud 如果继续扩大收入并提高营业利润率，'
            '有望成为 Alphabet 未来利润增长的重要来源。这个判断成立，需要搜索和广告业务保持盈利能力，'
            '同时新增 AI 投入最终带来足够的现金回报。年报支持这一研究方向，但还不足以证明长期回报已经实现，'
            '也不足以判断当前股价是否便宜。')
        titles = {'H1':'Cloud：收入增长能否持续转化为更多利润？',
                  'H2':'搜索：AI 改变使用方式后，广告盈利能力能否保持？',
                  'H3':'现金回报：增加的利润能否覆盖 AI 投资支出？'}
        stages[0]['hypotheses'] = [dict(h, title=titles[h['id']]) for h in stages[0]['hypotheses']]
    labels = {'annual':'2025 10-K','q1':'2026 Q1','q2':'2026 Q2'}
    data = {}
    def sources(a, ids):
        ev = {e['id']: e for e in a['_evidence']}
        links = []
        for identity in ids:
            e = ev[identity]
            links.append(f'<a class="hm-evidence" href="{source_link(a,e)}" data-evidence="{identity}">{esc(e["label"])} <small>[{labels[a["stage"]]}]</small></a>')
        first, rest = links[:3], links[3:]
        return '<div class="hm-sources">'+ '； '.join(first) + (f'<details><summary>展开更多 / More ({len(rest)})</summary>{"； ".join(rest)}</details>' if rest else '') + '</div>'
    pieces = []
    for a in stages:
        key = a['stage']
        for e in a['_evidence']:
            data[e['id']] = {'label': e['label'], 'quote': e['quote'], 'url':source_link(a,e),
                             'document':labels[key], 'page':e['reported_page']}
        parts = [f'<section id="{key}" class="hm-stage"><p class="hm-stage-date">{labels[key]} · 材料截止 {a["cutoff"]}</p><h2>{esc(a["title"])}</h2><p class="hm-summary">{esc(a["summary"])}</p>']
        if a.get('business'):
            parts.append(f'<p>{esc(a["business"])}</p>')
        for h in a['hypotheses']:
            judgment = h['judgment']
            correction = ''
            if key == 'annual' and h['id'] == 'H1':
                judgment = judgment.replace('23.70%', '23.69%')
                correction = '<p class="hm-note">计算复核：冻结原稿的 23.70% 校正为 23.69%，不改变判断。<a href="review-notes.json">保留校正记录 / Correction log</a></p>'
            parts.append(f'<article id="{key}-{h["id"]}" class="hm-hypothesis"><h3>{esc(h["title"])}</h3><p class="hm-state">{esc(h["status"])}</p><p>{esc(judgment)}</p>{correction}{sources(a,h["sources"])}')
            fields = [('mechanism','为什么 / Rationale'),('change','改变了什么 / What changed'),('test','如何验证 / Test'),('falsifier','什么会推翻它 / Disconfirmation'),('next','下次看什么 / Next'),('unknown','仍然不知道 / Unknown')]
            for field, label in fields:
                if h.get(field):
                    parts.append(f'<p><b>{label}</b><br>{esc(h[field])}</p>')
            parts.append('</article>')
        if a.get('discovery'):
            parts.append(f'<aside class="hm-discovery"><h3>新增发现 / New findings</h3><p>{esc(a["discovery"])}</p>{sources(a,a["discovery_sources"])}</aside>')
            if key == 'q2':
                e = load(OUT/'review-notes.json')['supplemental_source']
                data['C11'] = dict(e, url=source_link(a,e),document=labels[key],page=a['_blocks'][e['block_id']]['reported_page'])
                parts.append(f'<p class="hm-sources"><a data-evidence="C11" href="{source_link(a,e)}">{esc(e["label"])} [2026 Q2]</a></p>')
        parts.append(f'<p class="hm-limit"><b>价格与价值 / Price & value</b><br>{esc(a["valuation"])}</p>')
        parts.append('<details class="hm-audit"><summary>边界、出处与真实读取记录 / Audit trail</summary><ul>'+''.join(f'<li>{esc(x)}</li>' for x in a['limitations'])+'</ul>')
        parts.append(f'<p><a href="{key}/answer.json">阶段结果 JSON</a> · <a href="{key}/materials.json">固定材料</a> · <a href="{key}/frozen.json">冻结记录</a> · <a href="{key}/evidence.json">全部引用</a></p><ol>')
        for name, log in a['_logs']:
            arg = log['arguments']
            description = arg.get('query') or arg.get('block') or 'Document → Part → Item'
            parts.append(f'<li><a href="{key}/reads/{name}">{esc(log["operation"])} · {esc(description)}</a></li>')
        parts.append('</ol></details></section>')
        pieces.append(''.join(parts))
    matrix = '<div class="hm-table-wrap"><table><caption>经营观察，不是投资绩效 / Operating observations</caption><thead><tr><th>指标</th>'+''.join(f'<th>{labels[m["stage"]]}</th>' for m in metrics)+'</tr></thead><tbody>'
    for label, field, fmt in [('Google Cloud 收入同比','cloud_growth_pct','{:.2f}%'),('Google Services 收入同比','services_growth_pct','{:.2f}%'),('↳ 其中：Search & other 收入同比','search_growth_pct','{:.2f}%'),('Cloud 当期营业利润率','cloud_margin_pct','{:.2f}%'),('简化 FCF 同比','fcf_growth_pct','{:.2f}%')]:
        matrix += '<tr><th>'+label+'</th>'
        for m in metrics:
            value=m[field][-1] if isinstance(m[field],list) else m[field]
            prefix={'annual':'A','q1':'B','q2':'C'}[m['stage']]
            eid=prefix+('8' if field=='fcf_growth_pct' else '2' if field=='cloud_margin_pct' else '1')
            sign='hm-positive' if value>0 else 'hm-negative' if value<0 else 'hm-neutral'
            shown=('+' if value>0 and field.endswith('growth_pct') else '')+fmt.format(value)
            matrix += f'<td><a class="{sign}" data-evidence="{eid}" href="{data[eid]["url"]}">{shown}</a></td>'
        matrix += '</tr>'
    matrix += '</tbody></table></div><p class="hm-note">收入和利润：全年 / Q1 单季 / Q2 单季，各对各自去年同期。现金：全年 / Q1 / 上半年，不能横向视为同一期间。<a href="metrics.json">查看取数与公式 / Calculations</a></p>'
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Alphabet · 假设如何被后续证据改变</title><style>
    .hm{--ink:#233249;--muted:#65758b;--blue:#285db0;--soft:#f2f6fb;--line:#dde5ef;margin:0;background:#fff;color:var(--ink);font:16px/1.8 'Avenir Next','PingFang SC','Microsoft YaHei',sans-serif}
    .hm .hm-header{padding:18px 5vw;display:flex;justify-content:space-between;gap:20px;font-size:14px}
    .hm a{color:var(--blue);text-decoration-thickness:1px;text-underline-offset:4px}.hm a:focus-visible,.hm button:focus-visible,.hm summary:focus-visible{outline:3px solid #77a2e4;outline-offset:4px}
    .hm .hm-nav{position:sticky;top:0;z-index:4;background:rgba(255,255,255,.97);padding:14px 5vw;display:flex;gap:24px;border-bottom:1px solid var(--line);overflow:auto;white-space:nowrap}
    .hm .hm-main{max-width:1080px;margin:0 auto;padding:36px 32px 100px}.hm h1{font-size:36px;line-height:1.35;letter-spacing:-.8px;margin:10px 0 20px}.hm h2{font-size:27px;line-height:1.5;margin:8px 0 20px}.hm h3{font-size:21px;line-height:1.5;margin:0 0 10px}.hm p{max-width:850px;margin:14px 0}.hm .hm-intro{font-size:20px}
    .hm .hm-note,.hm .hm-stage-date{color:var(--muted);font-size:14px}.hm .hm-stage{padding-top:52px;margin-top:36px;scroll-margin-top:60px;border-top:1px solid var(--line)}.hm .hm-summary{font-size:18px}.hm .hm-hypothesis{padding-top:30px;margin-top:16px;scroll-margin-top:90px}.hm .hm-state{color:#315e80;font-size:14px;margin:0 0 12px}.hm .hm-sources{max-width:850px;font-size:14px;line-height:2;color:var(--muted)}.hm .hm-sources a{display:inline}.hm small{color:var(--muted)}.hm details{margin:12px 0}.hm summary{cursor:pointer;color:var(--blue)}.hm .hm-hypothesis b,.hm .hm-limit b{font-size:14px;color:var(--muted)}
    .hm .hm-discovery{background:var(--soft);padding:24px 28px;margin-top:36px}.hm .hm-limit{padding-top:24px}.hm .hm-table-wrap{overflow:auto;margin-top:26px}.hm table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;text-align:left}.hm caption{text-align:left;font-size:15px;color:var(--muted);padding-bottom:12px}.hm td,.hm th{padding:12px 14px;border-bottom:1px solid var(--line);font-size:15px}.hm th{font-weight:600}.hm .hm-audit{padding:16px 0;font-size:14px}.hm .hm-audit ol{columns:2;word-break:break-word}.hm .hm-audit li{margin:6px 0}
    .hm .hm-drawer{padding:0;width:min(1000px,94vw);max-width:none;height:90vh;border:1px solid var(--line);border-radius:10px;color:var(--ink);box-shadow:0 20px 70px #23324933}.hm .hm-drawer::backdrop{background:#23324955}.hm .hm-drawer-bar{padding:18px 22px;display:flex;gap:18px;align-items:start;justify-content:space-between}.hm .hm-drawer-bar p{font-size:14px;margin:4px 0}.hm .hm-drawer button{background:#fff;border:1px solid var(--line);padding:8px 16px;border-radius:6px;cursor:pointer;white-space:nowrap}.hm iframe{border:0;border-top:1px solid var(--line);width:100%;height:calc(100% - 150px)}
    @media(max-width:650px){.hm .hm-main{padding:22px 20px 60px}.hm h1{font-size:28px}.hm h2{font-size:23px}.hm .hm-nav{gap:18px;padding:12px 20px}.hm .hm-header{padding:16px 20px}.hm .hm-audit ol{columns:1}.hm .hm-discovery{padding:18px}.hm td,.hm th{white-space:nowrap;padding:10px}.hm .hm-drawer-bar{padding:12px}.hm iframe{height:65vh}}
    @media(prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}.hm .hm-drawer[open]{animation:hm-open .16s ease-out}@keyframes hm-open{from{opacity:.5;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}}
    </style></head><body class="hm"><header class="hm-header"><a href="/companies/alphabet?tab=research">Uteki / Alphabet</a><span>Codex 研究实验 v0.1 · 待审核 / Pending review</span></header><nav class="hm-nav" aria-label="阶段导航"><a href="#overview">总览 / Overview</a><a href="#annual">初始判断 / 10-K</a><a href="#q1">第一次验证 / Q1</a><a href="#q2">第二次验证 / Q2</a><a href="#review">审核 / Review</a></nav><main class="hm-main"><section id="overview"><h1>不是看它涨了没有，<br>而是看我们的判断改变了什么。</h1><p class="hm-intro">Alphabet 的三阶段研究：云的利润贡献上升，搜索仍具韧性，但现金转化与业务构成变化让结论更有条件。</p><p class="hm-note">以 FY2025 10-K 建立判断，依次开放 2026 Q1、Q2。本轮由 Codex 实际阅读本地材料并撰写，不是产品 Single/Team 的运行结果，也不是历史盲测。研究正文为中文；证据原文保持英文。价格与估值尚未验证。</p>__MATRIX__</section>__STAGES__<section id="review" class="hm-stage"><h2>我们现在可以 review 什么？</h2><p>先审假设是否有意义、是否真的可能被推翻；再审证据是否支持推断；最后看新信息是否让判断发生了合理变化。不要因为结论符合偏好，就把它当作正确答案。</p><p>本轮刻意不输出“3/3 通过”或投资准确率：Cloud 的财务现象获得支持，但 AI 因果归因仍不完整；搜索收入增长不足以证明护城河；现金受压也不等于长期投资失败。</p><p><a href="README.md">实验方法 / Protocol</a> · <a href="validation.json">自动校验 / Validation</a> · <a href="metrics.json">计算记录 / Calculations</a></p><p class="hm-note">外部模型 API 调用 0 次；Codex 会话成本未知，不计为零。自动校验仅覆盖冻结记录、材料边界、原文定位和取数；不构成人工采纳，也未修改任何公司档案。</p></section></main><dialog class="hm-drawer" aria-labelledby="hm-source-title"><div class="hm-drawer-bar"><div><strong id="hm-source-title"></strong><p id="hm-quote"></p><a id="hm-open-source" target="_blank" rel="noopener">打开原文 / Open source</a></div><button id="hm-close">关闭 / Close</button></div><iframe title="原始 SEC 文档 / SEC source" id="hm-source-frame"></iframe></dialog><script>
    const evidence=__DATA__,drawer=document.querySelector('.hm-drawer'),frame=document.getElementById('hm-source-frame');let previous=null;
    document.querySelectorAll('[data-evidence]').forEach(a=>a.addEventListener('click',event=>{if(event.ctrlKey||event.metaKey||event.shiftKey)return;event.preventDefault();const e=evidence[a.dataset.evidence];previous=a;document.getElementById('hm-source-title').textContent=e.label+' ['+e.document+'] p.'+e.page;document.getElementById('hm-quote').textContent=e.quote;document.getElementById('hm-open-source').href=e.url;frame.src=e.url;drawer.showModal()}));
    document.getElementById('hm-close').onclick=()=>drawer.close();drawer.addEventListener('close',()=>{frame.src='about:blank';previous?.focus()});
    </script></body></html>'''
    page = page.replace('不是看它涨了没有，<br>而是看我们的判断改变了什么。', '云的利润贡献上升，<br>现金回报仍待兑现。')
    page = page.replace('</style>', '.hm section{scroll-margin-top:76px}</style>', 1)
    page = page.replace('</style>', '.hm a.hm-positive{color:#089981}.hm a.hm-negative{color:#f23645}.hm a.hm-neutral{color:#65758b}</style>', 1)
    if annual_only:
        page = re.sub(r'<nav class="hm-nav".*?</nav>', '<nav class="hm-nav" aria-label="报告导航"><a href="#annual">核心判断 / Thesis</a><a href="#annual-H1">Cloud</a><a href="#annual-H2">搜索 / Search</a><a href="#annual-H3">现金回报 / Cash return</a><a href="#annual-metrics">年报数据 / Metrics</a></nav>', page, count=1)
        page = re.sub(r'<section id="overview">.*?__MATRIX__</section>', '<section id="overview"><h1>Alphabet · 2025 年报研究</h1><p class="hm-note">仅依据 FY2025 10-K，材料截止 2026-02-05。初始研究的阅读整理版，尚待人工审核；未重新调用模型，未引入后续季度信息。<a href="annual/answer.json">保留原始研究结果</a></p></section>', page, count=1)
        page = re.sub(r'<section id="review".*?</section>', '<section id="annual-metrics" class="hm-stage"><h2>支撑判断的年报数据 / Annual metrics</h2>__MATRIX__<p class="hm-note">Google Cloud 与 Google Services 是不同分部；Search &amp; other 属于 Services 内的 Google advertising，不是第三个并列分部。单独观察搜索，是为了检验主要广告收入来源是否保持增长；不能与 Services 相加。</p><p class="hm-note">正数绿色、负数红色，只表示数值方向，不代表投资判断。利润率是当期水平，不是同比变化。简化 FCF = 经营现金流 − 购建固定资产支出。</p></section>', page, count=1)
        matrix = matrix.split('</tbody></table></div>')[0]+'</tbody></table></div><p class="hm-note">同比比较 2025 全年与 2024 全年；均来自本份年报。点击数值查看原始表格。</p>'
        page = page.replace('<title>Alphabet · 假设如何被后续证据改变</title>', '<title>Alphabet · 2025 年报初始研究</title>')
        page = page.replace('Codex 研究实验 v0.1 · 待审核 / Pending review','10-K 初始报告 · 待审核 / Pending review')
    page = page.replace('__MATRIX__',matrix).replace('__STAGES__',''.join(pieces)).replace('__DATA__',json.dumps(data,ensure_ascii=False).replace('</','<\\/'))
    if annual_only:
        from annual_report_editorial import restyle_annual
        page = restyle_annual(page, stages[0], metrics[0], data)
    return page


if __name__ == '__main__':
    stages, metrics, validation = validate()
    (OUT/'review.html').write_text(render(stages,metrics,validation))
    (OUT/'annual-report.html').write_text(render(stages,metrics,validation,annual_only=True))
    print(json.dumps(validation,ensure_ascii=False,indent=2))
