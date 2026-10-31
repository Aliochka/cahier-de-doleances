/* Uses the synthetic article_test_server fixture, no real journal writes. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(r.method()==='POST')writes.push(r.url());});
  const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17897';
  await page.goto(base);await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleDocument&&articleCampaign?.selected.length===5);
  assert.equal(await page.locator('#article-campaign-list > li').count(),5);
  const choices=await page.evaluate(()=>articleCampaign.selected);
  for(const p of choices){
   await page.locator('#article-campaign-list').getByRole('button',{name:p.title,exact:true}).click();
   await page.waitForFunction(id=>articleDocument.parent.id===id,p.id);
   assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article').length),p.proposed_articles);
   assert.equal(await page.evaluate(()=>articleDocument.history.length),0);
  }
  await page.locator('#article-campaign-list button').first().focus();await page.keyboard.press('Enter');
  await page.waitForFunction(id=>articleDocument.parent.id===id,choices[0].id);
  await page.reload();await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleDocument&&articleCampaign?.selected.length===5);
  assert.deepEqual(await page.evaluate(()=>articleCampaign.selected.map(p=>p.id)),choices.map(p=>p.id));
  for(const width of [320,375,768,1280]){
   await page.setViewportSize({width,height:950});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
  console.log('Campaign OK: five frozen choices, correct counts, keyboard, reload, responsive, zero POSTs.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
