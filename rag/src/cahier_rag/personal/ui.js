'use strict';
let token;
const status=document.querySelector('#status'), button=document.querySelector('#submit');
function add(parent,tag,text){const el=document.createElement(tag);el.textContent=text;parent.append(el);return el;}
function display(result){
 const answer=document.querySelector('#answer'), sources=document.querySelector('#sources');
 answer.replaceChildren();sources.replaceChildren();add(answer,'h2','Synthèse à vérifier');add(answer,'p','Les paragraphes rapportent des contributions sélectionnées, pas des faits établis ni l’opinion de la population.');
 for(const block of result.answer.blocks){const p=add(answer,'p',block.text);for(const ref of block.references){const a=document.createElement('a');a.textContent=` [${ref}${result.sources.some(source=>source.reference===ref&&source.incomplete)?" · extrait incomplet":""}]`;a.href=`#source-${ref}`;p.append(a);}}
 if(result.answer.insufficient_sources)add(answer,'p','Sources insuffisantes pour une réponse utile.');
 for(const limit of result.answer.limits)add(answer,'p',`Limite : ${limit}`);
 add(answer,'p',`Durée totale : ${result.timings.total_seconds.toFixed(1)} s. Références vérifiables, fidélité non garantie.`);
 add(sources,'h2','Sources consultées');
 for(const source of result.sources){const entry=result.citation_map[source.reference].source;const d=document.createElement('details');d.id=`source-${source.reference}`;sources.append(d);add(d,'summary',`${source.reference} — ${source.questionnaire}${source.incomplete?' · extrait incomplet':''}`);add(d,'h3',source.question);add(d,'pre',source.answer);add(d,'p',`Texte citoyen consultable normalisé. ${source.incomplete?'Seul cet extrait a été transmis au générateur.':''}`);add(d,'pre',JSON.stringify({metadata:entry.metadata,excerpt:entry.technical.excerpt,omitted_ranges:entry.technical.omitted_ranges},null,2));}
}
async function poll(id){const r=await fetch(`/api/jobs/${id}`);if(!r.ok)throw Error('Calcul introuvable.');const state=await r.json();status.textContent=state.phase;if(state.status==='error')throw Error(state.error);if(state.status==='complete'){display(state.result);return;}await new Promise(resolve=>setTimeout(resolve,1500));return poll(id);}
document.querySelector('#ask').addEventListener('submit',async event=>{event.preventDefault();button.disabled=true;status.textContent='Démarrage…';document.querySelector('#answer').replaceChildren();document.querySelector('#sources').replaceChildren();try{if(!token)throw Error('Session locale non initialisée. Recharger.');const r=await fetch('/api/ask',{method:'POST',headers:{'Content-Type':'application/json','X-Rag-Token':token},body:JSON.stringify({query:document.querySelector('#query').value})});const data=await r.json();if(!r.ok)throw Error(data.error||'Échec du démarrage.');await poll(data.job_id);}catch(error){status.textContent=error.message;}finally{button.disabled=false;}});
fetch('/api/state').then(r=>r.json()).then(state=>{token=state.token;document.querySelector("#scope").textContent=state.scope;}).catch(()=>{status.textContent='Service local indisponible.';});

document.addEventListener("click",event=>{const link=event.target.closest("a[href^=\"#source-\"]");if(link){const target=document.getElementById(link.hash.slice(1));if(target)target.open=true;}});
