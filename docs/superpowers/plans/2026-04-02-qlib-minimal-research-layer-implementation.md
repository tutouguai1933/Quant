# Qlib 最小研究层计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把当前最小信号流水线升级成真正可解释的研究层，先覆盖数据准备、特征、训练、推理、signal 输出和结果展示。

**Architecture:** 控制平面继续只消费标准化结果，不直接耦合 Qlib 内部实现。Qlib 第一阶段只做 crypto 场景下的最小研究闭环，先服务当前两套波段策略和市场观察页面。

**Tech Stack:** Python、Qlib、FastAPI、现有信号契约、现有 unittest、WebUI

**运行约定：** 所有 Python 相关命令默认在 conda 环境 `quant` 中执行。

---

## 范围

### 本计划要做

- Qlib 最小运行配置
- crypto 研究数据准备入口
- 特征与标签的最小定义
- 训练、推理、signal 输出
- 模型版本、运行记录、解释摘要
- 策略页和图表页的研究结果展示

### 本计划不做

- 完整实验平台
- 自动调参
- 多模型管理界面
- 多市场研究

## 文件规划

### 新建

- `services/worker/qlib_runner.py`
  负责训练、推理和结果落盘的统一入口
- `services/worker/qlib_config.py`
  负责研究层配置和路径约束
- `services/worker/qlib_features.py`
  负责最小特征定义
- `services/worker/qlib_labels.py`
  负责最小标签定义
- `services/api/app/services/research_service.py`
  负责读取研究运行结果并转成控制平面视图
- `services/api/tests/test_research_service.py`
- `services/worker/tests/test_qlib_runner.py`
- `docs/ops-qlib.md`

### 修改

- `services/api/app/services/signal_service.py`
  从 mock/最小流水线逐步切到真实研究输出
- `services/api/app/routes/signals.py`
  增加训练、推理、结果读取入口
- `services/api/app/services/strategy_workspace_service.py`
  聚合研究分数和解释
- `apps/web/app/signals/page.tsx`
  展示研究运行结果
- `apps/web/app/market/[symbol]/page.tsx`
  展示研究解释摘要
- `apps/web/app/strategies/page.tsx`
  展示研究分数和模型版本
- `apps/web/lib/api.ts`
  对接研究结果字段
- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `CONTEXT.md`

## Todo List

- [x] 定义 Qlib 最小配置和目录结构
- [x] 定义 crypto 最小特征和标签
- [x] 跑通最小训练入口
- [x] 跑通最小推理入口
- [x] 输出标准化 `signal / score / explanation / model_version`
- [x] 把研究结果接入策略页
- [x] 把研究解释接入图表页
- [x] 增加研究运行记录与最近一次结果查看
- [x] 补研究层运维文档
- [x] 完成最小研究闭环验收

## 任务拆分

### Task 1：整理研究层目录与配置

- [x] 新建 Qlib 运行配置文件和目录约束
- [x] 写失败测试：无 Qlib 配置时仍能给出明确状态
- [x] 写失败测试：运行目录不存在时给出明确错误
- [x] 实现最小配置加载
- [x] 运行目标测试并确认通过

### Task 2：定义最小特征和标签

- [x] 写失败测试：给定 K 线样本能产生固定特征集合
- [x] 写失败测试：标签输出结构稳定
- [x] 实现最小特征和标签定义
- [x] 运行目标测试并确认通过

### Task 3：实现训练和推理入口

- [x] 写失败测试：训练入口返回运行记录
- [x] 写失败测试：推理入口返回标准化 signal 结果
- [x] 实现 `qlib_runner`
- [x] 运行 worker 相关测试并确认通过

### Task 4：接入控制平面

- [x] 写失败测试：研究服务能读取最近一次结果
- [x] 写失败测试：signals 路由能触发训练 / 推理
- [x] 实现 `research_service` 与路由改造
- [x] 运行后端相关测试并确认通过

### Task 5：接入页面展示

- [x] 写失败测试：策略页显示研究分数和模型版本
- [x] 写失败测试：图表页显示研究解释摘要
- [x] 实现最小页面改动
- [x] 运行前端测试、类型检查和构建

### Task 6：文档和验收

- [x] 新增 `docs/ops-qlib.md`
- [x] 更新 README、架构、接口、CONTEXT
- [x] 完成最小训练到 signal 输出的验收
- [x] 在 Todo 中勾掉已完成项

## 验收标准

- 能执行一次最小训练
- 能执行一次最小推理
- 控制平面能读取并展示 `signal / score / explanation / model_version`
- 策略页和图表页能看见研究结果，不只是接口可用
- 研究层故障时会给出明确状态，不静默失败

## 建议验证命令

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
python -m unittest discover -s services/api/tests -v
python -m unittest discover -s services/worker/tests -v
python -m unittest discover -s tests -v
cd apps/web && pnpm exec tsc --noEmit && pnpm build
```

预期结果：

- API 测试通过
- worker 测试通过
- 前端测试通过
- 构建通过
