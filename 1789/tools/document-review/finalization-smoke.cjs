/* Technical navigation checks only; no documentary judgement of the 12 sampled cahiers. */
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
  await page.goto(base+'/?boundary_sample=1');
  await page.waitForFunction(()=>boundaryCampaign?.matches_active_generation&&document.querySelector('#boundary-sample').checked);
  const campaign=await page.evaluate(()=>boundaryCampaign);
  assert.equal(campaign.selected.length,12);assert.equal(new Set(campaign.selected.map(r=>r.document_id)).size,12);
  for(let v=1;v<=6;v++)assert.equal(campaign.selected.filter(r=>r.volume===v).length,2);
  assert.equal(await page.locator('#boundary-campaign-list>li').count(),12);
  assert.equal(await page.locator('#list>li').count(),12);
  assert.ok(await page.evaluate(()=>filtered.every(r=>r.status!=='human_validated')));
  await page.locator('#focused-blockers').check();assert.equal(await page.locator('#list>li').count(),5);
  await page.locator('#boundary-sample').check();assert.equal(await page.locator('#list>li').count(),12);
  const first=campaign.selected[0].document_id;
  await page.locator('#boundary-campaign-list>li').first().getByRole('button').click();
  await page.waitForFunction(id=>current?.record.id===id,first);
  assert.equal(await page.locator('#confirm').isChecked(),false);
  assert.notEqual(await page.evaluate(()=>current.state.status),'human_validated');
  await page.locator('#next').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(id=>current?.record.id!==id,first);
  const currentId=await page.evaluate(()=>current.record.id);assert.equal(currentId,campaign.selected[1].document_id);
  for(const width of [320,375,768,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,sample_size:12,two_per_volume:true,focused_blockers:5,sample_navigation:true,keyboard:true,viewports:[320,375,768,1280],text_200_percent:true,no_human_validation:true,no_POST:true,no_documentary_assessment_of_sample:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
