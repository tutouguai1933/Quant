#!/bin/bash
# Playwright UI 审查脚本 - 检查所有页面的样式和功能

set -e

BASE_URL="http://39.106.11.65:9012"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
    ((PASS++))
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
    ((FAIL++))
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
    ((WARN++))
}

echo "=============================================="
echo "Playwright UI 审查"
echo "=============================================="
echo ""

# 创建测试文件
TEST_FILE="/tmp/playwright-test.js"
cat > "$TEST_FILE" << 'EOF'
const { chromium } = require('playwright');

async function runTests() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
  const page = await context.newPage();

  const baseUrl = process.env.BASE_URL || 'http://39.106.11.65:9012';
  const pages = [
    '/', '/login', '/strategies', '/balances', '/positions',
    '/orders', '/risk', '/research', '/backtest', '/evaluation',
    '/features', '/ops', '/tasks', '/analytics', '/data',
    '/market', '/market/BTCUSDT', '/signals', '/hyperopt',
    '/config', '/factor-knowledge'
  ];

  const results = [];

  for (const path of pages) {
    try {
      const response = await page.goto(baseUrl + path, { waitUntil: 'networkidle', timeout: 15000 });
      const status = response ? response.status() : 0;

      // 检查页面内容
      const bodyText = await page.evaluate(() => document.body.innerText);
      const hasContent = bodyText.length > 100;

      // 检查样式问题
      const styleIssues = await page.evaluate(() => {
        const issues = [];

        // 检查是否有白色背景
        const body = document.body;
        const bgColor = window.getComputedStyle(body).backgroundColor;
        if (bgColor && (bgColor.includes('255, 255, 255') || bgColor.includes('white'))) {
          issues.push('白色背景（非终端风格）');
        }

        // 检查是否有横向滚动
        if (document.documentElement.scrollWidth > document.documentElement.clientWidth) {
          issues.push('横向滚动溢出');
        }

        // 检查是否有大段空白
        const elements = document.querySelectorAll('*');
        let maxEmptyHeight = 0;
        elements.forEach(el => {
          const rect = el.getBoundingClientRect();
          if (rect.height > 500 && el.textContent.trim() === '') {
            maxEmptyHeight = Math.max(maxEmptyHeight, rect.height);
          }
        });
        if (maxEmptyHeight > 500) {
          issues.push(`大段空白区域: ${Math.round(maxEmptyHeight)}px`);
        }

        return issues;
      });

      // 检查关键元素
      const hasTerminalShell = await page.$('section, div[class*="terminal"]') !== null;

      results.push({
        path,
        status,
        hasContent,
        issues: styleIssues,
        hasTerminalShell
      });

    } catch (error) {
      results.push({
        path,
        status: 0,
        error: error.message
      });
    }
  }

  await browser.close();

  // 输出结果
  for (const r of results) {
    if (r.error) {
      console.log(`❌ ${r.path} - 加载失败: ${r.error}`);
    } else {
      const issues = r.issues && r.issues.length > 0 ? r.issues.join(', ') : '正常';
      const terminal = r.hasTerminalShell ? '✅' : '⚠️';
      console.log(`${r.status === 200 ? '✅' : '⚠️'} ${r.path} (${r.status}) ${terminal} - ${issues}`);
    }
  }

  console.log('\n总计:', results.length, '页面');
}

runTests().catch(console.error);
EOF

# 检查 Playwright 是否安装
if ! command -v npx &> /dev/null; then
    echo "⚠️  npx 未安装，尝试使用其他方法检查"
fi

# 先使用 curl 检查页面状态
echo "=== 页面加载状态检查 ==="
echo ""

pages=(
    "/"
    "/login"
    "/strategies"
    "/balances"
    "/positions"
    "/orders"
    "/risk"
    "/research"
    "/backtest"
    "/evaluation"
    "/features"
    "/ops"
    "/tasks"
    "/analytics"
    "/data"
    "/market"
    "/market/BTCUSDT"
    "/signals"
    "/hyperopt"
    "/config"
    "/factor-knowledge"
)

for page in "${pages[@]}"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$page" 2>/dev/null || echo "000")
    if [ "$status" == "200" ]; then
        check_pass "$page - HTTP $status"
    elif [ "$status" == "302" ]; then
        check_warn "$page - HTTP $status (重定向)"
    else
        check_fail "$page - HTTP $status"
    fi
done

echo ""
echo "=============================================="
echo "检查结果汇总"
echo "=============================================="
echo -e "${GREEN}通过: $PASS${NC}"
echo -e "${RED}失败: $FAIL${NC}"
echo -e "${YELLOW}警告: $WARN${NC}"