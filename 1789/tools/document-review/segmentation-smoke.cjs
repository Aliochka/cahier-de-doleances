/* Read-only proposals + explicit corrections, temporary fixture journals only. */
const {createRequire}=require('node:module');
const path=require('node:path');
const {chromium}=createRequire(path.resolve(__dirname,'../../../frontend/package.json'))('@playwright/test');
const assert=require('node:assert/strict');
(async()=>{
 const base=process.env.REVIEW_TEST_URL||'http://127.0.0.1:17896';
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  page.on('request',r=>{if(r.method()==='POST'&&r.url().endsWith('/decision'))writes.push(r.url());});
  await page.goto(base);await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleDocument&&articleParents.length===29);
  const id=await page.evaluate(()=>articleParents.find(p=>p.persee_id.endsWith('_1_1_1530')).id);
  await page.locator('#article-parent').selectOption(id);await page.waitForFunction(id=>articleDocument?.parent.id===id,id);
  const initial=await page.evaluate(()=>({head:articleDocument.previous_event_id,ids:articleDocument.units.map(u=>u.id)}));
  const panel=page.locator('#segmentation-comparison');await panel.locator('> summary').click();
  assert.ok(await panel.getByText('Séparation proposée', {exact:false}).count()>=6);
  assert.equal(writes.length,0);
  const proposal=panel.locator('.segmentation-proposal').filter({has:page.locator('h3').filter({hasText:'« 2"'})});
  await proposal.getByRole('button',{name:'Préparer une séparation à vérifier'}).click();
  assert.equal(await page.locator('#article-action').inputValue(),'split');
  assert.equal(await page.evaluate(()=>articleRange.point),5155532);
  assert.equal(await page.locator('#article-second-number').inputValue(),'2');
  assert.equal(writes.length,0);
  await page.locator('#article-close-editor').click();
  assert.deepEqual(await page.evaluate(()=>({head:articleDocument.previous_event_id,ids:articleDocument.units.map(u=>u.id)})),initial);
  await page.locator('#article-reviewer').fill('SYNTHETIC SEGMENTATION TEST');
  // Explicit human action on the fixture: a model proposal never triggers this automatically.
  await page.evaluate(async()=>{
   const u=articleDocument.units.find(u=>u.type==='article'&&u.start<5155532&&5155532<u.end);
   await saveArticleDecision({...articlePayload('validate',[u.id]),acknowledge_anomalies:true});
  });
  await page.waitForFunction(()=>articleDocument.units.some(u=>u.human_validated));
  assert.equal(writes.length,1);
  const protectedItem=panel.locator('.segmentation-proposal').filter({has:page.locator('h3').filter({hasText:'« 2"'})});
  assert.ok(await protectedItem.getByText('décision humaine prioritaire',{exact:false}).count());
  assert.equal(await protectedItem.getByRole('button',{name:'Préparer une séparation à vérifier'}).count(),0);
  await page.reload();await page.locator('#mode-articles').click();
  await page.waitForFunction(()=>articleDocument&&articleParents.length===29);
  await page.locator('#article-parent').selectOption(id);await page.waitForFunction(id=>articleDocument?.parent.id===id,id);
  assert.ok(await page.evaluate(()=>articleDocument.units.some(u=>u.human_validated)));
  const dimensions=[];
  for(const width of [320,375,768,1280]){
   await page.setViewportSize({width,height:950});
   await page.locator('#segmentation-comparison').evaluate(e=>e.open=true);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));dimensions.push(width);
  }
  await page.setViewportSize({width:375,height:950});await page.evaluate(()=>document.documentElement.style.fontSize='200%');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await panel.locator('> summary').focus();await page.keyboard.press('Space');
  assert.equal(await panel.evaluate(e=>e.open),false);
  assert.deepEqual(errors,[]);
  process.stdout.write(JSON.stringify({passed:true,read_only_comparison:true,prepare_without_writes:true,human_priority:true,reload:true,widths:dimensions,text_200_percent:true,keyboard:true,js_errors:errors,synthetic_journals_only:true},null,2)+'\n');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
