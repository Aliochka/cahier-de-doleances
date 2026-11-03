/* Read-only collection, exact Unicode highlight, all six volumes; no human decisions. */
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
  await page.goto(base+'/passages');await page.waitForFunction(()=>window.technicalDocument);
  assert.equal(await page.locator('#technical-sample li').count(),12);
  const sample=await page.evaluate(()=>catalogue.sample.windows);
  assert.deepEqual([...new Set(sample.map(w=>w.volume))].sort(),[1,2,3,4,5,6]);
  for(const w of sample){
   await page.goto(base+'/passages?passage='+encodeURIComponent(w.passage_id));
   await page.waitForFunction(id=>window.technicalDocument?.passage?.id===id,w.passage_id);
   const d=await page.evaluate(()=>window.technicalDocument);
   assert.equal(await page.locator('#technical-highlight').textContent(),d.passage.text);
   assert.equal(await page.locator('#technical-full-text').textContent(),d.document.full_text);
   assert.equal(await page.locator('#technical-excerpt').textContent(),d.passage.text);
   assert.equal(await page.locator('#technical-error').textContent(),'');
   assert.ok(d.passage.token_count<=800);assert.equal(d.passage.historical_article_claim,false);
   const visible=await page.evaluate(()=>{const a=document.getElementById('technical-full-text').getBoundingClientRect(),b=document.getElementById('technical-highlight').getBoundingClientRect();return b.top<a.bottom&&b.bottom>a.top;});assert.ok(visible);
  }
  const next=await page.locator('#technical-next').getAttribute('href');
  if(next){await page.goto(base+next);await page.waitForFunction(()=>window.technicalDocument);assert.equal(await page.locator('#technical-error').textContent(),'');}
  const empty=await page.evaluate(()=>catalogue.summary.whitespace_only_documents[0]);
  if(empty){
   await page.goto(base+'/passages?document='+encodeURIComponent(empty));
   await page.waitForFunction(()=>window.technicalDocument?.passage===null);
   assert.ok((await page.locator('#technical-status').textContent()).includes('uniquement de blancs'));
  }else{
   for(const suffix of ['2837','2877']){
    await page.goto(base+'/passages?document='+encodeURIComponent('ap1789-registry-p1:arcpa_0000-0000_1879_num_5_1_'+suffix));
    await page.waitForFunction(()=>window.technicalDocument?.passage?.text.trim().length>0);
    assert.ok((await page.locator('#technical-full-text').textContent()).includes('CAHIER'));
    const recovered=await page.evaluate(()=>window.technicalDocument);
    assert.equal(recovered.document.boundary_status.certified,false);
    assert.equal(recovered.document.document_components.length,suffix==='2837'?1:3);
    assert.ok((await page.locator('#technical-status').textContent()).includes('Codex'));
    if(suffix==='2877')assert.ok((await page.locator('#technical-components').textContent()).includes('Pétition explicitement jointe'));
    assert.equal(await page.locator('#technical-error').textContent(),'');
   }
  }
  for(const width of [375,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  assert.equal(posts,0);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,sample_windows:12,six_volumes:true,exact_excerpt_and_parent:true,highlight_in_view:true,deep_links:true,passage_navigation:true,empty_or_recovered_exceptions_checked:true,responsive:true,no_POST:true,js_errors:errors},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
