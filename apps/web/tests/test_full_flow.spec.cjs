const { test, expect } = require('@playwright/test');

test.describe('Full Application Flow', () => {
  test('should complete full login and navigation flow', async ({ page }) => {
    // 1. Visit home page
    await page.goto('http://localhost:9012/');
    await expect(page).toHaveTitle(/Quant Control Plane/);

    // 2. Login
    await page.goto('http://localhost:9012/login');
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', '1933');
    await page.click('button[type="submit"]');

    // Wait for redirect after login
    await page.waitForURL(/.*\/(strategies|evaluation|research|tasks).*/);

    // 3. Test evaluation page
    console.log('Testing evaluation page...');
    await page.goto('http://localhost:9012/evaluation');
    await page.waitForLoadState('networkidle');

    // Should NOT show degraded mode
    const evalContent = await page.content();
    expect(evalContent).not.toContain('降级模式');
    expect(evalContent).not.toContain('部分数据加载失败');

    // Should show decision center
    await expect(page.locator('text=决策中心')).toBeVisible({ timeout: 10000 });

    // 4. Test research page
    console.log('Testing research page...');
    await page.goto('http://localhost:9012/research');
    await page.waitForLoadState('networkidle');

    const researchContent = await page.content();
    expect(researchContent).not.toContain('降级模式');
    expect(researchContent).not.toContain('部分数据加载失败');

    // 5. Test tasks page
    console.log('Testing tasks page...');
    await page.goto('http://localhost:9012/tasks');
    await page.waitForLoadState('networkidle');

    const tasksContent = await page.content();
    expect(tasksContent).not.toContain('降级模式');
    expect(tasksContent).not.toContain('部分数据加载失败');

    // 6. Test other pages
    const pages = [
      { path: '/strategies', title: '策略' },
      { path: '/signals', title: '信号' },
      { path: '/orders', title: '订单' },
      { path: '/positions', title: '持仓' },
      { path: '/market', title: '市场' },
      { path: '/balances', title: '余额' },
    ];

    for (const { path, title } of pages) {
      console.log(`Testing ${path}...`);
      await page.goto(`http://localhost:9012${path}`);
      await page.waitForLoadState('networkidle');
      const content = await page.content();
      expect(content).toContain(title);
    }

    console.log('All tests passed!');
  });
});
