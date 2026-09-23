from __future__ import annotations
from apps.review_workbench.assets import asset_text

import html
import json
from pathlib import Path
from uteki.agents.reading.reading_groups import build_reading_groups
from apps.review_workbench.components.visual_system import workbench_page


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
    bridge = ("""<style id="uteki-index-source-style">""" + asset_text('document_source_bridge.css') + """</style><script id="uteki-index-source-bridge">""" + asset_text('document_source_bridge.js') + """</script>""").replace("__LOCATIONS__", locations_json).replace("__IMAGES__", images_json).replace("__STATUS_LABEL__", _esc(status_label))
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
    template = ("""<!doctype html><html lang='zh'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Uteki · Document Navigator</title><style>""" + asset_text('document_navigator.css') + """</style></head><body>
<header class='topbar'><div class='brand'><i>Uteki</i> / Eval</div><div class='product'>Document Navigator</div><span class='candidate'>__STATUS_LABEL__</span><div class='top-meta'>__INDEX_ID__ · __PARSER__</div><div class='lang'><button id='en'>EN</button><button id='zh'>中文</button></div></header>
<main class='workspace'><aside class='outline'><div class='outline-head'><div class='eyebrow'>Legal filing outline</div><h1>Alphabet FY2025 10-K</h1><p>__OUTLINE_DESC__</p><div class='counts'><span>4 Parts</span><span>23 Items</span><span>999 Blocks</span></div></div><div class='tree-scroll'>__TREE__</div><section class='inspector'><div class='eyebrow'>Selected node</div><h2 id='detail-title'>—</h2><div class='facts'><div class='fact'><span>__TYPE__</span><b id='detail-kind'>—</b></div><div class='fact'><span>__PAGE__</span><b id='detail-page'>—</b></div><div class='fact'><span>__RANGE__</span><b id='detail-range'>—</b></div><div class='fact'><span>Anchor</span><b id='detail-anchor'>—</b></div></div><div class='diagnostic' id='detail-diagnostic'>—</div></section></aside>
<section class='reader'><div class='reader-head'><div class='reader-title'><strong id='reader-title'>—</strong><span id='reader-subtitle'>—</span></div><div class='reader-actions'><div class='switch'><button type='button' data-view='original'>__ORIGINAL__</button><button type='button' data-view='blocks'>__STRUCTURED__</button></div><a href='__SOURCE_URL__' target='_blank'>SEC ↗</a></div></div><iframe class='source-frame' title='SEC source snapshot' src='/source/document-index' sandbox='allow-scripts allow-same-origin allow-popups'></iframe><div class='blocks-view'><div class='blocks-content'><div class='blocks-summary' id='blocks-summary'></div><div id='blocks-list'></div></div></div></section></main>
<script>""" + asset_text('document_navigator.js') + """</script></body></html>""")
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
