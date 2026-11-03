/* Navigation only, private cloned journals. Never evaluates or validates the random sample. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts++;});
  const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898';
  await page.goto(base+'/?article_sample=1');
  await page.waitForFunction(()=>articleWorkbench?.independent_sample.length===24&&articleDocument&&document.querySelector('#article-quality-filter').value==='sample');
  const sample=await page.evaluate(()=>articleWorkbench.independent_sample);
  assert.equal(await page.locator('#article-sample-list>li').count(),24);
  assert.equal(new Set(sample.map(w=>w.unit_id)).size,24);
  for(let v=1;v<=6;v++)for(const g of ['regular_article','C_window'])assert.equal(sample.filter(w=>w.volume===v&&w.group===g).length,2);
  const first=sample.find(w=>w.group==='C_window');
  await page.evaluate(id=>openArticleWindow(id),first.id);
  await page.waitForFunction(id=>articleDocument?.parent.id===id,first.parent_id);
  const card=page.locator('[data-unit-id="'+first.unit_id+'"]');
  await card.waitFor({state:'visible'});assert.equal(await card.locator('details').first().getAttribute('open'),'');
  assert.equal(await card.evaluate(e=>e===document.activeElement),true);
  assert.equal(await card.locator('.review-human-badge').count(),0);
  const change=await page.evaluate(()=>articleWorkbench.examples.find(w=>w.group==='automatic_correction'));
  await page.evaluate(id=>openArticleWindow(id),change.id);
  await page.waitForFunction(id=>articleDocument?.parent.id===id,change.parent_id);
  await page.locator('#article-final-changes').waitFor({state:'visible'});
  await page.locator('#article-final-changes>summary').click();
  assert.ok(await page.locator('.review-auto-correction').count()>0);
  await page.locator('#article-quality-filter').selectOption('possible_missed_article');
  assert.ok(await page.evaluate(()=>articleVisibleParents.length>0&&articleVisibleParents.every(p=>p.article_quality.possible_missed_article>0)));
  await page.locator('#article-quality-filter').selectOption('');
  await page.locator('#article-query').fill('Pecqueuse');
  await page.waitForFunction(()=>articleDocument?.parent.metadata.title.includes('Pecqueuse'));
  await page.locator('#article-review-boundaries').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>!document.querySelector('#cahiers-panel').hidden);
  await page.locator('#mode-articles').click();await page.waitForFunction(()=>!document.querySelector('#articles-panel').hidden&&articleDocument);
  for(const width of [320,375,768,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.goto(base+'/?article_window='+encodeURIComponent(first.id));
  await page.waitForFunction(id=>articleDocument?.parent.id===id,first.parent_id);
  await page.locator('[data-unit-id="'+first.unit_id+'"]').waitFor({state:'visible'});
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,sample_windows:24,two_articles_and_two_C_per_volume:true,source_window_navigation:true,comparison_before_after:true,quality_filters:true,keyboard:true,reload_deep_link:true,viewports:[320,375,768,1280],text_zoom_200_percent:true,no_POST:true,no_human_validation_created:true,no_documentary_judgement_of_sample:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
