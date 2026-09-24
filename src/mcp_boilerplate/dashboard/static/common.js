let token=sessionStorage.getItem('tok')||'';
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const when=t=>t?new Date(t).toLocaleString():'';
function askToken(){if(!token){token=prompt('Dashboard token')||'';sessionStorage.setItem('tok',token);}}
function ago(t){
  const m=Math.max(0,Math.round((Date.now()-new Date(t))/60000));
  if(m<1)return 'just now';if(m<60)return m+' min ago';
  const h=Math.round(m/60);if(h<24)return h+' h ago';
  const d=Math.round(h/24);if(d<60)return d+(d===1?' day ago':' days ago');
  return Math.round(d/30)+' months ago';
}
const STATES={up_to_date:'Up to date',outdated:'Outdated',failed:'Failed',never_crawled:'Never crawled'};
function badge(s){
  const recency=s.last_refresh?' - '+ago(s.last_refresh):'';
  const text=s.state==='never_crawled'?STATES[s.state]
    :s.state==='failed'?'Refresh failed - saved copy '+ago(s.last_refresh).replace(' ago',' old')
    :(s.state==='up_to_date'?'Updated':STATES[s.state])+recency;
  return '<span class="pill '+s.state+'" title="'+esc(STATES[s.state])+'">'+esc(text)+'</span>';
}
