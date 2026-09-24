let needsToken=false;
async function load(){
  const d=await (await fetch('/api/status')).json();
  needsToken=d.needs_token;
  [['CRAWLORA_API_KEY','s1'],['OPENAI_API_KEY','s2']].forEach(([k,id])=>{
    const v=d.keys[k];
    document.getElementById(id).innerHTML='<span class="dot'+(v.set?' on':'')+'"></span>'+(v.set?'set'+(v.hint?' ('+esc(v.hint)+')':''):'not set');
  });
}
document.addEventListener('click',e=>{
  const b=e.target.closest('.help');if(!b)return;
  const t=document.getElementById(b.dataset.tip),open=t.hidden;
  t.hidden=!open;b.setAttribute('aria-expanded',String(open));
});
document.getElementById('settings').addEventListener('submit',async e=>{
  e.preventDefault();
  const body={},msg=document.getElementById('smsg');
  new FormData(e.target).forEach((v,k)=>{if(v.trim())body[k]=v.trim();});
  if(needsToken)askToken();
  const r=await fetch('/api/settings',{method:'POST',headers:{'content-type':'application/json','x-dashboard-token':token},body:JSON.stringify(body)});
  const d=await r.json();
  msg.className='msg '+(r.ok?'ok':'bad');
  msg.textContent=r.ok?'Saved. Refresh is active now. Restart your harness so the MCP server picks up the new keys.':(d.error||r.statusText);
  if(r.ok){e.target.reset();await load();}
});
load();
