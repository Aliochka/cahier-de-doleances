'use strict';
const $ = id => document.getElementById(id);
let state, token, dirty = false, busy = false, timer, loaded = false;
function status(message, error=false) { $('status').textContent=message; $('status').className=error?'error':''; }
function controls(disabled) {
  document.querySelectorAll('button:not(#retry),select').forEach(b=>b.disabled=disabled);
  $('comment').disabled=disabled;
}
async function api(url, payload) {
  const response=await fetch(url, payload ? {method:'POST', headers:{'Content-Type':'application/json','X-Annotation-Token':token},body:JSON.stringify(payload)} : {});
  if (!response.ok) { let message='Opération échouée. Réessayer sans quitter cette page.'; try {message=(await response.json()).error||message;}catch{} throw Error(message); }
  return response.json();
}
function text(id,value) { $(id).textContent=value||''; }
async function render() {
  loaded=false; controls(true); $('retry').hidden=true;
  text('query',state.query); text('progress',`${state.done} / ${state.total} couples annotés`);
  $('queries').replaceChildren(...state.groups.map(g=>{const o=document.createElement('option');o.value=g.position;o.textContent=`${g.text} (${g.done}/${g.total})`;o.selected=g.query_id===state.query_id;return o;}));
  const group=state.groups.find(g=>g.query_id===state.query_id);
  text('localprogress',`Cette requête : ${group.done}/${group.total} annotés · document ${state.position-group.position+1}/${group.total}`);
  text('existing',state.judgment?`Déjà annoté : ${state.judgment.grade}. Vous pouvez modifier la note.`:'Pas encore annoté.');
  $('comment').value=state.draft; dirty=false; $('parent').hidden=true; $('parent').replaceChildren();
  text('answer','Chargement de la réponse…'); text('question','');text('title','');text('form','');
  try {
    const data=await api(`/api/document?position=${state.position}`);const doc=data.documents[0];
    text('answer',doc.text);text('question',doc.question_text);text('form',doc.questionnaire_name);
    text('title',doc.contribution_title ? `Titre : ${doc.contribution_title}`:'');
    loaded=true; controls(false); $('previous').disabled=state.position===0;$('next').disabled=state.position===state.total-1;
    status(state.done===state.total?'Tous les couples sont annotés. Export disponible.':'Prêt · sauvegarde automatique active.');
  } catch(error) { status(error.message,true);$('retry').hidden=false; }
}
async function change(grade=null,destination=null,move=false) {
  if (busy || !loaded) return false;
  clearTimeout(timer);busy=true;controls(true);status('Sauvegarde en cours…');
  try {
    const updated=await api('/api/change',{revision:state.revision,position:state.position,comment:$('comment').value,grade,destination});
    state=updated;dirty=false;status('Enregistré sur disque.');
    if (move || grade!==null) await render();
    return true;
  } catch(error) {
    $('queries').value=state.groups.find(g=>g.query_id===state.query_id).position;
    status(error.message,true);return false;
  }
  finally {busy=false;if(loaded){controls(false);$('previous').disabled=state.position===0;$('next').disabled=state.position===state.total-1;}}
}
$('comment').addEventListener('input',()=>{dirty=true;status('Commentaire non enregistré…');clearTimeout(timer);timer=setTimeout(()=>change(),700);});
$('grades').addEventListener('click',e=>{if(e.target.dataset.grade!==undefined)change(Number(e.target.dataset.grade));});
$('previous').onclick=()=>change(null,state.position-1,true);
$('next').onclick=()=>change(null,state.position+1,true);
$('queries').onchange=e=>change(null,Number(e.target.value),true);
$('retry').onclick=()=>render();
$('parentbutton').onclick=async()=>{
  if (!$('parent').hidden){$('parent').hidden=true;return;}
  try {
    const position=state.position;
    const data=await api(`/api/document?position=${position}&parent=true`);
    if (state.position!==position) return;
    $('parent').replaceChildren(...data.documents.map(d=>{const a=document.createElement('article');const h=document.createElement('h4');h.textContent=d.question_text;const t=document.createElement('p');t.className='text';t.textContent=d.text;a.append(h,t);return a;}));
    $('parent').hidden=false;
  }catch(error){status(error.message,true);}
};
document.addEventListener('keydown',e=>{
  if(e.repeat||e.ctrlKey||e.altKey||e.metaKey||['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)||e.target.isContentEditable||busy||!loaded)return;
  if(['0','1','2','3'].includes(e.key)){e.preventDefault();change(Number(e.key));}
  if(e.key==='ArrowLeft'&&state.position>0){e.preventDefault();change(null,state.position-1,true);}
  if(e.key==='ArrowRight'&&state.position<state.total-1){e.preventDefault();change(null,state.position+1,true);}
});
window.addEventListener('beforeunload',e=>{if(dirty||busy){e.preventDefault();e.returnValue='';}});
async function start(){try{controls(true);state=await api('/api/state');token=state.token;await render();}catch(error){status(error.message,true);$('retry').hidden=false;$('retry').onclick=start;}}
start();

$('export').onclick=async e=>{
  e.preventDefault();
  if(busy)return;
  if(dirty && !(await change()))return;
  try {
    const rows=await api('/api/export');
    const url=URL.createObjectURL(new Blob([JSON.stringify(rows,null,2)+'\n'],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='judgments.json';a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(error){status(error.message,true);}
};
