from __future__ import annotations

import argparse
import gzip
import html
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from apps.review_workbench.company_universe import render_company_universe_page
from apps.review_workbench.company_data import render_company_data, render_document_status
from apps.review_workbench.research_archive_ui import render_archive
from apps.review_workbench.visual_system import workbench_page, theme_html
from apps.review_workbench.research_archive_import import import_rows
from uteki.agents.research_archive import Store, ArchiveError, ConflictError
from apps.review_workbench.document_library import index_url, resolve_index
from uteki.agents.material_library import load_catalog
from apps.review_workbench.earnings_reader import render_transcript
from apps.review_workbench.cloud_spike import render_cloud_spike
from apps.review_workbench.cloud_analysis import render_cloud_analysis
from apps.review_workbench.document_index import (
    load_jsonl,
    render_document_index_page,
    render_index_source_document,
)


ROOT = Path(__file__).resolve().parents[2]
RESEARCH_DATA_DIR = ROOT / "data/research_data/alphabet_2025_10k/v0.2-candidate"
DEFAULT_DATA = RESEARCH_DATA_DIR / "business_map.json"
EVIDENCE_BUNDLE_DATA = RESEARCH_DATA_DIR / "evidence_bundle.json"
RESEARCH_DATA_MANIFEST = RESEARCH_DATA_DIR / "manifest.json"
SOURCE_EXCERPT = ROOT / "data/source_documents/alphabet_2025_10k/review_excerpt.json"
RAW_SOURCE_GZIP = ROOT / "data/source_documents/alphabet_2025_10k/source.html.gz"
SOURCE_MANIFEST = RAW_SOURCE_GZIP.parent / "manifest.json"
SOURCE_ASSETS = RAW_SOURCE_GZIP.parent / "assets"
DOCUMENT_INDEX_DIR = RAW_SOURCE_GZIP.parent / "indexes/v0.1"
DOCUMENT_INDEX_MANIFEST = DOCUMENT_INDEX_DIR / "manifest.json"
DOCUMENT_INDEX_DATA = DOCUMENT_INDEX_DIR / "index.json"
DOCUMENT_BLOCKS_DATA = DOCUMENT_INDEX_DIR / "blocks.jsonl"
DOCUMENT_ASSETS_DATA = DOCUMENT_INDEX_DIR / "assets.json"
COMPANY_UNIVERSE_DATA = ROOT / "data/company_universe/v0.1-candidate/companies.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def evidence_bundle_views(bundle: dict) -> tuple[dict, dict]:
    """Expose the published bundle through the legacy read-only UI view shape."""
    source_snapshot_ids = bundle.get("source_snapshot_ids", [])
    source_snapshot_id = source_snapshot_ids[0] if source_snapshot_ids else None
    claims = {
        "schema_version": bundle["schema_version"],
        "source_snapshot_id": source_snapshot_id,
        "claims": bundle["claims"],
    }
    spans = {
        "schema_version": bundle["schema_version"],
        "source_snapshot_id": source_snapshot_id,
        "spans": [
            {
                "claim_id": item["claim_id"],
                "evidence_id": item["evidence_id"],
                "quote_en": item["quote_en"],
                "quote_zh": item["quote_zh"],
            }
            for item in bundle["evidence_links"]
        ],
    }
    return claims, spans


def document_index_status_label(manifest: dict) -> str:
    version = manifest["index_version"]
    return f"Index {version} · Frozen" if manifest["status"] == "frozen" else f"Index Candidate {version.removesuffix('-candidate')}"


def esc(value: object) -> str:
    return html.escape(str(value))


def bilingual(en: object, zh: object) -> str:
    return f"<span data-lang='en'>{esc(en)}</span><span data-lang='zh'>{esc(zh)}</span>"


def render_original_source_document(raw_html: str, excerpt: dict) -> str:
    """Add a read-only evidence bridge to the immutable SEC filing HTML."""
    evidence_blocks = [
        {
            "ordinal": item["ordinal"],
            "text": item["text"],
            "translation_zh": item["translation_zh"],
        }
        for item in excerpt["paragraphs"]
    ]
    payload = json.dumps(evidence_blocks, ensure_ascii=False).replace("</", "<\\/")
    bridge = f"""<style id="uteki-source-style">
html{{scroll-behavior:smooth}}body{{padding-top:36px!important}}
#uteki-source-status{{position:fixed;z-index:2147483647;left:0;right:0;top:0;height:36px;display:flex;align-items:center;gap:9px;padding:0 14px;background:#f3f7f4;border-bottom:1px solid #cbd7cf;color:#365244;font:11px/1.2 Arial,sans-serif}}
#uteki-source-status b{{color:#175c3f}}#uteki-source-status span:last-child{{margin-left:auto;color:#6d756f}}
[data-uteki-covered].uteki-focus,.uteki-translation.uteki-focus{{outline:3px solid #e7c53b!important;outline-offset:5px;background:#fff8cf!important}}
.uteki-translation{{display:none;margin:8pt 0;padding:10pt 12pt;border-left:3px solid #2b7657;background:#f2f8f4;color:#17231c;font-family:Arial,'PingFang SC',sans-serif;font-size:10pt;line-height:1.65;text-align:left}}
.uteki-translation:before{{content:'中文候选译文 · 对应 SEC 原文';display:block;margin-bottom:5pt;color:#2b7657;font-size:7.5pt;font-weight:700;letter-spacing:.04em}}
body.uteki-zh .uteki-translation{{display:block}}body.uteki-zh [data-uteki-covered]:not([data-uteki-table]){{display:none!important}}
body:not(.uteki-zh) .uteki-translation{{display:none!important}}
::highlight(uteki-evidence){{background:#ffe36e;color:#101713}}
.uteki-exact-fallback{{background:#ffe36e!important;color:#101713!important}}
</style><script id="uteki-source-bridge">
const UTEKI_BLOCKS={payload};
const normalize=value=>(value||'').replace(/\\u00a0/g,' ').replace(/\\s+/g,' ').trim();
const compact=value=>normalize(value).replace(/\\s/g,'');
const blockByOrdinal=new Map();
let currentLanguage='zh';
let fallbackHighlights=[];
function textMap(root){{
  const walker=document.createTreeWalker(root,4,{{acceptNode(node){{
    return node.parentElement?.closest('#uteki-source-status,.uteki-translation')?2:1;
  }}}});
  let output='',node,mapping=[];
  while(node=walker.nextNode()){{
    for(let offset=0;offset<node.data.length;offset++){{
      const char=node.data[offset];
      if(/\\s/.test(char))continue;
      output+=char;mapping.push({{node,offset}});
    }}
  }}
  return {{text:output.trim(),mapping}};
}}
function locateBlocks(){{
  const elements=Array.from(document.querySelectorAll('body div,body p,body li,body td'));
  for(const block of UTEKI_BLOCKS){{
    const needle=compact(block.text);
    const target=elements
      .filter(element=>!element.closest('#uteki-source-status,.uteki-translation')&&compact(element.textContent).includes(needle))
      .sort((left,right)=>normalize(left.textContent).length-normalize(right.textContent).length)[0];
    if(!target)continue;
    target.dataset.utekiOrdinals=[target.dataset.utekiOrdinals,block.ordinal].filter(Boolean).join(',');target.dataset.utekiCovered='true';
    if(target.querySelector('table'))target.dataset.utekiTable='true';
    const translation=document.createElement('div');translation.className='uteki-translation';translation.dataset.utekiOrdinal=block.ordinal;translation.textContent=block.translation_zh;
    target.before(translation);blockByOrdinal.set(String(block.ordinal),{{target,translation}});
  }}
}}
function highlight(root,quote){{
  if(!root||!quote)return;
  const needle=compact(quote);if(!compact(root.textContent).includes(needle))return;
  if(window.CSS?.highlights){{
    const value=textMap(root),start=value.text.indexOf(needle),first=value.mapping[start],last=value.mapping[start+needle.length-1];if(!first||!last)return;
    const range=document.createRange();range.setStart(first.node,first.offset);range.setEnd(last.node,last.offset+1);CSS.highlights.set('uteki-evidence',new Highlight(range));return;
  }}
  const candidates=[...root.querySelectorAll('span,td,th')].filter(element=>{{const value=compact(element.textContent);return value&&(needle.includes(value)||value.includes(needle))}});
  fallbackHighlights=candidates.filter(element=>!candidates.some(other=>other!==element&&element.contains(other)));if(!fallbackHighlights.length)fallbackHighlights=[root];fallbackHighlights.forEach(element=>element.classList.add('uteki-exact-fallback'));
}}
function clearHighlight(){{
  if(window.CSS?.highlights)CSS.highlights.delete('uteki-evidence');
  fallbackHighlights.forEach(element=>element.classList.remove('uteki-exact-fallback'));fallbackHighlights=[];
}}
function focusEvidence(message){{
  currentLanguage=message.language||currentLanguage;document.body.classList.toggle('uteki-zh',currentLanguage==='zh');
  document.querySelectorAll('.uteki-focus').forEach(value=>value.classList.remove('uteki-focus'));clearHighlight();
  const block=blockByOrdinal.get(String(message.ordinal));if(!block)return;
  const target=currentLanguage==='zh'?block.translation:block.target;target.classList.add('uteki-focus');highlight(target,currentLanguage==='zh'?message.quoteZh:message.quoteEn);target.scrollIntoView({{behavior:'smooth',block:'center'}});
}}
window.addEventListener('message',event=>{{if(event.data?.type==='uteki-focus')focusEvidence(event.data);if(event.data?.type==='uteki-language'){{currentLanguage=event.data.language;document.body.classList.toggle('uteki-zh',currentLanguage==='zh')}}}});
window.addEventListener('DOMContentLoaded',()=>{{
  const status=document.createElement('div');status.id='uteki-source-status';status.innerHTML=`<b>SEC 10-K · 原始版式</b><span>中文证据译文 ${{UTEKI_BLOCKS.length}} / 1311</span><span>未覆盖内容保留英文</span>`;document.body.prepend(status);locateBlocks();parent.postMessage({{type:'uteki-source-ready',located:blockByOrdinal.size,total:UTEKI_BLOCKS.length}},'*');
}});
</script>"""
    marker = "</head>"
    if marker not in raw_html.lower():
        raise ValueError("SEC source HTML has no closing head element")
    position = raw_html.lower().index(marker)
    return raw_html[:position] + bridge + raw_html[position:]


def parent_and_children(data: dict) -> tuple[dict[str, str], dict[str, list[str]]]:
    hierarchy_kinds = {"reported_under", "part_of", "revenue_component_of"}
    parents: dict[str, str] = {}
    for relationship in data["relationships"]:
        if relationship["kind"] not in hierarchy_kinds:
            continue
        source_id = relationship["source_id"]
        if source_id in parents:
            raise ValueError(f"business has multiple hierarchy parents: {source_id}")
        parents[source_id] = relationship["target_id"]
    children: dict[str, list[str]] = {}
    for item in data["businesses"]:
        children.setdefault(parents.get(item["id"], "__root__"), []).append(item["id"])
    return parents, children


def validate_claims(data: dict, claims_data: dict, excerpt: dict, spans_data: dict | None = None) -> None:
    if spans_data is None:
        _, spans_data = evidence_bundle_views(load_json(EVIDENCE_BUNDLE_DATA))
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


def research_data_status_label(manifest: dict) -> str:
    version = manifest["release_version"].removesuffix("-candidate")
    return f"Data {version} · Frozen" if manifest["status"] == "frozen" else f"Data candidate {version}"


def page_shell(body: str, data: dict, bundle: dict, release_manifest: dict) -> str:
    counts = release_manifest["counts"]
    metadata = f"""Alphabet · FY2025 10-K · Business Map {esc(bundle['business_map_version'])} · {counts['claims']} {bilingual('claims','条 Claims')} · {counts['metrics']} {bilingual('metrics','项 Metrics')} · {counts['evidence_links']} {bilingual('evidence','条 Evidence')}"""
    return f"""<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Uteki · Alphabet Data Agent Result</title>
<style>
:root{{--ink:#202420;--soft:#555d56;--muted:#79807a;--line:#e1e5e1;--line2:#cbd1cc;--paper:#fff;--wash:#f7f8f6;--green:#1d6548;--green2:#e9f3ed;--yellow:#fff7cf}}*{{box-sizing:border-box}}html,body{{height:100%}}body{{margin:0;background:var(--wash);color:var(--ink);font:13px/1.5 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}}[data-lang=zh]{{display:none}}body.zh [data-lang=en]{{display:none}}body.zh [data-lang=zh]{{display:inline}}button{{font:inherit}}header{{height:54px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 18px;gap:28px}}.brand{{font-weight:750}}.brand i{{font-style:normal;color:var(--green)}}.page-name{{font-weight:650}}.status{{color:var(--green);background:var(--green2);padding:3px 7px;border-radius:4px;font-size:10px}}.meta{{margin-left:auto;color:var(--muted);font-size:11px}}.lang button{{border:0;background:none;color:var(--muted);padding:4px;cursor:pointer}}.lang button.on{{color:var(--ink);font-weight:700}}.split{{height:calc(100vh - 54px);display:grid;grid-template-columns:minmax(430px,45%) minmax(470px,55%)}}.knowledge-pane,.source-pane{{min-width:0;background:var(--paper)}}.knowledge-pane{{overflow:auto;border-right:1px solid var(--line2)}}.source-pane{{overflow:hidden;display:flex;flex-direction:column;background:#fafbf9}}.pane-head{{position:sticky;top:0;z-index:4;background:#fffd;backdrop-filter:blur(12px);min-height:68px;padding:13px 18px;border-bottom:1px solid var(--line)}}.pane-head h1{{font-size:15px;margin:0}}.pane-head p{{font-size:11px;color:var(--muted);margin:3px 0 0}}.source-head{{position:relative;flex:none;display:flex;align-items:center;justify-content:space-between;gap:12px}}.source-actions{{display:flex;align-items:center;gap:8px}}.source-head a{{color:var(--green);text-decoration:none}}.view-switch{{display:flex;border:1px solid var(--line2);border-radius:5px;padding:2px;background:#f3f5f2}}.view-switch button{{border:0;background:transparent;color:var(--muted);padding:4px 8px;border-radius:3px;font-size:10px;cursor:pointer}}.view-switch button.on{{background:#fff;color:var(--ink);font-weight:650;box-shadow:0 1px 2px #0001}}.tree-wrap{{padding:10px;border-bottom:1px solid var(--line)}}ul.tree,.tree ul{{list-style:none;margin:0;padding-left:0}}.tree ul{{padding-left:20px}}.tree li{{position:relative}}.toggle,.toggle-space{{position:absolute;left:0;top:7px;width:18px;height:22px;border:0;background:none;color:var(--muted);cursor:pointer}}li.collapsed>ul{{display:none}}li.collapsed>.toggle{{transform:rotate(-90deg)}}.tree-node{{width:calc(100% - 20px);margin-left:20px;display:flex;align-items:center;gap:8px;text-align:left;border:0;background:none;padding:6px 8px;border-radius:5px;color:var(--ink);cursor:pointer}}.tree-node:hover{{background:#f2f4f2}}.tree-node.active{{background:var(--green2);color:#174d38}}.node-main{{min-width:0;flex:1}}.node-main strong,.node-main small{{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.node-main small{{font:8px ui-monospace,monospace;color:var(--muted);text-transform:uppercase}}.node-metric{{font:10px ui-monospace,monospace;color:var(--muted)}}.knowledge-detail{{display:none;padding:22px 20px 70px}}.knowledge-detail.active{{display:block}}.detail-kicker{{font:9px ui-monospace,monospace;text-transform:uppercase;color:var(--green)}}h2{{font:600 27px/1.2 Georgia,"Songti SC",serif;margin:3px 0 5px}}.detail-heading p{{color:var(--muted);margin:0 0 20px}}.claim-list{{border-top:1px solid var(--line2)}}.claim{{border-bottom:1px solid var(--line)}}.claim-main{{width:100%;border:0;background:#fff;padding:12px 2px;display:flex;align-items:flex-start;justify-content:space-between;gap:14px;text-align:left;color:var(--ink);cursor:pointer}}.claim-main:hover{{background:#fafbf9}}.claim-label{{display:block;color:var(--muted);font-size:10px;margin-bottom:3px}}.claim-main strong{{display:block;font-weight:550;line-height:1.55}}.claim-meta{{flex:none;display:flex;align-items:center;gap:5px;padding-top:2px}}.claim-meta i,.claim-meta b{{font-style:normal;font-weight:500;font-size:9px;padding:3px 5px;border-radius:3px}}.claim-meta i{{color:var(--green);background:var(--green2)}}.claim-meta b{{color:var(--muted);border:1px solid var(--line)}}.evidence-cards{{display:none;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;padding:0 0 12px}}.claim.active .evidence-cards{{display:grid}}.claim.active>.claim-main{{color:var(--green)}}.evidence-card{{border:1px solid var(--line);background:#fbfcfa;color:var(--ink);border-radius:5px;padding:8px;text-align:left;cursor:pointer;min-width:0}}.evidence-card:hover,.evidence-card.active{{border-color:#83a994;background:var(--green2)}}.evidence-index{{font:700 9px ui-monospace,monospace;color:var(--green);margin-right:6px}}.evidence-location{{font-size:9px;color:var(--muted)}}.evidence-snippet{{display:block;margin-top:5px;font:11px/1.45 Georgia,"Songti SC",serif;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}}.source-notice{{padding:10px 18px;border-bottom:1px solid #eadf9b;background:#fffbed;color:#665c2b;font-size:10px}}.structured-view{{display:none;min-height:0;flex:1;overflow:auto}}body.view-structured .structured-view{{display:block}}.source-document{{max-width:850px;margin:auto;padding:10px 28px 90px;background:#fff;min-height:100%}}.original-frame{{display:none;width:100%;min-height:0;flex:1;border:0;background:#fff}}body.view-original .original-frame{{display:block}}.source-empty{{padding:80px 20px;text-align:center;color:var(--muted)}}.source-row{{display:none;grid-template-columns:48px 1fr;padding:24px 0;border-bottom:1px solid var(--line);scroll-margin:100px}}.source-row.relevant{{display:grid}}.source-row.active{{background:var(--yellow);box-shadow:0 0 0 11px var(--yellow)}}.source-marker{{font:10px ui-monospace,monospace;color:var(--muted);padding-top:3px;display:flex;flex-direction:column;align-items:flex-start;gap:8px}}.source-marker span{{width:16px;height:2px;background:var(--line2)}}.source-path{{font-size:10px;color:var(--muted)}}.source-translation{{display:none;font:15px/1.75 Georgia,"Songti SC",serif;margin:8px 0 12px}}body.zh .source-translation{{display:block}}.original-label{{font-size:9px;color:var(--muted);text-transform:uppercase;margin-top:8px}}body:not(.zh) .original-label{{display:none}}.source-original{{font:15px/1.68 Georgia,"Songti SC",serif;margin:6px 0;color:var(--ink)}}body.zh .source-original{{font-size:12px;line-height:1.6;color:var(--muted);padding-left:10px;border-left:2px solid var(--line)}}.source-hash{{font:9px ui-monospace,monospace;color:#989e99;margin-top:9px}}@media(max-width:900px){{header{{gap:10px;padding:0 10px}}.meta{{display:none}}.split{{grid-template-columns:360px minmax(430px,1fr)}}.evidence-cards{{grid-template-columns:1fr}}.source-document{{padding:8px 18px 70px}}}}
body.zh .source-notice[data-lang=zh]{{display:block}}
mark{{background:#ffe36e;color:#1d251f;padding:1px 2px;border-radius:2px}}
</style></head><body>
<header><div class='brand'><i>Uteki</i> / Data</div><div class='page-name'>{bilingual('Data Agent result','Data Agent 解析结果')}</div><span class='status'>{esc(research_data_status_label(release_manifest))}</span><div class='meta'>{metadata}</div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>{body}
<script>
const body=document.body;
let currentLanguage='zh',currentView='original',currentFocus=null,sourceReady=false;
const sourceFrame=document.querySelector('.original-frame');
function sendToSource(message){{if(sourceReady&&sourceFrame?.contentWindow)sourceFrame.contentWindow.postMessage(message,'*')}}
function language(value){{currentLanguage=value;body.classList.toggle('zh',value==='zh');document.querySelectorAll('.lang button').forEach(button=>button.classList.toggle('on',button.id===value));localStorage.setItem('uteki-lang',value);sendToSource({{type:'uteki-language',language:value}});if(currentFocus)sendFocus()}}
function setView(value){{currentView=value;body.classList.toggle('view-original',value==='original');body.classList.toggle('view-structured',value==='structured');document.querySelectorAll('.view-switch button').forEach(button=>button.classList.toggle('on',button.dataset.view===value));localStorage.setItem('uteki-source-view',value);if(value==='original'&&currentFocus)sendFocus();if(value==='structured'&&currentFocus)focusStructured(currentFocus)}}
function sendFocus(){{if(!currentFocus)return;sendToSource({{type:'uteki-focus',language:currentLanguage,ordinal:currentFocus.ordinal,quoteEn:currentFocus.quoteEn,quoteZh:currentFocus.quoteZh}})}}
function markExact(element,needle){{
  if(!element)return;const raw=element.dataset.raw||element.textContent;element.dataset.raw=raw;element.textContent='';const index=needle?raw.indexOf(needle):-1;
  if(index<0){{element.textContent=raw;return}}element.append(document.createTextNode(raw.slice(0,index)));const mark=document.createElement('mark');mark.textContent=needle;element.append(mark,document.createTextNode(raw.slice(index+needle.length)));
}}
function focusStructured(focus){{
  const row=document.querySelector(`.source-row[data-paragraph="${{focus.ordinal}}"]`);if(!row)return;
  row.classList.add('active');markExact(row.querySelector('.source-original'),focus.quoteEn);markExact(row.querySelector('.source-translation'),focus.quoteZh);row.scrollIntoView({{behavior:'smooth',block:'center'}});
}}
function showClaim(claim,focusOrdinal,focusEvidence){{
  document.querySelectorAll('.claim').forEach(value=>value.classList.remove('active'));claim.classList.add('active');
  document.querySelectorAll('.source-original,.source-translation').forEach(value=>{{if(value.dataset.raw)value.textContent=value.dataset.raw}});
  const ordinals=claim.dataset.ordinals.split(',').filter(Boolean);
  document.querySelectorAll('.source-row').forEach(row=>{{row.classList.toggle('relevant',ordinals.includes(row.dataset.paragraph));row.classList.remove('active')}});
  const sourceDocument=document.querySelector('.source-document');ordinals.forEach(ordinal=>{{const value=document.querySelector(`.source-row[data-paragraph="${{ordinal}}"]`);if(value)sourceDocument.appendChild(value)}});
  const target=String(focusOrdinal||ordinals[0]||'');const cards=Array.from(claim.querySelectorAll('.evidence-card'));const activeCard=cards.find(card=>focusEvidence?card.dataset.evidence===focusEvidence:card.dataset.ordinal===target)||cards[0];
  const anchor=activeCard?.querySelector('.evidence-snippet');currentFocus={{ordinal:target,quoteEn:anchor?.dataset.quoteEn||'',quoteZh:anchor?.dataset.quoteZh||''}};
  if(currentView==='structured')focusStructured(currentFocus);else sendFocus();
  document.querySelectorAll('.evidence-card').forEach(card=>card.classList.toggle('active',card===activeCard));
}}
function selectNode(button){{
  document.querySelectorAll('.tree-node').forEach(value=>value.classList.remove('active'));document.querySelectorAll('.knowledge-detail').forEach(value=>value.classList.remove('active'));button.classList.add('active');
  const detail=document.querySelector(`[data-detail="${{button.dataset.select}}"]`);detail.classList.add('active');const first=detail.querySelector('.claim');if(first)showClaim(first);
}}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');
document.querySelectorAll('.view-switch button').forEach(button=>button.onclick=()=>setView(button.dataset.view));
document.querySelectorAll('.toggle').forEach(button=>button.onclick=event=>{{event.stopPropagation();button.closest('li').classList.toggle('collapsed')}});
document.querySelectorAll('.tree-node').forEach(button=>button.onclick=()=>selectNode(button));
document.querySelectorAll('.claim-main').forEach(button=>button.onclick=()=>showClaim(button.closest('.claim')));
document.querySelectorAll('.evidence-card').forEach(button=>button.onclick=event=>{{event.stopPropagation();showClaim(button.closest('.claim'),button.dataset.ordinal,button.dataset.evidence)}});
window.addEventListener('message',event=>{{if(event.data?.type==='uteki-source-ready'){{sourceReady=true;sendFocus()}}}});
language(localStorage.getItem('uteki-lang')||'zh');setView(localStorage.getItem('uteki-source-view')||'original');
selectNode(document.querySelector('.tree-node.active'));
</script></body></html>"""


@workbench_page('result')
def render_result_page(
    data: dict,
    excerpt: dict,
    selected: str | None = None,
    claims_data: dict | None = None,
    spans_data: dict | None = None,
    bundle: dict | None = None,
    release_manifest: dict | None = None,
) -> str:
    bundle = bundle or load_json(EVIDENCE_BUNDLE_DATA)
    release_manifest = release_manifest or load_json(RESEARCH_DATA_MANIFEST)
    bundle_claims, bundle_spans = evidence_bundle_views(bundle)
    claims_data = claims_data or bundle_claims
    spans_data = spans_data or bundle_spans
    validate_claims(data, claims_data, excerpt, spans_data)
    selected = selected if any(item["id"] == selected for item in data["businesses"]) else data["businesses"][0]["id"]
    body = f"""<main class='split'><section class='knowledge-pane'>
      <div class='pane-head'><h1>{bilingual('Structured research data','结构化研究数据')}</h1><p>{bilingual('Business Map is one view of the published Data Snapshot.','Business Map 是已发布 Data Snapshot 的一个视图。')} · {esc(bundle['data_snapshot_id'])} · {esc(bundle['bundle_id'])}</p></div>
      <div class='tree-wrap'>{render_tree(data, selected)}</div>{render_knowledge_details(data, claims_data, excerpt, spans_data, selected)}
    </section><section class='source-pane'>
      <div class='pane-head source-head'><div><h1>{bilingual('Evidence source','证据原文')}</h1><p>{bilingual('Same evidence, two reading modes.','同一条证据，两种阅读方式。')}</p></div><div class='source-actions'><div class='view-switch'><button type='button' data-view='original'>{bilingual('Original layout','原始版式')}</button><button type='button' data-view='structured'>{bilingual('Structured','结构化')}</button></div><a href='{esc(data['evidence'][0]['source_url'])}' target='_blank'>SEC ↗</a></div></div>
      <iframe class='original-frame' title='{esc('SEC original filing layout')}' src='/source/original' sandbox='allow-scripts allow-same-origin allow-popups'></iframe>
      <div class='structured-view'><div class='source-notice' data-lang='zh'>{esc(excerpt['translation']['notice_zh'])}</div><div class='source-document'>{render_source(excerpt)}</div></div>
    </section></main>"""
    return page_shell(body, data, bundle, release_manifest)


def render_page(data: dict, reviews: dict) -> str:
    return render_result_page(data, load_json(SOURCE_EXCERPT))


def make_handler(data_path: Path, archive_path: Path | None = None):
    archive = Store(archive_path or ROOT / 'data/research_archive/state.json')
    imports = import_rows(ROOT)
    archive.migrate_researchers({row['id']: {key: row[key] for key in ('researcher_id', 'researcher_label', 'config_version')} for row in imports}, dry_run=False)
    archive.seed(imports)
    class Handler(BaseHTTPRequestHandler):
        def archive_json(self, body, status=200):
            payload = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(payload)

        def do_POST(self):
            path = urlparse(self.path).path
            if path not in {'/api/research-archive', '/api/research-annotations'}:
                self.send_error(404); return
            host = self.headers.get('Host', '')
            origin = self.headers.get('Origin')
            if (urlparse('http://' + host).hostname not in {'localhost', '127.0.0.1', '::1'}
                    or (origin is not None and origin != 'http://' + host)
                    or self.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or self.headers.get('X-Uteki-Request') != '1'
                    or self.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
                self.archive_json({'error': 'Same-origin JSON requests only'}, 403); return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 100000:
                    raise ArchiveError('Invalid request size')
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ArchiveError('Expected a JSON object')
                snapshot_id = data.pop('snapshot_id')
                action = data.pop('action')
                revision = data.pop('expected_revision')
                if action == 'agent_edit':
                    raise ArchiveError('Agent revisions must come from a recorded local run')
                for protected in ('agent_provenance', 'editor_type', 'citation_errors'):
                    data.pop(protected, None)
                data.pop('actor', None)
                operation = archive.annotate if path == '/api/research-annotations' else archive.act
                self.archive_json(operation(snapshot_id, action, revision, **data))
            except ConflictError as error:
                self.archive_json({'error': str(error)}, 409)
            except (ArchiveError, KeyError, TypeError, ValueError) as error:
                self.archive_json({'error': str(error)}, 400)

        def workspace_route(self, parsed):
            """Canonical product pages; legacy research URLs remain readable."""
            from apps.review_workbench.site_navigation import (
                render_company_overview, render_materials, render_structured,
                render_reports, company_tabs, crumb)
            from urllib.parse import unquote
            path = parsed.path
            query = parse_qs(parsed.query)
            def send(page, content_type='text/html; charset=utf-8'):
                body = page.encode() if isinstance(page, str) else page
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
            if path == '/':
                from apps.review_workbench.attention_dashboard import render_dashboard
                send(render_dashboard(load_json(COMPANY_UNIVERSE_DATA), archive.list()))
                return True
            legacy_target = None
            if path in {'/result', '/benchmark'} and not query.get('view'):
                legacy_target = '/companies/alphabet/data/business-map' + ('?' + parsed.query if parsed.query else '')
            elif path == '/data':
                from urllib.parse import quote
                legacy_target = '/companies/' + quote(query.get('company', ['alphabet'])[0], safe='') + '/data'
            elif path.startswith('/companies/') and len(path.strip('/').split('/')) == 2 and query.get('tab') == ['data']:
                legacy_target = path + '/data'
            if legacy_target:
                self.send_response(303)
                self.send_header('Location', legacy_target)
                self.end_headers()
                return True
            parts = path.strip('/').split('/')
            if len(parts) < 2 or parts[0] != 'companies' or 'documents' in parts:
                return False
            companies = load_json(COMPANY_UNIVERSE_DATA)['companies']
            company = next((c for c in companies if c['id'] == parts[1]), None)
            if company is None:
                self.send_error(404, 'Unknown company'); return True
            section = '/'.join(parts[2:])
            # Preserve bookmarks with an explicit legacy selection.
            if not section and query:
                return False
            catalog = load_catalog(ROOT) if company['id'] == 'alphabet' else {'documents': []}
            rows = archive.list(company=company['id'])
            bundle = load_json(EVIDENCE_BUNDLE_DATA) if company['id'] == 'alphabet' else None
            if not section:
                send(render_company_overview(company, rows, catalog, bundle))
            elif section == 'materials' or section.startswith('materials/pdf/'):
                library = ROOT / 'data/reading_library' / company['id']
                manifest = library / 'download_manifest.json'
                docs = load_json(manifest).get('documents', []) if manifest.exists() else []
                docs = [d for d in docs if d.get('status') == 'downloaded' and d.get('path')]
                if section == 'materials':
                    send(render_materials(company, catalog, docs))
                else:
                    identity = unquote(section.removeprefix('materials/pdf/'))
                    doc = next((d for d in docs if Path(d['path']).stem == identity), None)
                    target = (library / doc['path']).resolve() if doc else None
                    if target is None or not target.is_relative_to(library.resolve()) or not target.is_file():
                        self.send_error(404, 'Unknown PDF'); return True
                    send(target.read_bytes(), 'application/pdf')
            elif section == 'data':
                send(render_structured(company, bundle))
            elif section == 'data/business-map' and company['id'] == 'alphabet':
                page = render_result_page(load_json(data_path), load_json(SOURCE_EXCERPT),
                    query.get('selected', [None])[0], bundle=bundle,
                    release_manifest=load_json(RESEARCH_DATA_MANIFEST))
                context = '<div class="company-context">' + crumb(company, ('业务图', 'Business map')) + company_tabs(company['id'], 'data') + '</div>'
                page = page.replace('</nav>', '</nav>' + context, 1)
                send(page)
            elif section == 'reports' and not query:
                send(render_reports(rows, company))
            elif section == 'reports' or section.startswith('reports/'):
                identity = unquote(section.removeprefix('reports/')) if section != 'reports' else query.get('snapshot', [None])[0]
                if identity and not any(r['id'] == identity for r in rows):
                    self.send_error(404, 'Unknown company report'); return True
                send(render_archive(company, rows, identity,
                    documents={d['id']: d for d in catalog.get('documents', [])},
                    researcher_id=query.get('researcher', [None])[0], scope=query.get('scope', [None])[0],
                    material_id=query.get('material', [None])[0]))
            else:
                self.send_error(404, 'Unknown company section')
            return True

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if self.workspace_route(parsed):
                return
            if parsed.path == '/api/research-annotations':
                try:
                    self.archive_json(archive.annotations(parse_qs(parsed.query).get('snapshot_id', [''])[0]))
                except ArchiveError as error:
                    self.archive_json({'error': str(error)}, 400)
                return
            if parsed.path == '/api/research-archive':
                query = parse_qs(parsed.query)
                self.archive_json({'snapshots': archive.list(company='alphabet', scope=query.get('scope', [None])[0], researcher_id=query.get('researcher', [None])[0])}); return
            if parsed.path == '/api/research-archive/context':
                query = parse_qs(parsed.query)
                try:
                    from uteki.agents.research_archive_context import build_context
                    documents={d['id']:d for d in load_catalog(ROOT)['documents']}
                    material_id=query.get('material',[None])[0]
                    if material_id and material_id not in documents:
                        raise ArchiveError('Unknown current material')
                    self.archive_json(build_context(archive, 'alphabet', query.get('scope', ['company-drivers'])[0],
                        query.get('cutoff', [''])[0], strict=query.get('mode', ['strict'])[0] != 'retrospective', researcher_id=query.get('researcher', [None])[0],
                        material=documents.get(material_id),document_metadata=documents if material_id else None,
                        rerun_from=query.get('rerun_from',[None])[0]))
                except (ArchiveError, ValueError) as error:
                    self.archive_json({'error': str(error)}, 400)
                return
            if parsed.path == '/experiments':
                from html import escape
                runs = sorted((ROOT/'experiments/analysis_comparison').glob('*/review.html'))
                body = ('<!doctype html><meta charset="utf-8"><h1>分析实验</h1><a href="/result">返回研究结果</a><ul>'+''.join('<li><a href="/experiments/'+escape(p.parent.name)+'/review.html">'+escape(p.parent.name)+'</a></li>' for p in runs)+'</ul>').encode()
                body = theme_html(body.decode(), 'experiment').encode()
                self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8'); self.end_headers(); self.wfile.write(body)
                return
            if parsed.path.startswith('/experiments/'):
                from urllib.parse import unquote
                base=(ROOT/'experiments/analysis_comparison').resolve()
                target=(base/unquote(parsed.path.removeprefix('/experiments/'))).resolve()
                if not target.is_relative_to(base) or not target.is_file() or target.suffix not in {'.html','.json','.md'}:
                    self.send_error(404); return
                body=target.read_bytes()
                if target.suffix == '.html':
                    body = theme_html(body.decode('utf-8'), 'experiment').encode('utf-8')
                self.send_response(200); self.send_header('Content-Type',(mimetypes.guess_type(str(target))[0] or 'text/plain')+'; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
                return
            if '/documents/' in parsed.path and parsed.path.startswith('/companies/'):
                catalog = load_catalog(ROOT)
                resolved = resolve_index(parsed.path, catalog, ROOT)
                if resolved is None:
                    self.send_error(404, 'Unknown document or index version')
                    return
                doc, source, index_dir, suffix, base = resolved
                try:
                    manifest = load_json(index_dir / 'manifest.json')
                    index = load_json(index_dir / 'index.json')
                    blocks = load_jsonl(index_dir / 'blocks.jsonl')
                    assets = load_json(index_dir / 'assets.json')
                    content_type = 'text/html; charset=utf-8'
                    if suffix == '':
                        body = (render_transcript(doc,index,blocks,assets,base) if doc.get('source_format') == 'pdf' else render_document_index_page(index, blocks, assets, doc['source_url'],
                            document_index_status_label(manifest), title=doc['title'],
                            source_path=base + '/source', asset_prefix=base + '/assets/')).encode()
                        from apps.review_workbench.site_navigation import crumb, company_tabs
                        company = next(c for c in load_json(COMPANY_UNIVERSE_DATA)['companies'] if c['id'] == 'alphabet')
                        context = '<div class="company-context">' + crumb(company, ('材料库 / 文档目录', 'Materials / Document outline')) + company_tabs(company['id'], 'materials') + '</div>'
                        body = body.decode().replace('</nav>', '</nav>' + context, 1).encode()
                    elif suffix == '/original' and doc.get('source_format') == 'pdf':
                        body = (source / 'source.pdf').read_bytes()
                        content_type = 'application/pdf'
                    elif suffix == '/source':
                        if doc.get('source_format') == 'pdf':
                            body = render_transcript(doc,index,blocks,assets,base).encode()
                        else:
                            with gzip.open(source / 'source.html.gz', 'rt', encoding='utf-8') as stream:
                                body = render_index_source_document(stream.read(), index, blocks, assets,
                                    document_index_status_label(manifest), asset_prefix=base + '/assets/').encode()
                    elif suffix.startswith('/assets/'):
                        filename = suffix.removeprefix('/assets/')
                        if filename not in {a['filename'] for a in assets['assets']} or Path(filename).name != filename:
                            self.send_error(404)
                            return
                        body = (source / 'assets' / filename).read_bytes()
                        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                    else:
                        self.send_error(404)
                        return
                except (FileNotFoundError, ValueError, KeyError) as error:
                    self.send_error(503, 'Document artifacts unavailable')
                    return
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path.startswith('/companies/') or parsed.path == '/data' or parsed.path.startswith('/documents/'):
                catalog_path = ROOT / 'data/document_library/alphabet/catalog.json'
                catalog = load_catalog(ROOT) if catalog_path.exists() else {'documents': []}
                if parsed.path.startswith('/documents/'):
                    requested = parsed.path.removeprefix('/documents/')
                    doc = next((d for d in catalog['documents'] if d['id'] == requested), None)
                    if doc is None:
                        self.send_error(404, 'Unknown document')
                        return
                    if doc.get('index_folder') and doc['status'].startswith('indexed'):
                        self.send_response(303)
                        self.send_header('Location', index_url(doc))
                        self.end_headers()
                        return
                    body = render_document_status(doc).encode()
                else:
                    company_id = parsed.path.removeprefix('/companies/') if parsed.path.startswith('/companies/') else parse_qs(parsed.query).get('company', ['alphabet'])[0]
                    company = next((c for c in load_json(COMPANY_UNIVERSE_DATA)['companies'] if c['id'] == company_id), None)
                    if company is None:
                        self.send_error(404, 'Unknown company')
                        return
                    query = parse_qs(parsed.query)
                    if company_id == 'alphabet' and parsed.path != '/data' and query.get('tab', ['research'])[0] != 'data':
                        body = render_archive(company, archive.list(company=company_id), query.get('snapshot', [None])[0],
                            documents={d['id']: d for d in catalog.get('documents', [])},
                            researcher_id=query.get('researcher', [None])[0], scope=query.get('scope', [None])[0],
                            material_id=query.get('material', [None])[0]).encode()
                    else:
                        body = render_company_data(company, catalog, parsed.path == '/data' or query.get('tab') == ['data']).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(body)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/analysis":
                runs = [p for p in (ROOT / "experiments/cloud_analysis").glob("analysis-*/run.json")
                        if load_json(p).get("status") == "candidate"]
                requested = parse_qs(parsed.query).get("run", [None])[0]
                if requested:
                    runs = [p for p in runs if p.parent.name == requested]
                if not runs:
                    self.send_error(404, "No analysis run available")
                    return
                latest = max(runs, key=lambda p: load_json(p)["started_at"]).parent
                body = render_cloud_analysis(latest, ROOT).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/result" and parse_qs(parsed.query).get("view") == ["cloud-spike"]:
                runs = [p for p in (ROOT / "data/research_data/google_cloud_spike").glob("run-*/run.json")
                        if load_json(p).get("status") == "candidate" and
                        all((p.parent / name).is_file() for name in ("snapshot.json", "trace.json"))]
                if not runs:
                    self.send_error(503, "No Cloud spike run available")
                    return
                latest = max(runs, key=lambda p: load_json(p)["started_at"]).parent
                requested = parse_qs(parsed.query).get("run", [None])[0]
                if requested is not None:
                    matches = [p.parent for p in runs if p.parent.name == requested]
                    if not matches:
                        self.send_error(404, "Cloud run unavailable")
                        return
                    latest = matches[0]
                body = render_cloud_spike(latest, RAW_SOURCE_GZIP.parent).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path.startswith("/source-assets/"):
                filename = Path(parsed.path).name
                assets = load_json(DOCUMENT_ASSETS_DATA)["assets"] if DOCUMENT_ASSETS_DATA.exists() else []
                allowed = {item["filename"] for item in assets}
                target = SOURCE_ASSETS / filename
                if filename not in allowed or not target.is_file():
                    self.send_error(404)
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(filename)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/source/document-index":
                required = (RAW_SOURCE_GZIP, DOCUMENT_INDEX_MANIFEST, DOCUMENT_INDEX_DATA, DOCUMENT_BLOCKS_DATA, DOCUMENT_ASSETS_DATA)
                if not all(path.exists() for path in required):
                    self.send_error(503, "Document Index candidate is unavailable")
                    return
                with gzip.open(RAW_SOURCE_GZIP, "rt", encoding="utf-8", errors="replace") as source:
                    body = render_index_source_document(
                        source.read(),
                        load_json(DOCUMENT_INDEX_DATA),
                        load_jsonl(DOCUMENT_BLOCKS_DATA),
                        load_json(DOCUMENT_ASSETS_DATA),
                        document_index_status_label(load_json(DOCUMENT_INDEX_MANIFEST)),
                    ).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/source/original":
                if not RAW_SOURCE_GZIP.exists():
                    self.send_error(503, "Frozen SEC source is unavailable")
                    return
                with gzip.open(RAW_SOURCE_GZIP, "rt", encoding="utf-8", errors="replace") as source:
                    body = render_original_source_document(source.read(), load_json(SOURCE_EXCERPT)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed.path == "/document-index":
                self.send_response(303)
                self.send_header('Location', '/companies/alphabet/documents/0001652044-26-000018/indexes/v0.1')
                self.end_headers()
                return
            if parsed.path == "/companies":
                if not COMPANY_UNIVERSE_DATA.exists():
                    self.send_error(503, "Company universe candidate is unavailable")
                    return
                body = render_company_universe_page(load_json(COMPANY_UNIVERSE_DATA)).encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
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
                bundle=load_json(EVIDENCE_BUNDLE_DATA),
                release_manifest=load_json(RESEARCH_DATA_MANIFEST),
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
    parser.add_argument("--check", action="store_true", help="Check local inputs without starting the server or writing review state")
    args = parser.parse_args()
    from apps.review_workbench.workspace_check import format_report, inspect_workspace
    report = inspect_workspace(ROOT, data_path=args.data)
    if args.check or not report["ready"]:
        print(format_report(report), file=sys.stdout if report["ready"] else sys.stderr)
        if not report["ready"]:
            raise SystemExit(2)
        return
    if any(c["status"] != "ok" for c in report["checks"]):
        print(format_report(report), file=sys.stderr)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(args.data))
    print(f"Uteki Data Agent Result: http://{args.host}:{args.port}/result")
    print(f"Uteki Document Navigator: http://{args.host}:{args.port}/document-index")
    server.serve_forever()


if __name__ == "__main__":
    main()
