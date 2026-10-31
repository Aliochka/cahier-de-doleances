/* Real browser, synthetic journals only. Start the fixture server described in README. */
const {createRequire}=require('node:module');
const path=require('node:path');
const requireFrontend=createRequire(path.resolve(__dirname,'../../../frontend/package.json'));
const {chromium}=requireFrontend('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17895';
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage({viewport:{width:1280,height:950}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
 await page.goto(base);await page.locator('#mode-articles').click();
 await page.waitForFunction(()=>document.querySelector('#article-parent').options.length===29&&articleDocument);
 const parents=await (await page.request.get(base+'/api/articles/list')).json();
 const pierrelez=parents.find(p=>p.persee_id.endsWith('_5_1_2339'));
 const ferrieres=parents.find(p=>p.persee_id.endsWith('_4_1_2175'));
 const choose=async id=>{await page.locator('#article-parent').selectOption(id);await page.waitForFunction(id=>articleDocument?.parent.id===id,id);};
 await choose(pierrelez.id);
 const articleUnits=()=>page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article'));
 let original=await articleUnits();assert.equal(original.length,9);
 await page.locator('#article-reviewer').fill('SYNTHETIC BROWSER ARTICLE REVIEW');
 if(!await page.locator('#article-group-tools').evaluate(e=>e.open))await page.locator('#article-group-tools > summary').click();
 await page.locator('#article-range-start').fill('1');await page.locator('#article-range-end').fill('9');await page.locator('#article-select-range').click();
 assert.equal(await page.locator('input[data-article-select]:checked').count(),9);
 await page.locator('#article-validate-group').click();
 await page.waitForFunction(()=>document.querySelector('#article-status').textContent.includes('Confirmez'));
 assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.human_validated).length),0);
 await page.locator('#article-group-confirm').check();await page.locator('#article-validate-group').click();
 await page.waitForFunction(()=>articleDocument.units.filter(u=>u.human_validated).length===9);
 assert.equal(await page.locator('.review-human').count(),9);
 assert.equal(await page.locator('.review-human-badge').filter({hasText:'Validé humainement'}).count(),9);
 await page.setViewportSize({width:375,height:900});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'human badges overflow at 200%');
 await page.evaluate(()=>document.documentElement.style.fontSize='');await page.setViewportSize({width:1280,height:950});
 await page.locator('#article-undo').click();await page.waitForFunction(()=>articleDocument.units.every(u=>!u.human_validated));
 assert.equal(await page.locator('.review-human').count(),0);
 const firstId=original[0].id;
 const card=id=>page.locator('.review-unit').filter({has:page.locator(`input[data-article-select="${id}"]`)});
 await card(firstId).getByRole('button',{name:'Valider',exact:true}).click();
 await page.waitForFunction(()=>articleDocument.units.filter(u=>u.human_validated).length===1);
 await page.reload();await page.locator('#mode-articles').click();
 await page.waitForFunction(()=>document.querySelector('#article-parent').options.length===29&&articleDocument);
 await choose(pierrelez.id);assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.human_validated).length),1);
 await page.locator('#article-reviewer').fill('SYNTHETIC BROWSER ARTICLE REVIEW');
 const selectSource=async(start,end)=>{
  await page.evaluate(({start,end})=>{
   const pre=document.querySelector('#article-source-text');
   const utf16Start=unicodeSlice(articleDocument.parent.full_text,0,start-articleDocument.parent.start).length;
   const utf16End=unicodeSlice(articleDocument.parent.full_text,0,end-articleDocument.parent.start).length;
   const locate=offset=>{const walker=document.createTreeWalker(pre,NodeFilter.SHOW_TEXT);let node;
    while((node=walker.nextNode())){if(offset<=node.textContent.length)return[node,offset];offset-=node.textContent.length;}
    throw new Error('Selection offset not found');};
   const [a,x]=locate(utf16Start),[b,y]=locate(utf16End),range=document.createRange();range.setStart(a,x);range.setEnd(b,y);
   const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
  },{start,end});
 };
 // Split inside the source paragraph; offsets are selected, never typed by the reviewer.
 await card(firstId).getByRole('button',{name:'Contexte / corriger'}).click();
 await page.locator('#article-action').selectOption('split');
 const point=original[0].start+40;
 await selectSource(point,point);await page.locator('#article-take-point').click();
 await page.locator('#article-number').fill('1a');await page.locator('#article-second-number').fill('1b');
 await page.locator('#article-preview').click();await page.locator('#article-save-edit').waitFor({state:'visible'});
 await page.waitForFunction(()=>!document.querySelector('#article-save-edit').disabled);
 await page.locator('#article-save-edit').click();await page.waitForFunction(()=>articleDocument.units.filter(u=>u.type==='article').length===10);
 let split=await page.evaluate(id=>articleDocument.units.filter(u=>u.type==='article'&&u.origin_ids.includes(id)),firstId);
 assert.equal(split.map(u=>u.text).join(''),original[0].text);
 // Merge the two explicitly selected fragments back; history remains reversible.
 for(const u of split)await page.locator(`input[data-article-select="${u.id}"]`).check();
 await page.locator('#article-merge').click();await page.locator('#article-number').fill('1er');
 await page.locator('#article-preview').click();await page.waitForFunction(()=>!document.querySelector('#article-save-edit').disabled);
 await page.locator('#article-save-edit').click();await page.waitForFunction(()=>articleDocument.units.filter(u=>u.type==='article').length===9);
 const merged=await page.evaluate(id=>articleDocument.units.find(u=>u.type==='article'&&u.origin_ids.includes(id)),firstId);
 assert.equal(merged.text,original[0].text);
 assert.ok(await card(merged.id).locator('.review-human-badge').filter({hasText:'Corrigé humainement'}).count());
 assert.notEqual(await card(merged.id).evaluate(e=>getComputedStyle(e).backgroundColor),await card(original[1].id).evaluate(e=>getComputedStyle(e).backgroundColor));
 // Classifying C as paratext must not create a historical article or an indexable claim.
 await page.locator('#article-show-c').check();
 const c=await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='technical_passage'&&u.text.trim()).sort((a,b)=>b.text.length-a.text.length)[0]);
 await card(c.id).getByRole('button',{name:'Classer…'}).click();await page.locator('#article-type').selectOption('paratext');
 await page.locator('#article-preview').click();await page.waitForFunction(()=>!document.querySelector('#article-save-edit').disabled);
 await page.locator('#article-save-edit').click();await page.waitForFunction(id=>articleDocument.units.some(u=>u.origin_ids.includes(id)&&u.type==='paratext'),c.id);
 const classified=await page.evaluate(id=>articleDocument.units.find(u=>u.origin_ids.includes(id)&&u.type==='paratext'),c.id);
 assert.equal(classified.indexing_eligible,false);assert.equal(classified.number,null);assert.equal(classified.source_status,'C');
 // Missing article in a C range remains an explicit human documentary decision.
 await page.locator('#article-undo').click();await page.waitForFunction(id=>articleDocument.units.some(u=>u.id===id),c.id);
 await page.locator('#article-missing').click();await selectSource(c.start,c.end);await page.locator('#article-take-range').click();
 await page.locator('#article-preview').click();await page.waitForFunction(()=>!document.querySelector('#article-save-edit').disabled);
 await page.locator('#article-save-edit').click();await page.waitForFunction(()=>articleDocument.units.filter(u=>u.type==='article').length===10);
 // Return to the nine historical candidates; mark one uncertain, never batch-validate it silently.
 await page.locator('#article-undo').click();await page.waitForFunction(()=>articleDocument.units.filter(u=>u.type==='article').length===9);
 original=await articleUnits();await card(original[1].id).getByRole('button',{name:'Incertain',exact:true}).click();
 await page.waitForFunction(()=>articleDocument.units.some(u=>u.validation_status==='uncertain'));
 const historyCount=await page.evaluate(()=>articleDocument.history.length);
 if(!await page.locator('#article-group-tools').evaluate(e=>e.open))await page.locator('#article-group-tools > summary').click();
 await page.locator('#article-range-start').fill('1');await page.locator('#article-range-end').fill('9');await page.locator('#article-select-range').click();
 await page.waitForFunction(()=>document.querySelector('#article-status').textContent.includes('anomalie ou une incertitude'));
 assert.equal(await page.evaluate(()=>articleDocument.history.length),historyCount);
 // Ferrières: rubrics and original text remain readable; page links available.
 await choose(ferrieres.id);assert.equal((await articleUnits()).length,25);
 assert.ok((await page.locator('#article-stream').textContent()).includes('COMMERCE'));
 assert.ok(await page.locator('#article-stream a').count()>0);
 // A B-heavy dossier and a long C dossier are actually rendered, not just counted offline.
 const manyB=[...parents].sort((a,b)=>b.proposed_articles-a.proposed_articles)[0];await choose(manyB.id);
 assert.ok((await page.locator('#article-stream').textContent()).includes('Origine B'));
 const longC=[...parents].sort((a,b)=>b.longest_technical_passage-a.longest_technical_passage)[0];await choose(longC.id);await page.locator('#article-show-c').check();
 assert.ok(await page.locator('.review-technical:visible').count()>0);
 const viewports=[];
 for(const width of [320,375,768,1280]){
  await page.setViewportSize({width,height:900});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width}`);
  viewports.push({width,no_horizontal_overflow:true});
 }
 await page.setViewportSize({width:375,height:900});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'200% overflow');
 await page.evaluate(()=>document.documentElement.style.fontSize='');
 await page.locator('#article-parent').focus();await page.keyboard.press('Tab');
 assert.equal(await page.evaluate(()=>document.activeElement.tagName),'BUTTON');
 assert.deepEqual(await page.evaluate(()=>[unicodeLength('a😀b'),unicodeSlice('a😀b',1,2)]),[3,'😀']);
 await page.locator('#article-export').click();
 await page.waitForFunction(()=>document.querySelector('#article-status').textContent.includes('Export local produit'));
 await page.locator('#mode-cahiers').click();await page.waitForSelector('#cahiers-panel:not([hidden])');
 assert.equal(await page.locator('#batch').isChecked(),true);
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({passed:true,Pierrelez_nine_articles:true,group_confirmation:true,group_undo:true,human_visual_markers:true,
  save_reload:true,split_inside_paragraph:true,merge_preserves_text:true,C_classification_not_article:true,
  missing_article_explicit:true,uncertain_not_batch_validated:true,Ferrieres_rubrics:true,
  B_dossier:manyB.title,long_C_dossier:longC.title,viewports,text_200_percent:true,keyboard:true,
  Unicode_codepoints:true,cahiers_mode_preserved:true,structured_export:true,synthetic_journals_only:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exit(1);});
