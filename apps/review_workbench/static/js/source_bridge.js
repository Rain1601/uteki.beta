
const UTEKI_BLOCKS=__UTEKI_DATA_JSON__;
const normalize=value=>(value||'').replace(/\u00a0/g,' ').replace(/\s+/g,' ').trim();
const compact=value=>normalize(value).replace(/\s/g,'');
const blockByOrdinal=new Map();
let currentLanguage='zh';
let fallbackHighlights=[];
function textMap(root){
  const walker=document.createTreeWalker(root,4,{acceptNode(node){
    return node.parentElement?.closest('#uteki-source-status,.uteki-translation')?2:1;
  }});
  let output='',node,mapping=[];
  while(node=walker.nextNode()){
    for(let offset=0;offset<node.data.length;offset++){
      const char=node.data[offset];
      if(/\s/.test(char))continue;
      output+=char;mapping.push({node,offset});
    }
  }
  return {text:output.trim(),mapping};
}
function locateBlocks(){
  const elements=Array.from(document.querySelectorAll('body div,body p,body li,body td'));
  for(const block of UTEKI_BLOCKS){
    const needle=compact(block.text);
    const target=elements
      .filter(element=>!element.closest('#uteki-source-status,.uteki-translation')&&compact(element.textContent).includes(needle))
      .sort((left,right)=>normalize(left.textContent).length-normalize(right.textContent).length)[0];
    if(!target)continue;
    target.dataset.utekiOrdinals=[target.dataset.utekiOrdinals,block.ordinal].filter(Boolean).join(',');target.dataset.utekiCovered='true';
    if(target.querySelector('table'))target.dataset.utekiTable='true';
    const translation=document.createElement('div');translation.className='uteki-translation';translation.dataset.utekiOrdinal=block.ordinal;translation.textContent=block.translation_zh;
    target.before(translation);blockByOrdinal.set(String(block.ordinal),{target,translation});
  }
}
function highlight(root,quote){
  if(!root||!quote)return;
  const needle=compact(quote);if(!compact(root.textContent).includes(needle))return;
  if(window.CSS?.highlights){
    const value=textMap(root),start=value.text.indexOf(needle),first=value.mapping[start],last=value.mapping[start+needle.length-1];if(!first||!last)return;
    const range=document.createRange();range.setStart(first.node,first.offset);range.setEnd(last.node,last.offset+1);CSS.highlights.set('uteki-evidence',new Highlight(range));return;
  }
  const candidates=[...root.querySelectorAll('span,td,th')].filter(element=>{const value=compact(element.textContent);return value&&(needle.includes(value)||value.includes(needle))});
  fallbackHighlights=candidates.filter(element=>!candidates.some(other=>other!==element&&element.contains(other)));if(!fallbackHighlights.length)fallbackHighlights=[root];fallbackHighlights.forEach(element=>element.classList.add('uteki-exact-fallback'));
}
function clearHighlight(){
  if(window.CSS?.highlights)CSS.highlights.delete('uteki-evidence');
  fallbackHighlights.forEach(element=>element.classList.remove('uteki-exact-fallback'));fallbackHighlights=[];
}
function focusEvidence(message){
  currentLanguage=message.language||currentLanguage;document.body.classList.toggle('uteki-zh',currentLanguage==='zh');
  document.querySelectorAll('.uteki-focus').forEach(value=>value.classList.remove('uteki-focus'));clearHighlight();
  const block=blockByOrdinal.get(String(message.ordinal));if(!block)return;
  const target=currentLanguage==='zh'?block.translation:block.target;target.classList.add('uteki-focus');highlight(target,currentLanguage==='zh'?message.quoteZh:message.quoteEn);target.scrollIntoView({behavior:'smooth',block:'center'});
}
window.addEventListener('message',event=>{if(event.data?.type==='uteki-focus')focusEvidence(event.data);if(event.data?.type==='uteki-language'){currentLanguage=event.data.language;document.body.classList.toggle('uteki-zh',currentLanguage==='zh')}});
window.addEventListener('DOMContentLoaded',()=>{
  const status=document.createElement('div');status.id='uteki-source-status';status.innerHTML=`<b>SEC 10-K · 原始版式</b><span>中文证据译文 ${UTEKI_BLOCKS.length} / 1311</span><span>未覆盖内容保留英文</span>`;document.body.prepend(status);locateBlocks();parent.postMessage({type:'uteki-source-ready',located:blockByOrdinal.size,total:UTEKI_BLOCKS.length},'*');
});
