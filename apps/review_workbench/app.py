from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "data/evaluation/pilots/alphabet_2025_item1_business_map.json"
REVIEW_FILE = ROOT / "data/evaluation/reviews/alphabet_2025_item1_review.json"

ZH = {
    "summary": "Alphabet 由 Google 和非 Google 业务组成；Google 通过 Google Services 与 Google Cloud 两个分部报告，非 Google 业务统一归入 Other Bets。",
    "business": {
        "alphabet": {"description": "由多项业务组成的公司，其中规模最大的业务是 Google。", "money": "该层级未单独说明"},
        "google": {"description": "Alphabet 最大的业务，通过 Google Services 和 Google Cloud 报告。", "money": "该层级未单独说明"},
        "google-services": {"description": "主要面向消费者的产品与平台，以广告为主要变现方式，并包含订阅、平台及设备收入。", "money": "效果广告与品牌广告、消费者订阅、平台费用及设备销售"},
        "google-cloud": {"description": "面向企业客户提供基础设施、平台、应用和其他云服务。", "money": "按使用量收费及订阅"},
        "other-bets": {"description": "处于不同研发与商业化阶段的非 Google 业务组合。", "money": "自动驾驶运输和互联网服务销售"},
    },
    "relationship": {
        "google:alphabet": "Google 是 Alphabet 最大的业务。",
        "google-services:google": "Google Services 是 Google 的两个报告分部之一。",
        "google-cloud:google": "Google Cloud 是 Google 的两个报告分部之一。",
        "other-bets:alphabet": "非 Google 业务统一归入 Other Bets 报告。",
    },
    "evidence": {
        "e-overview-2": "说明 Alphabet 是多业务集合，并定义 Google 分部与 Other Bets 的报告方式。",
        "e-google-segments": "说明 Google 的两个报告分部。",
        "e-services-products": "列出 Google Services 的代表性产品和平台。",
        "e-services-money": "说明广告是主要变现方式，以及订阅、平台和设备等其他收入。",
        "e-cloud-money": "说明 Google Cloud 的产品、企业客户以及使用量和订阅变现方式。",
        "e-other-bets": "说明 Other Bets 的业务成熟度、示例、独立性和主要收入来源。",
    },
    "unknown_question": "Other Bets 完整包含哪些业务？",
    "unknown_reason": "Item 1 只提供示例，没有给出明确、完整的成员清单。",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return html.escape(str(value))


def bilingual(en: object, zh: object) -> str:
    return f"<span data-lang='en'>{esc(en)}</span><span data-lang='zh'>{esc(zh)}</span>"


def render_source_row(item: dict) -> str:
    path = " › ".join(item.get("section_path", []))
    return f"""<tr id="source-{esc(item['id'])}">
      <td class="mono">¶{esc(item['paragraph_ordinal'])}</td>
      <td>{esc(path)}</td>
      <td class="source-text">{esc(item.get('source_text', '—'))}</td>
      <td>{bilingual(item['support'], ZH['evidence'].get(item['id'], item['support']))}</td>
      <td class="mono"><span title="{esc(item['text_hash'])}">{esc(item['text_hash'][:12])}</span> <a href="{esc(item['source_url'])}" target="_blank">↗</a></td>
    </tr>"""


def render_business_row(item: dict, review: dict, index: int) -> str:
    zh_item = ZH["business"].get(item["id"], {})
    products = " · ".join(item.get("products_services", [])) or "—"
    money_en = "; ".join(value["description"] for value in item.get("monetization", [])) or "Not stated at this level"
    money_zh = zh_item.get("money", "该层级未单独说明")
    current = review.get(item["id"], {}).get("status", item.get("review_status", "candidate"))
    note = review.get(item["id"], {}).get("note", "")
    options = "".join(f"<option value='{status}' {'selected' if status == current else ''}>{status}</option>" for status in ("candidate", "accepted", "edited", "rejected", "ambiguous"))
    evidence_links = " ".join(f'<a href="#source-{esc(eid)}">{esc(eid)}</a>' for eid in item.get("evidence_ids", []))
    marker = "●" if index == 0 else "└"
    return f"""<div class="sheet-record" id="business-{esc(item['id'])}">
      <div class="identity"><span class="tree">{marker}</span><strong>{esc(item['name'])}</strong><small>{esc(item['kind'])}</small></div>
      <div>{bilingual(item['description'], zh_item.get('description', item['description']))}</div>
      <div>{esc(products)}</div>
      <div>{bilingual(money_en, money_zh)}</div>
      <div class="evidence-links">{evidence_links or '—'}</div>
      <form method="post" action="/review" class="inline-review">
        <input type="hidden" name="item_id" value="{esc(item['id'])}">
        <select name="status" aria-label="Decision for {esc(item['name'])}">{options}</select>
        <input name="note" value="{esc(note)}" placeholder="{esc('审核备注 / Review note')}">
        <button type="submit">{bilingual('Save','保存')}</button>
      </form>
    </div>"""


def render_page(data: dict, reviews: dict) -> str:
    business_reviews = reviews.get("businesses", {})
    source_rows = "".join(render_source_row(item) for item in data["evidence"])
    business_rows = "".join(render_business_row(item, business_reviews, index) for index, item in enumerate(data["businesses"]))
    relationships = "".join(f"<tr><td>{esc(item['source_id'])}</td><td>{esc(item['kind'])}</td><td>{esc(item['target_id'])}</td><td>{bilingual(item['description'], ZH['relationship'].get(item['source_id']+':'+item['target_id'], item['description']))}</td></tr>" for item in data["relationships"])
    unknown = data["unknowns"][0] if data["unknowns"] else None
    reviewed = sum(1 for item in business_reviews.values() if item.get("status") != "candidate")
    unknown_html = "" if not unknown else f"<div class='unknown'><b>{bilingual(unknown['question'], ZH['unknown_question'])}</b><p>{bilingual(unknown['reason_unanswered'], ZH['unknown_reason'])}</p></div>"
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Uteki · Business Map Review</title>
<style>
:root{{--ink:#17201b;--muted:#69736d;--bg:#f7f8f5;--line:#d8ddd7;--line-strong:#b9c2bb;--green:#1f6047;--soft:#eef3ef;--amber:#9b5d1d}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:13px/1.45 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}header{{position:sticky;top:0;z-index:5;height:52px;border-bottom:1px solid var(--line-strong);background:#fff;display:flex;align-items:center;justify-content:space-between;padding:0 22px}}.brand{{font-weight:700}}.brand span{{color:var(--green)}}.toolbar,.nav{{display:flex;gap:16px;align-items:center;color:var(--muted)}}.nav a{{color:var(--muted);text-decoration:none}}.nav a:hover{{color:var(--green)}}.lang button{{border:0;background:none;padding:4px;color:var(--muted);cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}main{{padding:0 22px 70px;max-width:1800px;margin:auto}}.intro{{display:grid;grid-template-columns:170px minmax(0,850px) 1fr;gap:24px;padding:24px 0 20px;border-bottom:1px solid var(--line-strong)}}h1{{font-size:18px;margin:0}}.intro p{{margin:0;color:var(--muted)}}.counts{{display:flex;justify-content:flex-end;gap:20px;color:var(--muted)}}.counts b{{color:var(--ink)}}section.workspace{{padding-top:26px;scroll-margin-top:58px}}.section-head{{display:flex;align-items:baseline;gap:12px;margin-bottom:10px}}.step{{font:11px ui-monospace,monospace;color:var(--green)}}h2{{font-size:16px;margin:0}}.section-head p{{margin:0;color:var(--muted)}}.table-wrap{{overflow-x:auto;border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line-strong)}}table{{border-collapse:collapse;width:100%;min-width:1100px;background:#fff}}th{{position:sticky;top:52px;z-index:2;background:#edf1ed;text-align:left;font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:600}}th,td{{padding:8px 9px;border-right:1px solid var(--line);border-bottom:1px solid var(--line);vertical-align:top}}tr:last-child td{{border-bottom:0}}td:last-child,th:last-child{{border-right:0}}.source-table th:nth-child(1){{width:58px}}.source-table th:nth-child(2){{width:210px}}.source-table th:nth-child(3){{width:42%}}.source-table th:nth-child(4){{width:25%}}.source-table th:nth-child(5){{width:110px}}.source-text{{font-family:Georgia,"Songti SC",serif;font-size:13px}}.mono{{font:10px ui-monospace,SFMono-Regular,monospace;color:var(--muted)}}a{{color:var(--green)}}.sheet{{min-width:1380px;border-top:1px solid var(--line-strong);background:#fff}}.sheet-head,.sheet-record{{display:grid;grid-template-columns:155px 1.25fr .9fr .9fr 105px 260px}}.sheet-head{{position:sticky;top:52px;z-index:2;background:#edf1ed;color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:.05em}}.sheet-head>div,.sheet-record>div,.sheet-record>form{{padding:8px 9px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}}.sheet-record:hover{{background:#fbfcfa}}.identity{{display:grid;grid-template-columns:16px 1fr}}.identity small{{grid-column:2;color:var(--muted);font-size:9px;text-transform:uppercase}}.tree{{color:#9aa49d}}.evidence-links a{{display:block;font:10px ui-monospace,monospace}}.inline-review{{display:grid;grid-template-columns:92px 1fr 46px;gap:5px;align-content:start}}select,input,button{{font:inherit;border:1px solid var(--line-strong);background:white;padding:6px;min-width:0}}button{{background:var(--green);border-color:var(--green);color:white;cursor:pointer}}.subsection{{margin-top:24px}}.relation-table{{max-width:900px;min-width:700px}}.unknown{{border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line);padding:10px 9px;background:#fffaf0}}.unknown p{{display:inline;margin-left:18px;color:var(--muted)}}@media(max-width:800px){{header{{padding:0 12px}}.nav{{display:none}}main{{padding:0 12px 50px}}.intro{{grid-template-columns:1fr}}.counts{{justify-content:flex-start}}}}
</style></head><body>
<header><div class="brand"><span>Uteki</span> / Review Workbench</div><nav class="nav"><a href="#source">{bilingual('01 Parsed source','01 解析原始数据')}</a><a href="#result">{bilingual('02 Result & review','02 结果与标注')}</a></nav><div class="toolbar"><span>Alphabet · 10-K · FY2025</span><div class="lang"><button id="en">EN</button><button id="zh" class="on">中文</button></div></div></header>
<main><div class="intro"><h1>{bilingual('Company business map','公司业务地图')}</h1><p>{bilingual(data['summary'], ZH['summary'])}</p><div class="counts"><span><b>{len(data['evidence'])}</b> {bilingual('source rows','条原始数据')}</span><span><b>{len(data['businesses'])}</b> {bilingual('results','项结果')}</span><span><b>{reviewed}</b> {bilingual('reviewed','已审核')}</span></div></div>
<section class="workspace" id="source"><div class="section-head"><span class="step">01</span><h2>{bilingual('Parsed source data','解析原始数据')}</h2><p>{bilingual('Normalized rows used by this result; original filing text remains authoritative.','本次结果实际使用的规范化数据行；申报原文始终是事实依据。')}</p></div><div class="table-wrap"><table class="source-table"><thead><tr><th>Row</th><th>{bilingual('Section path','章节路径')}</th><th>{bilingual('Original text','英文原文')}</th><th>{bilingual('Extraction meaning','提取含义')}</th><th>Hash / SEC</th></tr></thead><tbody>{source_rows}</tbody></table></div></section>
<section class="workspace" id="result"><div class="section-head"><span class="step">02</span><h2>{bilingual('Analysis result & annotation','分析结果与标注')}</h2><p>{bilingual('Review every row in place; no result is hidden.','直接逐行审核，所有结果保持可见。')}</p></div><div class="table-wrap"><div class="sheet"><div class="sheet-head"><div>{bilingual('Business','业务')}</div><div>{bilingual('Description','业务描述')}</div><div>{bilingual('Products / services','产品与服务')}</div><div>{bilingual('Monetization','变现方式')}</div><div>{bilingual('Evidence','证据')}</div><div>{bilingual('Decision / note','结论与备注')}</div></div>{business_rows}</div></div>
<div class="subsection section-head"><h2>{bilingual('Relationships','业务关系')}</h2></div><div class="table-wrap"><table class="relation-table"><tbody>{relationships}</tbody></table></div>
<div class="subsection section-head"><h2>{bilingual('Unresolved','尚未解决')}</h2></div>{unknown_html}</section></main>
<script>
const body=document.body; function language(v){{body.classList.toggle('zh',v==='zh');document.querySelectorAll('.lang button').forEach(b=>b.classList.toggle('on',b.id===v));localStorage.setItem('uteki-lang',v)}}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');language(localStorage.getItem('uteki-lang')||'zh');
</script></body></html>"""


def save_review(item_id: str, status: str, note: str) -> None:
    if status not in {"candidate", "accepted", "edited", "rejected", "ambiguous"}:
        raise ValueError("invalid review status")
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {"businesses": {}}
    value.setdefault("businesses", {})[item_id] = {"status": status, "note": note}
    temporary = REVIEW_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REVIEW_FILE)


def make_handler(data_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/":
                self.send_error(404)
                return
            data = load_json(data_path)
            reviews = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {}
            body = render_page(data, reviews).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/review":
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            fields = parse_qs(self.rfile.read(length).decode())
            item_id = fields.get("item_id", [""])[0]
            allowed_ids = {item["id"] for item in load_json(data_path)["businesses"]}
            if item_id not in allowed_ids:
                self.send_error(400, "unknown business id")
                return
            save_review(item_id, fields.get("status", [""])[0], fields.get("note", [""])[0])
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.data))
    print(f"Uteki Review Workbench: http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
