# Lean / vn.py / OpenClaw 扩展位计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不打断当前 crypto 主线的前提下，把 Lean、vn.py、OpenClaw 的目录位、接口位、任务位和文档位补齐，确保未来扩展时不需要重做控制平面。

**Architecture:** 当前阶段只保留扩展边界，不接真实市场或真实执行。重点是把控制平面的契约、任务、目录和页面说明先收敛好。

**Tech Stack:** Python、FastAPI、现有任务系统、现有文档体系、WebUI 文案与入口

---

## 范围

### 本计划要做

- Lean 扩展位目录与接口约定
- vn.py 扩展位目录与接口约定
- OpenClaw 任务入口与非交易任务契约
- 文档、页面和任务系统对齐

### 本计划不做

- Lean 真实接入
- vn.py 真实接入
- OpenClaw 实际部署
- 多市场真实数据或真实交易

## 文件规划

### 新建

- `services/api/app/adapters/lean/README.md`
- `services/api/app/adapters/vnpy/README.md`
- `services/api/app/services/openclaw_service.py`
- `services/api/tests/test_openclaw_service.py`
- `docs/extensions.md`
- `docs/ops-openclaw.md`

### 修改

- `services/api/app/routes/tasks.py`
  增加 OpenClaw 触发的非交易任务入口
- `services/api/app/services/task_service.py` 或现有任务模块
  对齐训练、同步、对账、归档、巡检任务类型
- `services/api/app/domain/contracts.py`
  明确扩展执行器与任务契约枚举
- `apps/web/app/tasks/page.tsx`
  展示非交易任务来源和状态
- `apps/web/app/page.tsx`
  补长期架构说明卡片
- `apps/web/lib/api.ts`
  对接新的任务来源字段
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `CONTEXT.md`

## Todo List

- [ ] 补 Lean 扩展目录和说明
- [ ] 补 vn.py 扩展目录和说明
- [ ] 定义 OpenClaw 非交易任务入口
- [ ] 收敛训练、同步、对账、归档、巡检任务类型
- [ ] 在任务页显示任务来源和类型
- [ ] 在首页补长期架构说明
- [ ] 补扩展架构文档
- [ ] 补 OpenClaw 运维文档
- [ ] 完成扩展位一致性验收

## 任务拆分

### Task 1：整理扩展目录

- [ ] 新建 Lean / vn.py 扩展目录说明文件
- [ ] 写失败测试：目录说明文件必须存在
- [ ] 补最小说明内容
- [ ] 运行目标测试并确认通过

### Task 2：定义 OpenClaw 任务入口

- [ ] 写失败测试：非交易任务入口返回标准任务结构
- [ ] 写失败测试：不允许通过该入口触发直接交易动作
- [ ] 实现 `openclaw_service`
- [ ] 运行目标测试并确认通过

### Task 3：收敛任务系统

- [ ] 写失败测试：训练、同步、对账、归档、巡检任务类型稳定
- [ ] 修改任务服务和路由
- [ ] 给任务记录加来源字段
- [ ] 运行后端相关测试并确认通过

### Task 4：接入页面说明

- [ ] 写失败测试：任务页显示任务来源
- [ ] 写失败测试：首页显示长期架构卡片
- [ ] 实现最小页面改动
- [ ] 运行前端测试、类型检查和构建

### Task 5：文档和验收

- [ ] 新增 `docs/extensions.md`
- [ ] 新增 `docs/ops-openclaw.md`
- [ ] 更新 README、架构、接口、CONTEXT
- [ ] 在 Todo 中勾掉已完成项

## 验收标准

- 仓库中能清晰看到 Lean、vn.py 的扩展位置
- 任务系统支持非交易任务来源标记
- OpenClaw 只负责非交易任务，不会越过控制平面触发交易
- 页面和文档都能说明这些扩展位当前是什么状态

## 建议验证命令

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s tests -v
cd apps/web && pnpm exec tsc --noEmit && pnpm build
```

预期结果：

- 后端测试通过
- 前端测试通过
- 构建通过
