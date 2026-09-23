"""Transcript reader: extracted text beside a faithful PDF page render."""
from apps.review_workbench.assets import asset_text
import json
from html import escape as e
from apps.review_workbench.pages.company_data import shell, bi


def render_transcript(doc, index, blocks, assets, base):
    groups = []
    positions = {b['block_id']:i for i,b in enumerate(blocks)}
    for node in index['nodes']:
        if node['kind'] not in {'turn','exchange'}:
            continue
        subset = blocks[positions[node['start_block_id']]:positions[node['end_block_id']]+1]
        paragraphs = ''.join(
            f'<p id="{e(b["block_id"])}"><button class="passage" data-block="{e(b["block_id"])}" '
            f'aria-label="PDF p.{b["pdf_page"]}: {e(b["text"][:70])}">{e(b["text"])}</button>'
            f'<small>{e(b["speaker"] or "Notice")} · PDF p.{b["pdf_page"]}</small></p>' for b in subset)
        groups.append(f'<details class="call-group" open><summary>{e(node["title"])}</summary>{paragraphs}</details>')
    sections = ''.join(f'<button data-jump="{e(n["start_block_id"])}">{bi(zh,en)}</button>'
                       for n,zh,en in [(n,{'prepared':'管理层发言','qa':'分析师问答','closing':'结束语'}[n['node_id']],n['title'])
                                      for n in index['nodes'] if n['kind']=='section'])
    data = json.dumps({'blocks':blocks,'assets':assets['assets'],'base':base},ensure_ascii=False).replace('</','<\\/')
    body = f'''<h1>{e(doc['title'])}</h1><p class="muted">{bi('候选材料 · 原始英文；点击段落查看 PDF 原页高亮。','Candidate material · Original English; select a passage to locate it on the PDF.')}</p>
<p class="muted">{bi('活动日期：2026-02-04。文字稿上传时间未独立核验；管理层发言不等于已验证事实。','Event date: 2026-02-04. Transcript upload time not independently verified; management statements are not verified facts.')}</p>
<div class="call-controls">{sections}<label>{bi('查找原文','Find text')} <input id="call-search" type="search" placeholder="Cloud / CapEx…"></label><span id="call-matches" aria-live="polite"></span></div>
<div class="call-layout"><section class="call-text">{''.join(groups)}</section><aside class="pdf-reader"><div class="pdf-toolbar"><span id="pdf-page"></span><a id="pdf-original" href="{e(base)}/original" target="_blank" rel="noopener">{bi('打开原始 PDF','Open original PDF')}</a></div><div class="pdf-page"><img id="pdf-image" alt="Official transcript PDF page"><div id="pdf-highlight"></div></div></aside></div>
<style>{asset_text('earnings_reader.css')}</style><script>{asset_text('earnings_reader.js').replace('__UTEKI_DATA_JSON__', data)}</script>'''
    return shell(doc['title'],body)
