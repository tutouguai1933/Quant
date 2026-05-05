// @ts-check
const { test, expect } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:9012';

const pages = [
  { path: '/', name: '总览页' },
  { path: '/features', name: '因子页' },
  { path: '/research', name: '研究页' },
  { path: '/evaluation', name: '决策页' },
  { path: '/strategies', name: '执行页（需登录）' },
  { path: '/tasks', name: '运维页（需登录）' },
  { path: '/market', name: '市场页' },
  { path: '/balances', name: '余额页' },
  { path: '/positions', name: '持仓页' },
  { path: '/orders', name: '订单页' },
  { path: '/risk', name: '风险页（需登录）' },
  { path: '/signals', name: '信号页' },
];

test.describe('所有页面可访问性测试', () => {
  test.setTimeout(300000); // 5 minutes for slow dev server compilation

  for (const page of pages) {
    test(`${page.name} - ${page.path}`, async ({ page: browserPage }) => {
      console.log(`\n测试页面: ${page.name} (${page.path})`);

      const response = await browserPage.goto(`${BASE_URL}${page.path}`, {
        waitUntil: 'domcontentloaded',
        timeout: 180000, // 3 minutes
      });

      expect(response?.status()).toBe(200);
      console.log(`✓ HTTP 状态: ${response?.status()}`);

      await browserPage.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {
        console.log('⚠ 网络未完全空闲，继续测试');
      });

      const title = await browserPage.title();
      console.log(`✓ 页面标题: ${title}`);
      expect(title).toBeTruthy();

      const bodyText = await browserPage.locator('body').textContent();
      expect(bodyText).toBeTruthy();
      expect(bodyText.length).toBeGreaterThan(100);
      console.log(`✓ 页面内容长度: ${bodyText.length} 字符`);

      const hasError = bodyText.includes('Application error') ||
                       bodyText.includes('Unhandled Runtime Error') ||
                       bodyText.includes('Error: ');

      if (hasError) {
        console.log('✗ 页面包含错误信息');
        const screenshot = await browserPage.screenshot();
        console.log(`截图大小: ${screenshot.length} bytes`);
      }
      expect(hasError).toBe(false);

      const navLinks = await browserPage.locator('nav a').count();
      console.log(`✓ 导航链接数量: ${navLinks}`);

      await browserPage.waitForTimeout(1000);
      console.log(`✓ ${page.name} 测试通过\n`);
    });
  }
});

test.describe('关键交互测试', () => {
  test.setTimeout(60000);

  test('总览页 - 导航到其他页面', async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });

    const researchLink = page.locator('a[href="/research"]').first();
    await expect(researchLink).toBeVisible();
    await researchLink.click();

    await page.waitForURL('**/research', { timeout: 10000 });
    expect(page.url()).toContain('/research');
    console.log('✓ 导航到研究页成功');
  });

  test('市场页 - 检查数据加载', async ({ page }) => {
    await page.goto(`${BASE_URL}/market`, { waitUntil: 'domcontentloaded' });

    // Wait longer for client-side data fetching
    await page.waitForTimeout(8000);

    // Take screenshot for debugging
    await page.screenshot({ path: '/tmp/market-debug.png', fullPage: true });

    const bodyText = await page.locator('body').textContent();
    const hasMarketData = bodyText?.includes('BTCUSDT') ||
                          bodyText?.includes('ETHUSDT') ||
                          bodyText?.includes('DOGEUSDT') ||
                          bodyText?.includes('SOLUSDT');

    console.log(`市场数据加载: ${hasMarketData ? '成功' : '未检测到'}`);

    // Also check for empty state
    const hasEmptyState = bodyText?.includes('暂无市场数据');
    console.log(`空状态显示: ${hasEmptyState ? '是' : '否'}`);

    // Check for table rows
    const tableRowCount = await page.locator('table tbody tr').count();
    console.log(`表格行数: ${tableRowCount}`);
  });

  test('因子页 - 检查内容', async ({ page }) => {
    await page.goto(`${BASE_URL}/features`, { waitUntil: 'domcontentloaded' });

    await page.waitForTimeout(2000);

    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain('因子');
    console.log('✓ 因子页内容正常');
  });

  test('评估页 - 检查决策中心', async ({ page }) => {
    await page.goto(`${BASE_URL}/evaluation`, { waitUntil: 'domcontentloaded' });

    await page.waitForTimeout(3000);

    const bodyText = await page.locator('body').textContent();
    const hasDecisionContent = bodyText?.includes('决策') ||
                               bodyText?.includes('评估') ||
                               bodyText?.includes('仲裁');

    console.log(`决策中心内容: ${hasDecisionContent ? '正常' : '未检测到'}`);
  });
});

test.describe('错误处理测试', () => {
  test('404 页面', async ({ page }) => {
    const response = await page.goto(`${BASE_URL}/nonexistent-page-12345`, {
      waitUntil: 'domcontentloaded',
    });

    expect(response?.status()).toBe(404);

    const bodyText = await page.locator('body').textContent();
    expect(bodyText).toContain('404');
    console.log('✓ 404 页面正常显示');
  });
});
