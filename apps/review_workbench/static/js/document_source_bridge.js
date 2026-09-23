
const UTEKI_LOCATIONS=__LOCATIONS__;
const UTEKI_IMAGES=__IMAGES__;
let focused=null;
const sourceTargets={};
function xpath(path){
  // SEC inline-XBRL tag names cannot use an unbound XPath namespace prefix.
  let target=document;
  for(const step of (path||'').split('/').filter(Boolean)){
    const match=step.match(/^([^\[]+)(?:\[(\d+)\])?$/);if(!match)return null;
    const siblings=Array.from(target.children||[]).filter(el=>el.tagName.toLowerCase()===match[1].toLowerCase());
    target=siblings[Number(match[2]||1)-1];if(!target)return null;
  }
  return target;
}
const normalized=value=>(value||'').replace(/\s+/g,'').toUpperCase();
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
