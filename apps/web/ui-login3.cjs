const { chromium } = require('@playwright/test');
const TOKEN = process.env.QTOKEN || '';
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext();
  await ctx.addCookies([{ name: 'quant_admin_token', value: TOKEN, url: 'http://39.106.11.65:9012' }]);
  const page = await ctx.newPage();
  await page.goto('http://39.106.11.65:9012/tasks', { waitUntil: 'networkidle', timeout: 30000 }).catch(()=>{});
  await page.waitForTimeout(3500);
  const info = await page.evaluate(() => {
    const txt = document.body.innerText;
    return {
      logged: !txt.includes('先去登录'),
      hasCard: txt.includes('方向做空'),
      seg: (txt.match(/方向做空[\s\S]{0,280}/) || ['(无)'])[0].replace(/\n/g, ' | '),
    };
  });
  console.log('已登录:', info.logged, '| 方向做空卡:', info.hasCard);
  console.log(info.seg);
  await browser.close();
})();
