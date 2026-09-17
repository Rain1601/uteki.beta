from __future__ import annotations

import html
import json
from apps.review_workbench.visual_system import workbench_page


ATTENTION = {
    "core": ("Core", "重点"),
    "active": ("Active", "关注"),
    "context": ("Control", "对照"),
}

HOLDING = {
    "held": ("Held", "已持仓"),
    "not_held": ("Not held", "未持仓"),
    "unknown": ("Unconfirmed", "待确认"),
}


def esc(value: object) -> str:
    return html.escape(str(value))


def bilingual(en: object, zh: object) -> str:
    return f"<span data-lang='en'>{esc(en)}</span><span data-lang='zh'>{esc(zh)}</span>"


def validate_company_universe(data: dict) -> None:
    themes = {item["id"]: item for item in data["themes"]}
    company_ids = [item["id"] for item in data["companies"]]
    tickers = [item["ticker"] for item in data["companies"]]
    if len(company_ids) != len(set(company_ids)):
        raise ValueError("company ids must be unique")
    if len(tickers) != len(set(tickers)):
        raise ValueError("company tickers must be unique")
    if len(data["companies"]) != data["selection_policy"]["target_count"]:
        raise ValueError("company count does not match selection target")

    counts = {theme_id: 0 for theme_id in themes}
    for company in data["companies"]:
        if company["theme_id"] not in themes:
            raise ValueError(f"unknown theme for {company['id']}")
        if "sp500" not in company["indices"]:
            raise ValueError(f"company is outside the declared S&P 500 universe: {company['id']}")
        if company["attention"] not in ATTENTION:
            raise ValueError(f"unknown attention level for {company['id']}")
        if company["holding"] not in HOLDING:
            raise ValueError(f"unknown holding state for {company['id']}")
        counts[company["theme_id"]] += 1

    for theme_id, count in counts.items():
        if not 3 <= count <= 5:
            raise ValueError(f"theme {theme_id} must contain 3 to 5 companies")


def _company_row(company: dict, theme: dict) -> str:
    searchable = " ".join(
        [
            company["ticker"],
            company["name"],
            company["sector"],
            theme["label_en"],
            theme["label_zh"],
            *company["tags"],
        ]
    ).lower()
    index_badges = "".join(
        f"<span class='index-tag {'ndx' if value == 'nasdaq100' else ''}'>{'Nasdaq-100' if value == 'nasdaq100' else 'S&P 500'}</span>"
        for value in company["indices"]
    )
    tags = "".join(f"<span class='topic'>{esc(tag)}</span>" for tag in company["tags"])
    attention_en, attention_zh = ATTENTION[company["attention"]]
    holding_en, holding_zh = HOLDING[company["holding"]]
    destination = (
        f"<a class='research-link ready' href='/companies/{esc(company['id'])}'>{bilingual('Open company', '进入公司')} →</a>"
    )
    return f"""<tr class='company-row' data-theme='{esc(company['theme_id'])}' data-index='{esc(' '.join(company['indices']))}' data-attention='{esc(company['attention'])}' data-holding='{esc(company['holding'])}' data-search='{esc(searchable)}'>
      <td class='company-cell'><span class='ticker'>{esc(company['ticker'])}</span><span><strong><a href='/companies/{esc(company['id'])}'>{esc(company['name'])}</a></strong><small>{esc(company['sector'])}</small></span></td>
      <td><span class='theme-name'>{bilingual(theme['label_en'], theme['label_zh'])}</span><span class='topics'>{tags}</span></td>
      <td class='indices'>{index_badges}</td>
      <td><span class='attention {esc(company['attention'])}'><i></i>{bilingual(attention_en, attention_zh)}</span></td>
      <td><span class='holding {esc(company['holding'])}'>{bilingual(holding_en, holding_zh)}</span></td>
      <td class='action'>{destination}</td>
    </tr>"""


@workbench_page('companies')
def render_company_universe_page(data: dict) -> str:
    validate_company_universe(data)
    themes = sorted(data["themes"], key=lambda item: item["order"])
    theme_by_id = {item["id"]: item for item in themes}
    theme_counts = {
        item["id"]: sum(company["theme_id"] == item["id"] for company in data["companies"])
        for item in themes
    }

    tech_count = sum(
        theme_by_id[item["theme_id"]]["group"] == "technology"
        for item in data["companies"]
    )
    core_count = sum(item["attention"] == "core" for item in data["companies"])
    ndx_count = sum("nasdaq100" in item["indices"] for item in data["companies"])
    theme_buttons = "".join(
        f"<button type='button' data-filter='theme' data-value='{esc(item['id'])}'>{bilingual(item['label_en'], item['label_zh'])}<b>{theme_counts[item['id']]}</b></button>"
        for item in themes
    )
    attention_order = {"core": 0, "active": 1, "context": 2}
    companies = sorted(
        data["companies"],
        key=lambda item: (attention_order[item["attention"]], item["name"].casefold()),
    )
    rows = [_company_row(item, theme_by_id[item["theme_id"]]) for item in companies]

    source_links = " · ".join(
        f"<a href='{esc(item['url'])}' target='_blank' rel='noreferrer'>{esc(item['label'])} {esc(item['as_of'])}</a>"
        for item in data["sources"]
    )
    payload = json.dumps(
        {
            "total": len(data["companies"]),
            "page_size": 20,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    return f"""<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Uteki · Company Universe</title>
<style>
:root{{--ink:#1f2420;--muted:#717a73;--line:#dfe4df;--paper:#fff;--wash:#f6f8f5;--green:#1d6548;--green-soft:#eaf3ed;--blue:#315f93;--amber:#9a6a13}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--wash);color:var(--ink);font:13px/1.45 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}button,input,select{{font:inherit}}a{{color:inherit}}.topbar{{position:sticky;top:0;z-index:20;height:54px;display:flex;align-items:center;gap:22px;padding:0 24px;background:#fffffff2;border-bottom:1px solid var(--line);backdrop-filter:blur(12px)}}.brand{{font-weight:760;letter-spacing:-.01em}}.brand i{{font-style:normal;color:var(--green)}}.nav{{display:flex;gap:5px}}.nav a{{padding:5px 8px;color:var(--muted);text-decoration:none;border-radius:4px;font-size:11px}}.nav a.active,.nav a:hover{{background:var(--green-soft);color:var(--green)}}.candidate{{padding:3px 6px;background:#fff5d9;color:var(--amber);border-radius:4px;font-size:9px}}.lang{{margin-left:auto;display:flex}}.lang button{{border:0;background:none;padding:4px;color:var(--muted);cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}main{{max-width:1440px;margin:auto;padding:38px 34px 90px}}.hero{{display:grid;grid-template-columns:minmax(480px,1fr) auto;align-items:end;gap:30px;padding-bottom:27px;border-bottom:1px solid var(--line)}}.eyebrow{{font:700 9px ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:var(--green)}}h1{{margin:5px 0 9px;font:500 34px/1.2 Georgia,"Songti SC",serif}}.hero p{{max-width:680px;margin:0;color:var(--muted)}}.metrics{{display:flex;gap:25px}}.metric{{min-width:72px}}.metric b{{display:block;font:500 25px/1 ui-monospace,monospace}}.metric span{{font-size:9px;color:var(--muted)}}.controls{{position:sticky;top:54px;z-index:15;padding:15px 0 13px;background:linear-gradient(var(--wash) 85%,transparent)}}.primary-controls{{display:flex;align-items:center;gap:12px}}.search{{position:relative;flex:1;max-width:430px}}.search input{{width:100%;height:36px;padding:0 12px 0 34px;border:1px solid #cdd4ce;border-radius:5px;background:#fff;outline:none}}.search input:focus{{border-color:#77a18b;box-shadow:0 0 0 3px #dcebe2}}.search:before{{content:'⌕';position:absolute;left:12px;top:6px;color:var(--muted);font-size:16px}}.filter-group{{display:flex;align-items:center;padding:2px;border:1px solid var(--line);border-radius:5px;background:#eef1ed}}.filter-group button{{height:30px;border:0;background:transparent;padding:0 9px;color:var(--muted);font-size:10px;cursor:pointer;border-radius:3px}}.filter-group button.on{{background:#fff;color:var(--ink);font-weight:650;box-shadow:0 1px 2px #0001}}.holding-select{{height:36px;border:1px solid var(--line);border-radius:5px;background:#fff;padding:0 28px 0 10px;color:var(--ink)}}.result-count{{margin-left:auto;color:var(--muted);font-size:10px;white-space:nowrap}}.theme-filters{{display:flex;gap:6px;margin-top:9px;overflow:auto;padding-bottom:2px}}.theme-filters button{{flex:none;border:1px solid var(--line);background:#fff;color:var(--muted);padding:5px 8px;border-radius:4px;font-size:9px;cursor:pointer}}.theme-filters button b{{margin-left:6px;color:#9ba19c}}.theme-filters button.on{{border-color:#77a18b;background:var(--green-soft);color:var(--green)}}.table-shell{{border-top:1px solid #bac3bb;border-bottom:1px solid var(--line);background:#fff}}table{{width:100%;border-collapse:collapse;table-layout:fixed}}thead th{{position:sticky;top:145px;z-index:10;height:34px;padding:0 12px;background:#f2f4f1;border-bottom:1px solid var(--line);color:var(--muted);font-size:9px;font-weight:650;text-align:left;text-transform:uppercase;letter-spacing:.04em}}thead th:nth-child(1){{width:24%}}thead th:nth-child(2){{width:27%}}thead th:nth-child(3){{width:16%}}thead th:nth-child(4){{width:10%}}thead th:nth-child(5){{width:10%}}thead th:nth-child(6){{width:13%}}td{{padding:9px 12px;border-bottom:1px solid #edf0ed;vertical-align:middle}}.company-row:hover td{{background:#fafcf9}}.company-cell{{display:flex;align-items:center;gap:11px}}.ticker{{display:flex;align-items:center;justify-content:center;width:48px;height:27px;background:#f0f3f0;border-radius:3px;font:700 10px ui-monospace,monospace;color:#39413b}}.company-cell strong,.company-cell small{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.company-cell strong{{font-weight:650}}.company-cell small{{font-size:9px;color:var(--muted);margin-top:1px}}.theme-name{{display:block;font-size:10px;color:#37443c}}.topics{{display:flex;gap:4px;margin-top:3px;overflow:hidden}}.topic{{white-space:nowrap;font-size:8px;color:#7b837c}}.topic+ .topic:before{{content:'·';margin-right:4px}}.indices{{white-space:nowrap}}.index-tag{{display:inline-block;padding:2px 5px;margin-right:4px;border:1px solid #d8ddd8;border-radius:3px;color:#69716b;font-size:8px}}.index-tag.ndx{{border-color:#cbd9e9;color:var(--blue);background:#f3f7fb}}.attention{{display:inline-flex;align-items:center;gap:5px;font-size:9px;color:var(--muted)}}.attention i{{width:6px;height:6px;border-radius:50%;background:#aab0ab}}.attention.core{{color:var(--green);font-weight:650}}.attention.core i{{background:var(--green)}}.attention.active i{{background:#7b9f8d}}.holding{{font-size:9px;color:var(--muted)}}.action{{text-align:right}}.research-link{{font-size:9px;color:#a2a8a3;text-decoration:none}}.research-link.ready{{color:var(--green);font-weight:650}}.empty{{display:none;padding:70px 20px;text-align:center;color:var(--muted);background:#fff}}.pagination{{display:flex;align-items:center;justify-content:flex-end;gap:8px;padding:11px 12px;border-top:1px solid var(--line);background:#fafbf9}}.pagination button{{height:28px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--ink);padding:0 10px;font-size:9px;cursor:pointer}}.pagination button:disabled{{color:#b2b8b3;background:#f4f5f3;cursor:default}}.pagination span{{min-width:72px;text-align:center;color:var(--muted);font-size:9px}}.pagination select{{height:28px;border:1px solid var(--line);border-radius:4px;background:#fff;color:var(--ink);padding:0 24px 0 8px;font-size:9px}}footer{{display:flex;justify-content:space-between;gap:20px;padding-top:14px;color:var(--muted);font-size:9px}}footer a{{color:var(--green);text-decoration:none}}@media(max-width:980px){{main{{padding:25px 14px 70px}}.hero{{display:block}}.metrics{{margin-top:22px}}.primary-controls{{flex-wrap:wrap}}.result-count{{margin-left:0}}.table-shell{{overflow:auto}}table{{min-width:920px}}thead th{{top:190px}}.nav{{display:none}}}}
</style></head><body>
<header class='topbar'><div class='brand'><i>Uteki</i> / Research</div><nav class='nav'><a class='active' href='/companies'>{bilingual('Companies','公司')}</a></nav><span class='candidate'>Candidate v0.1</span><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>
<main><section class='hero'><div><div class='eyebrow'>Research universe · S&P 500</div><h1>{bilingual('Landmark companies, deliberately selected.','公司观察池')}</h1><p>{bilingual(data['selection_policy']['note_en'],data['selection_policy']['note_zh'])} {bilingual('Technology is the research core; payments, industrials, healthcare, consumer, and energy provide comparison baselines.','以科技产业为研究核心，并保留支付、工业、医疗、消费和能源作为对照。')}</p></div><div class='metrics'><div class='metric'><b>{len(data['companies'])}</b><span>{bilingual('companies','家公司')}</span></div><div class='metric'><b>{len(themes)}</b><span>{bilingual('themes','个行业主题')}</span></div><div class='metric'><b>{tech_count}</b><span>{bilingual('technology core','科技核心')}</span></div><div class='metric'><b>{core_count}</b><span>{bilingual('high attention','重点关注')}</span></div></div></section>
<section class='controls'><div class='primary-controls'><label class='search'><input id='search' type='search' data-placeholder-en='Search company, ticker, or tag' data-placeholder-zh='搜索公司、代码或标签' placeholder='搜索公司、代码或标签' autocomplete='off'></label><div class='filter-group' data-group='index'><button class='on' data-filter='index' data-value='all'>{bilingual('All indices','全部指数')}</button><button data-filter='index' data-value='sp500'>S&amp;P 500</button><button data-filter='index' data-value='nasdaq100'>Nasdaq-100</button></div><div class='filter-group' data-group='attention'><button class='on' data-filter='attention' data-value='all'>{bilingual('All focus','全部关注度')}</button><button data-filter='attention' data-value='core'>{bilingual('Core','重点')}</button><button data-filter='attention' data-value='active'>{bilingual('Active','关注')}</button><button data-filter='attention' data-value='context'>{bilingual('Control','对照')}</button></div><select id='holding' class='holding-select'><option value='all' data-en='All holdings' data-zh='全部持仓'>全部持仓</option><option value='held' data-en='Held' data-zh='已持仓'>已持仓</option><option value='not_held' data-en='Not held' data-zh='未持仓'>未持仓</option><option value='unknown' data-en='Unconfirmed' data-zh='待确认'>待确认</option></select><span id='result-count' class='result-count'></span></div><div class='theme-filters'><button class='on' data-filter='theme' data-value='all'>{bilingual('All themes','全部行业')}<b>{len(data['companies'])}</b></button>{theme_buttons}</div></section>
<section class='table-shell'><table><thead><tr><th>{bilingual('Company','公司')}</th><th>{bilingual('Research theme','行业主题')}</th><th>{bilingual('Index','指数')}</th><th>{bilingual('Attention','关注度')}</th><th>{bilingual('Holding','持仓')}</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table><div class='empty'>{bilingual('No companies match these filters.','没有符合当前条件的公司。')}</div><div class='pagination'><select id='page-size' aria-label='Page size'><option value='10' data-en='10 / page' data-zh='10 / 页'>10 / 页</option><option value='20' data-en='20 / page' data-zh='20 / 页' selected>20 / 页</option><option value='50' data-en='50 / page' data-zh='50 / 页'>50 / 页</option></select><button id='previous' type='button' data-en='Previous' data-zh='上一页'>上一页</button><span id='page-label'></span><button id='next' type='button' data-en='Next' data-zh='下一页'>下一页</button></div></section>
<footer><span>{bilingual('Membership labels are point-in-time snapshots and will be versioned.','指数标签是时点快照，后续变更将通过版本记录。')} · {source_links}</span><span>Nasdaq-100 {data['sources'][1]['as_of']} · {ndx_count} / {len(data['companies'])}</span></footer></main>
<script>const META={payload};const state={{index:'all',attention:'all',theme:'all',holding:'all',query:'',page:1,pageSize:META.page_size}};const body=document.body;const rows=Array.from(document.querySelectorAll('.company-row'));function language(value){{body.classList.toggle('zh',value==='zh');document.querySelectorAll('.lang button').forEach(button=>button.classList.toggle('on',button.id===value));document.querySelectorAll('#holding option,#page-size option').forEach(option=>option.textContent=option.dataset[value]);const search=document.getElementById('search');search.placeholder=search.dataset[`placeholder${{value==='zh'?'Zh':'En'}}`];for(const id of ['previous','next']){{const button=document.getElementById(id);button.textContent=button.dataset[value]}}localStorage.setItem('uteki-lang',value);render()}}function matches(row){{return (state.index==='all'||row.dataset.index.split(' ').includes(state.index))&&(state.attention==='all'||row.dataset.attention===state.attention)&&(state.theme==='all'||row.dataset.theme===state.theme)&&(state.holding==='all'||row.dataset.holding===state.holding)&&(!state.query||row.dataset.search.includes(state.query))}}function render(){{const matched=rows.filter(matches);const pages=Math.max(1,Math.ceil(matched.length/state.pageSize));state.page=Math.min(state.page,pages);const start=(state.page-1)*state.pageSize;const end=Math.min(start+state.pageSize,matched.length);rows.forEach(row=>row.hidden=true);matched.slice(start,end).forEach(row=>row.hidden=false);document.querySelector('.empty').style.display=matched.length?'none':'block';const zh=body.classList.contains('zh');document.getElementById('result-count').textContent=matched.length?`${{zh?'当前显示':'Showing'}} ${{start+1}}–${{end}} / ${{matched.length}}`:`${{zh?'当前显示':'Showing'}} 0 / 0`;document.getElementById('page-label').textContent=`${{zh?'第':'Page'}} ${{state.page}} / ${{pages}}${{zh?' 页':''}}`;document.getElementById('previous').disabled=state.page===1;document.getElementById('next').disabled=state.page===pages}}function resetAndRender(){{state.page=1;render()}}document.querySelectorAll('button[data-filter]').forEach(button=>button.onclick=()=>{{const key=button.dataset.filter;state[key]=button.dataset.value;document.querySelectorAll(`button[data-filter="${{key}}"]`).forEach(item=>item.classList.toggle('on',item===button));resetAndRender()}});document.getElementById('holding').onchange=event=>{{state.holding=event.target.value;resetAndRender()}};document.getElementById('search').oninput=event=>{{state.query=event.target.value.trim().toLowerCase();resetAndRender()}};document.getElementById('page-size').onchange=event=>{{state.pageSize=Number(event.target.value);resetAndRender()}};document.getElementById('previous').onclick=()=>{{if(state.page>1){{state.page--;render();window.scrollTo({{top:document.querySelector('.table-shell').offsetTop-150,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}})}}}};document.getElementById('next').onclick=()=>{{const pages=Math.max(1,Math.ceil(rows.filter(matches).length/state.pageSize));if(state.page<pages){{state.page++;render();window.scrollTo({{top:document.querySelector('.table-shell').offsetTop-150,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'}})}}}};document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');language(localStorage.getItem('uteki-lang')||'zh');</script></body></html>"""
