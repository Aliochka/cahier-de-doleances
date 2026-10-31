/* Full collection, global_test_server.py only: cloned journals, temporary changes. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17898';
  await page.goto(base);await page.waitForFunction(()=>records.length===1305);
  assert.equal(await page.locator('#batch').isChecked(),false);
  assert.equal(await page.locator('#list > li').count(),1305);
  await page.locator('#mode-articles').click();await page.waitForFunction(()=>articleDocument&&articleParents.length>=1200);
  assert.ok(await page.locator('#article-unresolved-list > li').count()>=60);
  assert.equal(await page.evaluate(()=>articleParents.reduce((n,p)=>n+p.human_reviewed,0)),333);
  await page.locator('#article-volume').selectOption('6');
  await page.waitForFunction(()=>articleDocument.parent.volume===6);
  await page.locator('#article-query').fill('');await page.locator('#article-volume').selectOption('');
  await page.locator('#article-query').fill('Pecqueuse');
  await page.waitForFunction(()=>articleDocument?.parent.metadata.id?.endsWith('_5_1_2333'));
  const id=await page.evaluate(()=>articleDocument.parent.id);
  assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article').length),38);
  await page.locator('#article-review-boundaries').click();await page.waitForFunction(id=>current?.record.id===id,id);
  await page.getByText('Rechercher un bloc dans le volume de ce document',{exact:true}).click();
  await page.locator('#source-query').fill('gabelle');await page.locator('#source-find').click();
  await page.waitForFunction(()=>document.querySelector('#source-find-results').children.length>0);
  await page.locator('#reviewer').fill('SYNTHETIC GLOBAL BROWSER');await page.locator('#confirm').check();
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/decision')&&r.request().method()==='POST');
  await page.locator('#decision button[type=submit]').click();assert.equal((await saved).status(),200);
  await page.waitForFunction(()=>document.querySelector('#save-notice').textContent.includes('enregistrée'));
  const reviewed=(await (await page.request.get(base+'/api/list')).json()).find(r=>r.id===id);
  assert.equal(reviewed.documentary_review?.priority||'none','none');
  await page.evaluate(id=>open(id),id);
  const rebuilt=page.waitForResponse(r=>r.url().endsWith('/api/articles/rebuild'));
  await page.locator('#document-rebuild').click();assert.equal((await rebuilt).status(),200);
  await page.waitForFunction(id=>articleDocument?.parent.id===id&&articleDocument.parent.boundary_class==='human_validated'&&!document.querySelector('#article-stream').hidden&&!document.querySelector('#articles-panel').hidden,id);
  assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.type==='article').length),38);
  assert.equal(await page.evaluate(()=>articleDocument.units.filter(u=>u.human_validated).length),0);
  await page.locator('#article-reviewer').fill('SYNTHETIC GLOBAL BROWSER');
  const first=await page.evaluate(()=>articleDocument.units.find(u=>u.type==='article').id);
  await page.locator(`.review-unit[data-unit-id="${first}"]`).getByRole('button',{name:'Valider',exact:true}).click();
  await page.waitForFunction(()=>articleDocument.units.some(u=>u.human_validated),null,{timeout:10000}).catch(async e=>{console.error('VALIDATION DEBUG',await page.locator('#article-status').textContent());throw e;});
  await page.reload();await page.waitForFunction(()=>records.length===1305);await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleParents.length>=1200&&articleDocument);
  await page.locator('#article-query').fill('Pecqueuse');await page.waitForFunction(id=>articleDocument?.parent.id===id,id);
  assert.ok(await page.evaluate(()=>articleDocument.units.some(u=>u.human_validated)));
  for(const width of [320,375,768,1280]){await page.setViewportSize({width,height:950});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.locator('#article-review-boundaries').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(id=>current?.record.id===id&&!document.querySelector('#cahiers-panel').hidden,id);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({passed:true,notices:1305,full_collection:true,original_human_articles_preserved:333,Pecqueuse_articles:38,volume_filter:true,title_search:true,unresolved_access:true,source_search:true,parent_validation_then_rebuild:true,article_validation_reload:true,keyboard:true,viewports:[320,375,768,1280],text_zoom_200_percent:true,js_errors:errors,temporary_journals_only:true},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
