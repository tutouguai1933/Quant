const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  console.log('Navigating to market page...');
  await page.goto('http://127.0.0.1:9012/market', { waitUntil: 'networkidle', timeout: 30000 });

  // Wait for data to load
  await page.waitForTimeout(5000);

  // Get page content
  const content = await page.content();

  // Check for market data
  const hasBTCUSDT = content.includes('BTCUSDT');
  const hasETHUSDT = content.includes('ETHUSDT');
  const hasEmptyMessage = content.includes('暂无市场数据');

  console.log('Has BTCUSDT:', hasBTCUSDT);
  console.log('Has ETHUSDT:', hasETHUSDT);
  console.log('Has empty message:', hasEmptyMessage);

  // Take screenshot
  await page.screenshot({ path: '/tmp/market-page-final.png', fullPage: true });
  console.log('Screenshot saved to /tmp/market-page-final.png');

  // Check the DataTable content
  const tableRows = await page.locator('table tbody tr').count();
  console.log('Table rows count:', tableRows);

  // Get first table row content
  if (tableRows > 0) {
    const firstRow = await page.locator('table tbody tr:first-child td:first-child').textContent();
    console.log('First row symbol:', firstRow);
  }

  await browser.close();
})();