let run=null,filter='failed';
const pct=(p,t)=>t?Math.round(100*p/t)+'%':'-';
const $=id=>document.getElementById(id);
function meter(p,t){return '<span class="meter"><span style="width:'+(t?100*p/t:0)+'%"></span></span> '+p+'/'+t;}
function render(){
  const m=run.meta||{},labels={};
  (run.causes||[]).forEach(c=>labels[c.cause]=c.label);
  $('bscore').innerHTML='<b>'+pct(run.passed,run.total)+'</b><span class="sub">'+run.passed+'/'+run.total+' passed</span>';
  $('bsub').innerHTML=esc(m.model||'?')+' - '+(m.mcp===false?'without tools (baseline)':'with the MCP tools')+' - '+
    (m.finished?esc(when(m.finished))+' ('+ago(m.finished)+')':'')+' - '+esc(run.run)+
    (run.run_count>1?' - latest of '+run.run_count+' runs':'');
  $('bpills').innerHTML=(run.by_behavior||[]).map(b=>'<span class="pill '+(b.passed===b.total?'up_to_date':b.passed?'outdated':'failed')+'">'+
    esc(b.name.replace(/_/g,' '))+' '+b.passed+'/'+b.total+'</span>').join('');
  $('headline').innerHTML=(run.headline||[]).map(l=>'<p>'+esc(l)+'</p>').join('');
  $('causes').innerHTML=(run.causes||[]).map(c=>'<div class="cause"><span class="count">'+c.count+'</span><div><b>'+esc(c.label)+'</b>'+
    '<div class="sub">'+esc(c.advice)+'</div><div class="ids">'+c.examples.slice(0,6).map(esc).join(', ')+
    (c.count>6?' +'+(c.count-6)+' more':'')+'</div></div></div>').join('');
  $('todo').innerHTML=(run.next_steps||[]).map(t=>'<li>'+esc(t)+'</li>').join('');
  $('topics').innerHTML=(run.by_topic||[]).map(t=>'<tr><td>'+esc(t.name)+'</td><td>'+meter(t.passed,t.total)+'</td></tr>').join('');
  $('tools').innerHTML=(run.tools||[]).length?run.tools.map(t=>'<tr><td>'+esc(t.tool)+(t.example_error?'<div class="err">'+esc(t.example_error.split('\n')[0])+'</div>':'')+
    '</td><td>'+t.calls+'</td><td>'+(t.errors||'')+'</td><td>'+(t.empty||'')+'</td></tr>').join('')
    :'<tr><td colspan="4" class="sub">No tool calls in this run.</td></tr>';
  const cmp=run.compare,other=cmp?cmp.questions:{};
  $('cmp').hidden=$('fchanged').hidden=$('otherhead').hidden=!cmp;
  if(cmp)renderCompare(cmp);
  const cols=cmp?5:4;
  const qs=(run.questions||[]).filter(q=>filter==='all'||(filter==='changed'?q.id in other&&other[q.id]!==q.passed:!q.passed));
  $('qrows').innerHTML=qs.length?qs.map(q=>'<tr>'+
    '<td><span class="pill '+(q.passed?'up_to_date':'failed')+'">'+(q.passed?'Passed':'Failed')+'</span></td>'+
    (cmp?'<td>'+(q.id in other?'<span class="pill '+(other[q.id]?'up_to_date':'failed')+'">'+(other[q.id]?'Passed':'Failed')+'</span>':'')+'</td>':'')+
    '<td>'+esc(q.question)+'<div class="sub">'+esc(q.id)+' - '+esc(q.topic)+'</div>'+
      '<details><summary>Answer</summary><div class="answer">'+(esc(q.answer)||'<i>no answer</i>')+'</div></details></td>'+
    '<td>'+(q.cause?'<b>'+esc(labels[q.cause]||q.cause)+'</b>':'')+'<div class="err">'+q.problems.map(esc).join('<br>')+'</div>'+
      ((q.evidence||[]).length?'<details><summary>Evidence in tool output</summary><div class="answer">'+
        q.evidence.map(esc).join('\n\n')+'</div></details>':'')+'</td>'+
    '<td class="sub">'+(q.tools.length?q.tools.map(esc).join(', '):'none')+'</td></tr>').join('')
    :'<tr><td colspan="'+cols+'" class="sub">No '+(filter==='all'?'questions':filter==='changed'?'differences':'failures')+'.</td></tr>';
}
function renderCompare(cmp){
  const mcpFirst=(run.meta||{}).mcp!==false,withRun=mcpFirst?run:cmp,without=mcpFirst?cmp:run;
  const rate=r=>r&&r.total?r.passed/r.total:null;
  const diff=(a,b)=>{
    if(rate(a)===null||rate(b)===null)return '';
    const d=Math.round(100*(rate(a)-rate(b)));
    return '<span class="pill '+(d>0?'up_to_date':d<0?'failed':'outdated')+'">'+(d>0?'+':'')+d+' pts</span>';
  };
  const row=(name,a,b,strong)=>'<tr><td>'+(strong?'<b>'+esc(name)+'</b>':esc(name))+'</td><td>'+(a?meter(a.passed,a.total):'-')+
    '</td><td>'+(b?meter(b.passed,b.total):'-')+'</td><td>'+diff(a,b)+'</td></tr>';
  const byName=list=>Object.fromEntries((list||[]).map(t=>[t.name,t]));
  const wt=byName(withRun.by_topic),nt=byName(without.by_topic);
  const topics=[...new Set([...Object.keys(wt),...Object.keys(nt)])].sort((x,y)=>parseInt(x)-parseInt(y)||x.localeCompare(y));
  const wb=byName(withRun.by_behavior),nb=byName(without.by_behavior);
  $('cmpsub').textContent='Same '+run.total+' questions. The other run: '+cmp.run+(cmp.meta&&cmp.meta.finished?' ('+ago(cmp.meta.finished)+')':'')+'.';
  $('cmprows').innerHTML=row('All questions',withRun,without,true)+
    Object.keys(wb).map(n=>row('Expected: '+n.replace(/_/g,' '),wb[n],nb[n])).join('')+
    topics.map(n=>row(n.trim(),wt[n],nt[n])).join('');
  const picked=topics.filter(n=>HIST_AREAS.includes(parseInt(n))).map(n=>[n.trim(),wt[n],nt[n]]);
  const sum=i=>picked.reduce((s,x)=>({passed:s.passed+(x[i]?x[i].passed:0),total:s.total+(x[i]?x[i].total:0)}),{passed:0,total:0});
  renderHist([['Total (areas '+HIST_AREAS.join(', ')+')',sum(1),sum(2)]].concat(picked),diff);
}
const HIST_AREAS=[1,11,12];
function renderHist(rows,diff){
  const r=x=>x&&x.total?x.passed/x.total:0,gap=x=>Math.round(100*(r(x[1])-r(x[2])));
  const [all,...topics]=rows;
  const bar=(cls,x)=>'<div class="vbar '+cls+'" style="height:'+100*r(x)+'%"><i>'+(x?Math.round(100*r(x)):'-')+'</i></div>';
  const col=(x,i)=>{const g=gap(x);
    return '<div class="vg '+(i?'':'all ')+(g>0?'up':g<0?'down':'same')+'" data-i="'+i+'"><div class="vd">'+(g?diff(x[1],x[2]):'')+'</div>'+
      '<div class="vbars">'+bar('w',x[1])+bar('n',x[2])+'</div><div class="vl">'+esc(x[0].replace(/_/g,' '))+'</div></div>';};
  const list=[all,...topics];
  $('hist').innerHTML='<div class="vchart"><div class="yaxis">'+[0,25,50,75,100].map(p=>'<span style="bottom:'+p+'%">'+p+'%</span>').join('')+'</div>'+
    '<div class="vscroll"><div class="vplot">'+list.map(col).join('')+'</div></div></div>';
  const tip=$('htip'),fmt=x=>x?x.passed+'/'+x.total+' ('+Math.round(100*r(x))+'%)':'-';
  $('hist').onmousemove=e=>{const row=e.target.closest('.vg');tip.hidden=!row;if(!row)return;
    const x=list[row.dataset.i],g=gap(x);
    tip.innerHTML='<b>'+esc(x[0])+'</b><br>With MCP: '+fmt(x[1])+'<br>Without MCP: '+fmt(x[2])+'<br>Difference: '+(g>0?'+':'')+g+' pts';
    tip.style.left=Math.min(e.clientX+14,innerWidth-tip.offsetWidth-8)+'px';tip.style.top=(e.clientY+14)+'px';};
  $('hist').onmouseleave=()=>tip.hidden=true;
}
async function load(){
  const d=await (await fetch('/api/benchmark')).json();
  run=d.run;
  $('empty').hidden=!!run;$('bench').hidden=!run;
  if(run)render();
}
document.addEventListener('click',e=>{
  const b=e.target.closest('button[data-f]');if(!b)return;
  filter=b.dataset.f;
  document.querySelectorAll('button[data-f]').forEach(x=>x.classList.toggle('on',x===b));
  render();
});
load();
