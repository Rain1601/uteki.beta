// Anchored review notes are unverified human input, never source evidence.
(() => {
 if (!state.selected) return;
 const nodes = [...document.querySelectorAll('[data-annotatable]')];
 const originals = new Map(nodes.map(node => [Number(node.dataset.annotatable), node.textContent]));
 let records = {revision: 0, marks: []}, ready = false, saving = false, pending = null, timer;
 const toolbar = document.createElement('div');
 toolbar.id = 'annotation-toolbar'; toolbar.hidden = true; toolbar.setAttribute('role', 'toolbar');
 const button = document.createElement('button'); button.type = 'button'; toolbar.append(button);
 const dismiss = document.createElement('button'); dismiss.type = 'button'; dismiss.textContent = '×';
 dismiss.setAttribute('aria-label', '关闭 / Close'); toolbar.append(dismiss); document.body.append(toolbar);
 const editor = document.createElement('dialog'); editor.id='annotation-editor';
 editor.innerHTML='<form><h2 id="annotation-heading"></h2><blockquote id="annotation-quote"></blockquote><label id="annotation-label" for="annotation-note"></label><textarea id="annotation-note" rows="5" maxlength="12000" required></textarea><label class="annotation-carry"><input type="checkbox" id="annotation-carry" checked><span id="annotation-carry-label"></span></label><p class="muted" id="annotation-policy"></p><p id="annotation-error" role="alert"></p><div class="actions"><button type="submit" class="primary" id="annotation-save"></button><button type="button" id="annotation-cancel"></button><button type="button" id="annotation-remove"></button></div></form>';
 document.body.append(editor);
 const note=editor.querySelector('#annotation-note'),carry=editor.querySelector('#annotation-carry');
 let editing=null;
 const status = document.createElement('div'); status.id = 'annotation-status'; status.role = 'status'; status.hidden = true; document.body.append(status);
 const hint = document.createElement('p'); hint.className = 'annotation-hint';
 hint.innerHTML = state.selected.status === 'deleted'
  ? '<span lang="zh">已删除快照的划线为只读</span><span lang="en">Underlines on deleted snapshots are read-only</span>'
  : '<span lang="zh">选中文字写修改意见 · 点击划线可查看或编辑 · 勾选后用于重跑，Agent 需依据证据复核</span><span lang="en">Select text to write feedback · Click an underline to edit · Included in reruns when selected, subject to evidence review</span>';
 nodes[0]?.closest('section')?.querySelector('h2')?.after(hint);
 const hide = () => { toolbar.hidden = true; pending = null; };
 const message = text => { status.textContent = text; status.hidden = false; };
 function place(rect) {
  toolbar.hidden = false;
  toolbar.style.left = Math.max(12, Math.min(rect.right - toolbar.offsetWidth / 2, innerWidth - toolbar.offsetWidth - 12)) + 'px';
  toolbar.style.top = Math.max(12, rect.top >= toolbar.offsetHeight + 20 ? rect.top - toolbar.offsetHeight - 8 : Math.min(rect.bottom + 8, innerHeight - toolbar.offsetHeight - 12)) + 'px';
 }
 function paint() {
  if (document.body.classList.contains('editing-report')) return;
  for (const node of nodes) {
   const number = Number(node.dataset.annotatable), text = originals.get(number), points = Array.from(text);
   const marks = records.marks.filter(m => m.claim_number === number && m.text_hash === node.dataset.textHash)
    .filter(m => points.slice(m.start, m.end).join('') === m.quote).sort((a,b) => a.start-b.start);
   const fragment = document.createDocumentFragment(); let cursor = 0;
   for (const mark of marks) {
    fragment.append(document.createTextNode(points.slice(cursor, mark.start).join('')));
    const span = document.createElement('mark'); span.className = 'reading-underline'; span.textContent = mark.quote;
    span.dataset.annotationId = mark.annotation_id;
    if (state.selected.status === 'deleted') {fragment.append(span); cursor = mark.end; continue;}
    span.tabIndex = 0; span.setAttribute('role', 'button');
    span.setAttribute('aria-label', tr('查看修改意见：', 'Review feedback: ') + mark.quote);
    span.title=mark.note&&!mark.note_withdrawn?mark.note:tr('点击写修改意见','Click to add feedback');
    span.onclick = () => { if (saving || getSelection()?.toString()) return; clearTimeout(timer); openEditor({action:'note',annotation_id:mark.annotation_id},mark); };
    span.onkeydown = event => { if (event.key==='Enter'||event.key===' ') {event.preventDefault(); span.click();} };
    fragment.append(span); cursor = mark.end;
   }
   fragment.append(document.createTextNode(points.slice(cursor).join(''))); node.replaceChildren(fragment);
  }
 }
 async function load() {
  const response = await fetch('/api/research-annotations?snapshot_id='+encodeURIComponent(state.selected.id));
  if (!response.ok) throw Error(tr('标注读取失败，请刷新重试。','Annotations could not load. Please reload.'));
  records = await response.json(); ready = true; paint();
 }
 function selectionChanged() {
  if (document.body.classList.contains('editing-report')) {hide();return;}
  if (saving || editor.open || toolbar.contains(document.activeElement)) return;
  const selection = getSelection();
  if (pending?.action === 'remove' && (!selection || selection.isCollapsed)) return;
  if (!ready || state.selected.status === 'deleted' || !selection?.rangeCount || selection.isCollapsed) {hide();return;}
  const range = selection.getRangeAt(0);
  const element = node => node.nodeType===Node.ELEMENT_NODE ? node : node.parentElement;
  const startNode = element(range.startContainer)?.closest('[data-annotatable]');
  const endNode = element(range.endContainer)?.closest('[data-annotatable]');
  if (!startNode || startNode !== endNode) {hide();return;}
  const prefix = range.cloneRange(); prefix.selectNodeContents(startNode); prefix.setEnd(range.startContainer,range.startOffset);
  const start = Array.from(prefix.toString()).length, quote = range.toString();
  if (!quote.trim()) {hide();return;}
  pending = {action:'add', claim_number:Number(startNode.dataset.annotatable), start,
   end:start+Array.from(quote).length, quote, text_hash:startNode.dataset.textHash};
  // Position at the drag endpoint, including backward and multi-line selections.
  const endpoint = document.createRange();
  endpoint.setStart(selection.focusNode, selection.focusOffset); endpoint.collapse(true);
  let endpointRect = endpoint.getClientRects()[0];
  if (!endpointRect || !endpointRect.height) {
   const rects = [...range.getClientRects()];
   const backward = selection.focusNode === range.startContainer && selection.focusOffset === range.startOffset;
   const edge = backward ? rects[0] : rects[rects.length - 1];
   if (edge) endpointRect = {left: backward ? edge.left : edge.right, right: backward ? edge.left : edge.right, top:edge.top, bottom:edge.bottom};
  }
  button.textContent=tr('写修改意见','Add feedback'); place(endpointRect || range.getBoundingClientRect());
 }
 document.addEventListener('selectionchange', () => {clearTimeout(timer);timer=setTimeout(selectionChanged,60);});
 toolbar.addEventListener('pointerdown', event => event.preventDefault());
 dismiss.onclick = hide;
 function openEditor(request,mark={}) {
  if (document.body.classList.contains('editing-report')) return;
  editing={...request,expected_note_version:mark.note_version||0}; hide(); getSelection()?.removeAllRanges();
  editor.querySelector('#annotation-heading').textContent=tr('针对选文写修改意见','Feedback on selected text');
  editor.querySelector('#annotation-quote').textContent=mark.quote||request.quote;
  editor.querySelector('#annotation-label').textContent=tr('你希望检查或修改什么？','What should be checked or revised?');
  note.value=mark.note&&!mark.note_withdrawn?mark.note:'';
  carry.checked=mark.note_withdrawn?true:mark.carry_forward!==false;
  editor.querySelector('#annotation-carry-label').textContent=tr('用于下次重跑及符合规则的后续分析','Use in the next rerun and eligible future analyses');
  editor.querySelector('#annotation-policy').textContent=tr('这是待核查的人工意见，不是事实或强制结论。同版重跑可使用；跨材料继承仍须采纳。保存不会自动运行模型。','Unverified human feedback, not a fact or mandatory conclusion. Same-report reruns can use it; later material analyses still require adoption. Saving does not run a model.');
  editor.querySelector('#annotation-save').textContent=tr('保存意见','Save feedback');
  editor.querySelector('#annotation-cancel').textContent=tr('取消','Cancel');
  editor.querySelector('#annotation-remove').textContent=tr('删除划线并撤回意见','Remove underline and withdraw feedback');
  editor.querySelector('#annotation-remove').hidden=!request.annotation_id;
  editor.querySelector('#annotation-error').textContent='';
  editor.showModal(); note.focus();
 }
 button.onclick=()=>{if(pending&&!saving)openEditor(pending);};
 editor.querySelector('#annotation-cancel').onclick=()=>editor.close();
 editor.querySelector('form').onsubmit=event=>{event.preventDefault();saveNote(false);};
 editor.querySelector('#annotation-remove').onclick=()=>saveNote(true);
 async function saveNote(remove) {
  if (!editing || saving || (!remove&&!note.value.trim())) return;
  const request = {...editing, snapshot_id:state.selected.id, expected_revision:records.revision};
  if(remove)request.action='remove'; else {request.note=note.value.trim();request.carry_forward=carry.checked;}
  saving = true; editor.querySelectorAll('button').forEach(b=>b.disabled=true); status.hidden = true;
  try {
   const response = await fetch('/api/research-annotations',{method:'POST',headers:{'Content-Type':'application/json','X-Uteki-Request':'1'},body:JSON.stringify(request)});
   const result = await response.json();
   if (!response.ok) {
    if (response.status===409) {await load();throw Error(tr('标注已在其他页面更新，请重新选中文字。','Annotations changed elsewhere; select the text again.'));}
    throw Error(result.error?.includes('overlaps') ? tr('选区与已有划线重叠，请先取消原划线。','Selection overlaps an underline. Remove it first.') : tr('未保存，请刷新后重试：','Not saved; reload and retry: ')+(result.error||response.status));
   }
   records=result; editor.close(); getSelection()?.removeAllRanges(); paint();
   // Refresh snapshot revision / slot guards and the opinion list together.
   location.reload();
  } catch(error) {editor.querySelector('#annotation-error').textContent=error.message;} finally {saving=false;editor.querySelectorAll('button').forEach(b=>b.disabled=false);hide();}
 }
 document.addEventListener('keydown', event => {if(event.key==='Escape') {hide();status.hidden=true;}});
 document.addEventListener('pointerdown', event => {if(!toolbar.contains(event.target)&&!event.target.closest('.reading-underline'))hide();});
 document.addEventListener('scroll',event=>{if(!toolbar.contains(event.target))hide();},true);
 window.addEventListener('resize',hide);
 document.getElementById('language').addEventListener('click',()=>{hide();paint();status.hidden=true;});
 load().catch(error=>message(error.message));
})();
