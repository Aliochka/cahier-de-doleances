/* Uses article_test_server.py: synthetic decisions, no writes to real journals. */
const {createRequire}=require('node:module');
const path=require('node:path');
const requireFrontend=createRequire(path.resolve(__dirname,'../../../frontend/package.json'));
const {chromium}=requireFrontend('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
 const page=await browser.newPage();
 let acceptDiscard=true;page.on('dialog',d=>acceptDiscard?d.accept():d.dismiss());
 const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17897';
 const results=[];
 for(const width of [1280,375]){
  await page.setViewportSize({width,height:900});await page.goto(base);
  await page.locator('#mode-articles').click();await page.waitForFunction(()=>articleDocument&&document.querySelector('#article-parent').options.length===29);
  const parents=await (await page.request.get(base+'/api/articles/list')).json();
  const key=parents.find(p=>p.persee_id.endsWith('_5_1_2339')).id;
  await page.locator('#article-parent').selectOption(key);await page.waitForFunction(key=>articleDocument.parent.id===key,key);
  const unit=await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article')[4]);
  const button=page.locator(`.review-unit[data-unit-id="${unit.id}"]`).getByRole('button',{name:'Contexte / corriger'});
  const prepare=async()=>{
   await button.scrollIntoViewIfNeeded();await button.evaluate(e=>window.scrollTo(0,scrollY+e.getBoundingClientRect().top-180));
   return page.evaluate(()=>scrollY);
  };
  let before=await prepare();await button.click();
  await page.waitForSelector('#article-editor:not([hidden])');
  assert.ok(Math.abs(await page.evaluate(()=>scrollY)-before)>200);
  await page.locator('#article-close-editor').click();
  await page.waitForFunction(y=>Math.abs(scrollY-y)<3,before);
  assert.ok(await button.evaluate(e=>document.activeElement===e));
  // Dismissing the unsaved-change prompt keeps the editor open. Accepting returns to the article.
  before=await prepare();await button.click();await page.locator('#article-note').fill('SYNTHETIC UNSAVED SCROLL TEST');
  acceptDiscard=false;await page.locator('#article-close-editor').click();assert.equal(await page.locator('#article-editor').isVisible(),true);
  acceptDiscard=true;await page.locator('#article-close-editor').click();await page.waitForFunction(y=>Math.abs(scrollY-y)<3,before);
  // Saving closes/rebuilds the editor and must restore the same reading point as well.
  await page.locator('#article-reviewer').fill('SYNTHETIC SCROLL TEST ONLY');
  before=await prepare();await button.click();await page.locator('#article-action').selectOption('number');
  await page.locator('#article-number').fill(unit.number||'5');await page.locator('#article-preview').click();
  await page.waitForFunction(()=>!document.querySelector('#article-save-edit').disabled);
  await page.locator('#article-save-edit').click();
  await page.waitForFunction(()=>document.querySelector('#article-editor').hidden&&document.querySelector('#article-status').textContent.includes('Décision enregistrée'));
  await page.waitForFunction(id=>{const card=[...document.querySelectorAll('.review-unit')].find(c=>c.dataset.unitId===id);const trigger=card&&[...card.querySelectorAll('button')].find(b=>b.textContent==='Contexte / corriger');return trigger&&Math.abs(trigger.getBoundingClientRect().top-180)<3;},unit.id);
  const replacement=page.locator(`.review-unit[data-unit-id="${unit.id}"]`).getByRole('button',{name:'Contexte / corriger'});
  assert.ok(await replacement.evaluate(e=>document.activeElement===e));
  results.push({width,close_restores_reading_point:true,cancel_preserves_editor:true,save_restores_reading_point:true,keyboard_focus_restored:true});
 }
 console.log(JSON.stringify({passed:true,synthetic_journals_only:true,results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1)});
