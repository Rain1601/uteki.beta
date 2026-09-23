/* Isolated browser demo. Never calls archive mutation or model APIs. */
const RevisionDemo = (() => {
  const copy = value => JSON.parse(JSON.stringify(value));
  function initial(seed) {
    return {schema:1, seed:seed.identity, revision:0, active:'v1', versions:[{
      id:'v1', parent:null, status:'active', report:copy(seed.reports.annual),
      basis:null, time:null, reason:'实验原稿作为演示起点；不代表正式采纳。'
    }], decisions:[]};
  }
  function save(state, input) {
    if (input.parent !== state.active) throw Error('主报告已变化，请从当前版本重新编辑。');
    if (!input.text.trim() || !input.watch.trim() || !input.reason.trim()) throw Error('请填写观点、下次验证事项和修改理由。');
    const next=copy(state), base=next.versions.find(v=>v.id===input.parent);
    const h=base.report.hypotheses.find(h=>h.id===input.hypothesis);
    if (!h) throw Error('Unknown hypothesis');
    if (h.judgment===input.text.trim() && h.test===input.watch.trim()) throw Error('内容没有修改，无需创建新版本。');
    if (input.basis.stage!=='q1') throw Error('本轮仅演示基于 Q1 修订年度主报告。');
    const report=copy(base.report), edited=report.hypotheses.find(h=>h.id===input.hypothesis);
    edited.judgment=input.text.trim(); edited.test=input.watch.trim();
    edited.sources=[...new Set([...edited.sources,...input.sources])];
    edited.status='人工修订 / Human revision';
    next.versions.push({id:'v'+(next.versions.length+1),parent:base.id,status:'candidate',report,
      basis:copy(input.basis),hypothesis:input.hypothesis,time:input.time,reason:input.reason.trim(),
      before:{text:h.judgment,watch:h.test},after:{text:edited.judgment,watch:edited.test}});
    next.revision++;
    return next;
  }
  function adopt(state,id,time) {
    const next=copy(state), v=next.versions.find(v=>v.id===id);
    if (!v || v.status!=='candidate') throw Error('只有候选修订可确认生效。');
    if (v.parent!==next.active) throw Error('候选基于旧版本，请基于当前主报告重新修订。');
    next.versions.find(x=>x.id===next.active).status='archived';
    next.active=id; v.status='active'; v.adopted_at=time; next.revision++;
    return next;
  }
  function decide(state,stage,hypothesis,outcome,reason,time) {
    if (!reason.trim()) throw Error('请填写处理理由；拒绝建议不会删除证据。');
    const next=copy(state);
    next.decisions.push({stage,hypothesis,outcome,reason:reason.trim(),time,base:state.active});
    next.revision++;
    return next;
  }
  function downstream(state,stage) {
    // Q1 caused the revision: retain it as historical evidence, not a circular rerun dependency.
    return stage==='q2' && state.active!=='v1';
  }
  function context(state,cutoff='2026-07-23') {
    const active=state.versions.find(v=>v.id===state.active);
    if (active.basis && active.basis.cutoff>cutoff) throw Error('修订依据晚于材料截止日；请选择较早版本。');
    return {kind:'demo_input_preview_not_a_run',mode:'retrospective_not_blind',
      cutoff,annual_revision:copy(active),verification_reports:['q1'],
      pending_current_material:'2026 Q2 10-Q', excluded:['旧 Q2 结论（待重新验证）','未生效候选'],
      human_decisions:copy(state.decisions.filter(d=>d.stage==='q1')), instruction:'人工意见不是事实；核对原始证据。发现偏好与证据冲突时提出异议，不自动修改主报告。旧 Q2 的意见也不进入这次重验输入。'};
  }
  return {initial,save,adopt,decide,downstream,context};
})();
if(typeof module!=='undefined') module.exports=RevisionDemo;

if(typeof document!=='undefined') (()=>{
  const seed=JSON.parse(document.getElementById('demo-data').textContent);
  const key='uteki-revision-demo:'+seed.identity;
  const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let state=RevisionDemo.initial(seed), view='q1', selected='v1', editor=null, lastFocus=null, memoryOnly=false;
  try {const saved=JSON.parse(localStorage.getItem(key)); if(saved?.seed===seed.identity&&saved.schema===1)state=saved;} catch {memoryOnly=true;}
  const active=()=>state.versions.find(v=>v.id===state.active);
  function persist(next){state=next;try{localStorage.setItem(key,JSON.stringify(state));}catch{memoryOnly=true;}render();}
  function notify(text){$('notice').textContent=text;}
  function currentStorage(){try{const stored=JSON.parse(localStorage.getItem(key));if(stored&&stored.revision!==state.revision)throw Error('另一个标签已修改演示。请刷新后再操作。');}catch(e){if(e.message.includes('另一个'))throw e;}}
  function evidence(ids){const links=ids.map(id=>{const e=seed.evidence[id];return e?`<a href="${esc(e.url)}" data-source="${id}">${esc(e.label)} <small>[${esc(e.document)}]</small></a>`:'';}).filter(Boolean);return '<div class="rd-evidence">'+links.slice(0,3).join('； ')+(links.length>3?`<details><summary>展开更多 / More (${links.length-3})</summary>${links.slice(3).join('； ')}</details>`:'')+'</div>';}
  function actions(){return `<div class="rd-links"><button data-view="annual">查看当前主报告 / Main report</button><button data-context>下次运行会读什么 / Context</button></div>`;}
  function render(){
    $('storage').textContent=memoryOnly?'仅保存在当前内存；刷新可能丢失。':'演示操作仅存于此浏览器，可导出；不会写入正式研究档案。';
    $('version-nav').innerHTML=state.versions.slice().reverse().map(v=>`<button data-version="${v.id}" class="${view==='annual'&&selected===v.id?'selected':''}"><b>${v.id} · ${v.status==='active'?'当前生效（演示）':v.status==='candidate'?'候选 / Candidate':'历史 / History'}</b><small>${v.basis?`基于 ${v.basis.stage.toUpperCase()} 修订 ${v.hypothesis}`:'FY2025 10-K 初始报告'}</small></button>`).join('');
    document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-current',b.dataset.view===view?'page':'false'));
    $('q2-status').textContent=RevisionDemo.downstream(state,'q2')?'上游已变，待复核 / Stale':'原实验结果 / Original';
    if(view==='annual') renderAnnual(); else renderVerification();
  }
  function renderAnnual(){
    const v=state.versions.find(x=>x.id===selected)||active();selected=v.id;
    const isCurrent=v.id===state.active;
    $('report').innerHTML=`<p class="rd-meta">年度研究主报告 / Annual research · ${v.id} · ${isCurrent?'当前生效（演示）':v.status==='candidate'?'候选，尚未进入上下文':'历史版本，只读'}</p>
      <h1>我们目前相信什么</h1><p class="rd-lead">${esc(v.report.summary)}</p>${v.id!=='v1'?'<p class="rd-muted">以上是年报原始总论；本版只修订下面指定观点，未自动重写其他内容。</p>':''}
      ${v.basis?`<div class="rd-basis">基于 <a href="#" data-view="${v.basis.stage}">${v.basis.stage.toUpperCase()} 验证报告</a>，从 ${v.parent} 修订 ${v.hypothesis}<br><span>${esc(v.reason)}</span><small>${esc(v.time)} · 演示操作者</small></div>`:''}
      ${v.status==='candidate'?`<div class="rd-actions"><button class="rd-primary" data-confirm="${v.id}">确认此修订生效 / Adopt revision</button><span>需再次确认；当前仍是 ${state.active}。</span></div>`:''}
      ${v.before?`<details class="rd-diff"><summary>查看修订差异 / Changes</summary><div class="rd-pair"><div><h3>修订前 / Before</h3><p>${esc(v.before.text)}</p><p>${esc(v.before.watch)}</p></div><div><h3>修订后 / After</h3><p>${esc(v.after.text)}</p><p>${esc(v.after.watch)}</p></div></div></details>`:''}
      ${v.report.hypotheses.map(h=>`<article><h2>${esc(h.title)}</h2><p class="rd-meta">${esc(h.id)} · ${esc(h.status)}</p><p>${esc(h.judgment)}</p>${h.id==='H1'&&h.judgment.includes('23.70%')?'<p class="rd-muted">原稿保留；利润率精确计算为 23.69%，原稿 23.70% 的取整误差已在原实验校正记录中说明。沿用原句的修订仍需注意这一更正。</p>':''}${evidence(h.sources)}<h3>下一次验证 / To watch</h3><p>${esc(h.test)}</p><details><summary>机制与反证条件 / Rationale & disconfirmation</summary><p>${esc(h.mechanism)}</p><p>${esc(h.falsifier)}</p></details></article>`).join('')}
      ${actions()}`;
  }
  function renderVerification(){
    const r=seed.reports[view], stale=RevisionDemo.downstream(state,view);
    $('report').innerHTML=`<p class="rd-meta">独立验证报告 / Verification · ${view.toUpperCase()} · 材料截止 ${r.cutoff}</p><h1>${esc(r.title)}</h1>
      <p class="rd-lead">${esc(r.summary)}</p><div class="rd-basis">研究来源：年度原稿 v1${view==='q2'?' + Q1 冻结验证报告':''}。<br>这份结果来自已完成的 Codex 实验；不会因本 Demo 的操作而自动变化。</div>
      ${stale?`<div class="rd-warning">当前主报告已是 ${state.active}。Q2 仍是旧输入下的结果，需重新验证；这里没有生成新的 Q2。<button data-context>查看拟用输入 / Preview inputs</button></div>`:''}
      ${r.hypotheses.map(h=>{const original=seed.reports.annual.hypotheses.find(x=>x.id===h.id);const decisions=state.decisions.filter(d=>d.stage===view&&d.hypothesis===h.id);return `<article><p class="rd-meta">对应年度观点 ${h.id}</p><h2>${esc(h.title)}</h2><details><summary>原判断与原定预期 / Original expectation</summary><p>${esc(original.judgment)}</p><p>${esc(original.test)}</p></details><p class="rd-status">${esc(h.status)}</p><p>${esc(h.judgment)}</p>${evidence(h.sources)}<h3>对原判断的影响 / Implication</h3><p>${esc(h.change)}</p><h3>建议保留的验证事项 / Next test</h3><p>${esc(h.next)}</p>
        <div class="rd-actions"><button class="rd-primary" data-edit="${h.id}" ${view==='q2'?'disabled':''}>${view==='q2'?'本轮仅演示 Q1 修订':'基于此建议修订 / Revise'}</button><button data-decision="${h.id}" data-outcome="deferred">暂不处理 / Defer</button><button data-decision="${h.id}" data-outcome="rejected">拒绝并说明 / Decline</button></div>
        ${decisions.length?`<details><summary>人工处理记录 (${decisions.length}) / Decisions</summary>${decisions.map(d=>`<p>${d.outcome==='rejected'?'拒绝':'暂不处理'}：${esc(d.reason)}<small>${esc(d.time)} · 基于 ${d.base}；证据保留</small></p>`).join('')}</details>`:''}</article>`;}).join('')}
      <article><h2>本次新增，不回填为旧预测 / New findings</h2><p>${esc(r.discovery)}</p>${evidence(r.discovery_sources)}</article><p class="rd-muted">${esc(r.valuation)}</p><p><a href="review.html#${view}">阅读原实验完整报告 / Original report</a> · <a href="${view}/answer.json">冻结结果 JSON</a></p>${actions()}`;
  }
  function open(id){lastFocus=document.activeElement;$(id).showModal();}
  document.querySelectorAll('dialog').forEach(d=>d.addEventListener('close',()=>lastFocus?.isConnected&&lastFocus.focus()));
  function beginEdit(hid){
    const base=active(), original=base.report.hypotheses.find(h=>h.id===hid), suggestion=seed.reports[view].hypotheses.find(h=>h.id===hid);
    editor={parent:base.id,hypothesis:hid,basis:{stage:view,answer_sha256:seed.hashes[view],cutoff:seed.reports[view].cutoff},sources:suggestion.sources};
    $('edit-title').textContent=`修订 ${hid} · ${base.id} → 候选版本`;
    $('edit-basis').textContent=`依据 ${view.toUpperCase()} 的已完成报告。这不是新的模型运行；建议文本由已有 change / next 段落组成，可自行修改。`;
    $('edit-original').textContent=original.judgment;
    $('edit-suggestion').textContent=suggestion.change;
    $('edit-text').value=original.judgment+'\n\n'+view.toUpperCase()+' 验证意见：'+suggestion.change;
    $('edit-watch').value=suggestion.next;$('edit-reason').value='';$('edit-error').textContent='';open('editor');
  }
  $('save-draft').onclick=()=>{try{currentStorage();const next=RevisionDemo.save(state,{...editor,text:$('edit-text').value,watch:$('edit-watch').value,reason:$('edit-reason').value,time:new Date().toISOString()});selected=next.versions.at(-1).id;view='annual';persist(next);$('editor').close();notify('候选已保存，尚未生效。请查看差异，再决定是否确认。');}catch(e){$('edit-error').textContent=e.message;}};
  let pendingVersion=null,pendingDecision=null;
  $('adopt-final').onclick=()=>{try{currentStorage();persist(RevisionDemo.adopt(state,pendingVersion,new Date().toISOString()));$('adoption').close();notify('演示修订已生效。旧版保留；Q2 已标记待复核，没有自动重跑。');}catch(e){$('adopt-error').textContent=e.message;}};
  $('decision-save').onclick=()=>{try{currentStorage();persist(RevisionDemo.decide(state,pendingDecision.stage,pendingDecision.id,pendingDecision.outcome,$('decision-reason').value,new Date().toISOString()));$('decision-dialog').close();notify('处理意见已记录，反向证据仍保留。');}catch(e){$('decision-error').textContent=e.message;}};
  document.addEventListener('click',event=>{
    const el=event.target.closest('button,a');if(!el)return;
    if(el.dataset.close){$(el.dataset.close).close();return;}
    if(el.dataset.view){event.preventDefault();view=el.dataset.view;if(view==='annual')selected=state.active;render();return;}
    if(el.dataset.version){view='annual';selected=el.dataset.version;render();return;}
    if(el.dataset.edit){beginEdit(el.dataset.edit);return;}
    if(el.dataset.confirm){pendingVersion=el.dataset.confirm;$('adopt-info').textContent=`将 ${pendingVersion} 设为当前演示主报告；${state.active} 保留为历史，Q2 标记待复核。不会修改正式档案或调用模型。`;$('adopt-error').textContent='';open('adoption');return;}
    if(el.dataset.decision){pendingDecision={stage:view,id:el.dataset.decision,outcome:el.dataset.outcome};$('decision-title').textContent=(el.dataset.outcome==='rejected'?'拒绝建议':'暂不处理')+' · '+el.dataset.decision;$('decision-reason').value='';$('decision-error').textContent='';open('decision-dialog');return;}
    if(el.hasAttribute('data-context')){try{$('context-content').textContent=JSON.stringify(RevisionDemo.context(state),null,2);}catch(e){$('context-content').textContent=e.message;}open('context-dialog');return;}
    if(el.dataset.source){if(event.metaKey||event.ctrlKey)return;event.preventDefault();const e=seed.evidence[el.dataset.source];$('source-title').textContent=e.label+' ['+e.document+']';$('source-open').href=e.url;$('source-frame').src=e.url;open('source-dialog');}
  });
  $('source-dialog').addEventListener('close',()=>$('source-frame').src='about:blank');
  $('reset').onclick=()=>open('reset-dialog');
  $('reset-final').onclick=()=>{persist(RevisionDemo.initial(seed));selected='v1';view='q1';render();$('reset-dialog').close();notify('已恢复演示起点；正式档案始终未修改。');};
  $('export').onclick=()=>{const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='alphabet-revision-demo.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  window.addEventListener('storage',e=>{if(e.key===key)notify('另一个标签更新了演示，请刷新后继续。');});
  render();
})();
