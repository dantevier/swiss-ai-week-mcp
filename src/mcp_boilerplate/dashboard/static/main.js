let can=false,needsToken=false;
async function load(){
  const d=await (await fetch('/api/status')).json();
  can=d.can_refresh;needsToken=d.needs_token;
  document.getElementById('sub').innerHTML=
    'Updated '+esc(when(d.generated_at))+' - outdated after '+d.stale_after_days+' days'+
    (can?'':' - refresh disabled: <a href="/settings">add your API keys in Settings</a>');
  document.querySelectorAll('.all button').forEach(b=>b.disabled=!can);
  const n={};d.sources.forEach(x=>n[x.state]=(n[x.state]||0)+1);
  document.getElementById('pills').innerHTML=Object.keys(STATES).filter(k=>n[k]).map(k=>'<span class="pill '+k+'">'+n[k]+' '+STATES[k].toLowerCase()+'</span>').join('');
  document.getElementById('rows').innerHTML=d.sources.map(s=>'<tr>'+
    '<td>'+esc(s.level)+'</td>'+
    '<td>'+(s.url?'<a href="'+esc(s.url)+'" target="_blank" rel="noopener">'+esc(s.source)+'</a>':esc(s.source))+
      '<div class="sub">'+esc(s.authority)+'</div></td>'+
    '<td>'+badge(s)+'</td>'+
    '<td>'+(when(s.last_refresh)||'never')+'</td>'+
    '<td>'+s.passages+'</td>'+
    '<td>'+when(s.last_failure)+'<div class="err">'+esc(s.error)+'</div></td>'+
    '<td>'+(s.refreshable?'<button data-l="'+esc(s.level)+'" data-s="'+esc(s.source)+'"'+(can?'':' disabled')+'>Refresh</button>':'')+'</td></tr>').join('');
}
async function refresh(btn){
  const l=btn.dataset.l,s=btn.dataset.s||'all';
  if(needsToken)askToken();
  const old=btn.textContent;btn.disabled=true;btn.textContent='Refreshing...';
  try{
    const r=await fetch('/api/refresh/'+l+'/'+s,{method:'POST',headers:{'x-dashboard-token':token}});
    if(!r.ok){alert((await r.json()).error||r.statusText);}
  }finally{btn.textContent=old;btn.disabled=false;await load();}
}
document.addEventListener('click',e=>{const b=e.target.closest('button[data-l]');if(b&&!b.disabled)refresh(b);});
load();
