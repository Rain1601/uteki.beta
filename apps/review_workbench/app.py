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
    return f"""<article class="source-row" id="source-{esc(item['id'])}">
      <div class="line-no">¶{esc(item['paragraph_ordinal'])}</div>
      <div class="source-body"><div class="source-meta"><span>{esc(path)}</span><span class="mono" title="{esc(item['text_hash'])}">{esc(item['text_hash'][:12])}</span><a href="{esc(item['source_url'])}" target="_blank">SEC ↗</a></div>
      <p class="source-text">{esc(item.get('source_text', '—'))}</p>
      <p class="extraction"><span class="tag">{bilingual('EXTRACTED','提取')}</span>{bilingual(item['support'], ZH['evidence'].get(item['id'], item['support']))}</p></div>
    </article>"""


def render_business_row(item: dict, evidence: dict[str, dict], review: dict, depth: int) -> str:
    zh_item = ZH["business"].get(item["id"], {})
    products = " · ".join(item.get("products_services", [])) or "—"
    money_en = "; ".join(value["description"] for value in item.get("monetization", [])) or "Not stated at this level"
    money_zh = zh_item.get("money", "该层级未单独说明")
    current = review.get(item["id"], {}).get("status", item.get("review_status", "candidate"))
    note = review.get(item["id"], {}).get("note", "")
    statuses = (("candidate", "待审核 / Candidate"), ("accepted", "通过 / Accepted"), ("edited", "需修订 / Edit"), ("rejected", "拒绝 / Rejected"), ("ambiguous", "存疑 / Ambiguous"))
    options = "".join(f"<option value='{status}' {'selected' if status == current else ''}>{label}</option>" for status, label in statuses)
    evidence_links = " ".join(f'<a href="#source-{esc(eid)}">¶{esc(evidence[eid]["paragraph_ordinal"])}</a>' for eid in item.get("evidence_ids", []) if eid in evidence)
    marker = "●" if depth == 0 else "└"
    return f"""<article class="result-row" id="business-{esc(item['id'])}">
      <div class="result-title" style="--depth:{depth}"><span class="tree">{marker}</span><h3>{esc(item['name'])}</h3><span class="kind">{esc(item['kind'])}</span></div>
      <p class="result-summary">{bilingual(item['description'], zh_item.get('description', item['description']))}</p>
      <dl><div><dt>{bilingual('Products & services','产品与服务')}</dt><dd>{esc(products)}</dd></div><div><dt>{bilingual('Monetization','变现方式')}</dt><dd>{bilingual(money_en, money_zh)}</dd></div><div><dt>{bilingual('Evidence','证据')}</dt><dd class="evidence-links">{evidence_links or '—'}</dd></div></dl>
      <form method="post" action="/review" class="inline-review">
        <input type="hidden" name="item_id" value="{esc(item['id'])}">
        <select name="status" aria-label="Decision for {esc(item['name'])}">{options}</select>
        <input name="note" value="{esc(note)}" placeholder="{esc('审核备注 / Review note')}">
        <button type="submit">{bilingual('Save','保存')}</button>
      </form>
    </article>"""


def render_page(data: dict, reviews: dict) -> str:
    business_reviews = reviews.get("businesses", {})
    source_rows = "".join(render_source_row(item) for item in data["evidence"])
    parent_by_child = {item["source_id"]: item["target_id"] for item in data["relationships"]}
    depths: dict[str, int] = {}
    for item in data["businesses"]:
        current, depth, seen = item["id"], 0, set()
        while current in parent_by_child and current not in seen:
            seen.add(current)
            current, depth = parent_by_child[current], depth + 1
        depths[item["id"]] = depth
    evidence_by_id = {item["id"]: item for item in data["evidence"]}
    business_rows = "".join(render_business_row(item, evidence_by_id, business_reviews, depths[item["id"]]) for item in data["businesses"])
    relationships = "".join(f"<tr><td>{esc(item['source_id'])}</td><td>{esc(item['kind'])}</td><td>{esc(item['target_id'])}</td><td>{bilingual(item['description'], ZH['relationship'].get(item['source_id']+':'+item['target_id'], item['description']))}</td></tr>" for item in data["relationships"])
    unknown = data["unknowns"][0] if data["unknowns"] else None
    reviewed = sum(1 for item in business_reviews.values() if item.get("status") != "candidate")
    unknown_html = "" if not unknown else f"<div class='unknown'><b>{bilingual(unknown['question'], ZH['unknown_question'])}</b><p>{bilingual(unknown['reason_unanswered'], ZH['unknown_reason'])}</p></div>"
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Uteki · Business Map Review</title>
<style>
:root{{--ink:#202421;--muted:#727873;--bg:#f8f9f7;--paper:#fff;--line:#e1e4e0;--line-strong:#cbd0cb;--green:#23674d;--green-soft:#edf5f0;--amber:#9b5d1d}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.55 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}header{{position:sticky;top:0;z-index:5;height:52px;border-bottom:1px solid var(--line);background:#fffc;backdrop-filter:blur(14px);display:flex;align-items:center;justify-content:space-between;padding:0 22px}}.brand{{font-weight:700}}.brand span{{color:var(--green)}}.toolbar{{display:flex;gap:14px;align-items:center;color:var(--muted);font-size:12px}}.lang button{{border:0;background:none;padding:4px;color:var(--muted);cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}main{{display:grid;grid-template-columns:170px minmax(0,900px);gap:54px;max-width:1180px;margin:0 auto;padding:38px 24px 90px}}aside{{position:sticky;top:88px;height:max-content}}.index-title{{font:10px ui-monospace,monospace;color:var(--muted);letter-spacing:.1em;margin-bottom:12px}}aside a{{display:block;padding:7px 0;color:var(--muted);text-decoration:none;border-left:1px solid var(--line);padding-left:13px}}aside a:hover{{color:var(--green);border-left-color:var(--green)}}aside small{{display:block;margin-top:22px;color:var(--muted)}}.document{{min-width:0}}.intro{{padding-bottom:30px;border-bottom:1px solid var(--line-strong)}}h1{{font:600 28px/1.2 Georgia,"Songti SC",serif;margin:0 0 12px}}.intro p{{max-width:720px;margin:0;color:var(--muted)}}.counts{{display:flex;gap:20px;margin-top:18px;color:var(--muted);font-size:12px}}.counts b{{color:var(--ink)}}section.workspace{{padding-top:42px;scroll-margin-top:60px}}.section-head{{display:grid;grid-template-columns:28px 1fr;column-gap:8px;margin-bottom:18px}}.step{{grid-row:1/3;font:11px ui-monospace,monospace;color:var(--green);padding-top:4px}}h2{{font-size:18px;margin:0}}.section-head p{{margin:3px 0 0;color:var(--muted)}}.source-list{{border-top:1px solid var(--line-strong)}}.source-row{{display:grid;grid-template-columns:52px 1fr;border-bottom:1px solid var(--line);padding:20px 0;scroll-margin-top:70px}}.line-no{{font:11px ui-monospace,monospace;color:var(--muted);padding-top:2px}}.source-meta{{display:flex;gap:12px;align-items:center;color:var(--muted);font-size:11px}}.source-meta span:first-child{{flex:1}}.mono{{font:10px ui-monospace,SFMono-Regular,monospace;color:var(--muted)}}a{{color:var(--green)}}.source-text{{font:15px/1.6 Georgia,"Songti SC",serif;margin:10px 0 8px}}.extraction{{margin:0;color:#4e5751;font-size:12px}}.tag{{display:inline-block;margin-right:8px;color:var(--green);font:9px ui-monospace,monospace;letter-spacing:.06em;background:var(--green-soft);padding:2px 5px}}.result-list{{border-top:1px solid var(--line-strong)}}.result-row{{padding:24px 0 20px;border-bottom:1px solid var(--line);scroll-margin-top:70px}}.result-title{{display:flex;align-items:baseline;gap:9px;padding-left:calc(var(--depth) * 20px)}}.tree{{color:#a1aaa4}}h3{{font:600 18px Georgia,"Songti SC",serif;margin:0}}.kind{{font:9px ui-monospace,monospace;text-transform:uppercase;color:var(--muted)}}.result-summary{{margin:8px 0 14px;padding-left:calc(var(--depth) * 20px + 24px)}}dl{{margin:0;display:grid;grid-template-columns:repeat(3,1fr);gap:18px;padding-left:calc(var(--depth) * 20px + 24px)}}dl div{{min-width:0}}dt{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em;margin-bottom:3px}}dd{{margin:0;font-size:12px}}.evidence-links a{{display:block;font:10px ui-monospace,monospace}}.inline-review{{margin:17px 0 0 calc(var(--depth) * 20px + 24px);display:grid;grid-template-columns:105px minmax(120px,1fr) 52px;gap:6px;padding:9px;background:#f1f3f0}}select,input,button{{font:12px ui-sans-serif,-apple-system,"PingFang SC",sans-serif;border:1px solid var(--line-strong);background:white;padding:7px;min-width:0}}button{{background:var(--green);border-color:var(--green);color:white;cursor:pointer}}.subsection{{margin-top:38px}}table{{border-collapse:collapse;width:100%;font-size:12px}}td{{border-bottom:1px solid var(--line);padding:9px 4px;vertical-align:top}}td:nth-child(-n+3){{white-space:nowrap;color:var(--muted);font-family:ui-monospace,monospace;font-size:10px}}.unknown{{border-top:1px solid var(--line-strong);border-bottom:1px solid var(--line);padding:12px 4px}}.unknown p{{margin:4px 0 0;color:var(--muted)}}@media(max-width:900px){{header{{padding:0 12px}}main{{display:block;padding:25px 18px 70px}}aside{{display:none}}h1{{font-size:24px}}.source-meta{{align-items:flex-start;flex-wrap:wrap}}.source-meta span:first-child{{flex-basis:100%}}dl{{grid-template-columns:1fr 1fr}}.toolbar>span:first-child{{display:none}}}}@media(max-width:560px){{.source-row{{grid-template-columns:38px 1fr}}dl{{grid-template-columns:1fr}}.inline-review{{grid-template-columns:1fr}}}}
</style></head><body>
<header><div class="brand"><span>Uteki</span> / Review</div><div class="toolbar"><span>Alphabet · 10-K · FY2025</span><div class="lang"><button id="en">EN</button><button id="zh" class="on">中文</button></div></div></header>
<main><aside><div class="index-title">PAGE INDEX</div><a href="#overview">{bilingual('Overview','概览')}</a><a href="#source">{bilingual('Parsed source','解析原文')}</a><a href="#result">{bilingual('Result & review','结果与标注')}</a><a href="#relationships">{bilingual('Relationships','业务关系')}</a><a href="#unresolved">{bilingual('Unresolved','尚未解决')}</a><small>{bilingual('One continuous review page','单页连续审核')}</small></aside><div class="document">
<div class="intro" id="overview"><h1>{bilingual('Company business map','公司业务地图')}</h1><p>{bilingual(data['summary'], ZH['summary'])}</p><div class="counts"><span><b>{len(data['evidence'])}</b> {bilingual('source rows','条原文')}</span><span><b>{len(data['businesses'])}</b> {bilingual('results','项结果')}</span><span><b>{reviewed}</b> {bilingual('reviewed','已审核')}</span></div></div>
<section class="workspace" id="source"><div class="section-head"><span class="step">01</span><h2>{bilingual('Parsed source','解析原文')}</h2><p>{bilingual('The exact filing passages used by this result.','本次分析实际引用的申报原文。')}</p></div><div class="source-list">{source_rows}</div></section>
<section class="workspace" id="result"><div class="section-head"><span class="step">02</span><h2>{bilingual('Result & annotation','分析结果与标注')}</h2><p>{bilingual('Read in hierarchy order, verify its evidence, and review in place.','按层级连续阅读、核验证据并就地审核。')}</p></div><div class="result-list">{business_rows}</div>
<div class="subsection section-head" id="relationships"><h2>{bilingual('Relationships','业务关系')}</h2></div><table><tbody>{relationships}</tbody></table>
<div class="subsection section-head" id="unresolved"><h2>{bilingual('Unresolved','尚未解决')}</h2></div>{unknown_html}</section></div></main>
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
