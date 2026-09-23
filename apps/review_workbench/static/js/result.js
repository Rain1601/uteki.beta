
const body=document.body;
let currentLanguage='zh',currentView='original',currentFocus=null,sourceReady=false;
const sourceFrame=document.querySelector('.original-frame');
function sendToSource(message){if(sourceReady&&sourceFrame?.contentWindow)sourceFrame.contentWindow.postMessage(message,'*')}
function language(value){currentLanguage=value;body.classList.toggle('zh',value==='zh');document.querySelectorAll('.lang button').forEach(button=>button.classList.toggle('on',button.id===value));localStorage.setItem('uteki-lang',value);sendToSource({type:'uteki-language',language:value});if(currentFocus)sendFocus()}
function setView(value){currentView=value;body.classList.toggle('view-original',value==='original');body.classList.toggle('view-structured',value==='structured');document.querySelectorAll('.view-switch button').forEach(button=>button.classList.toggle('on',button.dataset.view===value));localStorage.setItem('uteki-source-view',value);if(value==='original'&&currentFocus)sendFocus();if(value==='structured'&&currentFocus)focusStructured(currentFocus)}
function sendFocus(){if(!currentFocus)return;sendToSource({type:'uteki-focus',language:currentLanguage,ordinal:currentFocus.ordinal,quoteEn:currentFocus.quoteEn,quoteZh:currentFocus.quoteZh})}
function markExact(element,needle){
  if(!element)return;const raw=element.dataset.raw||element.textContent;element.dataset.raw=raw;element.textContent='';const index=needle?raw.indexOf(needle):-1;
  if(index<0){element.textContent=raw;return}element.append(document.createTextNode(raw.slice(0,index)));const mark=document.createElement('mark');mark.textContent=needle;element.append(mark,document.createTextNode(raw.slice(index+needle.length)));
}
function focusStructured(focus){
  const row=document.querySelector(`.source-row[data-paragraph="${focus.ordinal}"]`);if(!row)return;
  row.classList.add('active');markExact(row.querySelector('.source-original'),focus.quoteEn);markExact(row.querySelector('.source-translation'),focus.quoteZh);row.scrollIntoView({behavior:'smooth',block:'center'});
}
function showClaim(claim,focusOrdinal,focusEvidence){
  document.querySelectorAll('.claim').forEach(value=>value.classList.remove('active'));claim.classList.add('active');
  document.querySelectorAll('.source-original,.source-translation').forEach(value=>{if(value.dataset.raw)value.textContent=value.dataset.raw});
  const ordinals=claim.dataset.ordinals.split(',').filter(Boolean);
  document.querySelectorAll('.source-row').forEach(row=>{row.classList.toggle('relevant',ordinals.includes(row.dataset.paragraph));row.classList.remove('active')});
  const sourceDocument=document.querySelector('.source-document');ordinals.forEach(ordinal=>{const value=document.querySelector(`.source-row[data-paragraph="${ordinal}"]`);if(value)sourceDocument.appendChild(value)});
  const target=String(focusOrdinal||ordinals[0]||'');const cards=Array.from(claim.querySelectorAll('.evidence-card'));const activeCard=cards.find(card=>focusEvidence?card.dataset.evidence===focusEvidence:card.dataset.ordinal===target)||cards[0];
  const anchor=activeCard?.querySelector('.evidence-snippet');currentFocus={ordinal:target,quoteEn:anchor?.dataset.quoteEn||'',quoteZh:anchor?.dataset.quoteZh||''};
  if(currentView==='structured')focusStructured(currentFocus);else sendFocus();
  document.querySelectorAll('.evidence-card').forEach(card=>card.classList.toggle('active',card===activeCard));
}
function selectNode(button){
  document.querySelectorAll('.tree-node').forEach(value=>value.classList.remove('active'));document.querySelectorAll('.knowledge-detail').forEach(value=>value.classList.remove('active'));button.classList.add('active');
  const detail=document.querySelector(`[data-detail="${button.dataset.select}"]`);detail.classList.add('active');const first=detail.querySelector('.claim');if(first)showClaim(first);
}
document.getElementById('en').onclick=()=>language('en');document.getElementById('zh').onclick=()=>language('zh');
document.querySelectorAll('.view-switch button').forEach(button=>button.onclick=()=>setView(button.dataset.view));
document.querySelectorAll('.toggle').forEach(button=>button.onclick=event=>{event.stopPropagation();button.closest('li').classList.toggle('collapsed')});
document.querySelectorAll('.tree-node').forEach(button=>button.onclick=()=>selectNode(button));
document.querySelectorAll('.claim-main').forEach(button=>button.onclick=()=>showClaim(button.closest('.claim')));
document.querySelectorAll('.evidence-card').forEach(button=>button.onclick=event=>{event.stopPropagation();showClaim(button.closest('.claim'),button.dataset.ordinal,button.dataset.evidence)});
window.addEventListener('message',event=>{if(event.data?.type==='uteki-source-ready'){sourceReady=true;sendFocus()}});
language(localStorage.getItem('uteki-lang')||'zh');setView(localStorage.getItem('uteki-source-view')||'original');
selectNode(document.querySelector('.tree-node.active'));
