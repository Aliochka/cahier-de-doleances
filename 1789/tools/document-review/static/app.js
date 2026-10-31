'use strict';
const $=id=>document.getElementById(id);
const reviewReasonLabels={human_boundary_validated_since_generation:'Les frontières ont été validées humainement depuis la génération du corpus.',overlap_requires_attribution_review:'Les plages de plusieurs notices se recouvrent : vérifier l’attribution du texte.',identity_ambigu:'L’identité documentaire reste ambiguë.',identity_non_retrouve:'Aucune correspondance suffisamment établie.',identity_hors_perimetre:'La nature ou le périmètre documentaire demande un contrôle.',alignment_probable_not_independently_established:'Le rapprochement est plausible mais manque encore d’indices concordants.',cahier_not_located:'Le cahier n’a pas encore de plage source exploitable.',associated_document_not_located:'La pièce associée reste à localiser.',human_boundary_preserved_with_documentary_alternative:'La frontière humaine est conservée ; une autre ouverture possible est signalée.',documentary_alternatives_require_review:'Des ouvertures ou périmètres concurrents restent à départager.'};
const reviewLevels={high:'haute',medium:'moyenne',low:'basse / échantillonnage',none:'aucun contrôle demandé'};
const labels={proposed:'Proposé automatiquement',codex_reviewed:'Examiné par Codex',human_validated:'Validé humainement',uncertain:'Incertain',blocked:'Bloqué'};
let corpusDefaultApplied=false;
let records=[],filtered=[],current=null,draft={},token='',dirty=false,radius=6,activeSeconds=0,lastTick=performance.now(),lastActivity=performance.now();
const el=(tag,text)=>{const e=document.createElement(tag);e.textContent=text;return e;};
async function api(path,options){const r=await fetch(path,options);const data=await r.json();if(!r.ok)throw new Error(data.error||r.status);return data;}
function showError(error){$('message').textContent='Erreur : '+error.message;}

const documentaryAlerts={
 following_section_or_attached_piece_within_metadata_pages:'Le regroupement automatique inclut une section suivante ou une pièce jointe située dans les pages indiquées. Vérifiez qu’elle appartient bien au même dossier.',
 end_page_mismatch_requires_review:'La page de fin proposée diffère de celle du catalogue. Vérifiez la clôture et le document suivant.',
 new_control_boundary_incorrect:'Un contrôle antérieur a repéré une erreur dans les frontières automatiques. Comparez-les à la référence examinée.',
 new_control_boundary_uncertain:'Un contrôle antérieur laisse les frontières incertaines. Un examen supplémentaire est nécessaire.',
 new_control_source_composite_or_interleaved_columns:'La source mêle plusieurs documents ou des colonnes intercalées. Une simple plage continue peut être insuffisante.',
 next_literal_internal_cahier_title:'Un autre titre de cahier apparaît dans le contexte. Vérifiez où commence le document suivant.',
 new_control_classification_disagreement:'Les contrôles antérieurs divergent sur la nature du document : cahier, pièce associée ou autre document.',
 historical_cahier_announced_but_text_absent:'Une notice annonce un cahier dont le texte semble absent. Ne validez pas la notice comme le texte du cahier.',
 new_control_identity_error:'Un contrôle antérieur a repéré une erreur d’identification. Vérifiez le titre, le lieu et l’ordre concernés.',
 same_primary_anchor_multiple_notices:'Plusieurs notices pointent vers le même emplacement Stanford. Vérifiez les limites entre ces documents.'
};
const documentaryFindings={
 'arcpa_0000-0000_1879_num_4_1_2175':'Contrôle de Ferrières : après Agriculture, le cahier continue avec Commerce, puis Justices seigneuriales. Conservez la clôture et les signatures du bloc v4-b013967 ; le cahier de Férolles commence ensuite. Une fin avant ces sections doit être réexaminée.'
};
function alertMessages(record,state){
 const codes=[...new Set([...(record.anomalies||[]),...(record.boundaries.proposal?.flags||[])])];
 const messages=codes.map(code=>documentaryAlerts[code]||'Un autre point documentaire nécessite un examen. Consultez les détails techniques ci-dessous.');
 if(documentaryFindings[record.persee_id])messages.push(documentaryFindings[record.persee_id]);
 if(state.stale)messages.push('Décision ancienne incompatible avec les sources actuelles.');
 if(state.selected?.inside_block)messages.push('La plage initiale coupe un bloc ou ne contient aucun bloc complet : ne pas accepter silencieusement.');
 return [...new Set(messages)];
}

async function refresh(){const meta=await api('/api/meta');token=meta.token;if(meta.corpus?.available){if(!corpusDefaultApplied){$('batch').checked=false;corpusDefaultApplied=true;}const c=meta.corpus.summary;$('corpus-summary').textContent=`Collection globale : ${c.notices_examined} notices · ${c.texts_extracted} textes extraits · ${c.counts.article} articles (état à la génération). Les frontières automatiques restent des propositions.`;}const s=meta.stats;$('stats').textContent=`${s.examined_documents} dossiers examinés dans l’outil · ${s.human_validated} validés humainement · ${s.corrected_endpoints} frontières corrigées · ${Math.round(s.measured_active_seconds)} s d’activité enregistrée (estimation)`;records=await api('/api/list');filter();}
function filter(){const q=$('query').value.toLocaleLowerCase('fr');filtered=records.filter(r=>(!$('volume-filter').value||String(r.volume)===$('volume-filter').value)&&(!$('batch').checked||r.batch)&&(!$('priority').checked||(r.documentary_review?r.documentary_review.priority==='high':r.priority==='haute'||r.boundary_class==='automatic_suspect'||r.extraction_state==='unresolved'))&&(!$('review-level').value||r.documentary_review?.priority===$('review-level').value)&&(!$('status').value||r.status===$('status').value)&&(!q||`${r.title} ${r.persee_id} ${r.id}`.toLocaleLowerCase('fr').includes(q)));$('count').textContent=`${filtered.length} dossiers affichés sur ${records.length}`;$('list').replaceChildren();for(const r of filtered){const li=el('li',''),button=el('button',r.title);button.addEventListener('click',()=>open(r.id));li.append(button,el('small',`Tome ${r.volume}, p. ${r.pages.join('–')} · ${labels[r.status]} · rapprochement ${r.alignment} · priorité ${r.documentary_review?reviewLevels[r.documentary_review.priority]:r.priority}`));$('list').append(li);}}
function canLeave(){return !dirty||window.confirm('Des modifications ne sont pas enregistrées. Les abandonner ?');}
async function open(id,expanding=false){if(!expanding&&!canLeave())return;try{if(!expanding){radius=6;draft={};activeSeconds=0;lastTick=performance.now();lastActivity=lastTick;}const p=new URLSearchParams({id,radius});if(expanding){if(draft.start_id)p.set('start_id',draft.start_id);if(draft.end_id)p.set('end_id',draft.end_id);}current=await api('/api/document?'+p);if(!expanding){draft={start_id:current.state.selected?.start_id,end_id:current.state.selected?.end_id};$('note').value=current.state.event?.note||'';for(const which of ['start','end']){$(which+'-decision').value=current.state.event?.endpoint_decisions[which]||(current.state.selected?.[which+'_inside_block']?'inside_block':draft[which+'_id']?'accepted':'uncertain');}$('confirm').checked=false;$('message').textContent='';$('save-notice').hidden=true;dirty=false;}render();$('catalogue').hidden=true;$('document').hidden=false;if(!expanding){$('title').focus();const url=new URL(window.location.href);url.searchParams.set('document',id);history.replaceState(null,'',url);}return true;}catch(e){showError(e);window.alert(e.message);return false;}}
function render(){const r=current.record;const resolution=current.documentary_resolution;const review=current.documentary_review;$('documentary-review-info').textContent=(review?'Contrôle documentaire : priorité '+reviewLevels[review.priority]+'. '+[...new Set(review.reasons.map(code=>reviewReasonLabels[code]).filter(Boolean))].join(' ')+' ':'')+(resolution?.changed?'Une correction automatique étayée par les titres et positions XML a été appliquée. Elle ne constitue pas une validation humaine. ':'')+(resolution?.resolved_alerts?.length?resolution.resolved_alerts.length+' alerte(s) historique(s) expliquée(s), avec preuves dans les détails. ':'')+(resolution?.conflicts?.length?'Des alternatives ou divergences restent à examiner ; les décisions humaines sont conservées.':'');$('title').textContent=r.metadata.title;$('metadata').textContent=`${r.persee_id} · tome ${r.metadata.volume}, p. ${r.metadata.page_start}–${r.metadata.page_end} · ${labels[current.state.status]} · identité ${r.alignment_status}`;$('links').replaceChildren();for(const [title,url] of [['Notice Persée',r.metadata.document_url],['Numérisation Stanford',r.source.scan_url]]){const a=el('a',title);a.href=url;a.target='_blank';a.rel='noopener noreferrer';$('links').append(a,document.createTextNode(' · '));}$('alerts').textContent=alertMessages(r,current.state).join(' · ')||'Aucune alerte automatique ; cela ne certifie pas le périmètre.';$('selection').textContent=current.batch?.reason||'Hors lot initial ; notice du registre complet.';$('provenance').textContent=JSON.stringify({alertes_brutes:r.anomalies,automatique:r.boundaries.proposal,reference:current.state.selected,origine:current.state.origin,resolution_documentaire:current.documentary_resolution,controle_documentaire:current.documentary_review,controles:r.controls,version:current.source_version},null,2);$('history').textContent=current.history.length?JSON.stringify(current.history,null,2):'Aucune décision humaine enregistrée.';$('alternatives').replaceChildren();for(const alt of current.alternatives){if(!alt.span?.start_id)continue;const b=el('button','Afficher le début candidat : '+alt.title);b.addEventListener('click',()=>{draft.start_id=alt.span.start_id;$('start-decision').value='corrected';dirty=true;open(r.id,true);});$('alternatives').append(b);}for(const which of ['start','end']){const panel=$(which+'-panel');panel.replaceChildren();for(const block of current.panels[which].blocks){const item=el('article','');item.className='block';item.dataset.blockId=block.id;item.append(el('small',`${block.id} · page ${block.page.page??'?'} (${block.page.method||'pb'}) · ${block.tag}`));if(block.tag==='pb'){item.append(el('p','— Changement de page —'));}else{const text=el('p',block.text);text.className='source';item.append(text);const controls=el('div','');controls.className='choices';for(const side of ['start','end']){const button=el('button',side==='start'?'Choisir comme début':'Choisir comme fin');button.type='button';button.setAttribute('aria-label',`${side==='start'?'Début':'Fin'} : ${block.id}`);button.addEventListener('click',()=>{draft[side+'_id']=block.id;$(side+'-decision').value='corrected';$('confirm').checked=false;dirty=true;highlight();});controls.append(button);}item.append(controls);}panel.append(item);}}$('radius').textContent=` ${radius} blocs de chaque côté de chaque ancre · tous les blocs affichés sont complets`;$('expand').disabled=radius>=2000;const i=filtered.findIndex(x=>x.id===r.id);$('previous').disabled=i<=0;$('next').disabled=i<0||i===filtered.length-1;highlight();}
function highlight(){for(const b of document.querySelectorAll('.block')){b.classList.toggle('selected-start',b.dataset.blockId===draft.start_id);b.classList.toggle('selected-end',b.dataset.blockId===draft.end_id);} $('chosen').textContent=`Début : ${draft.start_id||'non établi'} · fin incluse : ${draft.end_id||'non établie'}`;}
for(const id of ['query','status','batch','priority','volume-filter','review-level'])$(id).addEventListener(id==='query'?'input':'change',filter);
$('back').addEventListener('click',()=>{if(canLeave()){$('document').hidden=true;$('catalogue').hidden=false;current=null;dirty=false;}});
for(const [id,step] of [['previous',-1],['next',1]])$(id).addEventListener('click',()=>{const i=filtered.findIndex(x=>x.id===current.record.id);if(filtered[i+step])open(filtered[i+step].id);});
$('expand').addEventListener('click',()=>{radius=Math.min(2000,radius*2);open(current.record.id,true);});
$('decision').addEventListener('input',()=>{dirty=true;});
$('decision').addEventListener('submit',async e=>{e.preventDefault();$('message').textContent='Enregistrement en cours…';const submit=$('decision').querySelector('button[type=submit]');submit.disabled=true;const payload={document_id:current.record.id,source_version:current.source_version,previous_event_id:current.state.event?.id||null,...draft,endpoint_decisions:{start:$('start-decision').value,end:$('end-decision').value},note:$('note').value,reviewer:$('reviewer').value,human_confirmation:$('confirm').checked,active_seconds:activeSeconds};const id=current.record.id;const index=filtered.findIndex(r=>r.id===id);const followingIds=index<0?[]:filtered.slice(index+1).map(r=>r.id);try{const saved=await api('/api/decision',{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':token},body:JSON.stringify(payload)});dirty=false;await refresh();const nextId=saved.status==='human_validated'?followingIds.find(candidate=>filtered.some(r=>r.id===candidate)):null;const opened=await open(nextId||id);const message=!opened?'Décision enregistrée, mais le dossier n’a pas pu être rechargé.':nextId?'Validation enregistrée. Dossier suivant ouvert.':saved.status==='human_validated'?'Validation enregistrée. Aucun dossier suivant dans cette sélection.':'Décision enregistrée. Le dossier reste ouvert pour examen.';$('save-notice').textContent=message;$('save-notice').hidden=false;$('message').textContent=message;}catch(error){showError(error);}finally{submit.disabled=false;}});
for(const name of ['pointerdown','keydown','scroll'])document.addEventListener(name,()=>lastActivity=performance.now(),{passive:true});
setInterval(()=>{const now=performance.now();if(current&&document.visibilityState==='visible'&&document.hasFocus()&&now-lastActivity<60000)activeSeconds+=Math.min(2,(now-lastTick)/1000);lastTick=now;},1000);
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
refresh().then(async()=>{const params=new URLSearchParams(window.location.search);const level=params.get('review_priority');if(level&&Object.hasOwn(reviewLevels,level)){$('review-level').value=level;filter();}const id=params.get('document');if(id&&records.some(r=>r.id===id))await open(id);}).catch(e=>{window.alert('Impossible de charger le registre : '+e.message);});

async function showDocumentArticles(id){
 await switchReviewMode('articles',id);
 if(!articleParents.some(p=>p.id===id))articleMessage('Cette notice ne possède pas de texte extrait. Vérifiez ses frontières dans le mode Cahiers.');
}
async function rebuildDocument(id){
 try{
  const doc=await api('/api/document?'+new URLSearchParams({id,radius:2}));
  const result=await articlePost('/api/articles/rebuild',{document_id:id,parent_event_id:doc.state.event?.id||null});
  $('document-rebuild-message').textContent=result.message;
  articleParents=await api('/api/articles/list');
  await showDocumentArticles(id);
 }catch(e){$('document-rebuild-message').textContent='Erreur : '+e.message;articleMessage(e.message,true);}
}
$('document-articles').addEventListener('click',()=>{if(current&&canLeave()){dirty=false;showDocumentArticles(current.record.id);}});
$('document-rebuild').addEventListener('click',()=>{if(current&&canLeave()){dirty=false;rebuildDocument(current.record.id);}});
$('source-find').addEventListener('click',async()=>{
 if(!current)return;
 try{
  const result=await api('/api/volume/search?'+new URLSearchParams({volume:current.record.metadata.volume,query:$('source-query').value}));
  $('source-find-count').textContent=`${result.total} blocs correspondants ; affichage des 50 premiers au maximum. Une proposition de limite ne valide rien.`;
  const list=$('source-find-results');list.replaceChildren();
  for(const b of result.blocks){
   const item=el('section','');const text=el('p',`${b.id} · ${b.text}`);text.className='source';item.append(text);
   for(const side of ['start','end']){
    const button=el('button',side==='start'?'Proposer comme début':'Proposer comme fin');
    button.addEventListener('click',()=>{draft[side+'_id']=b.id;$(side+'-decision').value='corrected';$('confirm').checked=false;dirty=true;open(current.record.id,true);});item.append(button);
   }list.append(item);
  }
 }catch(e){$('source-find-count').textContent=e.message;}
});
