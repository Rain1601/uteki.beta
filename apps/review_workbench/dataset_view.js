(()=>{
 const search=document.getElementById('ds-search'),metric=document.getElementById('ds-metric');
 const rows=[...document.querySelectorAll('.ds-grid tbody tr')];
 function filter(){const q=search.value.trim().toLowerCase(),m=metric.value;let count=0;rows.forEach(row=>{row.hidden=!(row.dataset.search.includes(q)&&(!m||row.dataset.metric===m));if(!row.hidden)count++});document.getElementById('ds-count').textContent=count+' / '+rows.length;document.getElementById('ds-empty').hidden=count!==0}
 search.addEventListener('input',filter);metric.addEventListener('change',filter);filter();
})();
