
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
