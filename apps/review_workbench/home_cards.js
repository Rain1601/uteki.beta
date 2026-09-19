document.addEventListener('DOMContentLoaded',()=>{
 document.body.classList.add('home-cards');
 const main=document.querySelector('.workspace-main'),nav=document.getElementById('site-navigation');
 const resize=()=>document.documentElement.style.setProperty('--home-height',Math.max(280,innerHeight-main.getBoundingClientRect().top-12)+'px');
 new ResizeObserver(resize).observe(nav);window.addEventListener('resize',resize);resize();
 const rows=[...document.querySelectorAll('.hc-item')],filter=document.getElementById('hc-only-unread');
 const marks=new Map();let storageOK=true;
 rows.forEach(r=>{try{marks.set(r.dataset.readKey,localStorage.getItem('uteki-report-read:'+r.dataset.readKey)==='1')}catch{storageOK=false}});
 function refresh(){rows.forEach(r=>{const read=marks.get(r.dataset.readKey);r.classList.toggle('is-read',!!read);r.querySelector('.hc-unread').hidden=!!read;r.hidden=!!(r.closest('.hc-primary')&&filter.checked&&read)})}
 function mark(key,value){try{localStorage.setItem('uteki-report-read:'+key,value?'1':'0');marks.set(key,value);refresh()}catch{document.getElementById('hc-status').textContent='无法保存查看标记 / Could not save read mark'}}
 if(!storageOK)document.getElementById('hc-status').textContent='本机查看标记暂不可用 / Local read marks unavailable';
 function close(card){card.querySelector('.hc-list').hidden=false;card.querySelector('.hc-detail').hidden=true;card.classList.remove('is-reading');card.querySelectorAll('.hc-open').forEach(b=>b.setAttribute('aria-expanded','false'));const target=card._opener;if(target&&!target.closest('[hidden]'))target.focus();else card.querySelector('.hc-list').focus()}
 rows.forEach(row=>{const button=row.querySelector('.hc-open');button.addEventListener('click',()=>{const card=row.closest('.hc-card'),detail=card.querySelector('.hc-detail');card._opener=button;detail.replaceChildren(row.querySelector('template').content.cloneNode(true));card.querySelector('.hc-list').hidden=true;detail.hidden=false;card.classList.add('is-reading');button.setAttribute('aria-expanded','true');mark(row.dataset.readKey,true);detail.querySelector('.hc-back').onclick=()=>close(card);detail.querySelector('.hc-unread-action').onclick=()=>{mark(row.dataset.readKey,false);close(card)};detail.querySelector('.hc-back').focus()});});
 filter.addEventListener('change',refresh);document.querySelectorAll('[data-history]').forEach(button=>button.onclick=()=>{const card=button.closest('.hc-card');if(card.classList.contains('is-reading'))close(card);card.querySelectorAll('[data-events]').forEach(el=>el.hidden=el.dataset.events!==button.dataset.history);card.querySelectorAll('[data-history]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));card.querySelector('.hc-list').scrollTop=0});
 document.querySelectorAll('.hc-card').forEach(card=>card.addEventListener('keydown',event=>{if(event.key==='Escape'&&card.classList.contains('is-reading'))close(card)}));refresh();
});
