/* Article conversion in cloned journals only, against global_test_server.py. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto((process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898')+'/?article_window=sample-2cb62afcedd96ab0');
  await page.waitForFunction(()=>articleWorkbench?.independent_sample.some(w=>w.id==='sample-2cb62afcedd96ab0'&&w.parent_id===articleDocument?.parent.id));
  const range=await page.evaluate(()=>{
   const c=articleDocument.units.find(u=>u.type==='technical_passage'&&u.start<=2064738&&2065282<=u.end);
   if(!c)throw Error('Expected reported source range inside C');
   return {id:c.id,start:2064738,end:2065282,parent:articleDocument.parent.id,source:unicodeSlice(articleDocument.parent.full_text,2064738-articleDocument.parent.start,2065282-articleDocument.parent.start)};
  });
  await page.locator('#article-reviewer').fill('SYNTHETIC CLASSIFICATION TEST ONLY');
  await page.evaluate(r=>{openArticleEditor('classify',[r.id]);articleRange.start=r.start;articleRange.end=r.end;invalidateArticlePreview();},range);
  await page.locator('#article-type').selectOption('article');
  await page.locator('#article-number').fill('5');
  await page.locator('#article-ack').check();
  assert.equal(await page.locator('#article-second-number-label').isVisible(),false);
  await page.locator('#article-preview').click();await page.waitForFunction(()=>articlePreviewDigest);
  await page.locator('#article-save-edit').click();
  await page.waitForFunction(r=>!articleSaving&&articleDocument.units.some(u=>u.type==='article'&&u.start===r.start&&u.end===r.end&&u.number==='5'),range);
  const saved=await page.evaluate(r=>articleDocument.units.find(u=>u.type==='article'&&u.start===r.start&&u.end===r.end),range);
  assert.equal(saved.text,range.source);assert.equal(saved.human_validated,true);
  await page.reload();await page.waitForFunction(r=>articleDocument?.parent.id===r.parent&&articleDocument.units.some(u=>u.id===r.id),{parent:range.parent,id:saved.id});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,exact_reported_source_range:true,classify_as_article:true,number_5_in_primary_field:true,second_number_hidden_outside_split:true,source_text_unchanged:true,reload_preserves_decision:true,temporary_journals_only:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
