'use strict';
// One interface and one source: the Articles view uses the existing API/DOM helpers.
let articleParents = [], articleDocument = null, articleSelected = new Set();
let articleEditorIds = [], articleRange = {}, articlePreviewDigest = null, articleDirty = false, articleSaving = false;
let articleReturnPosition = null, articleCampaign = null;
const articleTypes = {article:'Article historique',section:'Section historique',technical_passage:'Passage C non classé',claim_passage:'Passage revendicatif technique',paratext:'Paratexte'};
const articleStates = {codex_examined:'Limites examinées par Codex',automatic_proposal:'Proposition automatique',technical_unclassified:'À classer',human_validated:'Validé humainement',human_corrected:'Corrigé humainement',uncertain:'Incertain',review_required:'Validation périmée — à réexaminer'};
const articleButton = (text, callback) => { const b=el('button',text); b.type='button'; b.addEventListener('click',callback); return b; };
const unicodeLength = text => Array.from(text).length;
const unicodeSlice = (text,start,end) => Array.from(text).slice(start,end).join('');
function articleMessage(message,error=false){ $('article-status').textContent=(error?'Erreur : ':'')+message; }
function articleCanLeave(){ return !articleDirty || window.confirm('Cette correction n’est pas enregistrée. L’abandonner ?'); }
function captureArticlePosition(){
 const trigger=document.activeElement,card=trigger?.closest('.review-unit');
 const unit=card?articleDocument?.units.find(u=>u.id===card.dataset.unitId):null;
 const usable=trigger&&trigger!==document.body&&trigger!==document.documentElement;
 return {parentId:articleDocument?.parent.id,scrollY:window.scrollY,trigger:usable?trigger:null,
  triggerId:usable?trigger.id:null,triggerText:usable?trigger.textContent:null,
  offset:usable?trigger.getBoundingClientRect().top:null,unitId:unit?.id,unitStart:unit?.start,unitType:unit?.type};
}
function restoreArticlePosition(position){
 if(!position||articleDocument?.parent.id!==position.parentId)return;
 requestAnimationFrame(()=>{
  let target=position.trigger?.isConnected?position.trigger:null;
  if(!target&&position.unitId){
   const units=articleDocument.units;
   const unit=units.find(u=>u.id===position.unitId)
    ||units.find(u=>u.type===position.unitType&&(u.origin_ids.includes(position.unitId)||(u.start<=position.unitStart&&position.unitStart<u.end)))
    ||units.find(u=>u.start<=position.unitStart&&position.unitStart<u.end);
   const card=unit?[...document.querySelectorAll('.review-unit')].find(c=>c.dataset.unitId===unit.id):null;
   target=card?[...card.querySelectorAll('button')].find(b=>b.textContent===position.triggerText):null;
  }
  if(!target&&position.triggerId)target=$(position.triggerId);
  if(target?.getClientRects().length){
   target.focus({preventScroll:true});
   window.scrollTo({top:window.scrollY+target.getBoundingClientRect().top-position.offset,behavior:'instant'});
  }else window.scrollTo({top:position.scrollY,behavior:'instant'});
 });
}
async function articlePost(path,payload){
 const request=()=>api(path,{method:'POST',headers:{'Content-Type':'application/json','X-Review-Token':token},body:JSON.stringify(payload)});
 try{return await request();}catch(e){
  if(e.message!=='Review token required')throw e;
  token=(await api('/api/meta')).token;
  return await request();
 }
}
async function switchReviewMode(mode){
 if(mode==='articles'){
  if(!canLeave())return;
  dirty=false;current=null;$('document').hidden=true;$('catalogue').hidden=false;
 }else if(!articleCanLeave())return;
 document.body.classList.toggle('articles-active',mode==='articles');
 $('cahiers-panel').hidden=mode!=='cahiers';$('articles-panel').hidden=mode!=='articles';
 $('mode-cahiers').setAttribute('aria-pressed',String(mode==='cahiers'));
 $('mode-articles').setAttribute('aria-pressed',String(mode==='articles'));
 if(mode==='cahiers'){ articleDirty=false;await refresh();return; }
 try{
  articleMessage('Chargement des cahiers et des unités…');
  articleParents=await api('/api/articles/list');
  articleCampaign=await api('/api/articles/campaign').catch(()=>null);
  renderArticleCampaign();
  const select=$('article-parent');select.replaceChildren();
  for(const p of articleParents){const option=el('option',`${p.title} · ${p.articles} articles · ${p.human_reviewed} unités examinées`);option.value=p.id;select.append(option);}
  if(articleDocument&&articleParents.some(p=>p.id===articleDocument.parent.id))select.value=articleDocument.parent.id;
  if(select.value)await loadArticleParent(select.value);
  $('articles-title').focus();
 }catch(e){articleMessage(e.message,true);}
}
async function loadArticleParent(id,afterMessage=''){
 try{
  articleDocument=await api('/api/articles/document?'+new URLSearchParams({id}));
  articleSelected=new Set();articleDirty=false;articlePreviewDigest=null;articleReturnPosition=null;
  $('article-editor').hidden=true;$('article-parent').value=id;$('article-note').value='';
  const row=articleParents.find(r=>r.id===id);
  if(row){row.articles=articleDocument.units.filter(u=>u.type==='article').length;row.human_reviewed=articleDocument.units.filter(u=>u.human_validated).length;const option=[...$('article-parent').options].find(o=>o.value===id);if(option)option.textContent=`${row.title} · ${row.articles} articles · ${row.human_reviewed} unités examinées`;}
  renderArticles();renderArticleCampaign();articleMessage(afterMessage);
 }catch(e){articleMessage(e.message,true);}
}
function articlePayload(action,ids){
 if(!articleDocument)throw new Error('Ouvrez un cahier.');
 return {document_id:articleDocument.parent.id,version:articleDocument.version,previous_event_id:articleDocument.previous_event_id,
  action,unit_ids:ids,reviewer:$('article-reviewer').value,note:'',confirmation:true};
}
async function saveArticleDecision(payload){
 if(articleSaving)return;articleSaving=true;
 const returnPosition=!$('article-editor').hidden&&document.activeElement?.closest('#article-editor')?articleReturnPosition:captureArticlePosition();
 try{
  await articlePost('/api/articles/decision',payload);
  await loadArticleParent(payload.document_id,'Décision enregistrée. Les textes sources et l’historique sont conservés.');
  restoreArticlePosition(returnPosition);
 }catch(e){articleMessage(e.message,true);}finally{articleSaving=false;}
}
function articleGroupCount(){
 if(articleSelected.size)$('article-group-tools').open=true;
 $('article-selected-count').textContent=`${articleSelected.size} unité(s) explicitement sélectionnée(s).`;
 $('article-group-confirm').checked=false;
 for(const box of document.querySelectorAll('input[data-article-select]'))box.checked=articleSelected.has(box.dataset.articleSelect);
}
function renderArticles(){
 const d=articleDocument,p=d.parent,units=d.units,articles=units.filter(u=>u.type==='article');
 const human=units.filter(u=>u.human_validated).length;
 $('article-meta').textContent=`Tome ${p.volume} · ${p.metadata.title} · ${articles.length} articles · ${human} unités validées/corrigées humainement. La validation du cahier reste distincte.`;
 $('article-warning').hidden=!d.warning&&!d.stale_events.length;
 $('article-warning').textContent=d.warning||`${d.stale_events.length} décision(s) concernent une autre version du parent. Les validations correspondantes doivent être reprises.`;
 $('article-range-end').max=String(articles.length);$('article-range-start').max=String(articles.length);
 $('article-range-end').value=String(Math.min(15,articles.length)||1);
 const stream=$('article-stream');stream.replaceChildren();let articleRank=0;
 for(const unit of units){
  const card=el('article','');card.className='review-unit';card.dataset.unitId=unit.id;card.dataset.unitType=unit.type;
  if(unit.type==='technical_passage'||unit.type==='paratext'){card.hidden=!$('article-show-c').checked;card.classList.add('review-technical');}
  if(unit.human_validated){
   card.classList.add('review-human');
   const badge=el('span','');badge.className='review-human-badge';
   const check=el('span','✓');check.setAttribute('aria-hidden','true');
   badge.append(check,document.createTextNode(unit.validation_status==='human_corrected'?'Corrigé humainement':'Validé humainement'));
   card.append(badge);
  }
  if(unit.type==='article')articleRank++;
  const heading=el('h3',unit.type==='article'?`Article ${unit.number||'sans numéro reconnu'} · rang ${articleRank}`:articleTypes[unit.type]);
  card.append(heading);
  const page=unit.pages.map(p=>p.n||p.id).join(', ');
  card.append(el('p',`Origine ${unit.source_status==='human_created'?'création/correction humaine':unit.source_status} · ${articleStates[unit.validation_status]||unit.validation_status} · page ${page||'non identifiée'} · ordre documentaire ${unit.order}`));
  if(unit.section)card.append(el('p',`Rubrique : ${unit.section.trim()}`));
  if(unit.anomalies.length)card.append(el('p',unit.anomalies.join(' ')));
  const text=el('p',unit.text);text.className='article-original';
  if(unit.type==='technical_passage'||unit.type==='paratext'){
   const detail=document.createElement('details');detail.append(el('summary',`${unit.text.trim()?'Lire le passage conservé':'Blancs entre unités'} (${unicodeLength(unit.text)} caractères)`),text);card.append(detail);
  }else card.append(text);
  if(unit.spans.length>1)card.append(el('small','Texte en plusieurs plages ; les notes et autres éléments séparés restent dans le cahier complet.'));
  const controls=el('div','');controls.className='unit-controls';
  const label=el('label',' Sélectionner');const box=document.createElement('input');box.type='checkbox';box.dataset.articleSelect=unit.id;
  box.setAttribute('aria-label',`Sélectionner ${heading.textContent}`);
  box.addEventListener('change',()=>{if(box.checked)articleSelected.add(unit.id);else articleSelected.delete(unit.id);articleGroupCount();});label.prepend(box);controls.append(label);
  if(unit.type!=='technical_passage')controls.append(articleButton('Valider',()=>{
   if(unit.anomalies.length&&!window.confirm('Examen individuel requis : '+unit.anomalies.join(' ')+' Confirmez-vous avoir vérifié ces points ?'))return;
   const payload=articlePayload('validate',[unit.id]);payload.acknowledge_anomalies=unit.anomalies.length>0;saveArticleDecision(payload);
  }));
  controls.append(articleButton('Contexte / corriger',()=>openArticleEditor('correct',[unit.id])),articleButton('Incertain',()=>saveArticleDecision(articlePayload('uncertain',[unit.id]))));
  controls.append(articleButton('Classer…',()=>openArticleEditor('classify',[unit.id])));
  const link=el('a','Page source');link.href=unit.source_page_url||p.source.scan_url;link.target='_blank';link.rel='noopener noreferrer';controls.append(link);card.append(controls);
  stream.append(card);
 }
 $('article-history').textContent=d.history.length?JSON.stringify(d.history,null,2):'Aucune décision sur les articles de ce cahier.';
 $('article-undo').disabled=!d.history.length;
 const index=articleParents.findIndex(row=>row.id===p.id);
 $('article-prev-parent').disabled=index<=0;$('article-next-parent').disabled=index<0||index===articleParents.length-1;
 articleGroupCount();
 renderSegmentationComparison();
}
function sourceSelection(){
 const container=$('article-source-text'),selection=window.getSelection();
 if(!selection.rangeCount)throw new Error('Sélectionnez le texte source dans le cahier complet.');
 const range=selection.getRangeAt(0);
 if(!container.contains(range.startContainer)||!container.contains(range.endContainer))throw new Error('La sélection doit être située dans le texte original du cahier.');
 const prefix=document.createRange();prefix.selectNodeContents(container);prefix.setEnd(range.startContainer,range.startOffset);
 const start=articleDocument.parent.start+unicodeLength(prefix.toString()),end=start+unicodeLength(range.toString());
 if(unicodeSlice(articleDocument.parent.full_text,start-articleDocument.parent.start,end-articleDocument.parent.start)!==range.toString())throw new Error('La sélection coupe un caractère Unicode. Sélectionnez un caractère complet.');
 return {start,end};
}
function renderArticleSource(){
 const p=articleDocument.parent,pre=$('article-source-text');pre.replaceChildren();pre.scrollTop=0;
 const a=articleRange.start,b=articleRange.end;
 if(Number.isInteger(a)&&Number.isInteger(b)&&p.start<=a&&a<=b&&b<=p.end){
  pre.append(document.createTextNode(unicodeSlice(p.full_text,0,a-p.start)));
  const mark=el('mark',unicodeSlice(p.full_text,a-p.start,b-p.start));mark.id='article-source-highlight';pre.append(mark,document.createTextNode(unicodeSlice(p.full_text,b-p.start)));
 }else pre.append(document.createTextNode(p.full_text));
 requestAnimationFrame(()=>{const mark=$('article-source-highlight');if(mark)pre.scrollTop=Math.max(0,mark.getBoundingClientRect().top-pre.getBoundingClientRect().top-pre.clientHeight/3);});
}
function invalidateArticlePreview(){
 articlePreviewDigest=null;articleDirty=true;$('article-save-edit').disabled=true;$('article-preview-result').replaceChildren();
 $('article-offsets').textContent=`Début ${articleRange.start??'à sélectionner'} · fin exclue ${articleRange.end??'à sélectionner'} · séparation ${articleRange.point??'à sélectionner'} (positions Unicode calculées dans la source).`;
}
function openArticleEditor(action,ids){
 if(!articleCanLeave())return;
 articleReturnPosition=captureArticlePosition();
 articleEditorIds=[...ids];const units=articleDocument.units.filter(u=>ids.includes(u.id));
 articleRange=units.length?{start:Math.min(...units.map(u=>u.start)),end:Math.max(...units.map(u=>u.end))}:{};
 $('article-action').value=action;
 $('article-type').value=action==='classify'?'paratext':units.length?units[0].type:'article';
 $('article-number').value=units[0]?.number||'';$('article-second-number').value='';$('article-note').value='';$('article-ack').checked=false;
 $('article-editor').hidden=false;$('article-editor-title').textContent=action==='missing'?'Article manquant — choisir sa plage dans le cahier':'Correction et contexte — '+units.map(u=>u.number||articleTypes[u.type]).join(', ');
 invalidateArticlePreview();articleDirty=false;renderArticleSource();
 $('article-source-details').open=true;$('article-editor-title').focus();
}
function editorPayload(){
 const payload=articlePayload($('article-action').value,articleEditorIds);
 return {...payload,...articleRange,note:$('article-note').value,type:$('article-type').value,number:$('article-number').value.trim()||null,second_number:$('article-second-number').value.trim()||null,acknowledge_anomalies:$('article-ack').checked};
}
$('mode-cahiers').addEventListener('click',()=>switchReviewMode('cahiers'));
$('mode-articles').addEventListener('click',()=>switchReviewMode('articles'));
$('article-parent').addEventListener('change',()=>{if(articleCanLeave())loadArticleParent($('article-parent').value);else $('article-parent').value=articleDocument.parent.id;});
for(const [id,step] of [['article-prev-parent',-1],['article-next-parent',1]])$(id).addEventListener('click',()=>{
 if(!articleCanLeave())return;const i=articleParents.findIndex(p=>p.id===articleDocument.parent.id);if(articleParents[i+step])loadArticleParent(articleParents[i+step].id);
});
$('article-show-c').addEventListener('change',()=>{for(const card of document.querySelectorAll('.review-technical'))card.hidden=!$('article-show-c').checked;});
$('article-clear-selection').addEventListener('click',()=>{articleSelected.clear();articleGroupCount();});
$('article-select-range').addEventListener('click',()=>{
 const articles=articleDocument.units.filter(u=>u.type==='article'),start=Number($('article-range-start').value),end=Number($('article-range-end').value);
 if(!Number.isInteger(start)||!Number.isInteger(end)||start<1||end<start||end>articles.length||end-start>=100){articleMessage('Choisissez une plage de 1 à 100 articles existants.',true);return;}
 const selected=articles.slice(start-1,end);
 if(selected.some(u=>u.anomalies.length||u.validation_status==='uncertain')){articleMessage('La plage contient une anomalie ou une incertitude : examinez ces articles individuellement.',true);return;}
 for(const u of selected)articleSelected.add(u.id);articleGroupCount();articleMessage('Les articles de cette plage sont cochés ; leur texte reste visible ci-dessous.');
});
$('article-validate-group').addEventListener('click',()=>{
 if(!$('article-group-confirm').checked){articleMessage('Confirmez avoir examiné les unités cochées.',true);return;}
 saveArticleDecision(articlePayload('validate',[...articleSelected]));
});
$('article-merge').addEventListener('click',()=>{if(articleSelected.size<2){articleMessage('Sélectionnez au moins deux fragments.',true);return;}openArticleEditor('merge',[...articleSelected]);});
$('article-missing').addEventListener('click',()=>openArticleEditor('missing',[]));
$('article-full-parent').addEventListener('click',()=>openArticleEditor('missing',[]));
$('article-undo').addEventListener('click',()=>{if(articleCanLeave()&&window.confirm('Annuler la dernière décision sur ce cahier ? Une nouvelle entrée conservera la trace de cette annulation.'))saveArticleDecision(articlePayload('undo',[]));});
for(const [id,field] of [['article-take-start','start'],['article-take-end','end'],['article-take-point','point'],['article-take-range','range']])$(id).addEventListener('click',()=>{
 try{const selected=sourceSelection();if(field==='range')Object.assign(articleRange,selected);else articleRange[field]=field==='end'?selected.end:selected.start;invalidateArticlePreview();}catch(e){articleMessage(e.message,true);}
});
for(const id of ['article-action','article-type','article-number','article-second-number','article-note','article-ack'])$(id).addEventListener('input',invalidateArticlePreview);
$('article-preview').addEventListener('click',async()=>{
 try{const data=await articlePost('/api/articles/preview',editorPayload());articlePreviewDigest=data.digest;
  const target=$('article-preview-result');target.replaceChildren(el('p',`${data.removed_ids.length} unité(s) remplacée(s), ${data.after.length} unité(s) conservée(s)/créée(s). ${data.message}`));
  for(const row of data.after){const details=document.createElement('details');details.open=row.type!=='technical_passage';details.append(el('summary',`${articleTypes[row.type]} ${row.number||''} · ${row.text.length} caractères`));const text=el('p',row.text);text.className='article-original';details.append(text);target.append(details);}
  $('article-save-edit').disabled=false;articleMessage('Prévisualisation prête. Vérifiez le texte avant de confirmer.');
 }catch(e){articlePreviewDigest=null;$('article-save-edit').disabled=true;articleMessage(e.message,true);}
});
$('article-save-edit').addEventListener('click',()=>{if(!articlePreviewDigest)return;saveArticleDecision({...editorPayload(),preview_digest:articlePreviewDigest});});
$('article-close-editor').addEventListener('click',()=>{if(articleCanLeave()){const position=articleReturnPosition;articleDirty=false;$('article-editor').hidden=true;articleReturnPosition=null;restoreArticlePosition(position);}});
$('article-export').addEventListener('click',async()=>{
 try{const result=await articlePost('/api/articles/export',{});articleMessage(`Export local produit : ${result.units} unités, ${result.indexing_eligible} éligibles à une indexation expérimentale ; ${result.human_validated_units} examinées humainement. Aucun embedding calculé.`);}catch(e){articleMessage(e.message,true);}
});
window.addEventListener('beforeunload',event=>{if(articleDirty){event.preventDefault();event.returnValue='';}});

// Read-only overlay: decisions and current unit IDs always remain authoritative.
function renderSegmentationComparison(){
 let panel=$('segmentation-comparison');
 if(!panel){panel=document.createElement('details');panel.id='segmentation-comparison';$('article-stream').before(panel);}
 panel.replaceChildren();const c=articleDocument.segmentation_comparison;
 panel.hidden=!c;if(!c)return;
 panel.append(el('summary','Comparer les nouvelles propositions de segmentation'));
 panel.append(el('p',c.warning));if(!c.available)return;
 panel.append(el('p',`${c.old_count} articles selon les anciennes règles ; ${c.new_count} propositions selon les nouvelles. Ces nombres ne remplacent pas le corpus actuel.`));
 if(c.reference_misses?.length)panel.append(el('p',`${c.reference_misses.length} unité(s) héritée(s) non reproduite(s) par les règles : elles sont conservées dans le corpus actuel et doivent rester disponibles.`));
 const labels={Codex_note_after_frozen_evaluation_not_an_extractor_prediction:'Signalement documentaire de Codex après évaluation, pas une détection automatique',XML_paragraph_start:'Début de paragraphe XML',sentence_boundary_inside_XML_p:'Limite de phrase dans un paragraphe',previous_number_agrees:'Numéro précédent concordant',next_number_agrees:'Numéro suivant concordant',structural_section_before:'Rubrique avant',structural_section_after:'Rubrique ou clôture après',text_follows_marker_without_space:'Texte collé au numéro',OCR_number_hint_only_not_historical_number:'Chiffres OCR incertains : aucun numéro historique inventé',bare_number_confirmed_by_two_neighbours:'Numéro sans Art. confirmé par ses voisins',explicit_Art_prefix:'Marqueur Art. explicite',punctuated_number_with_two_neighbours:'Numéro ponctué confirmé par ses voisins'};
 for(const m of c.markers){
  const item=el('section','');item.className='segmentation-proposal';
  item.append(el('h3',`${m.status==='review_note'?'Signalement documentaire à examiner':m.status==='suspect'?'Fusion potentielle à examiner':'Séparation proposée'} : ${m.label}`),el('p',`Position source ${m.start} · ${m.evidence.map(e=>labels[e]||e).join(' ; ')}`),el('p',m.text));
  const current=articleDocument.units.find(u=>u.start<=m.start&&m.start<u.end);
  const already=articleDocument.units.find(u=>u.type==='article'&&Math.abs(u.start-m.start)<=3);
  if(already){item.append(el('p',already.human_validated?'Déjà couvert par une décision humaine. Cette décision est conservée.':'Ce début est déjà présent dans le découpage actuel.'));}
  else if(current?.human_validated){item.append(el('p','Cette plage possède une décision humaine prioritaire. Proposition non appliquée ; réexamen manuel possible depuis l’article actuel.'));}
  else if(current?.type==='article'&&current.start<m.start&&m.start<current.end){
   item.append(articleButton('Préparer une séparation à vérifier',()=>{
    if(!articleCanLeave())return;articleDirty=false;openArticleEditor('split',[current.id]);articleRange.point=m.start;$('article-second-number').value=m.number||'';invalidateArticlePreview();
    $('article-note').value='Examen de la proposition '+c.method+' : '+m.label;
   }));
  }else if(current&&m.end&&m.status==='proposed'){
   item.append(articleButton('Examiner cet article manquant',()=>{
    if(!articleCanLeave())return;articleDirty=false;openArticleEditor('missing',[]);articleRange={start:m.start,end:m.end};$('article-number').value=m.number||'';invalidateArticlePreview();renderArticleSource();
   }));
  }
  panel.append(item);
 }
 const ranges=document.createElement('details');ranges.append(el('summary',`${c.changed_ranges.length} plages différentes : ancien et nouveau découpage`));
 for(const u of c.changed_ranges)ranges.append(el('p',`${u.label||'Unité'} : ancienne(s) plage(s) ${u.old_ranges.map(r=>`[${r.start}, ${r.end}[`).join(', ')||'aucune'} → proposition [${u.start}, ${u.end}[. ${u.text}`));
 panel.append(ranges);
}

function renderArticleCampaign(){
 const panel=$('article-campaign'),list=$('article-campaign-list');
 panel.hidden=!articleCampaign;list.replaceChildren();if(!articleCampaign)return;
 $('article-campaign-info').textContent=`Tirage figé : graine ${articleCampaign.seed}, cinq cahiers parmi ${articleCampaign.eligible_document_ids.length}, sans sélection par difficulté. Notez le temps de vérification pour ce lot.`;
 for(const chosen of articleCampaign.selected){
  const current=articleParents.find(p=>p.id===chosen.id),item=el('li','');
  const button=articleButton(chosen.title,()=>{if(articleCanLeave())loadArticleParent(chosen.id);});
  button.disabled=!current;item.append(button);
  let status='Articles non examinés humainement';
  if(current?.human_reviewed)status=`Décisions humaines enregistrées : ${current.human_reviewed} unités validées ou corrigées`;
  else if(current?.uncertain)status='Relecture commencée, avec des unités laissées incertaines';
  item.append(el('p',`${chosen.proposed_articles} articles proposés au tirage · ${status}.`));
  if(current&&!current.parent_ready)item.append(el('p','Attention : les frontières du cahier doivent être réexaminées.'));
  list.append(item);
 }
}
