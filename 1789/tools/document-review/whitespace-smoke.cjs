/* Read-only browser checks; global_test_server.py uses temporary journal copies. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts++;});
  await page.goto(process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898');
  await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleDocument?.units.some(u=>u.automatic_classification));
  const stats=await page.evaluate(()=>({total:articleDocument.units.length,white:articleDocument.units.filter(u=>u.automatic_classification).length,human:articleDocument.units.filter(u=>u.human_validated).length}));
  assert.equal(await page.locator('#article-show-whitespace').isChecked(),false);
  assert.equal(await page.locator('[data-automatic-whitespace="true"]:visible').count(),0);
  await page.locator('#article-show-c').check();
  assert.equal(await page.locator('[data-automatic-whitespace="true"]:visible').count(),0);
  assert.ok(await page.locator('.review-technical:not([data-automatic-whitespace]):visible').count()>0);
  const ordinary=await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='technical_passage'||u.type==='paratext').filter(u=>!u.automatic_classification).map(u=>u.id));
  for(const id of ordinary.slice(0,5))await page.locator('[data-unit-id="'+id+'"]').waitFor({state:'visible'});
  await page.locator('#article-show-whitespace').check();
  assert.equal(await page.locator('[data-automatic-whitespace="true"]:visible').count(),stats.white);
  assert.equal(await page.locator('[data-automatic-whitespace="true"] input[data-article-select]').count(),0);
  assert.equal(await page.locator('[data-automatic-whitespace="true"] .review-human-badge').count(),0);
  assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.automatic_classification).every(u=>u.type==='paratext'&&u.original_type==='technical_passage'&&!u.human_validated&&!u.requires_human_classification&&!u.indexing_eligible&&!u.publication_ready)),true);
  await page.locator('#article-show-whitespace').uncheck();
  await page.locator('#article-show-c').uncheck();
  assert.equal(await page.locator('[data-automatic-whitespace="true"]:visible').count(),0);
  assert.equal(await page.evaluate(()=>articleDocument.units.length),stats.total);
  assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.human_validated).length),stats.human);
  for(const width of [375,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,whitespace_hidden_by_default:true,show_C_does_not_reveal_whitespace:true,separate_whitespace_toggle:true,ordinary_passages_remain_visible:true,no_selection_or_human_badge_for_automatic_blanks:true,no_records_removed:true,no_human_decisions_created:true,no_POST:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
