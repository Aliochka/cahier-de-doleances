/* Validate/undo only inside the private cloned journals of global_test_server.py. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  await page.goto(process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898');
  await page.locator('#mode-articles').click();await page.waitForFunction(()=>articleWorkbench?.fusion_validation.every(w=>w.review));
  const window=await page.evaluate(()=>articleWorkbench.fusion_validation.find(w=>w.group==='fusion_validation'&&w.review.status==='pending'));
  assert.ok(window,'Need an unreviewed sample article in the cloned fixture');
  const row=page.locator('[data-window-id="'+window.id+'"]');
  assert.equal(await row.getAttribute('data-review-status'),'pending');
  await page.evaluate(id=>openArticleWindow(id),window.id);
  await page.waitForFunction(id=>articleDocument?.parent.id===id,window.parent_id);
  assert.equal(await row.getAttribute('data-review-status'),'pending');
  await page.locator('#article-reviewer').fill('SYNTHETIC FUSION PROGRESS TEST ONLY');
  await page.locator('[data-unit-id="'+window.unit_id+'"]').getByRole('button',{name:'Valider',exact:true}).click();
  await page.waitForFunction(id=>articleWorkbench.fusion_validation.find(w=>w.id===id)?.review.status==='completed'&&!articleSaving,window.id);
  assert.ok((await row.textContent()).includes('✓ Terminé'));
  await page.reload();await page.waitForFunction(id=>articleWorkbench?.fusion_validation.find(w=>w.id===id)?.review.status==='completed'&&articleDocument?.parent.id===articleWorkbench.fusion_validation.find(w=>w.id===id).parent_id,window.id);
  await page.locator('#article-reviewer').fill('SYNTHETIC FUSION PROGRESS TEST ONLY');
  await page.locator('#article-undo').evaluate(e=>{const details=e.closest('details');if(details)details.open=true;});
  await page.locator('#article-undo').click();
  await page.waitForFunction(id=>articleWorkbench.fusion_validation.find(w=>w.id===id)?.review.status==='pending'&&!articleSaving,window.id);
  const corrected=await page.evaluate(()=>articleWorkbench.fusion_validation.find(w=>w.review.status==='completed'&&w.review.unit_ids&&!w.review.unit_ids.includes(w.unit_id)));
  if(corrected){await page.evaluate(id=>openArticleWindow(id),corrected.id);await page.waitForFunction(id=>articleDocument?.parent.id===id,corrected.parent_id);assert.ok(await page.evaluate(ids=>ids.some(id=>[...document.querySelectorAll('[data-unit-id]')].some(e=>e.dataset.unitId===id&&!e.hidden)),corrected.review.unit_ids));}
  for(const width of [375,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,opening_does_not_complete:true,validation_refreshes_badge:true,reload_preserves_status:true,undo_returns_to_pending:true,corrected_unit_navigation:Boolean(corrected),js_errors:errors,temporary_journals_only:true},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
