/* Read-only checks against global_test_server.py (copied, temporary journals). */
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
  await page.goto(base+'/?review_priority=high');
  await page.waitForFunction(()=>records.length===1305&&document.querySelector('#review-level').value==='high');
  const counts=await page.evaluate(()=>Object.fromEntries(['high','medium','low','none'].map(v=>[v,records.filter(r=>r.documentary_review.priority===v).length])));
  assert.equal(await page.locator('#list>li').count(),counts.high);
  await page.locator('#review-level').selectOption('medium');
  assert.equal(await page.locator('#list>li').count(),counts.medium);
  const id='ap1789-registry-p1:arcpa_0000-0000_1879_num_4_1_2168';
  await page.goto(base+'/?document='+encodeURIComponent(id));
  await page.waitForFunction(id=>current?.record.id===id&&!document.querySelector('#document').hidden,id);
  assert.equal(await page.evaluate(()=>current.state.selected.start),4774125);
  assert.equal(await page.evaluate(()=>current.documentary_resolution.changed),true);
  assert.notEqual(await page.evaluate(()=>current.state.status),'human_validated');
  assert.equal(await page.locator('#confirm').isChecked(),false);
  assert.match(await page.locator('#documentary-review-info').textContent(),/correction automatique/);
  assert.equal(await page.locator('.selected-start').count(),1);
  await page.locator('#expand').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>current.radius===12);
  for(const width of [320,375,768,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,priorities:counts,direct_document_link:true,corrected_XML_boundary_displayed:true,not_human_validation:true,no_write_request:true,keyboard:true,viewports:[320,375,768,1280],text_200_percent:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
