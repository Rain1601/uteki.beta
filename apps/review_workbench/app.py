from __future__ import annotations

import argparse
import html
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA = ROOT / "benchmarks/alphabet_2025_business_map/v0.1-candidate/business_map.json"
CLAIMS_DATA = ROOT / "benchmarks/alphabet_2025_business_map/v0.1-candidate/claims.json"
SPANS_DATA = ROOT / "benchmarks/alphabet_2025_business_map/v0.1-candidate/evidence_spans.json"
SOURCE_EXCERPT = ROOT / "data/source_documents/alphabet_2025_10k/review_excerpt.json"


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


def validate_claims(data: dict, claims_data: dict, excerpt: dict, spans_data: dict | None = None) -> None:
    spans_data = spans_data or load_json(SPANS_DATA)
    business_ids = {item["id"] for item in data["businesses"]}
    evidence = {item["id"]: item for item in data["evidence"]}
    paragraphs = {item["ordinal"]: item for item in excerpt["paragraphs"]}
    claim_ids: set[str] = set()
    expected_links: set[tuple[str, str]] = set()
    for claim in claims_data["claims"]:
        if claim["id"] in claim_ids:
            raise ValueError(f"duplicate claim id: {claim['id']}")
        claim_ids.add(claim["id"])
        if claim["business_id"] not in business_ids:
            raise ValueError(f"unknown business in claim: {claim['id']}")
        if not claim.get("evidence_ids"):
            raise ValueError(f"claim has no evidence: {claim['id']}")
        for evidence_id in claim["evidence_ids"]:
            expected_links.add((claim["id"], evidence_id))
            if evidence_id not in evidence:
                raise ValueError(f"unknown evidence {evidence_id} in claim {claim['id']}")
            reference = evidence[evidence_id]
            paragraph = paragraphs.get(reference["paragraph_ordinal"])
            if not paragraph or paragraph["text_hash"] != reference["text_hash"]:
                raise ValueError(f"evidence does not resolve to source: {evidence_id}")
    actual_links: set[tuple[str, str]] = set()
    for span in spans_data["spans"]:
        key = (span["claim_id"], span["evidence_id"])
        if key in actual_links:
            raise ValueError(f"duplicate evidence span: {key[0]} / {key[1]}")
        actual_links.add(key)
        if key not in expected_links:
            raise ValueError(f"orphan evidence span: {key[0]} / {key[1]}")
        reference = evidence[key[1]]
        paragraph = paragraphs[reference["paragraph_ordinal"]]
        if span["quote_en"] not in paragraph["text"]:
            raise ValueError(f"English quote does not match source: {key[0]} / {key[1]}")
        if span["quote_zh"] not in paragraph["translation_zh"]:
            raise ValueError(f"Chinese quote does not match translation: {key[0]} / {key[1]}")
    missing_links = expected_links - actual_links
    if missing_links:
        claim_id, evidence_id = sorted(missing_links)[0]
        raise ValueError(f"claim evidence has no exact span: {claim_id} / {evidence_id}")


def span_index(spans_data: dict) -> dict[tuple[str, str], dict]:
    return {(item["claim_id"], item["evidence_id"]): item for item in spans_data["spans"]}


def evidence_context(data: dict, excerpt: dict) -> tuple[dict[str, dict], dict[int, dict]]:
    evidence = {item["id"]: item for item in data["evidence"]}
    paragraphs = {item["ordinal"]: item for item in excerpt["paragraphs"]}
    return evidence, paragraphs


def claim_ordinals(claim: dict, evidence: dict[str, dict]) -> list[int]:
    return list(dict.fromkeys(evidence[value]["paragraph_ordinal"] for value in claim["evidence_ids"]))


def preview(value: str, length: int = 92) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= length else normalized[: length - 1].rstrip() + "…"


def render_tree(data: dict, selected: str) -> str:
    businesses = {item["id"]: item for item in data["businesses"]}
    _, children = parent_and_children(data)

    def branch(item_id: str) -> str:
        item = businesses[item_id]
        nested = children.get(item_id, [])
        revenue = next((value for value in item.get("importance_signals", []) if "2025 revenue:" in value), "")
        child_html = "" if not nested else f"<ul>{''.join(branch(value) for value in nested)}</ul>"
        toggle = "<button class='toggle' type='button' aria-label='Toggle'>⌄</button>" if nested else "<span class='toggle-space'></span>"
        return f"""<li data-branch='{esc(item_id)}'>{toggle}<button type='button' class='tree-node {'active' if item_id == selected else ''}' data-select='{esc(item_id)}'>
          <span class='node-main'><strong>{esc(item['name'])}</strong><small>{esc(item['kind'])}</small></span><span class='node-metric'>{esc(revenue.replace('2025 revenue: ', ''))}</span>
        </button>{child_html}</li>"""

    return f"<ul class='tree'>{''.join(branch(value) for value in children.get('__root__', []))}</ul>"


def render_evidence_cards(claim: dict, evidence: dict[str, dict], paragraphs: dict[int, dict], spans: dict[tuple[str, str], dict]) -> str:
    cards = []
    total = len(claim["evidence_ids"])
    for index, evidence_id in enumerate(claim["evidence_ids"], start=1):
        reference = evidence[evidence_id]
        paragraph = paragraphs[reference["paragraph_ordinal"]]
        anchor = spans[(claim["id"], evidence_id)]
        cards.append(f"""<button type='button' class='evidence-card' data-evidence='{esc(evidence_id)}' data-ordinal='{reference['paragraph_ordinal']}'>
          <span class='evidence-index'>{index}/{total}</span><span class='evidence-location'>¶{reference['paragraph_ordinal']} · {bilingual('source','原文')}</span>
          <span class='evidence-snippet' data-quote-en='{esc(anchor['quote_en'])}' data-quote-zh='{esc(anchor['quote_zh'])}'>{bilingual(preview(anchor['quote_en']), preview(anchor['quote_zh']))}</span>
        </button>""")
    return "".join(cards)


def render_knowledge_details(data: dict, claims_data: dict, excerpt: dict, spans_data: dict, selected: str) -> str:
    evidence, paragraphs = evidence_context(data, excerpt)
    spans = span_index(spans_data)
    claims_by_business: dict[str, list[dict]] = {}
    for claim in claims_data["claims"]:
        claims_by_business.setdefault(claim["business_id"], []).append(claim)
    rendered = []
    for item in data["businesses"]:
        claim_rows = []
        for index, claim in enumerate(claims_by_business.get(item["id"], [])):
            ordinals = ",".join(str(value) for value in claim_ordinals(claim, evidence))
            claim_rows.append(f"""<article class='claim {'active' if index == 0 else ''}' data-claim='{esc(claim['id'])}' data-ordinals='{ordinals}'>
              <button type='button' class='claim-main'>
                <span><span class='claim-label'>{bilingual(claim['label_en'], claim['label_zh'])}</span><strong>{bilingual(claim['value_en'], claim['value_zh'])}</strong></span>
                <span class='claim-meta'><i>{bilingual('explicit','明确披露') if claim['basis'] == 'explicit' else bilingual('derived','计算所得')}</i><b>{len(claim['evidence_ids'])} {bilingual('sources','条证据')}</b></span>
              </button>
              <div class='evidence-cards'>{render_evidence_cards(claim, evidence, paragraphs, spans)}</div>
            </article>""")
        rendered.append(f"""<section class='knowledge-detail {'active' if item['id'] == selected else ''}' data-detail='{esc(item['id'])}'>
          <div class='detail-heading'><div class='detail-kicker'>{esc(item['kind'])}</div><h2>{esc(item['name'])}</h2><p>{bilingual('Every statement below is independently traceable.','下方每一条知识均可独立追溯。')}</p></div>
          <div class='claim-list'>{''.join(claim_rows)}</div>
        </section>""")
    return "".join(rendered)


def render_source(excerpt: dict) -> str:
    return "".join(
        f"""<article class='source-row' data-paragraph='{item['ordinal']}'>
          <div class='source-marker'><b>¶{item['ordinal']}</b><span></span></div>
          <div><div class='source-path'>{esc(' › '.join(item['section_path']))}</div>
          <p class='source-translation' lang='zh-CN'>{esc(item['translation_zh'])}</p>
          <div class='original-label'>{bilingual('SEC original','SEC 英文原文')}</div><p class='source-original' lang='en'>{esc(item['text'])}</p>
          <div class='source-hash'>SHA · {esc(item['text_hash'][:12])}</div></div>
        </article>"""
        for item in excerpt["paragraphs"]
    )


def page_shell(body: str) -> str:
    return f"""<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Uteki · Alphabet Standard Answer</title>
<style>
:root{{--ink:#202420;--soft:#555d56;--muted:#79807a;--line:#e1e5e1;--line2:#cbd1cc;--paper:#fff;--wash:#f7f8f6;--green:#1d6548;--green2:#e9f3ed;--yellow:#fff7cf}}*{{box-sizing:border-box}}html,body{{height:100%}}body{{margin:0;background:var(--wash);color:var(--ink);font:13px/1.5 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}button{{font:inherit}}header{{height:54px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 18px;gap:28px}}.brand{{font-weight:750}}.brand i{{font-style:normal;color:var(--green)}}.page-name{{font-weight:650}}.status{{color:var(--green);background:var(--green2);padding:3px 7px;border-radius:4px;font-size:10px}}.meta{{margin-left:auto;color:var(--muted);font-size:11px}}.lang button{{border:0;background:none;color:var(--muted);padding:4px;cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}.split{{height:calc(100vh - 54px);display:grid;grid-template-columns:minmax(430px,45%) minmax(470px,55%)}}.knowledge-pane,.source-pane{{min-width:0;overflow:auto;background:var(--paper)}}.knowledge-pane{{border-right:1px solid var(--line2)}}.pane-head{{position:sticky;top:0;z-index:4;background:#fffd;backdrop-filter:blur(12px);min-height:68px;padding:13px 18px;border-bottom:1px solid var(--line)}}.pane-head h1{{font-size:15px;margin:0}}.pane-head p{{font-size:11px;color:var(--muted);margin:3px 0 0}}.source-head{{display:flex;align-items:center;justify-content:space-between}}.source-head a{{color:var(--green);text-decoration:none}}.tree-wrap{{padding:10px;border-bottom:1px solid var(--line)}}ul.tree,.tree ul{{list-style:none;margin:0;padding-left:0}}.tree ul{{padding-left:20px}}.tree li{{position:relative}}.toggle,.toggle-space{{position:absolute;left:0;top:7px;width:18px;height:22px;border:0;background:none;color:var(--muted);cursor:pointer}}li.collapsed>ul{{display:none}}li.collapsed>.toggle{{transform:rotate(-90deg)}}.tree-node{{width:calc(100% - 20px);margin-left:20px;display:flex;align-items:center;gap:8px;text-align:left;border:0;background:none;padding:6px 8px;border-radius:5px;color:var(--ink);cursor:pointer}}.tree-node:hover{{background:#f2f4f2}}.tree-node.active{{background:var(--green2);color:#174d38}}.node-main{{min-width:0;flex:1}}.node-main strong,.node-main small{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.node-main small{{font:8px ui-monospace,monospace;color:var(--muted);text-transform:uppercase}}.node-metric{{font:10px ui-monospace,monospace;color:var(--muted)}}.knowledge-detail{{display:none;padding:22px 20px 70px}}.knowledge-detail.active{{display:block}}.detail-kicker{{font:9px ui-monospace,monospace;text-transform:uppercase;color:var(--green)}}h2{{font:600 27px/1.2 Georgia,"Songti SC",serif;margin:3px 0 5px}}.detail-heading p{{color:var(--muted);margin:0 0 20px}}.claim-list{{border-top:1px solid var(--line2)}}.claim{{border-bottom:1px solid var(--line)}}.claim-main{{width:100%;border:0;background:#fff;padding:12px 2px;display:flex;align-items:flex-start;justify-content:space-between;gap:14px;text-align:left;color:var(--ink);cursor:pointer}}.claim-main:hover{{background:#fafbf9}}.claim-label{{display:block;color:var(--muted);font-size:10px;margin-bottom:3px}}.claim-main strong{{display:block;font-weight:550;line-height:1.55}}.claim-meta{{flex:none;display:flex;align-items:center;gap:5px;padding-top:2px}}.claim-meta i,.claim-meta b{{font-style:normal;font-weight:500;font-size:9px;padding:3px 5px;border-radius:3px}}.claim-meta i{{color:var(--green);background:var(--green2)}}.claim-meta b{{color:var(--muted);border:1px solid var(--line)}}.evidence-cards{{display:none;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:0 0 12px}}.claim.active .evidence-cards{{display:grid}}.claim.active>.claim-main{{color:var(--green)}}.evidence-card{{border:1px solid var(--line);background:#fbfcfa;color:var(--ink);border-radius:5px;padding:8px;text-align:left;cursor:pointer;min-width:0}}.evidence-card:hover,.evidence-card.active{{border-color:#83a994;background:var(--green2)}}.evidence-index{{font:700 9px ui-monospace,monospace;color:var(--green);margin-right:6px}}.evidence-location{{font-size:9px;color:var(--muted)}}.evidence-snippet{{display:block;margin-top:5px;font:11px/1.45 Georgia,"Songti SC",serif;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}.source-pane{{background:#fafbf9}}.source-notice{{padding:10px 18px;border-bottom:1px solid #eadf9b;background:#fffbed;color:#665c2b;font-size:10px}}.source-document{{max-width:850px;margin:auto;padding:10px 28px 90px;background:#fff;min-height:100%}}.source-empty{{padding:80px 20px;text-align:center;color:var(--muted)}}.source-row{{display:none;grid-template-columns:48px 1fr;padding:24px 0;border-bottom:1px solid var(--line);scroll-margin:100px}}.source-row.relevant{{display:grid}}.source-row.active{{background:var(--yellow);box-shadow:0 0 0 11px var(--yellow)}}.source-marker{{font:10px ui-monospace,monospace;color:var(--muted);padding-top:3px;display:flex;flex-direction:column;align-items:flex-start;gap:8px}}.source-marker span{{width:16px;height:2px;background:var(--line2)}}.source-path{{font-size:10px;color:var(--muted)}}.source-translation{{display:none;font:15px/1.75 Georgia,"Songti SC",serif;margin:8px 0 12px}}body.zh .source-translation{{display:block}}.original-label{{font-size:9px;color:var(--muted);text-transform:uppercase;margin-top:8px}}body:not(.zh) .original-label{{display:none}}.source-original{{font:15px/1.68 Georgia,"Songti SC",serif;margin:6px 0;color:var(--ink)}}body.zh .source-original{{font-size:12px;line-height:1.6;color:var(--muted);padding-left:10px;border-left:2px solid var(--line)}}.source-hash{{font:9px ui-monospace,monospace;color:#989e99;margin-top:9px}}@media(max-width:900px){{header{{gap:10px;padding:0 10px}}.meta{{display:none}}.split{{grid-template-columns:360px minmax(430px,1fr)}}.evidence-cards{{grid-template-columns:1fr}}.source-document{{padding:8px 18px 70px}}}}
body.zh .source-notice[data-lang=zh]{{display:block}}
mark{{background:#ffe36e;color:#1d251f;padding:1px 2px;border-radius:2px}}
</style></head><body>
<header><div class='brand'><i>Uteki</i> / Eval</div><div class='page-name'>{bilingual('Standard answer','标准答案')}</div><span class='status'>Candidate v0.1</span><div class='meta'>Alphabet · FY2025 10-K · field-level provenance</div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>{body}
<script>
const body=document.body;
function language(value){{body.classList.toggle('zh',value==='zh');document.querySelectorAll('.lang button').forEach(button=>button.classList.toggle('on',button.id===value));localStorage.setItem('uteki-lang',value)}}
function markExact(element,needle){{
  if(!element)return;const raw=element.dataset.raw||element.textContent;element.dataset.raw=raw;element.textContent='';const index=needle?raw.indexOf(needle):-1;
  if(index<0){{element.textContent=raw;return}}element.append(document.createTextNode(raw.slice(0,index)));const mark=document.createElement('mark');mark.textContent=needle;element.append(mark,document.createTextNode(raw.slice(index+needle.length)));
}}
function showClaim(claim,focusOrdinal,focusEvidence){{
  document.querySelectorAll('.claim').forEach(value=>value.classList.remove('active'));claim.classList.add('active');
  document.querySelectorAll('.source-original,.source-translation').forEach(value=>{{if(value.dataset.raw)value.textContent=value.dataset.raw}});
  const ordinals=claim.dataset.ordinals.split(',').filter(Boolean);
  document.querySelectorAll('.source-row').forEach(row=>{{row.classList.toggle('relevant',ordinals.includes(row.dataset.paragraph));row.classList.remove('active')}});
  const sourceDocument=document.querySelector('.source-document');ordinals.forEach(ordinal=>{{const value=document.querySelector(`.source-row[data-paragraph="${{ordinal}}"]`);if(value)sourceDocument.appendChild(value)}});
  const target=String(focusOrdinal||ordinals[0]||'');const cards=Array.from(claim.querySelectorAll('.evidence-card'));const activeCard=cards.find(card=>focusEvidence?card.dataset.evidence===focusEvidence:card.dataset.ordinal===target)||cards[0];
  const row=document.querySelector(`.source-row[data-paragraph="${{target}}"]`);if(row){{row.classList.add('active');const anchor=activeCard?.querySelector('.evidence-snippet');markExact(row.querySelector('.source-original'),anchor?.dataset.quoteEn||'');markExact(row.querySelector('.source-translation'),anchor?.dataset.quoteZh||'');row.scrollIntoView({{behavior:'smooth',block:'center'}})}}
  document.querySelectorAll('.evidence-card').forEach(card=>card.classList.toggle('active',card===activeCard));
}}
function selectNode(button){{
  document.querySelectorAll('.tree-node').forEach(value=>value.classList.remove('active'));document.querySelectorAll('.knowledge-detail').forEach(value=>value.classList.remove('active'));button.classList.add('active');
  const detail=document.querySelector(`[data-detail="${{button.dataset.select}}"]`);detail.classList.add('active');const first=detail.querySelector('.claim');if(first)showClaim(first);
}}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');language(localStorage.getItem('uteki-lang')||'zh');
document.querySelectorAll('.toggle').forEach(button=>button.onclick=event=>{{event.stopPropagation();button.closest('li').classList.toggle('collapsed')}});
document.querySelectorAll('.tree-node').forEach(button=>button.onclick=()=>selectNode(button));
document.querySelectorAll('.claim-main').forEach(button=>button.onclick=()=>showClaim(button.closest('.claim')));
document.querySelectorAll('.evidence-card').forEach(button=>button.onclick=event=>{{event.stopPropagation();showClaim(button.closest('.claim'),button.dataset.ordinal,button.dataset.evidence)}});
selectNode(document.querySelector('.tree-node.active'));
</script></body></html>"""


def render_result_page(data: dict, excerpt: dict, selected: str | None = None, claims_data: dict | None = None, spans_data: dict | None = None) -> str:
    claims_data = claims_data or load_json(CLAIMS_DATA)
    spans_data = spans_data or load_json(SPANS_DATA)
    validate_claims(data, claims_data, excerpt, spans_data)
    selected = selected if any(item["id"] == selected for item in data["businesses"]) else data["businesses"][0]["id"]
    body = f"""<main class='split'><section class='knowledge-pane'>
      <div class='pane-head'><h1>{bilingual('Alphabet business knowledge','Alphabet 业务知识')}</h1><p>{bilingual('Choose a node, then verify each statement independently.','选择业务节点，再逐条验证名称、描述、规模和产品组成。')}</p></div>
      <div class='tree-wrap'>{render_tree(data, selected)}</div>{render_knowledge_details(data, claims_data, excerpt, spans_data, selected)}
    </section><section class='source-pane'>
      <div class='pane-head source-head'><div><h1>{bilingual('Evidence source','证据原文')}</h1><p>{bilingual('Only sources for the selected statement are shown.','仅展示当前知识条目对应的出处，不伪装成连续全文。')}</p></div><a href='{esc(data['evidence'][0]['source_url'])}' target='_blank'>SEC ↗</a></div>
      <div class='source-notice' data-lang='zh'>{esc(excerpt['translation']['notice_zh'])}</div><div class='source-document'>{render_source(excerpt)}</div>
    </section></main>"""
    return page_shell(body)


def render_page(data: dict, reviews: dict) -> str:
    return render_result_page(data, load_json(SOURCE_EXCERPT))


def make_handler(data_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/annotate":
                self.send_response(303)
                self.send_header("Location", "/result")
                self.end_headers()
                return
            if parsed.path not in {"/", "/result", "/benchmark"}:
                self.send_error(404)
                return
            selected = parse_qs(parsed.query).get("selected", [None])[0]
            body = render_result_page(
                load_json(data_path),
                load_json(SOURCE_EXCERPT),
                selected,
                load_json(CLAIMS_DATA),
                load_json(SPANS_DATA),
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

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
    print(f"Uteki Standard Answer: http://{args.host}:{args.port}/result")
    server.serve_forever()


if __name__ == "__main__":
    main()
