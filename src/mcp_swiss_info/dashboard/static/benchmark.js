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
  const qs=(run.questions||[]).filter(q=>filter==='all'||!q.passed);
  $('qrows').innerHTML=qs.length?qs.map(q=>'<tr>'+
    '<td><span class="pill '+(q.passed?'up_to_date':'failed')+'">'+(q.passed?'Passed':'Failed')+'</span></td>'+
    '<td>'+esc(q.question)+'<div class="sub">'+esc(q.id)+' - '+esc(q.topic)+'</div>'+
      '<details><summary>Answer</summary><div class="answer">'+(esc(q.answer)||'<i>no answer</i>')+'</div></details></td>'+
    '<td>'+(q.cause?'<b>'+esc(labels[q.cause]||q.cause)+'</b>':'')+'<div class="err">'+q.problems.map(esc).join('<br>')+'</div>'+
      ((q.evidence||[]).length?'<details><summary>Evidence in tool output</summary><div class="answer">'+
        q.evidence.map(esc).join('\n\n')+'</div></details>':'')+'</td>'+
    '<td class="sub">'+(q.tools.length?q.tools.map(esc).join(', '):'none')+'</td></tr>').join('')
    :'<tr><td colspan="4" class="sub">No '+(filter==='all'?'questions':'failures')+'.</td></tr>';
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
