'use strict';
const byId=id=>document.getElementById(id);
const slice=(text,a,z)=>Array.from(text).slice(a,z).join('');
let catalogue;
const kinds={cahier_autonome_probable:'Cahier autonome probable',document_associe:'Document associé',proces_verbal:'Procès-verbal',liste:'Liste',extrait:'Extrait'};
const boundaries={codex_reviewed:'examinées dans le XML par Codex, sans validation humaine',human_validated:'validées humainement',automatic_no_alert:'proposées automatiquement, sans alerte détectée',automatic_suspect:'proposées automatiquement, avec alertes',uncertain:'incertaines'};
const methods={XML_paragraph_end:'fin de paragraphe XML',document_end:'fin du document',sentence_end:'fin de phrase',word_boundary_long_sentence:'frontière de mot dans une longue phrase',Unicode_boundary_exceptional_run:'coupure technique exceptionnelle'};
async function api(path){const r=await fetch(path);const d=await r.json();if(!r.ok)throw new Error(d.error||'Lecture impossible');return d;}
function link(id,passage){const e=byId(id);if(passage){e.href='/passages?passage='+encodeURIComponent(passage);e.hidden=false;}else{e.removeAttribute('href');e.hidden=true;}}
async function openPassage(passageId,documentId){
 try{
  const q=passageId?'passage='+encodeURIComponent(passageId):'document='+encodeURIComponent(documentId);
  const d=await api('/api/technical/document?'+q),p=d.passage,doc=d.document,m=d.metadata;
  byId('technical-document').value=doc.id;byId('technical-passage').replaceChildren();
  byId('technical-components').textContent=(doc.document_components||[]).map(c=>`${c.role==='main_cahier'?'Cahier principal':c.role==='attached_petition'?'Pétition explicitement jointe':'Pétition associée par le contexte documentaire'} : positions dans le document ${c.start-doc.source_start}–${c.end-doc.source_start}`).join(' ; ');
  if(!p){byId('technical-title').textContent=m.title;byId('technical-status').textContent='Plage source conservée, constituée uniquement de blancs. Aucun passage de recherche créé.';byId('technical-full-text').textContent=doc.full_text;byId('technical-excerpt').textContent='';byId('technical-position').textContent='';link('technical-previous',null);link('technical-next',null);link('technical-permalink',null);byId('technical-notice').href=m.original_metadata.document_url;byId('technical-scan').href=doc.source.scan_url;history.replaceState(null,'','/passages?document='+encodeURIComponent(doc.id));window.technicalDocument=d;return;}
  for(const u of d.passages){const o=new Option(`Passage ${u.ordinal} · ${u.token_count} tokens · ${u.start_in_document}–${u.end_in_document}`,u.id);byId('technical-passage').append(o);}
  byId('technical-passage').value=p.id;byId('technical-title').textContent=m.title;
  byId('technical-status').textContent=`Tome ${doc.volume} · ${kinds[doc.document_kind]||doc.document_kind} · Frontières : ${boundaries[doc.boundary_status.extracted_class]||doc.boundary_status.extracted_class} (état figé de la collection). Ordre : ${m.historical_orders.join(', ')||'non établi'}.`;
  byId('technical-notice').href=m.original_metadata.document_url;byId('technical-scan').href=doc.source.scan_url;
  byId('technical-position').textContent=`${p.token_count} tokens · positions dans le cahier [${p.start_in_document}, ${p.end_in_document}[ · coupure : ${methods[p.boundary_method]||p.boundary_method} · chevauchement précédent : ${p.overlap_previous?.tokens||0} tokens.`;
  byId('technical-excerpt').textContent=p.text;
  const mark=document.createElement('mark');mark.id='technical-highlight';mark.textContent=slice(doc.full_text,p.start_in_document,p.end_in_document);
  byId('technical-full-text').replaceChildren(document.createTextNode(slice(doc.full_text,0,p.start_in_document)),mark,document.createTextNode(slice(doc.full_text,p.end_in_document)));
  link('technical-previous',p.previous_id);link('technical-next',p.next_id);link('technical-permalink',p.id);
  history.replaceState(null,'','/passages?passage='+encodeURIComponent(p.id));
  const full=byId('technical-full-text');full.scrollTop+=mark.getBoundingClientRect().top-full.getBoundingClientRect().top-full.clientHeight/3;
  byId('technical-error').textContent='';
  window.technicalDocument=d;
 }catch(e){byId('technical-error').textContent=e.message;}
}
byId('technical-document').addEventListener('change',e=>openPassage(null,e.target.value));
byId('technical-passage').addEventListener('change',e=>openPassage(e.target.value));
(async()=>{try{
 catalogue=await api('/api/technical/catalogue');
 byId('technical-summary').textContent=`${catalogue.summary.probable_cahiers} cahiers probables · ${catalogue.summary.documents} textes conservés · ${catalogue.summary.passages} passages techniques. Aucun embedding calculé.`;
 for(const d of catalogue.documents){byId('technical-document').append(new Option(`Tome ${d.volume} · ${d.title} · ${d.passages} passage(s)`,d.id));}
 for(const w of catalogue.sample.windows){const d=catalogue.documents.find(d=>d.id===w.document_id),li=document.createElement('li'),a=document.createElement('a');a.textContent=`Tome ${w.volume} · ${d.title}`;a.href='/passages?passage='+encodeURIComponent(w.passage_id);li.append(a);byId('technical-sample').append(li);}
 const params=new URLSearchParams(location.search);await openPassage(params.get('passage'),params.get('document')||catalogue.documents[0].id);
}catch(e){byId('technical-error').textContent=e.message;}})();
