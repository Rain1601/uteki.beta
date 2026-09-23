
const state=JSON.parse(document.getElementById('archive-state').textContent);
document.getElementById('researcher-filter')?.addEventListener('change',event=>{const u=new URL(state.route,location.origin);u.searchParams.set('researcher',event.target.value);location.assign(u.href)});
const lang=()=>document.documentElement.dataset.language||'zh';
const tr=(zh,en)=>lang()==='en'?en:zh;
document.querySelectorAll('#scope-filter').forEach(el=>el.onchange=()=>{
 const u=new URL(state.route,location.origin);u.searchParams.set('tab','research');
 u.searchParams.set('researcher',state.researcher_id);
 u.searchParams.set('scope',document.getElementById('scope-filter').value);
 if(state.selected?.material_id)u.searchParams.set('material',state.selected.material_id);
 location.assign(u.href);
});
document.documentElement.dataset.language=localStorage.getItem('data-language')||'zh';
document.getElementById('language').onclick=()=>{const l=lang()==='en'?'zh':'en';document.documentElement.dataset.language=l;localStorage.setItem('data-language',l);closeSource();const caption=document.getElementById('source-caption');caption.textContent=caption.dataset[l]||''};
const showDeleted=document.getElementById('show-deleted');
showDeleted.checked=new URLSearchParams(location.search).get('deleted')==='1'||state.selected?.status==='deleted';
function toggleDeleted(){document.body.classList.toggle('show-deleted',showDeleted.checked);const u=new URL(location.href);if(showDeleted.checked)u.searchParams.set('deleted','1');else u.searchParams.delete('deleted');history.replaceState(null,'',u)}
showDeleted.onchange=toggleDeleted;toggleDeleted();
const versionFilter=document.getElementById('version-status');
const localizeVersions=()=>versionFilter.querySelectorAll('option').forEach(option=>option.textContent=option.dataset[lang()]||option.dataset.zh);
localizeVersions();document.getElementById('language').addEventListener('click',localizeVersions);
versionFilter.onchange=()=>document.querySelectorAll('.version-row').forEach(row=>row.hidden=versionFilter.value!=='all'&&row.dataset.status!==versionFilter.value);
let busy=false;
async function mutate(action,extra={}){
 if(busy||!state.selected)return;busy=true;
 const feedback=document.getElementById('feedback');feedback.hidden=false;feedback.textContent=tr('正在保存…','Saving…');
 try{const response=await fetch('/api/research-archive',{method:'POST',headers:{'Content-Type':'application/json','X-Uteki-Request':'1'},body:JSON.stringify({snapshot_id:state.selected.id,action,expected_revision:state.selected.revision,...extra})});const result=await response.json();if(!response.ok||result.error)throw new Error(result.error||result.message||('HTTP '+response.status));
 const next=result.snapshot?.id||result.snapshot_id||result.selected_id||state.selected.id;const u=new URL(state.route,location.origin);u.searchParams.set('tab','research');u.searchParams.set('researcher',state.researcher_id);u.searchParams.set('scope',state.scope);u.searchParams.set('snapshot',next);if(showDeleted.checked||action==='delete')u.searchParams.set('deleted','1');location.assign(u.href);
 }catch(error){feedback.textContent=tr('未保存：','Not saved: ')+error.message+tr('。若版本已变化，请刷新后重试。','. If the revision changed, refresh before retrying.');busy=false;}
}
document.querySelectorAll('[data-action]').forEach(button=>button.onclick=()=>{
 const action=button.dataset.action;
 if(action==='adopt'){
  const current=state.selected.effective;
  const msg=(current?tr('替换当前生效版本？旧版将归档，其他候选保留。当前版本：','Replace the effective report? Its predecessor will be archived; other candidates stay pending. Current: ')+current.id:tr('采纳此版本作为本研究者的生效报告？','Adopt this version for this researcher?'))+(state.selected.primary_inferred?tr('\n请同时确认推定主材料正确。','\nConfirm the inferred primary source.'):'');
  if(confirm(msg))mutate(action,{confirm_primary:true,expected_slot_revision:state.selected.slot_revision,replace_snapshot_id:current?.id,replace_revision:current?.revision});
 }else if(action==='review'){const notes=prompt(tr('请记录审核依据：确认人工修订没有引入无依据事实，也未掩盖反证。该操作不会自动采纳。','Record your review basis: confirm the notes introduce no unsupported facts and conceal no counterevidence. This does not adopt the revision.'));if(notes&&notes.trim())mutate(action,{review_notes:notes.trim()})}
 else if(action==='reject'){const reason=prompt(tr('拒绝原因（保留历史，不进入上下文）','Reason for rejection (history retained, excluded from context)'));if(reason?.trim())mutate(action,{reason:reason.trim()})}
 else if(action==='delete'){if(confirm(tr('软删除此快照？后续不会加载，可恢复为归档。','Soft-delete this snapshot? It will be excluded and can be restored as archived.')))mutate(action)}
 else if(action==='archive'){if(confirm(tr('归档后不再进入未来默认上下文。历史运行记录不变。确认？','Archive and exclude from future default context? Past run records stay unchanged.')))mutate(action)}
 else if(action==='withdraw_opinion'){if(confirm(tr('撤回此意见并停止后续继承？历史记录保留。','Withdraw and stop future inheritance? History is retained.')))mutate(action,{opinion_id:button.dataset.opinion})}
 else mutate(action);
});
let editing=false,editNodes=[],structuralDraft=null;
const editStatus=()=>document.getElementById('edit-state');
function inlineMarkdown(node){
 if(node.nodeType===3)return node.textContent;
 const t=[...node.childNodes].map(inlineMarkdown).join('');
 if(node.tagName==='STRONG'||node.tagName==='B')return '**'+t+'**';
 if(node.tagName==='A')return '['+t+']('+node.getAttribute('href')+')';
 if(node.tagName==='BR')return ' ';
 return t;
}
function stopEditing(restore){
 if(structuralDraft){if(structuralDraft.node)structuralDraft.node.remove();if(structuralDraft.removed)structuralDraft.removed.hidden=false;structuralDraft=null;}
 editNodes.forEach(({el,html})=>{if(restore)el.innerHTML=html;el.removeAttribute('contenteditable');el.onpaste=null;el.onkeydown=null;el.oninput=null});
 editing=false;document.querySelector('.edit-actions').hidden=true;document.querySelector('.read-actions').hidden=false;
 document.body.classList.remove('editing-report');
}
function startBlockEdit(target){
 if(editing||busy||feedbackOpen||state.selected?.status==='deleted')return;editing=true;
 editNodes=[{el:target,html:target.innerHTML}];
 editNodes.forEach(({el})=>{
  el.setAttribute('contenteditable','true');el.setAttribute('spellcheck','true');
  el.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();document.execCommand('insertText',false,' ')}};
  el.onpaste=e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain').replace(/\r?\n/g,' '))};
  el.oninput=()=>{editStatus().textContent=tr('尚未保存','Unsaved')};
 });
 document.querySelector('.read-actions').hidden=true;document.querySelector('.edit-actions').hidden=false;
 document.getElementById('inline-reason').value='';editStatus().textContent=tr('直接修改正文','Edit directly in the report');
 document.body.classList.add('editing-report');target.focus();
}
const sidebarTabs=[...document.querySelectorAll('[data-review-tab]')];
function selectReviewTab(key){sidebarTabs.forEach(tab=>{const on=tab.dataset.reviewTab===key;tab.setAttribute('aria-selected',String(on));tab.tabIndex=on?0:-1;document.getElementById('panel-'+tab.dataset.reviewTab).hidden=!on})}
sidebarTabs.forEach((tab,i)=>{tab.onclick=()=>selectReviewTab(tab.dataset.reviewTab);tab.onkeydown=e=>{let next;if(e.key==='ArrowRight')next=(i+1)%sidebarTabs.length;else if(e.key==='ArrowLeft')next=(i+sidebarTabs.length-1)%sidebarTabs.length;else if(e.key==='Home')next=0;else if(e.key==='End')next=sidebarTabs.length-1;else return;e.preventDefault();sidebarTabs[next].click();sidebarTabs[next].focus()}});
document.querySelectorAll('a[href="#revision-history"]').forEach(link=>link.addEventListener('click',()=>selectReviewTab('revisions')));
const blockNodes=[...document.querySelectorAll('#report-reading [data-md-line],#report-reading .claim [data-annotatable]')];
const blockKey=el=>el.hasAttribute('data-md-line')?'md:'+el.dataset.mdLine+(el.hasAttribute('data-md-cell')?':'+el.dataset.mdCell:''):'claim:'+(Number(el.dataset.annotatable)-1);
const progress=document.createElement('span');progress.id='block-progress';progress.setAttribute('role','status');
document.querySelector('.report-toolbar')?.prepend(progress);
const accepted=k=>state.block_decisions?.[k]?.accepted===true;
const rejected=k=>state.block_decisions?.[k]?.decision==='rejected';
function updateProgress(){const keys=Object.keys(state.blocks||{}),n=keys.filter(k=>accepted(k)||rejected(k)).length;progress.textContent=keys.length&&n===keys.length?tr('已完成批阅','Review complete'):tr('已批阅（','Reviewed (')+n+'/'+keys.length+tr('）',')');blockNodes.forEach(el=>{const k=blockKey(el);el.dataset.accepted=String(accepted(k));el.dataset.rejected=String(rejected(k))})}
function updateDecisionButtons(){const k=hoveredBlock&&blockKey(hoveredBlock);acceptButton.textContent=tr('采纳','Accept');rejectButton.textContent=tr('拒绝','Reject');acceptButton.setAttribute('aria-pressed',String(accepted(k)));rejectButton.setAttribute('aria-pressed',String(rejected(k)))}
const blockActions=document.createElement('div');blockActions.id='block-actions';blockActions.hidden=true;
const acceptButton=document.createElement('button');acceptButton.type='button';blockActions.append(acceptButton);document.body.append(blockActions);
let hoveredBlock=null, hideBlockTimer=null;const actionSlots=new Map();
function cancelBlockHide(){clearTimeout(hideBlockTimer);hideBlockTimer=null}
function scheduleBlockHide(){if(feedbackOpen||hideBlockTimer||blockActions.contains(document.activeElement))return;hideBlockTimer=setTimeout(()=>{blockActions.classList.remove('actions-visible');hideBlockTimer=null},600)}
blockActions.addEventListener('mouseenter',()=>{cancelBlockHide();blockActions.classList.add('actions-visible')});
blockActions.addEventListener('mouseleave',scheduleBlockHide);
blockActions.addEventListener('focusin',cancelBlockHide);
blockActions.addEventListener('focusout',scheduleBlockHide);
let feedbackOpen=false;
function positionActions(el){const slot=actionSlots.get(el);if(slot&&blockActions.parentElement!==slot)slot.append(blockActions)}
function showBlockActions(el){if(editing||busy||feedbackOpen)return;cancelBlockHide();hoveredBlock=el;updateDecisionButtons();positionActions(el);blockActions.hidden=false;requestAnimationFrame(()=>blockActions.classList.add('actions-visible'))}
blockNodes.forEach(el=>{
 el.classList.add('review-block');el.tabIndex=0;
 const anchor=el.closest('.report-table')||el;
 let slot=anchor.nextElementSibling;
 if(!slot?.classList.contains('block-action-slot')){slot=document.createElement('div');slot.className='block-action-slot';anchor.after(slot)}
 actionSlots.set(el,slot);
 slot.addEventListener('mouseenter',()=>{cancelBlockHide();if(hoveredBlock===el)blockActions.classList.add('actions-visible')});
 slot.addEventListener('mouseleave',scheduleBlockHide);
 el.addEventListener('mouseenter',()=>showBlockActions(el));el.addEventListener('mouseleave',scheduleBlockHide);
 el.addEventListener('focus',()=>showBlockActions(el));el.addEventListener('blur',scheduleBlockHide);
 el.addEventListener('dblclick',e=>{if(e.target.closest('a'))return;cancelBlockHide();blockActions.classList.remove('actions-visible');blockActions.hidden=true;startBlockEdit(el)});
 el.addEventListener('keydown',e=>{if(!editing&&e.key==='Enter'){e.preventDefault();cancelBlockHide();blockActions.classList.remove('actions-visible');blockActions.hidden=true;startBlockEdit(el)}});
});
function beginStructure(draft){
 if(editing||busy||feedbackOpen)return false;
 structuralDraft=draft;editing=true;editNodes=[];blockActions.hidden=true;
 document.querySelector('.read-actions').hidden=true;document.querySelector('.edit-actions').hidden=false;
 document.getElementById('inline-reason').value='';document.body.classList.add('editing-report');
 editStatus().textContent=tr('尚未保存 · 可取消恢复','Unsaved · Cancel to restore');return true;
}
function insertBoundary(after,index){
 const gap=document.createElement('div');gap.className='block-insert-gap';
 const menu=document.createElement('details');const plus=document.createElement('summary');plus.textContent='＋';plus.setAttribute('aria-label',tr('新增内容块','Insert block'));menu.append(plus);
 const choices=document.createElement('div');choices.className='block-type-choices';
 for(const [kind,zh,en] of [['fact','事实','Fact'],['inference','推断','Inference'],['hypothesis','假设','Hypothesis'],['question','待验证问题','Question']]){
  const button=document.createElement('button');button.type='button';button.textContent=tr(zh,en);
  button.onclick=()=>{
   const node=document.createElement('article');node.className='inserted-block';
   const label=document.createElement('small');label.textContent=tr(zh+' · 人工新增，待核查',en+' · Human addition, unverified');
   const editor=document.createElement('div');editor.className='prose';editor.contentEditable='true';editor.setAttribute('role','textbox');editor.setAttribute('aria-label',tr('新增段落','New paragraph'));editor.dataset.placeholder=tr('在这里写内容…','Write here…');
   editor.onpaste=e=>{e.preventDefault();document.execCommand('insertText',false,e.clipboardData.getData('text/plain'))};
   node.append(label,editor);
   if(!beginStructure({action:'insert_block',index,kind,node,editor}))return;
   menu.open=false;gap.after(node);editor.focus();
  };choices.append(button);
 }
 menu.append(choices);gap.append(menu);after.after(gap);return gap;
}
const structureNodes=[...document.querySelectorAll('#report-reading .claim,#report-reading .report-body > [data-md-line],#report-reading .report-body > .report-table')];
if(!structureNodes.length&&state.selected&&state.selected.status!=='deleted'){
 const sentinel=document.createElement('span');(document.querySelector('#report-reading .report-body')||document.getElementById('report-reading')).append(sentinel);insertBoundary(sentinel,0);
}
if(structureNodes.length&&state.selected?.status!=='deleted'){
 const first=structureNodes[0],sentinel=document.createElement('span');first.before(sentinel);insertBoundary(sentinel,0);
 structureNodes.forEach(node=>{
  const claim=node.classList.contains('claim');
  const indices=claim?[Number(node.querySelector('[data-annotatable]').dataset.annotatable)-1]:node.hasAttribute('data-md-line')?[Number(node.dataset.mdLine)]:[...node.querySelectorAll('[data-md-line]')].map(el=>Number(el.dataset.mdLine));
  const start=Math.min(...indices),end=Math.max(...indices),count=claim?1:end-start+1;
  // Control is outside editable text; deleting a table operates on the whole table.
  let shell=node;
  if(!claim){shell=document.createElement('div');shell.className='structure-block';node.before(shell);shell.append(node);}
  shell.classList.add('structure-block');
  const remove=document.createElement('button');remove.type='button';remove.className='delete-block';remove.textContent=tr('删除','Delete');remove.setAttribute('aria-label',tr('删除这一块','Delete this block'));
  remove.onclick=()=>{if(!beginStructure({action:'delete_block',index:start,count,removed:shell}))return;shell.hidden=true;};shell.prepend(remove);
  const following=shell.nextElementSibling;const boundaryAnchor=following?.classList.contains('block-action-slot')?following:shell;
  insertBoundary(boundaryAnchor,end+1);
 });
}
const rejectButton=document.createElement('button'),editButton=document.createElement('button');
rejectButton.type=editButton.type='button';editButton.textContent=tr('编辑','Edit');blockActions.append(rejectButton,editButton);
editButton.onclick=()=>{if(!hoveredBlock||busy||editing)return;const target=hoveredBlock;blockActions.hidden=true;startBlockEdit(target)};
async function decideBlock(action){
 if(!hoveredBlock||busy||editing)return;
 const key=blockKey(hoveredBlock);busy=true;acceptButton.disabled=rejectButton.disabled=editButton.disabled=true;
 try{
  const response=await fetch('/api/research-archive',{method:'POST',headers:{'Content-Type':'application/json','X-Uteki-Request':'1'},body:JSON.stringify({snapshot_id:state.selected.id,action,expected_revision:state.selected.revision,block_id:key,block_hash:state.blocks[key]})});
  const result=await response.json();if(!response.ok)throw Error(result.error||response.status);
  state.selected.revision=result.revision;state.block_decisions=result.snapshot.block_decisions||{};updateProgress();updateDecisionButtons();
 }catch(error){const feedback=document.getElementById('feedback');feedback.hidden=false;feedback.textContent=tr('未保存：','Not saved: ')+error.message}
 finally{busy=false;acceptButton.disabled=rejectButton.disabled=editButton.disabled=false}
}
acceptButton.onclick=()=>decideBlock(accepted(blockKey(hoveredBlock))?'unaccept_block':'accept_block');
rejectButton.onclick=()=>decideBlock(rejected(blockKey(hoveredBlock))?'unaccept_block':'reject_block');


document.getElementById('language').addEventListener('click',updateProgress);
updateProgress();
document.getElementById('cancel-inline')?.addEventListener('click',()=>stopEditing(true));
document.getElementById('save-inline')?.addEventListener('click',async()=>{
 if(busy)return;
 if(structuralDraft){
  const draft=structuralDraft;
  const text=draft.editor?.textContent?.trim();
  if(draft.action==='insert_block'&&!text){editStatus().textContent=tr('请填写内容','Enter block text');return}
  await mutate(draft.action,{block_index:draft.index,block_count:draft.count||1,block_kind:draft.kind,text,human_notes:document.getElementById('inline-reason').value.trim()||tr('调整报告内容块','Change report blocks')});return;
 }
 const changed=editNodes.filter(x=>x.el.innerHTML!==x.html);
 if(!changed.length){stopEditing(false);return}
 const answer=structuredClone(state.selected.answer), lines=answer.report_markdown?.split('\n');
 for(const {el} of changed){
  if(el.hasAttribute('data-md-line')){
   const i=Number(el.dataset.mdLine),value=inlineMarkdown(el);
   if(el.hasAttribute('data-md-cell')){
    if(value.includes('|')){editStatus().textContent=tr('表格内容不能包含竖线','Table text cannot contain a pipe');return}
    const cells=lines[i].trim().replace(/^\||\|$/g,'').split('|');cells[Number(el.dataset.mdCell)]=value;lines[i]='|'+cells.join('|')+'|';
   }else{const prefix=lines[i].match(/^\s*(#{1,6}\s+|-\s+)/)?.[0]||'';lines[i]=prefix+value}
  }else answer.claims[Number(el.dataset.annotatable)-1].text=el.textContent;
 }
 if(lines)answer.report_markdown=lines.join('\n');
 await mutate('edit',{answer,human_notes:document.getElementById('inline-reason').value.trim()||tr('正文原位修订','Inline report revision')});
});
window.addEventListener('beforeunload',e=>{if(editing&&(structuralDraft||editNodes.some(x=>x.el.innerHTML!==x.html))&&!busy){e.preventDefault();e.returnValue=''}});
document.addEventListener('click',e=>{if(editing&&e.target.closest('[contenteditable] a'))e.preventDefault()},true);
document.getElementById('opinion-form')?.addEventListener('submit',event=>{event.preventDefault();const data=new FormData(event.target);mutate('comment',{text:data.get('text'),kind:data.get('kind'),carry_forward:data.has('carry_forward')})});
const drawer=document.getElementById('source-drawer');
let sourceTrigger=null;
function closeSource(restoreFocus=false){drawer.hidden=true;if(restoreFocus)sourceTrigger?.focus()}
document.querySelectorAll('.citation-toggle').forEach(button=>button.onclick=()=>{
 const expanded=button.getAttribute('aria-expanded')==='true';
 document.getElementById(button.getAttribute('aria-controls')).hidden=expanded;
 button.setAttribute('aria-expanded',String(!expanded));
 button.querySelector('.more-label').hidden=!expanded;
 button.querySelector('.less-label').hidden=expanded;
});
document.querySelectorAll('[data-source]').forEach(link=>link.onclick=event=>{
 event.preventDefault();event.stopPropagation();sourceTrigger=link;drawer.hidden=false;
 const caption=document.getElementById('source-caption');caption.dataset.zh=link.dataset.sourceTitleZh||link.dataset.sourceTitle||'';caption.dataset.en=link.dataset.sourceTitle||'';caption.textContent=caption.dataset[lang()];
 const excerpt=document.getElementById('source-excerpt');excerpt.replaceChildren();
 if(lang()==='zh'&&link.dataset.quoteZh){const label=document.createElement('small');label.textContent='中文译文 · 辅助阅读';const translation=document.createElement('p');translation.textContent=link.dataset.quoteZh;excerpt.append(label,translation)}
 const label=document.createElement('small');label.textContent=tr('原文摘录','Original excerpt');const quote=document.createElement('blockquote');quote.textContent=link.title||link.dataset.fullQuote||tr('此引用未记录摘录。','No excerpt recorded for this reference.');excerpt.append(label,quote);
 document.getElementById('source-new-tab').href=link.dataset.source;document.getElementById('close-source').focus();
});
document.getElementById('close-source').onclick=()=>closeSource(true);
document.addEventListener('click',event=>{if(!drawer.hidden&&!drawer.contains(event.target))closeSource()});
document.addEventListener('keydown',event=>{if(event.key==='Escape')closeSource(true)});
