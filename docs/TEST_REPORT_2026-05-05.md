# 测试报告

> 测试日期：2026-05-05
> 测试环境：生产模式 (pnpm build + pnpm start)
> 服务器：39.106.11.65

---

## 1. 测试摘要

| 测试类型 | 结果 | 详情 |
|---------|------|------|
| 前端页面功能 | ✅ 通过 | 所有页面正常渲染 |
| API 后端功能 | ✅ 通过 | 所有 API 返回正确数据 |
| Playwright 自动化 | ✅ 通过 | 17/17 测试通过 |
| 性能测试 | ⚠️ 部分问题 | 3 个 API 响应过慢 |

---

## 2. 前端页面测试

### 2.1 页面加载性能（生产模式）

| 页面 | HTTP 状态 | 加载时间 |
|------|----------|---------|
| / (首页) | 200 | 41ms |
| /research (模型训练) | 200 | 35ms |
| /backtest (回测训练) | 200 | 31ms |
| /evaluation (选币回测) | 200 | 36ms |
| /features (因子研究) | 200 | 30ms |
| /factor-knowledge (因子知识库) | 200 | 35ms |
| /market (市场) | 200 | 38ms |
| /strategies (实盘管理) | 200 | 42ms |
| /tasks (运维) | 200 | 40ms |

**结论**：生产模式下页面加载极快（30-40ms），相比开发模式（2-4分钟编译）有巨大提升。

### 2.2 Playwright 自动化测试

| 项目 | 结果 |
|------|------|
| 测试总数 | 17 |
| 通过 | 17 |
| 失败 | 0 |
| 总耗时 | 1.7 分钟 |

所有页面可访问性测试和交互测试均通过。

---

## 3. API 性能测试

### 3.1 性能对比

| API 端点 | 响应时间 | 状态 |
|---------|---------|------|
| GET /healthz | 6.9s | ❌ 慢 |
| GET /api/v1/research/workspace | 10.5s | ❌ 慢 |
| GET /api/v1/features/workspace | 25s | ❌ 极慢 |
| GET /api/v1/evaluation/workspace | 30s | ❌ 极慢 |
| GET /api/v1/backtest/workspace | 0.09s | ✅ 正常 |
| GET /api/v1/market | 2.3s | ⚠️ 可接受 |
| GET /api/v1/signals/research/runtime | 0.03s | ✅ 正常 |

### 3.2 terminal 字段验证

所有工作区 API 都正确返回了 terminal 字段：

| API | route | breadcrumb | title |
|-----|-------|------------|-------|
| research/workspace | /research | 研究 / 模型训练 | 模型训练 |
| backtest/workspace | /backtest | 研究 / 回测训练 | 回测训练 |
| features/workspace | /features | 数据与知识 / 因子研究 | 因子研究 |
| evaluation/workspace | /evaluation | 研究 / 选币回测 | 选币回测 |

---

## 4. 性能问题分析

### 4.1 根本原因

三个慢 API 存在共同的性能瓶颈 - 重复计算链：

```
get_workspace() 
  → _controls_builder() → workbench_config_service.build_workspace_controls()
  → _read_factory_report() → research_service.get_factory_report()
    → research_service.get_latest_result() [读取 JSON 文件]
    → ResearchFactoryService.build_report() [构建报告]
```

### 4.2 具体问题

| 问题 | 影响范围 | 耗时估计 |
|------|---------|---------|
| `get_latest_result()` 无缓存，每次都读取 JSON 文件 | 所有慢 API | 3-4s |
| `build_workspace_controls()` 每次重新构建静态配置 | 所有慢 API | 2-3s |
| `_build_config_alignment()` 做了 ~100 个字段的字典比较 | research | 2-3s |
| 对每个因子调用 `get_factor_detail()` | features | 5-8s |
| `_read_validation_review()` 调用多个外部服务 | evaluation | 10-15s |

---

## 5. 优化建议

### 5.1 优先级 1：添加结果缓存

修改文件：`/services/api/app/services/research_service.py`

```python
import time

class ResearchService:
    def __init__(self, ...):
        ...
        self._latest_result_cache: dict[str, object] | None = None
        self._latest_result_cache_time: float = 0
        self._factory_report_cache: dict[str, object] | None = None
        self._factory_report_cache_time: float = 0
        self._cache_ttl: float = 5.0

    def get_latest_result(self) -> dict[str, object]:
        now = time.time()
        if (self._latest_result_cache is not None and 
            (now - self._latest_result_cache_time) < self._cache_ttl):
            return self._latest_result_cache
        result = self._compute_latest_result()
        self._latest_result_cache = result
        self._latest_result_cache_time = now
        return result

    def get_factory_report(self) -> dict[str, object]:
        now = time.time()
        if (self._factory_report_cache is not None and 
            (now - self._factory_report_cache_time) < self._cache_ttl):
            return self._factory_report_cache
        latest = self.get_latest_result()
        report = ResearchFactoryService(result_provider=lambda: latest).build_report()
        self._factory_report_cache = report
        self._factory_report_cache_time = now
        return report
```

### 5.2 优先级 2：缓存 workbench_config

修改文件：`/services/api/app/services/workbench_config_service.py`

```python
class WorkbenchConfigService:
    def __init__(self, ...):
        ...
        self._controls_cache: dict[str, object] | None = None

    def build_workspace_controls(self) -> dict[str, object]:
        if self._controls_cache is not None:
            return self._controls_cache
        self._controls_cache = self._build_workspace_controls()
        return self._controls_cache
```

### 5.3 预期性能提升

| API | 当前耗时 | 优化后预期 | 提升比例 |
|-----|---------|-----------|---------|
| /api/v1/research/workspace | 10.5s | 0.5-1s | ~90% |
| /api/v1/features/workspace | 25s | 1-2s | ~92% |
| /api/v1/evaluation/workspace | 30s | 2-3s | ~90% |

---

## 6. 结论

### 6.1 通过项

- ✅ 所有前端页面正常渲染
- ✅ 所有 API 返回正确数据
- ✅ Playwright 17/17 测试通过
- ✅ 生产模式页面加载 30-40ms
- ✅ terminal 字段数据完整

### 6.2 待优化项

- ❌ 3 个 API 响应时间过长（需要添加缓存）
- ⚠️ 健康检查 API 响应慢（需要检查实现）

### 6.3 下一步

1. 实现上述缓存优化
2. 重新测试验证性能提升
3. 检查 /healthz 端点实现
