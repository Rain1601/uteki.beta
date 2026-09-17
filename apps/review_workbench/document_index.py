from __future__ import annotations

import html
import json
from pathlib import Path
from uteki.agents.reading_groups import build_reading_groups
from apps.review_workbench.visual_system import workbench_page


def _esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def _bi(en: object, zh: object) -> str:
    return f"<span data-lang='en'>{_esc(en)}</span><span data-lang='zh'>{_esc(zh)}</span>"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _tree(index: dict, title: str = "Alphabet FY2025 10-K") -> str:
    nodes = index["nodes"]
    root = next(node for node in nodes if node["kind"] == "document")
    parts = [node for node in nodes if node["kind"] == "part"]
    children: dict[str, list[dict]] = {}
    for node in nodes:
        if node["parent_id"]:
            children.setdefault(node["parent_id"], []).append(node)

    def node_button(node: dict, label: str, badge: str) -> str:
        return (
            f"<button class='index-node' type='button' data-node='{_esc(node['node_id'])}'>"
            f"<span class='node-label'>{_esc(label)}</span><span class='node-badge'>{_esc(badge)}</span></button>"
        )

    branches = []
    if index.get('form_type') == 'EARNINGS_RELEASE':
        return '<ul class="index-tree"><li>' + node_button(root,title,'document') + '<ul>' + ''.join(
            '<li>'+node_button(n,n['title'],'section')+'</li>' for n in nodes if n['parent_id']==root['node_id'])+'</ul></li></ul>'
    for part in parts:
        item_rows = []
        for item in children.get(part["node_id"], []):
            label = f"Item {item['item_number']} · {item['title']}"
            page_badge = f"p.{item['reported_page']}"
            item_rows.append(f"<li>{node_button(item, label, page_badge)}</li>")
        items = "".join(item_rows)
        part_badge = f"{len(children.get(part['node_id'], []))} items"
        branches.append(
            f"<li class='part-branch'><div class='part-row'><button class='tree-toggle' type='button' aria-label='Toggle'>⌄</button>"
            f"{node_button(part, part['title'], part_badge)}</div><ul>{items}</ul></li>"
        )
    return (
        "<ul class='index-tree'><li>"
        + node_button(root, title, "document")
        + f"<ul>{''.join(branches)}</ul></li></ul>"
    )


def render_index_source_document(
    raw_html: str,
    index: dict,
    blocks: list[dict],
    assets: dict,
    status_label: str = "Index Candidate v0.1",
    asset_prefix: str = "/source-assets/",
) -> str:
    block_by_id = {block["block_id"]: block for block in blocks}
    locations = {
        node["node_id"]: {
            "anchor": node["source_anchor"],
            "domPath": block_by_id[node["start_block_id"]]["dom_path"],
            "title": node["title"],
            "kind": node["kind"],
            "expectedText": block_by_id[node["start_block_id"]]["text"],
        }
        for node in index["nodes"]
    }
    locations.update({block['block_id']: {
        'anchor': None, 'domPath': block['dom_path'], 'kind': 'block',
        'expectedText': block['text'], 'title': block['block_id'],
    } for block in blocks})
    image_paths = {
        item["source_path"]: f"{asset_prefix}{item['filename']}"
        for item in assets["assets"]
    }
    locations_json = json.dumps(locations, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    images_json = json.dumps(image_paths, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    bridge = """<style id="uteki-index-source-style">
html{scroll-behavior:smooth}body{padding-top:38px!important}
#uteki-index-source-status{position:fixed;z-index:2147483647;left:0;right:0;top:0;height:38px;display:flex;align-items:center;gap:10px;padding:0 14px;background:#f4f6f3;border-bottom:1px solid #cfd5cf;color:#4f5851;font:11px/1.2 Arial,sans-serif}
#uteki-index-source-status b{color:#184f38}#uteki-index-source-status span:last-child{margin-left:auto;color:#7c847e}
.uteki-index-focus{outline:3px solid #dfbc31!important;outline-offset:6px;background:#fff6c9!important;scroll-margin-top:70px!important}
</style><script id="uteki-index-source-bridge">
const UTEKI_LOCATIONS=__LOCATIONS__;
const UTEKI_IMAGES=__IMAGES__;
let focused=null;
const sourceTargets={};
function xpath(path){
  // SEC inline-XBRL tag names cannot use an unbound XPath namespace prefix.
  let target=document;
  for(const step of (path||'').split('/').filter(Boolean)){
    const match=step.match(/^([^\\[]+)(?:\\[(\\d+)\\])?$/);if(!match)return null;
    const siblings=Array.from(target.children||[]).filter(el=>el.tagName.toLowerCase()===match[1].toLowerCase());
    target=siblings[Number(match[2]||1)-1];if(!target)return null;
  }
  return target;
}
const normalized=value=>(value||'').replace(/\\s+/g,'').toUpperCase();
function focusNode(nodeId){
  const location=UTEKI_LOCATIONS[nodeId];if(!location)return;
  if(focused)focused.classList.remove('uteki-index-focus');
  const anchor=location.anchor?document.getElementById(location.anchor):null;
  let target=null;
  if(anchor){
    let candidate=anchor;
    for(let offset=0;candidate&&offset<10;offset++,candidate=candidate.nextElementSibling){
      if(normalized(candidate.textContent).startsWith(normalized(location.expectedText))){target=candidate;break}
    }
  }
  target=target||anchor||sourceTargets[nodeId];
  if(target&&!target.textContent.trim()&&target.nextElementSibling)target=target.nextElementSibling;
  if(!target)return;
  focused=target;focused.classList.add('uteki-index-focus');focused.scrollIntoView({behavior:'smooth',block:'center'});
}
window.addEventListener('message',event=>{if(event.data?.type==='uteki-index-focus')focusNode(event.data.nodeId)});
window.addEventListener('DOMContentLoaded',()=>{
  Object.entries(UTEKI_LOCATIONS).forEach(([id,location])=>{sourceTargets[id]=xpath(location.domPath)});
  document.querySelectorAll('img[src]').forEach(image=>{const local=UTEKI_IMAGES[image.getAttribute('src')];if(local)image.src=local});
  const status=document.createElement('div');status.id='uteki-index-source-status';status.innerHTML='<b>SEC 10-K · Source Snapshot</b><span>原始申报版式 · Read only</span><span>__STATUS_LABEL__</span>';document.body.prepend(status);
  parent.postMessage({type:'uteki-index-source-ready'},'*');
  if(location.hash)focusNode(decodeURIComponent(location.hash.slice(1)));
});
window.addEventListener('hashchange',()=>focusNode(decodeURIComponent(location.hash.slice(1))));
</script>""".replace("__LOCATIONS__", locations_json).replace("__IMAGES__", images_json).replace("__STATUS_LABEL__", _esc(status_label))
    bridge = bridge.replace("SEC 10-K ·", "SEC " + _esc(index.get("form_type", "10-K")) + " ·")
    lower = raw_html.lower()
    marker = "</head>"
    if marker not in lower:
        raise ValueError("SEC source HTML has no closing head element")
    position = lower.index(marker)
    return raw_html[:position] + bridge + raw_html[position:]


@workbench_page('document')
def render_document_index_page(
    index: dict,
    blocks: list[dict],
    assets: dict,
    source_url: str,
    status_label: str = "Index Candidate v0.1",
    title: str = "Alphabet FY2025 10-K",
    source_path: str = "/source/document-index",
    asset_prefix: str = "/source-assets/",
) -> str:
    block_payload = json.dumps(blocks, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    node_payload = json.dumps(index["nodes"], ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    diagnostic_payload = json.dumps(index["diagnostics"], ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    asset_payload = json.dumps(assets["assets"], ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    first_item = next((node["node_id"] for node in index["nodes"] if node["kind"] == "item"), index["nodes"][0]["node_id"])
    template = """<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Uteki · Document Navigator</title><style>
:root{--ink:#20241f;--soft:#626a63;--muted:#858c86;--line:#dfe4df;--line2:#cbd2cc;--paper:#fff;--wash:#f5f7f4;--green:#1d6548;--green-bg:#eaf3ed;--amber:#9b7413;--amber-bg:#fff6d9}*{box-sizing:border-box}html,body{height:100%;overflow:hidden}body{margin:0;background:var(--wash);color:var(--ink);font:13px/1.5 ui-sans-serif,-apple-system,"PingFang SC","Segoe UI",sans-serif}button{font:inherit}[data-lang=zh]{display:none}body.zh [data-lang=en]{display:none}body.zh [data-lang=zh]{display:inline}
.topbar{height:54px;display:flex;align-items:center;gap:18px;padding:0 18px;background:#fff;border-bottom:1px solid var(--line)}.brand{font-weight:760}.brand i{font-style:normal;color:var(--green)}.product{font-weight:650}.candidate{padding:3px 7px;border:1px solid #ead58d;background:var(--amber-bg);color:var(--amber);border-radius:4px;font-size:10px}.top-meta{margin-left:auto;color:var(--muted);font:10px ui-monospace,monospace}.lang button{border:0;background:none;color:var(--muted);cursor:pointer;padding:4px}.lang button.on{color:var(--ink);font-weight:700}
.workspace{height:calc(100vh - 54px);min-height:0;overflow:hidden;display:grid;grid-template-columns:370px minmax(650px,1fr)}.outline{min-width:0;min-height:0;background:#fff;border-right:1px solid var(--line2);display:flex;flex-direction:column}.outline-head{padding:15px 16px 13px;border-bottom:1px solid var(--line)}.eyebrow{color:var(--green);font:9px ui-monospace,monospace;text-transform:uppercase;letter-spacing:.06em}.outline h1{font:600 22px/1.25 Georgia,"Songti SC",serif;margin:3px 0}.outline-head p{margin:5px 0 0;color:var(--soft);font-size:11px}.counts{display:flex;gap:12px;margin-top:10px;color:var(--muted);font:10px ui-monospace,monospace}.tree-scroll{overflow:auto;padding:9px 9px 18px;min-height:0;flex:1}.index-tree,.index-tree ul{list-style:none;margin:0;padding:0}.index-tree ul{padding-left:17px}.index-tree li{position:relative}.part-row{display:flex}.part-row>.index-node{margin-left:0}.tree-toggle{width:21px;flex:none;border:0;background:none;color:var(--muted);cursor:pointer}.part-branch.collapsed>ul{display:none}.part-branch.collapsed .tree-toggle{transform:rotate(-90deg)}.index-node{width:100%;min-width:0;border:0;background:none;display:flex;gap:8px;align-items:center;text-align:left;color:var(--ink);padding:7px 8px;border-radius:5px;cursor:pointer}.index-node:hover{background:#f3f5f2}.index-node.active{background:var(--green-bg);color:#164c36}.node-label{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}.node-badge{color:var(--muted);font:9px ui-monospace,monospace;white-space:nowrap}
.inspector{border-top:1px solid var(--line2);padding:13px 16px;background:#fafbf9}.inspector h2{font-size:13px;margin:2px 0 9px}.facts{display:grid;grid-template-columns:1fr 1fr;gap:7px}.fact{border-top:1px solid var(--line);padding-top:5px;min-width:0}.fact span{display:block;color:var(--muted);font-size:9px}.fact b{display:block;font:10px/1.4 ui-monospace,monospace;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.diagnostic{margin-top:10px;padding:7px 8px;border-radius:4px;background:var(--green-bg);color:var(--green);font-size:10px}.diagnostic.has-errors{background:#fff0ec;color:#9a3e28}
.reader{min-width:0;min-height:0;display:flex;flex-direction:column;background:#fafbf9}.reader-head{height:59px;flex:none;display:flex;align-items:center;gap:14px;padding:0 16px;background:#fff;border-bottom:1px solid var(--line)}.reader-title{min-width:0}.reader-title strong{display:block}.reader-title span{display:block;color:var(--muted);font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.reader-actions{margin-left:auto;display:flex;align-items:center;gap:10px}.switch{display:flex;padding:2px;border:1px solid var(--line2);border-radius:5px;background:#f3f5f2}.switch button{border:0;background:none;color:var(--muted);font-size:10px;padding:5px 9px;border-radius:3px;cursor:pointer}.switch button.on{background:#fff;color:var(--ink);box-shadow:0 1px 2px #0001;font-weight:650}.reader-actions a{color:var(--green);text-decoration:none;font-size:11px}.source-frame{width:100%;height:0;min-height:0;flex:1;border:0;background:#fff}.blocks-view{display:none;min-height:0;flex:1;overflow:auto}.blocks-content{max-width:940px;margin:auto;padding:14px 24px 80px}.blocks-summary{position:sticky;top:0;z-index:2;background:#fafbf9ee;backdrop-filter:blur(10px);padding:8px 0;border-bottom:1px solid var(--line);color:var(--muted);font:10px ui-monospace,monospace}.source-block{display:grid;grid-template-columns:105px minmax(0,1fr);gap:16px;padding:14px 0;border-bottom:1px solid var(--line)}.block-meta{color:var(--muted);font:9px/1.6 ui-monospace,monospace}.block-meta b{color:var(--green);display:block}.block-text{font:13px/1.65 Georgia,serif}.source-block[data-type=heading_candidate] .block-text{font-weight:700}.source-block[data-type=page_marker] .block-text{text-align:center;color:var(--muted)}.block-table{overflow:auto}.block-table table{border-collapse:collapse;width:100%;font:10px/1.35 ui-sans-serif,sans-serif}.block-table td,.block-table th{border:1px solid var(--line);padding:4px;text-align:left}.block-image img{max-width:100%;height:auto;border:1px solid var(--line)}body.view-blocks .source-frame{display:none}body.view-blocks .blocks-view{display:block}
@media(max-width:900px){.workspace{grid-template-columns:320px minmax(560px,1fr)}.top-meta{display:none}}
</style></head><body>
<header class='topbar'><div class='brand'><i>Uteki</i> / Eval</div><div class='product'>Document Navigator</div><span class='candidate'>__STATUS_LABEL__</span><div class='top-meta'>__INDEX_ID__ · __PARSER__</div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>
<main class='workspace'><aside class='outline'><div class='outline-head'><div class='eyebrow'>Legal filing outline</div><h1>Alphabet FY2025 10-K</h1><p>__OUTLINE_DESC__</p><div class='counts'><span>4 Parts</span><span>23 Items</span><span>999 Blocks</span></div></div><div class='tree-scroll'>__TREE__</div><section class='inspector'><div class='eyebrow'>Selected node</div><h2 id='detail-title'>—</h2><div class='facts'><div class='fact'><span>__TYPE__</span><b id='detail-kind'>—</b></div><div class='fact'><span>__PAGE__</span><b id='detail-page'>—</b></div><div class='fact'><span>__RANGE__</span><b id='detail-range'>—</b></div><div class='fact'><span>Anchor</span><b id='detail-anchor'>—</b></div></div><div class='diagnostic' id='detail-diagnostic'>—</div></section></aside>
<section class='reader'><div class='reader-head'><div class='reader-title'><strong id='reader-title'>—</strong><span id='reader-subtitle'>—</span></div><div class='reader-actions'><div class='switch'><button type='button' data-view='original'>__ORIGINAL__</button><button type='button' data-view='blocks'>__STRUCTURED__</button></div><a href='__SOURCE_URL__' target='_blank'>SEC ↗</a></div></div><iframe class='source-frame' title='SEC source snapshot' src='/source/document-index' sandbox='allow-scripts allow-same-origin allow-popups'></iframe><div class='blocks-view'><div class='blocks-content'><div class='blocks-summary' id='blocks-summary'></div><div id='blocks-list'></div></div></div></section></main>
<script>
const NODES=__NODES__,BLOCKS=__BLOCKS__,DIAGNOSTICS=__DIAGNOSTICS__,ASSETS=__ASSETS__;
const nodeMap=new Map(NODES.map(value=>[value.node_id,value])),blockMap=new Map(BLOCKS.map(value=>[value.block_id,value])),assetMap=new Map(ASSETS.map(value=>[value.asset_id,value]));
const sourceFrame=document.querySelector('.source-frame');let sourceReady=false,currentNode=null,currentView='original';
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
function language(value){document.body.classList.toggle('zh',value==='zh');document.querySelectorAll('.lang button').forEach(button=>button.classList.toggle('on',button.id===value));localStorage.setItem('uteki-index-lang',value)}
function setView(value){currentView=value;document.body.classList.toggle('view-blocks',value==='blocks');document.querySelectorAll('.switch button').forEach(button=>button.classList.toggle('on',button.dataset.view===value));localStorage.setItem('uteki-index-view',value);if(value==='original')focusSource()}
function focusSource(){if(sourceReady&&currentNode)sourceFrame.contentWindow.postMessage({type:'uteki-index-focus',nodeId:currentNode.node_id},'*')}
function blockBody(block){
 if(block.type==='table'&&block.table){const rows=[];for(let row=0;row<block.table.row_count;row++){const cells=block.table.cells.filter(cell=>cell.row===row).map(cell=>`<${cell.is_header?'th':'td'} rowspan='${cell.rowspan}' colspan='${cell.colspan}'>${escapeHtml(cell.text)}</${cell.is_header?'th':'td'}>`).join('');rows.push(`<tr>${cells}</tr>`)}return `<div class='block-table'><table>${rows.join('')}</table></div>`}
 if(block.type==='image'){const asset=assetMap.get(block.image_asset_id);return asset?`<div class='block-image'><img src='/source-assets/${escapeHtml(asset.filename)}' alt='${escapeHtml(asset.alt||'SEC image')}'><div>${escapeHtml(asset.width)} × ${escapeHtml(asset.height)} · ${escapeHtml(asset.sha256.slice(0,12))}</div></div>`:''}
 return `<div class='block-text'>${escapeHtml(block.text)||'—'}</div>`;
}
const READING_GROUPS=__READING_GROUPS__;
function renderBlocks(node){
 const start=blockMap.get(node.start_block_id).ordinal,end=blockMap.get(node.end_block_id).ordinal,selected=BLOCKS.filter(b=>b.ordinal>=start&&b.ordinal<=end),used=new Set(),parts=[];
 const groups=new Map(READING_GROUPS.filter(g=>g.block_ids.every(id=>blockMap.get(id).ordinal>=start&&blockMap.get(id).ordinal<=end)).map(g=>[g.block_ids[0],g]));
 for(const block of selected){
  if(used.has(block.block_id))continue;
  const group=groups.get(block.block_id);
  if(group){
   group.block_ids.forEach(id=>used.add(id));
   const members=group.block_ids.map(id=>blockMap.get(id)),items=new Set(group.item_ids);
   const intro=members.filter(b=>!items.has(b.block_id)&&!b.layout_role&&b.type!=='page_marker');
   function list(parent){const children=(group.items||[]).filter(i=>i.parent_id===parent);return children.length?'<ul style="margin:8px 0;padding-left:24px;font:18px/1.6 Georgia,serif">'+children.map(i=>{const b=blockMap.get(i.block_id);return `<li style="margin:5px 0" title="${escapeHtml(b.block_id)}">${escapeHtml(b.text.replace(/^[ •◦]+/,''))}${list(i.block_id)}</li>`}).join('')+'</ul>':''}
   const body=intro.map(b=>blockBody(b)).join('')+list(null);
   parts.push(`<article class="source-block"><div class="block-meta">${group.kind}<br>p.${block.reported_page??'—'}<br>reading-group v0.2<details><summary>Block IDs</summary>${group.block_ids.map(escapeHtml).join('<br>')}</details></div><div>${body}</div></article>`);
  }else{parts.push(`<article class='source-block' data-type='${block.type}'><div class='block-meta'><b>#${String(block.ordinal).padStart(4,'0')}</b>${escapeHtml(block.type)}<br>p.${block.reported_page??'—'}<br>${escapeHtml(block.text_hash.slice(0,10))}</div>${blockBody(block)}</article>`)}
 }
 document.getElementById('blocks-summary').textContent=`${selected.length} source blocks · reading-groups v0.2`;
 document.getElementById('blocks-list').innerHTML=parts.join('');
}
function selectNode(id){const node=nodeMap.get(id);if(!node)return;currentNode=node;document.querySelectorAll('.index-node').forEach(button=>button.classList.toggle('active',button.dataset.node===id));const start=blockMap.get(node.start_block_id),end=blockMap.get(node.end_block_id);document.getElementById('detail-title').textContent=node.kind==='item'?`Item ${node.item_number} · ${node.title}`:node.title;document.getElementById('detail-kind').textContent=node.kind;document.getElementById('detail-page').textContent=node.reported_page?`p. ${node.reported_page}`:'—';document.getElementById('detail-range').textContent=`#${start.ordinal}–#${end.ordinal}`;document.getElementById('detail-anchor').textContent=node.source_anchor?`#${node.source_anchor}`:'DOM path';const related=DIAGNOSTICS.filter(value=>!value.node_id||value.node_id===id),errors=related.filter(value=>value.severity==='error');const diagnostic=document.getElementById('detail-diagnostic');diagnostic.classList.toggle('has-errors',errors.length>0);diagnostic.textContent=related.length?`${related.length} diagnostic(s) · ${errors.length} error(s)`:'0 diagnostics · deterministic mapping';document.getElementById('reader-title').textContent=node.kind==='item'?`Item ${node.item_number} · ${node.title}`:node.title;document.getElementById('reader-subtitle').textContent=`${node.kind} · blocks ${start.ordinal}–${end.ordinal} · reported page ${node.reported_page??'—'}`;renderBlocks(node);focusSource()}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');document.querySelectorAll('.switch button').forEach(button=>button.onclick=()=>setView(button.dataset.view));document.querySelectorAll('.index-node').forEach(button=>button.onclick=()=>selectNode(button.dataset.node));document.querySelectorAll('.tree-toggle').forEach(button=>button.onclick=()=>button.closest('.part-branch').classList.toggle('collapsed'));window.addEventListener('message',event=>{if(event.data?.type==='uteki-index-source-ready'){sourceReady=true;focusSource();window.scrollTo(0,0)}});language(localStorage.getItem('uteki-index-lang')||'zh');setView(localStorage.getItem('uteki-index-view')||'original');selectNode('__FIRST_NODE__');window.scrollTo(0,0);
</script></body></html>"""
    template = template.replace("<h1>Alphabet FY2025 10-K</h1>", "<h1>" + _esc(title) + "</h1>")
    template = template.replace("<span>4 Parts</span><span>23 Items</span><span>999 Blocks</span>",
        f"<span>{sum(n['kind']=='part' for n in index['nodes'])} Parts</span><span>{sum(n['kind']=='item' for n in index['nodes'])} Items</span><span>{len(blocks)} Blocks</span>")
    template = template.replace("src='/source/document-index'", "src='" + _esc(source_path) + "'")
    template = template.replace("/source-assets/", _esc(asset_prefix))
    if index['diagnostics']:
        detail = ''.join('<li>' + _esc(d['code']) + ': ' + _esc(d['message']) + '</li>' for d in index['diagnostics'])
        template = template.replace("<div class='tree-scroll'>", "<details style='padding:8px 16px;color:#9a3e28'><summary>解析诊断 / Diagnostics (" + str(len(index['diagnostics'])) + ")</summary><ul>" + detail + "</ul></details><div class='tree-scroll'>")
    replacements = {
        "__READING_GROUPS__": json.dumps(build_reading_groups(blocks, index['nodes']), ensure_ascii=False).replace('</', '<\\/'),
        "__INDEX_ID__": _esc(index["index_id"]),
        "__PARSER__": _esc(index["parser_version"]),
        "__STATUS_LABEL__": _esc(status_label),
        "__OUTLINE_DESC__": _bi("Legal structure only. Internal headings remain candidates.", "只显示法定结构；Item 内标题仍是候选，不推断层级。"),
        "__TREE__": _tree(index, title),
        "__TYPE__": _bi("Type", "类型"),
        "__PAGE__": _bi("Reported page", "报告页码"),
        "__RANGE__": _bi("Block range", "Block 范围"),
        "__ORIGINAL__": _bi("Original layout", "原始版式"),
        "__STRUCTURED__": _bi("Structured Blocks", "结构化 Blocks"),
        "__SOURCE_URL__": _esc(source_url),
        "__NODES__": node_payload,
        "__BLOCKS__": block_payload,
        "__DIAGNOSTICS__": diagnostic_payload,
        "__ASSETS__": asset_payload,
        "__FIRST_NODE__": first_item,
    }
    for key, value in replacements.items():
        template = template.replace(key, value)
    if index.get('form_type') == 'EARNINGS_RELEASE':
        template = template.replace('Legal filing outline','Earnings release').replace(
            '只显示法定结构；Item 内标题仍是候选，不推断层级。','官方发布稿；按原文标题导航，表格保留原始口径。').replace(
            'Legal structure only. Internal headings remain candidates.','Official release; explicit source headings and intact tables.').replace(
            '<span>0 Parts</span><span>0 Items</span>', '<span>Release</span>')
    return template
