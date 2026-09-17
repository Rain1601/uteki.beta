"""Transcript reader: extracted text beside a faithful PDF page render."""
import json
from html import escape as e
from apps.review_workbench.company_data import shell, bi


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
<style>
main{{max-width:none}}.call-controls{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:18px 0}}.call-controls input{{width:210px}}.call-layout{{display:grid;grid-template-columns:minmax(340px,1fr) minmax(400px,1.1fr);gap:28px;align-items:start}}.call-text{{max-width:76ch}}.call-group{{margin:0 0 24px}}.call-group summary{{cursor:pointer;font-weight:600;padding:12px 0;color:#275dad}}.call-group p{{margin:0 0 18px;scroll-margin-top:20px}}.passage{{border:0!important;background:transparent!important;border-radius:0!important;display:block;text-align:left;width:100%;font:inherit;line-height:1.7;color:inherit;padding:4px 0!important;cursor:pointer}}.passage:hover,.passage.selected{{color:#275dad;background:#f1f5fb!important}}.pdf-reader{{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto}}.pdf-toolbar{{display:flex;justify-content:space-between;padding:8px;background:#fff;position:sticky;top:0;z-index:2}}.pdf-page{{position:relative;line-height:0}}.pdf-page img{{width:100%;height:auto}}#pdf-highlight{{position:absolute;background:rgba(245,202,60,.25);outline:2px solid #bd8c21;pointer-events:none}}@media(max-width:850px){{.call-layout{{grid-template-columns:1fr}}.pdf-reader{{position:relative;max-height:70vh}}}}@media(prefers-reduced-motion:reduce){{*{{scroll-behavior:auto!important}}}}
</style><script>
const CALL={data};const byId=new Map(CALL.blocks.map(b=>[b.block_id,b]));
function selectPassage(id){{const b=byId.get(id);if(!b)return;document.querySelectorAll('.passage').forEach(x=>x.classList.toggle('selected',x.dataset.block===id));const a=CALL.assets.find(a=>a.pdf_page===b.pdf_page),img=document.getElementById('pdf-image'),mark=document.getElementById('pdf-highlight'),src=CALL.base+'/assets/'+a.filename;if(img.getAttribute('src')!==src){{img.style.visibility=mark.style.visibility='hidden';img.onload=()=>{{img.style.visibility=mark.style.visibility='visible'}};img.onerror=()=>{{document.getElementById('pdf-page').textContent='原页加载失败 / Page unavailable'}};img.src=src}}document.getElementById('pdf-page').textContent='PDF p.'+b.pdf_page;document.getElementById('pdf-original').href=CALL.base+'/original#page='+b.pdf_page;let [x,y,x2,y2]=b.bbox,[w,h]=b.page_size;Object.assign(mark.style,{{left:100*x/w+'%',top:100*y/h+'%',width:100*(x2-x)/w+'%',height:100*(y2-y)/h+'%'}});history.replaceState(null,'','#'+id)}}
document.querySelectorAll('[data-block]').forEach(b=>b.onclick=()=>selectPassage(b.dataset.block));
function jump(id){{const el=document.getElementById(id);if(!el)return;document.getElementById('call-search').value='';document.getElementById('call-matches').textContent='';document.querySelectorAll('.call-group').forEach(g=>g.hidden=false);el.closest('details').open=true;el.scrollIntoView({{block:'start'}});selectPassage(id)}}
document.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>jump(b.dataset.jump));
document.getElementById('call-search').oninput=event=>{{let q=event.target.value.trim().toLowerCase(),hits=0;document.querySelectorAll('.call-group').forEach(g=>{{let match=!q||g.textContent.toLowerCase().includes(q);g.hidden=!match;if(q&&match){{g.open=true;hits++}}}});document.getElementById('call-matches').textContent=q?hits+' groups':''}};
const initial=decodeURIComponent(location.hash.slice(1));selectPassage(byId.has(initial)?initial:CALL.blocks[0].block_id);if(byId.has(initial))jump(initial);
</script>'''
    return shell(doc['title'],body)
