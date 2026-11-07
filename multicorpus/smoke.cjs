// Uses the existing frontend browser runtime; no public frontend changes.
const {chromium}=require('../frontend/node_modules/@playwright/test');
(async()=>{
 const url=new URL(process.env.MULTICORPUS_LAB_URL||'http://127.0.0.1:1792');
 if(url.protocol!=='http:'||!['127.0.0.1','localhost'].includes(url.hostname))throw Error('Loopback only');
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url.href);await page.fill('[name=q]','Gabelle');await page.click('#submit');
  await page.waitForFunction(()=>document.querySelectorAll('#results article').length===50);
  const corpora=await page.locator('#results article>small').allTextContents();
  if(!corpora.some(s=>s.includes('1789'))||!corpora.some(s=>s.includes('2019')))throw Error('Expected both sources for this observed query');
  await page.locator('#results article').filter({hasText:'Cahiers de 1789'}).first().locator('a').first().click();
  await page.waitForSelector('#full-text mark');
  if(!(await page.locator('#full-text mark').textContent()).trim())throw Error('Empty source passage');
  await page.locator('#results article').filter({hasText:'Grand Débat 2019'}).first().getByText('Ouvrir la réponse complète').click();
  await page.waitForFunction(()=>document.querySelector('#reader-meta').textContent.includes('Réponse'));
  await page.click('#h1');await page.waitForFunction(()=>!document.querySelector('#h1').disabled);if(await page.locator('#h1-results').evaluate(n=>n.hidden))throw Error(await page.locator('#h1-status').textContent());
  await page.selectOption('[name=corpus]','1789');await page.selectOption('[name=mode]','lexical');
  await page.fill('[name=q]','zxqv1789inexistant');await page.click('#submit');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('0 documents'));
  await page.selectOption('[name=corpus]','2019');await page.fill('[name=place]','Agen');await page.click('#submit');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Historical filters require'));
  for(const width of [375,1280]){await page.setViewportSize({width,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow');}
  await page.screenshot({path:'/tmp/multicorpus-lab.png'});
  if(errors.length)throw Error(errors.join('\n'));
  console.log(JSON.stringify({both_corpora:true,historical_reader:true,answer_reader:true,h1_reference:true,no_lexical_result:true,incompatible_filter_refused:true,responsive:true,page_errors:errors}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
