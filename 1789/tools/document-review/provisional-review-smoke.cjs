/* Synthetic decisions only: run against global_test_server.py, never the real journal. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage(),base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17899';
  await page.goto(base+'/?article_window=sample-5c48fb8a2303cfda');
  await page.waitForFunction(()=>articleWorkbench?.independent_sample.some(w=>w.id==='sample-5c48fb8a2303cfda'&&w.parent_id===articleDocument?.parent.id));
  const before=await page.evaluate(()=>({parent:articleDocument.parent.id,ready:articleDocument.version.parent.ready,unit:articleDocument.units.find(u=>u.id===articleWorkbench.independent_sample.find(w=>w.id==='sample-5c48fb8a2303cfda').unit_id)}));
  assert.equal(before.ready,false);
  await page.locator('#article-reviewer').fill('SYNTHETIC BROWSER TEST ONLY');
  await page.evaluate(id=>openArticleEditor('classify',[id]),before.unit.id);
  await page.locator('#article-type').selectOption('paratext');
  await page.locator('#article-ack').check();
  await page.locator('#article-preview').click();
  await page.waitForFunction(()=>articlePreviewDigest);
  await page.locator('#article-save-edit').click();
  await page.waitForFunction(()=>!articleSaving&&articleDocument.history.length>0&&document.querySelector('#article-editor').hidden);
  const saved=await page.evaluate(spans=>articleDocument.units.find(u=>JSON.stringify(u.spans)===JSON.stringify(spans)),before.unit.spans);
  assert.equal(saved.type,'paratext');assert.equal(saved.human_validated,true);assert.equal(saved.indexing_eligible,false);assert.equal(saved.publication_ready,false);
  assert.equal(await page.evaluate(()=>articleDocument.version.parent.ready),false);
  await page.reload();await page.waitForFunction(id=>articleDocument?.parent.id===id&&articleDocument.history.length>0,before.parent);
  const resumed=await page.evaluate(spans=>articleDocument.units.find(u=>JSON.stringify(u.spans)===JSON.stringify(spans)),before.unit.spans);
  assert.equal(resumed.id,saved.id);assert.equal(resumed.human_validated,true);
  assert.equal(await page.evaluate(()=>articleDocument.version.parent.ready),false);
  console.log(JSON.stringify({passed:true,exact_reported_window:true,classification_preview_and_save:true,reload_preserves_decision:true,parent_remains_proposed:true,no_publication_or_index_eligibility:true,temporary_journals_only:true},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
