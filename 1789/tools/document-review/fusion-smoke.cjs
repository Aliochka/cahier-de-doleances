/* Read-only browser verification over a fixture with cloned human journals. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts++;});
  await page.goto((process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898')+'/?fusion_review=1');
  await page.waitForFunction(()=>articleDocument&&articleWorkbench?.fusion_validation?.length===16);
  assert.equal(await page.locator('#fusion-window-list li').count(),16);
  assert.ok(await page.locator('#fusion-campaign').isVisible());
  const campaign=await page.evaluate(()=>articleWorkbench.fusion_validation);
  assert.equal(campaign.filter(w=>w.group==='fusion_validation').length,9);
  assert.equal(campaign.filter(w=>w.group==='fusion_refusal').length,6);
  const amiens=campaign.find(w=>w.group==='fusion_development');
  await page.evaluate(id=>openArticleWindow(id),amiens.id);
  const dotation=await page.evaluate(id=>articleDocument.units.find(u=>u.id===id),amiens.unit_id);
  assert.equal(dotation.number,null);assert.equal(dotation.type,'article');assert.equal(dotation.human_validated,false);
  assert.ok(dotation.text.trim().startsWith('Dotation des cures'));
  assert.ok(!dotation.text.includes('Retraite pour les anciens'));
  const prefix=await page.evaluate(()=>articleDocument.units.find(u=>u.spans[0][0]===5640887));
  assert.equal(prefix.number,'2');assert.equal(prefix.spans.at(-1)[1],5643975);
  assert.ok(await page.locator('#fusion-comparison').isVisible());
  assert.ok((await page.locator('[data-unit-id="'+dotation.id+'"] mark').textContent()).includes('Dotation'));
  const positive=campaign.find(w=>w.group==='fusion_validation');
  await page.evaluate(id=>openArticleWindow(id),positive.id);
  const claim=await page.evaluate(id=>articleDocument.units.find(u=>u.id===id),positive.unit_id);
  assert.equal(claim.type,'article');assert.equal(claim.number,null);assert.equal(claim.human_validated,false);
  assert.equal(claim.thematic_context.unit_form,'unnumbered_thematic_claim');
  assert.ok(await page.locator('[data-unit-id="'+positive.unit_id+'"] mark').isVisible());
  const refusal=campaign.find(w=>w.group==='fusion_refusal');
  await page.evaluate(id=>openArticleWindow(id),refusal.id);
  assert.ok(await page.locator('[data-unit-id="'+refusal.unit_id+'"] mark').isVisible());
  assert.equal(await page.locator('#article-sample-list li').count(),24);
  await page.locator('#article-quality-filter').selectOption('automatic_thematic_fusion_split');
  assert.ok(await page.evaluate(()=>articleVisibleParents.length>0&&articleVisibleParents.every(p=>p.article_quality.automatic_thematic_fusion_split>0)));
  await page.reload();await page.waitForFunction(()=>articleWorkbench?.fusion_validation?.length===16);
  for(const width of [375,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,campaign_entries:16,held_out_separations:9,refusals:6,amiens_article_2_and_dotation_separate:true,old_sample_preserved:true,source_highlight:true,quality_filter:true,reload:true,responsive:true,no_POST:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
