const { test, expect } = require('@playwright/test');

const WEB_BASE_URL = 'http://localhost:9014';

test.describe('Full Acceptance Test', () => {
  test.beforeEach(async ({ page }) => {
    // 设置较长的超时时间
    test.setTimeout(120000);
  });

  test('should login successfully and navigate all pages', async ({ page, context }) => {
    test.setTimeout(120000);

    // 1. 访问首页
    await page.goto(WEB_BASE_URL);
    await expect(page).toHaveTitle(/Quant Control Plane/);
    console.log('✓ 首页加载成功');

    // 2. 登录 - 填写表单并提交
    await page.goto(`${WEB_BASE_URL}/login?next=/strategies`);
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', '1933');

    // 点击提交并等待页面内容变化
    await page.click('button[type="submit"]');

    // 等待策略页面的内容出现（不依赖导航事件）
    await page.waitForSelector('text=策略', { timeout: 30000 });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // 验证 cookie 已设置
    const cookies = await context.cookies();
    const sessionCookie = cookies.find(c => c.name === 'quant_admin_token');
    expect(sessionCookie).toBeDefined();
    console.log('✓ 登录成功，cookie 已设置');

    // 3. 检查所有核心页面不显示降级模式
    const corePages = [
      { path: '/evaluation', name: '评估页', title: '评估' },
      { path: '/research', name: '研究页', title: '研究' },
      { path: '/strategies', name: '策略页', title: '策略' },
      { path: '/tasks', name: '任务页', title: '任务' },
      { path: '/signals', name: '信号页', title: '信号' },
    ];

    for (const pageInfo of corePages) {
      await page.goto(`${WEB_BASE_URL}${pageInfo.path}`);
      await page.waitForLoadState('networkidle');
      await page.waitForTimeout(2000); // 等待客户端渲染完成

      // 检查页面标题存在
      const bodyContent = await page.locator('body').textContent();
      expect(bodyContent).toContain(pageInfo.title);

      // 检查不显示降级模式错误提示
      expect(bodyContent).not.toContain('部分数据加载失败');
      expect(bodyContent).not.toContain('后端 API 暂时不可用，当前显示降级数据');
      expect(bodyContent).not.toContain('正在使用本地 fallback 数据');

      console.log(`✓ ${pageInfo.name} 正常加载，无降级模式`);
    }

    // 4. 检查工具详情页
    const toolPages = [
      { path: '/market', name: '市场页', title: '市场' },
      { path: '/balances', name: '余额页', title: '余额' },
      { path: '/positions', name: '持仓页', title: '持仓' },
      { path: '/orders', name: '订单页', title: '订单' },
    ];

    for (const pageInfo of toolPages) {
      await page.goto(`${WEB_BASE_URL}${pageInfo.path}`);
      await page.waitForLoadState('networkidle');

      const bodyContent = await page.locator('body').textContent();
      expect(bodyContent).toContain(pageInfo.title);
      expect(bodyContent).not.toContain('部分数据加载失败');

      console.log(`✓ ${pageInfo.name} 正常加载`);
    }

    // 5. 检查因子页
    await page.goto(`${WEB_BASE_URL}/features`);
    await page.waitForLoadState('networkidle');
    const featuresContent = await page.locator('body').textContent();
    expect(featuresContent).toContain('因子');
    expect(featuresContent).not.toContain('部分数据加载失败');
    console.log('✓ 因子页正常加载');

    // 6. 检查首页主工作台
    await page.goto(WEB_BASE_URL);
    await page.waitForLoadState('networkidle');
    const homeContent = await page.locator('body').textContent();
    expect(homeContent).toContain('当前推荐');
    expect(homeContent).not.toContain('部分数据加载失败');
    console.log('✓ 首页主工作台正常');

    console.log('✓✓✓ 所有页面验收通过 ✓✓✓');
  });

  test('should verify OpenClaw functionality', async ({ page }) => {
    // 登录
    await page.goto(`${WEB_BASE_URL}/login`);
    await page.fill('input[name="username"]', 'admin');
    await page.fill('input[name="password"]', '1933');
    await page.click('button[type="submit"]');
    await page.waitForLoadState('networkidle');

    // 进入任务页
    await page.goto(`${WEB_BASE_URL}/tasks`);
    await page.waitForLoadState('networkidle');

    // 检查 OpenClaw 相关内容
    const bodyContent = await page.locator('body').textContent();

    // 检查自动化状态区存在
    expect(bodyContent).toContain('自动化');

    // 检查不显示降级模式错误提示
    expect(bodyContent).not.toContain('部分数据加载失败');
    expect(bodyContent).not.toContain('后端 API 暂时不可用，当前显示降级数据');

    console.log('✓ OpenClaw 功能区域正常显示');
  });

  test('should show login prompt when not authenticated', async ({ page }) => {
    // 清除 cookies 模拟未登录状态
    await page.context().clearCookies();

    // 访问需要登录的页面
    await page.goto(`${WEB_BASE_URL}/strategies`);
    await page.waitForLoadState('networkidle');

    const bodyContent = await page.locator('body').textContent();

    // 应显示登录提示而不是降级模式错误
    expect(bodyContent).toContain('需要登录');
    expect(bodyContent).not.toContain('部分数据加载失败');
    expect(bodyContent).not.toContain('后端 API 暂时不可用，当前显示降级数据');

    console.log('✓ 未登录时正确显示登录提示');
  });
});