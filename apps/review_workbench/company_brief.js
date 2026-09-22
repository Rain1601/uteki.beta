document.addEventListener('DOMContentLoaded',()=>{
 document.body.classList.add('company-brief');
 const main=document.querySelector('.workspace-main');
 const resize=()=>document.documentElement.style.setProperty('--brief-height',Math.max(320,innerHeight-main.getBoundingClientRect().top)+'px');
 new ResizeObserver(resize).observe(document.getElementById('site-navigation'));window.addEventListener('resize',resize);resize();
 document.querySelectorAll('.cb-toggle').forEach(button=>button.addEventListener('click',()=>{
  const article=button.closest('.cb-judgment'),text=article.querySelector('.cb-text'),expanded=button.getAttribute('aria-expanded')==='true';
  text.getAnimations().forEach(a=>a.cancel());const before=text.getBoundingClientRect().height;
  article.classList.toggle('expanded',!expanded);button.setAttribute('aria-expanded',String(!expanded));
  button.querySelector('.cb-toggle-label').innerHTML=expanded?'<span lang="zh">展开</span><span lang="en">Expand</span>':'<span lang="zh">收起</span><span lang="en">Collapse</span>';
  const after=text.getBoundingClientRect().height;
  if(!matchMedia('(prefers-reduced-motion: reduce)').matches)text.animate([{height:before+'px'},{height:after+'px'}],{duration:200,easing:'cubic-bezier(.2,.7,.2,1)'});
 }));
});
