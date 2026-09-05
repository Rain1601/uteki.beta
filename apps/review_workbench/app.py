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


def render_evidence(item: dict) -> str:
    path = " › ".join(item.get("section_path", []))
    zh = ZH["evidence"].get(item["id"], item["support"])
    return f"""<div class="evidence-row">
      <div class="evidence-index">¶{esc(item['paragraph_ordinal'])}</div>
      <div><div>{bilingual(item['support'], zh)}</div><code>{esc(item['text_hash'][:12])}</code> <span class="path">{esc(path)}</span></div>
      <a href="{esc(item['source_url'])}" target="_blank" aria-label="Open source">↗</a>
    </div>"""


def render_business_detail(item: dict, evidence: dict[str, dict], review: dict, active: bool) -> str:
    zh_item = ZH["business"].get(item["id"], {})
    products = " · ".join(item.get("products_services", [])) or "—"
    money_en = "; ".join(value["description"] for value in item.get("monetization", [])) or "Not stated at this level"
    money_zh = zh_item.get("money", "该层级未单独说明")
    evidence_rows = "".join(render_evidence(evidence[eid]) for eid in item.get("evidence_ids", []) if eid in evidence)
    current = review.get(item["id"], {}).get("status", item.get("review_status", "candidate"))
    note = review.get(item["id"], {}).get("note", "")
    options = "".join(f"<option value='{status}' {'selected' if status == current else ''}>{status}</option>" for status in ("candidate", "accepted", "edited", "rejected", "ambiguous"))
    return f"""<section class="detail {'active' if active else ''}" data-detail="{esc(item['id'])}">
      <div class="detail-title"><div><span class="eyebrow">{esc(item['kind'])}</span><h2>{esc(item['name'])}</h2></div><span class="state {esc(current)}">{esc(current)}</span></div>
      <div class="field"><label>{bilingual('Business description','业务描述')}</label><p>{bilingual(item['description'], zh_item.get('description', item['description']))}</p></div>
      <div class="field"><label>{bilingual('Representative products & services','代表性产品与服务')}</label><p>{esc(products)}</p></div>
      <div class="field"><label>{bilingual('How it makes money','如何赚钱')}</label><p>{bilingual(money_en, money_zh)}</p></div>
      <div class="field evidence-block"><label>{bilingual('Supporting evidence','支持证据')} <b>{len(item.get('evidence_ids', []))}</b></label>{evidence_rows}</div>
      <form method="post" action="/review" class="review-form">
        <input type="hidden" name="item_id" value="{esc(item['id'])}">
        <label>{bilingual('Decision','审核结论')}<select name="status">{options}</select></label>
        <label>{bilingual('Review note','审核备注')}<textarea name="note" placeholder="Why? / 原因">{esc(note)}</textarea></label>
        <button type="submit">{bilingual('Save review','保存审核')}</button>
      </form>
    </section>"""


def render_page(data: dict, reviews: dict) -> str:
    evidence = {item["id"]: item for item in data["evidence"]}
    business_reviews = reviews.get("businesses", {})
    rows = []
    details = []
    for index, item in enumerate(data["businesses"]):
        current = business_reviews.get(item["id"], {}).get("status", item.get("review_status", "candidate"))
        rows.append(f"""<button class="result-row {'active' if index == 0 else ''}" data-select="{esc(item['id'])}">
          <span class="tree-mark">{'●' if item['kind'] == 'company' else '└'}</span><span><b>{esc(item['name'])}</b><small>{esc(item['kind'])}</small></span><i class="dot {esc(current)}"></i>
        </button>""")
        details.append(render_business_detail(item, evidence, business_reviews, index == 0))
    relationships = "".join(f"<tr><td>{esc(item['source_id'])}</td><td>{esc(item['kind'])}</td><td>{esc(item['target_id'])}</td><td>{bilingual(item['description'], ZH['relationship'].get(item['source_id']+':'+item['target_id'], item['description']))}</td></tr>" for item in data["relationships"])
    unknown = data["unknowns"][0] if data["unknowns"] else None
    reviewed = sum(1 for item in business_reviews.values() if item.get("status") != "candidate")
    unknown_html = "" if not unknown else f"<div class='unknown'><b>{bilingual(unknown['question'], ZH['unknown_question'])}</b><p>{bilingual(unknown['reason_unanswered'], ZH['unknown_reason'])}</p></div>"
    return f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Uteki · Business Map Review</title>
<style>
:root{{--ink:#18211d;--muted:#6b746f;--bg:#f5f6f2;--panel:#fff;--line:#dfe3dd;--green:#21634a;--soft:#edf3ef;--amber:#a56220;--red:#a43f39}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}header{{height:58px;border-bottom:1px solid var(--line);background:white;display:flex;align-items:center;justify-content:space-between;padding:0 24px}}.brand{{font-weight:700;letter-spacing:.02em}}.brand span{{color:var(--green)}}.toolbar{{display:flex;gap:16px;align-items:center;color:var(--muted)}}.lang button{{border:0;background:none;padding:5px;color:var(--muted);cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}main{{display:grid;grid-template-columns:390px minmax(0,1fr);height:calc(100vh - 58px)}}aside{{border-right:1px solid var(--line);background:#fafbf8;overflow:auto}}.aside-head{{padding:22px 20px 14px;border-bottom:1px solid var(--line)}}h1{{font-size:18px;margin:0 0 6px}}.summary{{color:var(--muted);font-size:13px;margin:0}}.counts{{display:flex;gap:18px;margin-top:13px;font-size:12px;color:var(--muted)}}.counts b{{color:var(--ink)}}.section-label{{padding:16px 20px 8px;font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}}.result-row{{width:100%;display:grid;grid-template-columns:20px 1fr 12px;gap:7px;align-items:center;text-align:left;border:0;border-left:3px solid transparent;background:none;padding:10px 18px;cursor:pointer;color:var(--ink)}}.result-row:hover{{background:var(--soft)}}.result-row.active{{background:#e8f0eb;border-left-color:var(--green)}}.result-row small{{display:block;color:var(--muted);font-size:10px;text-transform:uppercase}}.tree-mark{{color:#9ba69f}}.dot{{width:7px;height:7px;border-radius:50%;background:#adb5b0}}.dot.accepted{{background:var(--green)}}.dot.rejected{{background:var(--red)}}.dot.ambiguous{{background:var(--amber)}}.relationships{{padding:0 18px 25px}}table{{border-collapse:collapse;width:100%;font-size:11px}}td{{border-bottom:1px solid var(--line);padding:7px 4px;vertical-align:top}}td:nth-child(-n+3){{white-space:nowrap;color:var(--muted)}}.workspace{{overflow:auto;padding:28px 34px 80px}}.workspace-head{{max-width:920px;margin:auto 18px auto;display:flex;justify-content:space-between;align-items:end;border-bottom:1px solid var(--line);padding-bottom:13px}}.workspace-head h3{{margin:0;font-size:13px}}.workspace-head p{{margin:3px 0 0;color:var(--muted);font-size:12px}}.detail{{display:none;max-width:920px;margin:0 auto}}.detail.active{{display:block}}.detail-title{{display:flex;justify-content:space-between;align-items:start;padding:28px 0 18px}}.detail-title h2{{font:500 30px/1.1 Georgia,"Songti SC",serif;margin:4px 0}}.eyebrow{{font-size:10px;color:var(--green);letter-spacing:.12em;text-transform:uppercase}}.state{{font-size:11px;border:1px solid var(--line);border-radius:20px;padding:4px 9px;color:var(--muted)}}.field{{display:grid;grid-template-columns:180px 1fr;border-top:1px solid var(--line);padding:15px 0}}.field>label{{font-size:12px;color:var(--muted)}}.field p{{margin:0}}.evidence-block{{align-items:start}}.evidence-row{{display:grid;grid-template-columns:52px 1fr 20px;gap:10px;background:white;border:1px solid var(--line);padding:11px;margin-bottom:7px}}.evidence-index{{font-weight:700;color:var(--green)}}code{{font-size:10px;color:var(--muted)}}.path{{font-size:10px;color:var(--muted);margin-left:7px}}.evidence-row a{{color:var(--green);text-decoration:none}}.review-form{{margin-top:22px;background:#fff;border:1px solid var(--line);padding:18px;display:grid;grid-template-columns:180px 1fr;gap:14px}}.review-form label{{display:contents}}.review-form select,.review-form textarea{{width:100%;border:1px solid var(--line);padding:9px;background:white;font:inherit}}.review-form textarea{{min-height:70px;resize:vertical}}.review-form button{{grid-column:2;width:max-content;border:0;background:var(--green);color:white;padding:9px 17px;cursor:pointer}}.unknown{{max-width:920px;margin:30px auto 0;border-left:3px solid var(--amber);padding:9px 14px;background:#fff9ee}}.unknown p{{margin:4px 0;color:var(--muted)}}@media(max-width:820px){{main{{grid-template-columns:1fr;height:auto}}aside{{border-right:0;border-bottom:1px solid var(--line)}}.workspace{{padding:20px}}.field,.review-form{{grid-template-columns:1fr}}.review-form label{{display:block}}.review-form button{{grid-column:1}}}}
</style></head><body>
<header><div class="brand"><span>Uteki</span> / Review Workbench</div><div class="toolbar"><span>SEC 10-K · FY2025</span><div class="lang"><button id="en">EN</button><button id="zh" class="on">中文</button></div></div></header>
<main><aside><div class="aside-head"><h1>{bilingual('Analysis result','分析结果')}</h1><p class="summary">{bilingual(data['summary'], ZH['summary'])}</p><div class="counts"><span><b>{len(data['businesses'])}</b> {bilingual('businesses','项业务')}</span><span><b>{len(data['relationships'])}</b> {bilingual('relationships','条关系')}</span><span><b>{reviewed}</b> {bilingual('reviewed','已审核')}</span></div></div><div class="section-label">Business map</div>{''.join(rows)}<div class="section-label">Relationships</div><div class="relationships"><table>{relationships}</table></div></aside>
<section class="workspace"><div class="workspace-head"><div><h3>{bilingual('Annotation & review','标注与审核')}</h3><p>{bilingual('Select one result on the left, verify evidence, then record one decision.','从左侧选择一项结果，核验证据，再记录一次审核决定。')}</p></div></div>{''.join(details)}{unknown_html}</section></main>
<script>
const body=document.body; function language(v){{body.classList.toggle('zh',v==='zh');document.querySelectorAll('.lang button').forEach(b=>b.classList.toggle('on',b.id===v));localStorage.setItem('uteki-lang',v)}}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');language(localStorage.getItem('uteki-lang')||'zh');
document.querySelectorAll('[data-select]').forEach(row=>row.onclick=()=>{{document.querySelectorAll('[data-select]').forEach(x=>x.classList.remove('active'));document.querySelectorAll('[data-detail]').forEach(x=>x.classList.remove('active'));row.classList.add('active');document.querySelector(`[data-detail="${{row.dataset.select}}"]`).classList.add('active')}});
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
