// Existing frontend Playwright runtime, tested only against a loopback laboratory.
const {chromium}=require('../frontend/node_modules/@playwright/test');
(async()=>{
 const url=new URL(process.env.DOCUMENTARY_LAB_URL||'http://127.0.0.1:1791');
 if(url.protocol!=='http:'||!['127.0.0.1','localhost'].includes(url.hostname))throw Error('Loopback laboratory required');
 const browser=await chromium.launch({headless:true});
 try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url.href);await page.selectOption('[name=mode]','lexical');
  await page.fill('[name=q]','Agen agriculture');await page.click('#submit');
  await page.waitForFunction(()=>document.querySelectorAll('#results article').length>0);
  await page.locator('#results article a').first().click();await page.waitForSelector('#full-text mark');
  if(!(await page.locator('#full-text mark').textContent()).trim())throw Error('Missing Unicode passage');
  await page.selectOption('[name=mode]','compare');await page.fill('[name=q]','Beauvais jurandes');
  await page.click('#submit');await page.waitForFunction(()=>!document.querySelector('#comparison').hidden&&document.querySelectorAll('#results article').length>0);
  if(!(await page.locator('#branches').textContent()).includes('Vectoriel'))throw Error('Missing comparison');
  await page.screenshot({path:'/tmp/documentary-lab.png'});
  await page.selectOption('[name=mode]','lexical');
  await page.selectOption('[name=depth]','200');await page.selectOption('[name=volume]','1');
  await page.fill('[name=q]','zxqv1789inexistant');await page.click('#submit');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('0 cahiers'));
  for(const width of [375,1280]){await page.setViewportSize({width,height:900});if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+2))throw Error('Horizontal overflow');}
  if(errors.length)throw Error(errors.join('\n'));
  console.log(JSON.stringify({browser:'chromium',lexical_query:true,hybrid_comparison:true,reader:true,no_result:true,responsive:true,page_errors:errors}));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
