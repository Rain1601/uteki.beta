from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "benchmarks/alphabet_2025_business_map/v0.1-candidate/business_map.json"
SOURCE_EXCERPT = ROOT / "data/source_documents/alphabet_2025_10k/review_excerpt.json"
REVIEW_FILE = ROOT / "data/evaluation/reviews/alphabet_2025_business_map_review.json"

ZH_DESCRIPTION = {
    "alphabet": "由多项业务组成的公司，其中规模最大的业务是 Google。",
    "google": "Alphabet 最大的业务，通过 Google Services 与 Google Cloud 两个分部报告。",
    "google-services": "面向消费者的产品与平台，以广告为主要收入来源，并包含订阅、平台和设备收入。",
    "google-advertising": "来自 Google Search 及其他自有媒体、YouTube 和 Google Network 的广告业务。",
    "google-spd": "Google Services 中包含消费者订阅、平台、设备及其他产品服务的收入类别。",
    "google-cloud": "面向企业提供基础设施、平台、应用、通信协作及其他云服务。",
    "google-cloud-platform": "提供基础设施、平台、企业 AI、网络安全以及数据分析等服务。",
    "google-workspace": "带有 Gemini 功能的企业云通信与协作工具。",
    "other-bets": "统一报告的非 Google 业务组合，处于不同研发和商业化阶段。",
}

ISSUES = (
    ("missing_node", "遗漏节点"), ("extra_node", "多余节点"),
    ("duplicate_node", "重复节点"), ("wrong_parent", "父级错误"),
    ("wrong_type", "类型错误"), ("wrong_description", "描述错误"),
    ("wrong_financial", "财务数字错误"), ("wrong_evidence", "证据错误"),
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: object) -> str:
    return html.escape(str(value))


def bilingual(en: object, zh: object) -> str:
    return f"<span data-lang='en'>{esc(en)}</span><span data-lang='zh'>{esc(zh)}</span>"


def parent_and_children(data: dict) -> tuple[dict[str, str], dict[str, list[str]]]:
    parents = {item["source_id"]: item["target_id"] for item in data["relationships"]}
    children: dict[str, list[str]] = {}
    for item in data["businesses"]:
        children.setdefault(parents.get(item["id"], "__root__"), []).append(item["id"])
    return parents, children


def evidence_ordinals(item: dict, evidence: dict[str, dict]) -> list[int]:
    return sorted({evidence[value]["paragraph_ordinal"] for value in item.get("evidence_ids", []) if value in evidence})


def render_tree(data: dict, selected: str) -> str:
    businesses = {item["id"]: item for item in data["businesses"]}
    evidence = {item["id"]: item for item in data["evidence"]}
    _, children = parent_and_children(data)

    def branch(item_id: str) -> str:
        item = businesses[item_id]
        nested = children.get(item_id, [])
        revenue = next((value for value in item.get("importance_signals", []) if "2025 revenue:" in value), "")
        ordinals = ",".join(str(value) for value in evidence_ordinals(item, evidence))
        child_html = "" if not nested else f"<ul>{''.join(branch(value) for value in nested)}</ul>"
        toggle = "<button class='toggle' type='button' aria-label='Toggle'>⌄</button>" if nested else "<span class='toggle-space'></span>"
        return f"""<li data-branch='{esc(item_id)}'>{toggle}<button type='button' class='tree-node {'active' if item_id == selected else ''}' data-select='{esc(item_id)}' data-ordinals='{ordinals}'>
          <span class='node-main'><strong>{esc(item['name'])}</strong><small>{esc(item['kind'])}</small></span><span class='node-metric'>{esc(revenue.replace('2025 revenue: ', ''))}</span>
        </button>{child_html}</li>"""

    return f"<ul class='tree'>{''.join(branch(value) for value in children.get('__root__', []))}</ul>"


def render_result_details(data: dict, selected: str) -> str:
    evidence = {item["id"]: item for item in data["evidence"]}
    parents, _ = parent_and_children(data)
    businesses = {item["id"]: item for item in data["businesses"]}
    rendered = []
    for item in data["businesses"]:
        evidence_buttons = "".join(
            f"<button type='button' class='evidence-link' data-jump='{value}'>¶{value}</button>"
            for value in evidence_ordinals(item, evidence)
        )
        signals = "".join(f"<li>{esc(value)}</li>" for value in item.get("importance_signals", [])) or "<li>—</li>"
        products = " · ".join(item.get("products_services", [])) or "—"
        parent_name = businesses.get(parents.get(item["id"], ""), {}).get("name", "—")
        rendered.append(f"""<article class='node-detail {'active' if item['id'] == selected else ''}' data-detail='{esc(item['id'])}'>
          <div class='detail-kicker'>{esc(item['kind'])}</div><h2>{esc(item['name'])}</h2>
          <p class='lead'>{bilingual(item['description'], ZH_DESCRIPTION.get(item['id'], item['description']))}</p>
          <dl><div><dt>{bilingual('Parent','父级')}</dt><dd>{esc(parent_name)}</dd></div><div><dt>{bilingual('Disclosed scale','披露规模')}</dt><dd><ul>{signals}</ul></dd></div><div><dt>{bilingual('Products / components','产品与组成')}</dt><dd>{esc(products)}</dd></div><div><dt>{bilingual('Source evidence','原文证据')}</dt><dd class='evidence-buttons'>{evidence_buttons}</dd></div></dl>
        </article>""")
    return "".join(rendered)


def render_source(excerpt: dict) -> str:
    return "".join(
        f"""<article class='source-row' data-paragraph='{item['ordinal']}'><div class='paragraph-no'>¶{item['ordinal']}</div><div><div class='source-path'>{esc(' › '.join(item['section_path']))}</div><p>{esc(item['text'])}</p><code>{esc(item['text_hash'][:12])}</code></div></article>"""
        for item in excerpt["paragraphs"]
    )


def page_shell(title: str, active: str, body: str, script: str = "") -> str:
    return f"""<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{esc(title)}</title>
<style>
:root{{--ink:#202420;--muted:#747b75;--line:#e2e5e1;--line-strong:#c9cec9;--bg:#f7f8f6;--paper:#fff;--green:#1f6549;--green-soft:#eaf3ed;--amber:#a46524}}*{{box-sizing:border-box}}html,body{{height:100%}}body{{margin:0;background:var(--bg);color:var(--ink);font:13px/1.5 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}button,input,textarea,select{{font:inherit}}header{{height:54px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 18px;gap:28px}}.brand{{font-weight:750}}.brand i{{font-style:normal;color:var(--green)}}nav{{display:flex;height:100%}}nav a{{display:flex;align-items:center;padding:0 13px;text-decoration:none;color:var(--muted);border-bottom:2px solid transparent}}nav a.active{{color:var(--ink);border-color:var(--green)}}.run-meta{{margin-left:auto;color:var(--muted);font-size:11px}}.lang button{{border:0;background:none;color:var(--muted);padding:4px;cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}.split{{height:calc(100vh - 54px);display:grid;grid-template-columns:minmax(330px,42%) minmax(360px,58%)}}.result-pane,.source-pane,.tree-pane,.annotation-pane{{min-width:0;overflow:auto;background:var(--paper)}}.result-pane,.tree-pane{{border-right:1px solid var(--line-strong)}}.pane-head{{position:sticky;top:0;z-index:3;background:#fffc;backdrop-filter:blur(12px);min-height:68px;padding:14px 18px;border-bottom:1px solid var(--line)}}.pane-head h1{{font-size:15px;margin:0}}.pane-head p{{margin:3px 0 0;color:var(--muted);font-size:11px}}.tree-wrap{{padding:12px 10px;border-bottom:1px solid var(--line)}}ul.tree,.tree ul{{list-style:none;margin:0;padding-left:0}}.tree ul{{padding-left:20px}}.tree li{{position:relative}}.toggle,.toggle-space{{position:absolute;left:0;top:8px;width:18px;height:22px;border:0;background:none;color:var(--muted);cursor:pointer}}.tree-node{{width:calc(100% - 20px);margin-left:20px;display:flex;align-items:center;gap:8px;text-align:left;border:0;background:none;padding:7px 8px;border-radius:5px;color:var(--ink);cursor:pointer}}.tree-node:hover{{background:#f1f4f1}}.tree-node.active{{background:var(--green-soft);color:#174c38}}.node-main{{min-width:0;flex:1}}.node-main strong,.node-main small{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.node-main small{{font:8px ui-monospace,monospace;color:var(--muted);text-transform:uppercase}}.node-metric{{font:10px ui-monospace,monospace;color:var(--muted)}}li.collapsed>ul{{display:none}}li.collapsed>.toggle{{transform:rotate(-90deg)}}.detail-stack{{padding:20px 22px 60px}}.node-detail{{display:none;max-width:720px}}.node-detail.active{{display:block}}.detail-kicker{{font:9px ui-monospace,monospace;text-transform:uppercase;color:var(--green)}}h2{{font:600 26px/1.2 Georgia,"Songti SC",serif;margin:4px 0 8px}}.lead{{font-size:14px;margin:0 0 22px}}dl{{margin:0}}dl>div{{display:grid;grid-template-columns:115px 1fr;border-top:1px solid var(--line);padding:11px 0}}dt{{color:var(--muted);font-size:11px}}dd{{margin:0}}dd ul{{margin:0;padding-left:16px}}.evidence-link{{border:0;background:var(--green-soft);color:var(--green);padding:4px 7px;margin:0 5px 5px 0;border-radius:4px;cursor:pointer}}.source-pane{{background:#fbfbfa}}.source-toolbar{{display:flex;justify-content:space-between;align-items:center}}.source-toolbar a{{color:var(--green);text-decoration:none}}.source-document{{max-width:820px;margin:auto;padding:12px 28px 90px;background:#fff;min-height:100%}}.source-row{{display:grid;grid-template-columns:48px 1fr;padding:21px 0;border-bottom:1px solid var(--line);transition:.2s;scroll-margin:90px}}.source-row.active{{background:#fff8d9;box-shadow:0 0 0 10px #fff8d9}}.paragraph-no{{font:10px ui-monospace,monospace;color:var(--muted);padding-top:3px}}.source-path{{font-size:10px;color:var(--muted)}}.source-row p{{font:15px/1.65 Georgia,"Songti SC",serif;margin:8px 0}}code{{font-size:9px;color:#929892}}.annotation-pane{{padding-bottom:60px}}.annotation-detail{{display:none;padding:24px 28px;max-width:760px}}.annotation-detail.active{{display:block}}.verdicts,.issues{{display:flex;flex-wrap:wrap;gap:7px}}.verdicts input,.issues input{{position:absolute;opacity:0;pointer-events:none}}.verdicts span,.issues span{{display:block;border:1px solid var(--line-strong);padding:7px 12px;border-radius:5px;background:#fff;cursor:pointer}}.verdicts input:checked+span{{background:var(--green);border-color:var(--green);color:white}}.issues input:checked+span{{background:#fff3df;border-color:#d59a51;color:#7f4914}}.form-section{{border-top:1px solid var(--line);padding:16px 0}}.form-section h3{{font-size:11px;margin:0 0 9px;color:var(--muted);font-weight:500}}.fields{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.fields label{{font-size:10px;color:var(--muted)}}.fields input,.fields textarea,.fields select{{display:block;width:100%;margin-top:4px;border:1px solid var(--line-strong);padding:8px;background:#fff}}.fields textarea{{min-height:78px;resize:vertical}}.savebar{{position:sticky;bottom:0;background:#fffe;border-top:1px solid var(--line);padding:10px 28px;display:flex;justify-content:flex-end}}.primary{{border:0;background:var(--green);color:white;padding:9px 16px;border-radius:5px;cursor:pointer}}@media(max-width:760px){{header{{gap:10px;padding:0 10px}}nav a{{padding:0 8px;font-size:11px}}.run-meta{{display:none}}.split{{grid-template-columns:300px minmax(390px,1fr)}}.detail-stack{{padding:16px}}.source-document{{padding:8px 18px 70px}}}}
.savebar{{position:static;background:transparent;margin-top:4px;padding:16px 0}}
</style></head><body>
<header><div class='brand'><i>Uteki</i> / Eval</div><nav><a class='{'active' if active == 'result' else ''}' href='/result'>{bilingual('Run result','运行结果')}</a><a class='{'active' if active == 'annotate' else ''}' href='/annotate'>{bilingual('Benchmark annotation','Benchmark 标注')}</a></nav><div class='run-meta'>Alphabet · FY2025 10-K · Candidate v0.1</div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>{body}
<script>const body=document.body;function language(v){{body.classList.toggle('zh',v==='zh');document.querySelectorAll('.lang button').forEach(b=>b.classList.toggle('on',b.id===v));localStorage.setItem('uteki-lang',v)}}document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');language(localStorage.getItem('uteki-lang')||'zh');document.querySelectorAll('.toggle').forEach(b=>b.onclick=e=>{{e.stopPropagation();b.closest('li').classList.toggle('collapsed')}});{script}</script></body></html>"""


def render_result_page(data: dict, excerpt: dict, selected: str | None = None) -> str:
    selected = selected if any(item["id"] == selected for item in data["businesses"]) else data["businesses"][0]["id"]
    body = f"""<main class='split'><section class='result-pane'><div class='pane-head'><h1>{bilingual('Extracted business map','提取业务结构')}</h1><p>{bilingual('Select a node; its exact 10-K evidence is highlighted on the right.','点击节点，右侧定位并高亮对应的 10-K 原文。')}</p></div><div class='tree-wrap'>{render_tree(data, selected)}</div><div class='detail-stack'>{render_result_details(data, selected)}</div></section><section class='source-pane'><div class='pane-head source-toolbar'><div><h1>Alphabet FY2025 10-K</h1><p>{bilingual('Authoritative source · evidence review excerpt','权威原文 · 证据审核摘录')}</p></div><a href='{esc(data['evidence'][0]['source_url'])}' target='_blank'>SEC ↗</a></div><div class='source-document'>{render_source(excerpt)}</div></section></main>"""
    script = """function highlight(csv){const ids=new Set(csv.split(',').filter(Boolean));document.querySelectorAll('.source-row').forEach(x=>x.classList.toggle('active',ids.has(x.dataset.paragraph)));const first=document.querySelector('.source-row.active');if(first)first.scrollIntoView({behavior:'smooth',block:'center'})}function selectNode(button){document.querySelectorAll('.tree-node').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.node-detail').forEach(x=>x.classList.remove('active'));button.classList.add('active');document.querySelector(`[data-detail="${button.dataset.select}"]`).classList.add('active');highlight(button.dataset.ordinals)}document.querySelectorAll('.tree-node').forEach(x=>x.onclick=()=>selectNode(x));document.querySelectorAll('.evidence-link').forEach(x=>x.onclick=()=>highlight(x.dataset.jump));selectNode(document.querySelector('.tree-node.active'));"""
    return page_shell("Uteki · Run Result", "result", body, script)


def render_annotation_page(data: dict, reviews: dict, selected: str | None = None) -> str:
    businesses = {item["id"]: item for item in data["businesses"]}
    selected = selected if selected in businesses else data["businesses"][0]["id"]
    parents, _ = parent_and_children(data)
    panels = []
    for item in data["businesses"]:
        review = reviews.get("businesses", {}).get(item["id"], {})
        status = review.get("status", "candidate")
        issues = set(review.get("issues", []))
        verdicts = "".join(f"<label><input type='radio' name='status' value='{value}' {'checked' if status == value else ''}><span>{label}</span></label>" for value, label in (("accepted", "正确"), ("edited", "需要修改"), ("rejected", "错误"), ("ambiguous", "无法判断")))
        issue_html = "".join(f"<label><input type='checkbox' name='issues' value='{value}' {'checked' if value in issues else ''}><span>{label}</span></label>" for value, label in ISSUES)
        parent_options = "".join(f"<option value='{value['id']}' {'selected' if parents.get(item['id']) == value['id'] else ''}>{esc(value['name'])}</option>" for value in data["businesses"] if value["id"] != item["id"])
        panels.append(f"""<form class='annotation-detail {'active' if item['id'] == selected else ''}' data-annotation='{esc(item['id'])}' method='post' action='/review'><input type='hidden' name='item_id' value='{esc(item['id'])}'><div class='detail-kicker'>{esc(item['kind'])}</div><h2>{esc(item['name'])}</h2><p class='lead'>{bilingual(item['description'], ZH_DESCRIPTION.get(item['id'], item['description']))}</p><section class='form-section'><h3>{bilingual('Verdict','审核结论')}</h3><div class='verdicts'>{verdicts}</div></section><section class='form-section'><h3>{bilingual('Issues · select all that apply','问题标签 · 可多选')}</h3><div class='issues'>{issue_html}</div></section><section class='form-section'><h3>{bilingual('Correction','人工修订')}</h3><div class='fields'><label>{bilingual('Name','名称')}<input name='corrected_name' value='{esc(review.get('corrected_name', item['name']))}'></label><label>{bilingual('Parent','父级')}<select name='corrected_parent'><option value=''>—</option>{parent_options}</select></label><label style='grid-column:1/-1'>{bilingual('Description','描述')}<textarea name='corrected_description'>{esc(review.get('corrected_description', item['description']))}</textarea></label><label style='grid-column:1/-1'>{bilingual('Review note','审核说明')}<textarea name='note'>{esc(review.get('note', ''))}</textarea></label></div></section><div class='savebar'><button class='primary' type='submit'>{bilingual('Save & next','保存并查看下一项')}</button></div></form>""")
    done = sum(1 for value in reviews.get("businesses", {}).values() if value.get("status") != "candidate")
    body = f"""<main class='split'><section class='tree-pane'><div class='pane-head'><h1>{bilingual('Business hierarchy','业务层级目录')}</h1><p>{done} / {len(data['businesses'])} {bilingual('reviewed','已审核')}</p></div><div class='tree-wrap'>{render_tree(data, selected)}</div></section><section class='annotation-pane'><div class='pane-head'><h1>{bilingual('Node annotation','节点标注')}</h1><p>{bilingual('Prediction remains immutable; corrections form the Gold draft.','原始结果保持不变；人工修订形成 Gold 草稿。')}</p></div>{''.join(panels)}</section></main>"""
    script = """document.querySelectorAll('.tree-node').forEach(x=>x.onclick=()=>{document.querySelectorAll('.tree-node').forEach(n=>n.classList.remove('active'));document.querySelectorAll('.annotation-detail').forEach(n=>n.classList.remove('active'));x.classList.add('active');document.querySelector(`[data-annotation="${x.dataset.select}"]`).classList.add('active')});"""
    return page_shell("Uteki · Benchmark Annotation", "annotate", body, script)


def render_page(data: dict, reviews: dict) -> str:
    return render_result_page(data, load_json(SOURCE_EXCERPT))


def save_review(item_id: str, status: str, note: str, issues: tuple[str, ...] = (), corrected: dict | None = None) -> None:
    if status not in {"candidate", "accepted", "edited", "rejected", "ambiguous"}:
        raise ValueError("invalid review status")
    REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    value = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {"businesses": {}}
    record = {"status": status, "issues": list(issues), "note": note}
    record.update(corrected or {})
    value.setdefault("businesses", {})[item_id] = record
    temporary = REVIEW_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(REVIEW_FILE)


def make_handler(data_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            data = load_json(data_path)
            reviews = load_json(REVIEW_FILE) if REVIEW_FILE.exists() else {}
            selected = parse_qs(parsed.query).get("selected", [None])[0]
            if parsed.path in {"/", "/result"}:
                body = render_result_page(data, load_json(SOURCE_EXCERPT), selected).encode()
            elif parsed.path == "/annotate":
                body = render_annotation_page(data, reviews, selected).encode()
            else:
                self.send_error(404)
                return
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
            data = load_json(data_path)
            ids = [item["id"] for item in data["businesses"]]
            item_id = fields.get("item_id", [""])[0]
            if item_id not in ids:
                self.send_error(400, "unknown business id")
                return
            corrected = {key: fields.get(key, [""])[0] for key in ("corrected_name", "corrected_parent", "corrected_description")}
            save_review(item_id, fields.get("status", ["candidate"])[0], fields.get("note", [""])[0], tuple(fields.get("issues", [])), corrected)
            next_id = ids[(ids.index(item_id) + 1) % len(ids)]
            self.send_response(303)
            self.send_header("Location", f"/annotate?selected={next_id}")
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
    print(f"Uteki Review Workbench: http://{args.host}:{args.port}/result")
    server.serve_forever()


if __name__ == "__main__":
    main()
