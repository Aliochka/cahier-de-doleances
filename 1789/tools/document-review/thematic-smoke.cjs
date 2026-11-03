/* Read-only source/context navigation; cloned journals, no documentary certification. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];let posts=0;
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')posts++;});
  await page.goto(process.env.REVIEW_TEST_URL||'http://127.0.0.1:17899');
  await page.locator('#mode-articles').click();await page.waitForFunction(()=>articleDocument&&articleWorkbench?.thematic_generation);
  const examples=await page.evaluate(()=>articleWorkbench.examples.filter(w=>w.group==='thematic_structure'));
  assert.equal(examples.length,12);
  const standalone=examples.find(w=>w.theme_form==='standalone_claim');
  await page.evaluate(id=>openArticleWindow(id),standalone.id);
  const card=page.locator('[data-unit-id="'+standalone.unit_id+'"]');await card.waitFor({state:'visible'});
  const claim=await page.evaluate(id=>articleDocument.units.find(u=>u.id===id),standalone.unit_id);
  assert.equal(claim.type,'article');assert.equal(claim.number,null);assert.equal(claim.thematic_context.unit_form,'unnumbered_thematic_claim');assert.equal(claim.human_validated,false);
  assert.ok((await card.locator('h3').textContent()).includes('non numéroté'));
  assert.ok(!claim.anomalies.some(a=>a.startsWith('Numéro non reconnu')));
  assert.ok(claim.text.includes(claim.thematic_context.title.trim()));
  await page.locator('#article-quality-filter').selectOption('historical_unnumbered_thematic_claim_proposal');
  assert.ok(await page.evaluate(()=>articleVisibleParents.length>0&&articleVisibleParents.every(p=>p.article_quality.historical_unnumbered_thematic_claim_proposal>0)));
  const section=examples.find(w=>w.theme_form==='section_with_articles');
  await page.evaluate(id=>openArticleWindow(id),section.id);
  await page.waitForFunction(id=>articleDocument?.parent.id===id,section.parent_id);
  const linked=await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article'&&u.thematic_context?.unit_form==='article_in_thematic_section'));
  assert.ok(linked.length>=2);assert.ok(linked.every(u=>u.number!==null&&u.effective_section_id===u.thematic_context.region_id));
  const key=await page.evaluate(()=>articleParents.find(p=>p.persee_id.endsWith('_2_1_1639')).id);
  await page.evaluate(id=>loadArticleParent(id),key);
  const jurandes=await page.evaluate(()=>articleDocument.units.find(u=>u.type==='article'&&u.number===null&&u.text.includes('Jurandes et maîtrises.')));
  assert.ok(jurandes.human_validated);assert.equal(jurandes.thematic_context.unit_form,'unnumbered_thematic_claim');assert.ok(jurandes.text.includes('Toutes les corporations désirent'));
  assert.equal(await page.locator('[data-automatic-whitespace="true"]:visible').count(),0);
  for(const width of [375,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,new_unnumbered_claim_with_title:true,numbered_articles_keep_section_context:true,theme_filters:true,beauvais_human_jurandes_preserved:true,whitespace_hidden:true,twelve_examples:true,no_POST:true,no_human_decisions_created:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
