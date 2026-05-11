# 降级模式误报修复 (2026-04-18)

## 问题描述

用户报告：点击登录后页面卡住，过一段时间显示未登录状态。所有主要页面（评估、研究、策略、信号）都显示"降级模式"警告，即使后端 API 正常返回数据。

## 根本原因

前端错误检测逻辑存在 bug：

```typescript
// 错误的检查方式
const hasApiErrors = results.some(
  (result) =>
    result.status === "rejected" ||
    (result.status === "fulfilled" && result.value && "error" in result.value && result.value.error)
);
```

问题：
- API 成功响应返回 `{"data": {...}, "error": null, "meta": {...}}`
- 检查 `"error" in result.value` 返回 `true`（因为 key 存在）
- 检查 `result.value.error` 在 `error: null` 时返回 `false`
- 但整个表达式仍然为 `true`，因为 JavaScript 的逻辑运算符优先级问题

## 修复方案

修改错误检测逻辑，明确检查 error 是否为 null 或 undefined：

```typescript
// 正确的检查方式
const hasApiErrors = results.some(
  (result) =>
    result.status === "rejected" ||
    (result.status === "fulfilled" && result.value && result.value.error !== null && result.value.error !== undefined)
);
```

## 修改的文件

1. `apps/web/app/evaluation/evaluation-client.tsx` - 评估页面客户端组件
2. `apps/web/app/research/page.tsx` - 研究工作台页面
3. `apps/web/app/strategies/page.tsx` - 策略中心页面
4. `apps/web/app/signals/page.tsx` - 信号页面

## 验证结果

修复后验证：
- ✅ 评估页面正常加载，不显示降级模式
- ✅ 研究页面正常加载，不显示降级模式
- ✅ 策略页面正常加载，不显示降级模式
- ✅ 信号页面正常加载，不显示降级模式
- ✅ 后端 API 返回 `"error": null` 时前端正确识别为成功响应

## 测试命令

```bash
# 检查页面是否显示降级模式
curl -s http://localhost:9012/evaluation | grep -o "降级模式" | wc -l  # 应返回 0
curl -s http://localhost:9012/research | grep -o "降级模式" | wc -l    # 应返回 0
curl -s http://localhost:9012/strategies | grep -o "降级模式" | wc -l  # 应返回 0
curl -s http://localhost:9012/signals | grep -o "降级模式" | wc -l     # 应返回 0

# 检查 API 响应
curl -s http://localhost:9012/api/control/evaluation/workspace | python3 -c "import sys, json; d=json.load(sys.stdin); print('Has error:', d.get('error') is not None)"
```

## 部署步骤

```bash
# 1. 重新构建 web 容器
docker compose -f infra/deploy/docker-compose.yml build web

# 2. 重启 web 服务
docker compose -f infra/deploy/docker-compose.yml up -d web

# 3. 等待服务健康检查通过
docker compose -f infra/deploy/docker-compose.yml ps web

# 4. 验证页面正常加载
curl -s http://localhost:9012/evaluation | grep -o "降级模式" | wc -l
```

## 相关提交

- Commit: 91d27f1
- Message: "fix(frontend): correct error detection logic to prevent false degraded mode"

## 影响范围

- 前端所有使用 `Promise.allSettled` 进行 API 调用的页面
- 降级模式检测逻辑
- 用户体验：修复后页面加载速度更快，不会误显示降级模式警告

## 后续建议

1. 在其他页面中检查是否存在类似的错误检测逻辑
2. 考虑创建统一的 API 错误检测工具函数，避免重复代码
3. 添加单元测试验证错误检测逻辑的正确性
