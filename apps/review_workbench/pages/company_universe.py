from __future__ import annotations
from apps.review_workbench.assets import asset_text

import html
import json
from apps.review_workbench.components.visual_system import workbench_page


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
<style>{asset_text('company_universe.css')}</style></head><body>
<main><section class='company-heading'><div><h1>{bilingual('Companies','公司观察池')}</h1><span>{bilingual(f"{len(data['companies'])} companies",f"{len(data['companies'])} 家公司")}</span></div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></section>
<section class='controls'><div class='primary-controls'><label class='search'><input id='search' type='search' data-placeholder-en='Search company, ticker, or tag' data-placeholder-zh='搜索公司、代码或标签' placeholder='搜索公司、代码或标签' aria-label='搜索公司 / Search companies' autocomplete='off'></label><div class='filter-group' data-group='index'><button class='on' data-filter='index' data-value='all'>{bilingual('All indices','全部指数')}</button><button data-filter='index' data-value='sp500'>S&amp;P 500</button><button data-filter='index' data-value='nasdaq100'>Nasdaq-100</button></div><div class='filter-group' data-group='attention'><button class='on' data-filter='attention' data-value='all'>{bilingual('All focus','全部关注度')}</button><button data-filter='attention' data-value='core'>{bilingual('Core','重点')}</button><button data-filter='attention' data-value='active'>{bilingual('Active','关注')}</button><button data-filter='attention' data-value='context'>{bilingual('Control','对照')}</button></div><select id='holding' class='holding-select' aria-label='持仓状态 / Holding status'><option value='all' data-en='All holdings' data-zh='全部持仓'>全部持仓</option><option value='held' data-en='Held' data-zh='已持仓'>已持仓</option><option value='not_held' data-en='Not held' data-zh='未持仓'>未持仓</option><option value='unknown' data-en='Unconfirmed' data-zh='待确认'>待确认</option></select><span id='result-count' class='result-count'></span></div><div class='theme-filters'><button class='on' data-filter='theme' data-value='all'>{bilingual('All themes','全部行业')}<b>{len(data['companies'])}</b></button>{theme_buttons}</div></section>
<section class='table-shell' tabindex='0' aria-label='Company list'><table><thead><tr><th>{bilingual('Company','公司')}</th><th>{bilingual('Research theme','行业主题')}</th><th>{bilingual('Index','指数')}</th><th>{bilingual('Attention','关注度')}</th><th>{bilingual('Holding','持仓')}</th><th></th></tr></thead><tbody>{''.join(rows)}</tbody></table><div class='empty'>{bilingual('No companies match these filters.','没有符合当前条件的公司。')}</div></section>
<footer><details class='company-sources'><summary>{bilingual('Scope and sources','范围与来源')}</summary><div>{bilingual(data['selection_policy']['note_en'],data['selection_policy']['note_zh'])}<br>{bilingual('Index membership is a dated snapshot. Holding labels do not imply trading decisions.','指数归属为时点快照，持仓标签不代表交易决定。')}<br>{source_links}</div></details><span>{bilingual('Scroll to browse · Open a company to continue research','滑动浏览 · 点击公司进入研究')}</span></footer></main>
<script>{asset_text('company_universe.js')}</script></body></html>"""
