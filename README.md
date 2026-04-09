# Quant

面向个人开发者的加密量化研究与执行工作台。  
当前目标不是做“大而全”的交易平台，而是把这条主链做扎实：

`数据 -> 特征 -> 研究 -> 回测 -> 评估 -> dry-run -> 小额 live -> 复盘`

## 当前状态

- `phase1` 已完成  
  主链已经打通：研究、回测、评估、执行、自动化都能跑。
- `phase2` 进行中  
  当前重点是把工作台从“能看”补成“能配”，并把实验对比、研究解释、长期运行能力继续收紧。

## 这套系统现在能做什么

### 已经可用

- 读取 Binance 真实行情
- 读取 Binance 真实余额
- 跑 `Freqtrade` 的 `dry-run`
- 做小额 `live` 验证
- 跑 `Qlib` 训练、推理、筛选、复盘
- 看统一研究报告
- 看研究 / 回测 / 执行的差异
- 看自动化状态、告警、人工接管和恢复建议

### 前端现在有 6 个工作台

- `/data` 数据工作台
- `/features` 特征工作台
- `/research` 策略研究工作台
- `/backtest` 回测工作台
- `/evaluation` 评估与实验中心
- `/strategies` 和 `/tasks` 承担执行与自动化工作台

### 当前最重要的新能力

- 研究和 `dry-run` 现在共用一组更大的候选池
- `live` 使用更严格的小子集，不再和研究推荐断链
- 研究训练、推理、流水线已经有后台进度、阶段、预计时长和结果去向
- 评估页已经能直接说明：
  - 为什么推荐
  - 为什么淘汰
  - 研究、回测、执行差在哪里

## 系统导览与接手顺序

这是最短接手路径：

1. [CONTEXT.md](/home/djy/Quant/CONTEXT.md)  
   看当前做到哪、最近决策是什么
2. [docs/roadmap.md](/home/djy/Quant/docs/roadmap.md)  
   看当前阶段、后续规划和待办
3. [docs/architecture.md](/home/djy/Quant/docs/architecture.md)  
   看系统分层、模块职责和主链关系
4. [docs/developer-handbook.md](/home/djy/Quant/docs/developer-handbook.md)  
   看怎么开发、怎么验证、怎么改文档
5. [docs/deployment-handbook.md](/home/djy/Quant/docs/deployment-handbook.md)  
   看本地和服务器部署
6. [docs/user-handbook.md](/home/djy/Quant/docs/user-handbook.md)  
   看页面怎么用
7. [docs/system-flow-guide.md](/home/djy/Quant/docs/system-flow-guide.md)  
   看系统导览、整条系统流程和按钮背后的运行逻辑

补充入口：

- [docs/api.md](/home/djy/Quant/docs/api.md)
- [docs/ops.md](/home/djy/Quant/docs/ops.md)
- [docs/ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)
- [docs/ops-qlib.md](/home/djy/Quant/docs/ops-qlib.md)
- [docs/archive/README.md](/home/djy/Quant/docs/archive/README.md)

## 使用动线

### 人工研究到执行

1. 进入 `/signals` 或 `/research`
2. 运行 `Qlib` 信号流水线
3. 查看 `/evaluation`
4. 进入 `/strategies`
5. 先做 `dry-run`
6. 条件满足后再进入小额 `live`
7. 到 `/tasks` 看自动化与复盘
8. 到 `/balances`、`/orders`、`/positions` 看结果

### Qlib 验证工作流

1. 先做研究训练
2. 再做研究推理
3. 看统一研究报告和实验对比
4. 只让通过门控的候选进入 `dry-run`
5. 先跑 `dry-run`
6. `dry-run` 稳定后，才允许进入小额 `live`
7. `live` 完成后，统一回看余额、订单、持仓、任务和风险

## 本地运行

### 标准端口

- API：`9011`
- Web：`9012`
- Freqtrade REST：`9013`
- Qlib：`9014`
- OpenClaw：`9015`

### 临时联调端口

- 如果通过端口注册表开 `Quant-Debug-N`，就使用那一段分配到的端口
- 例如 `Quant-Debug-1` 可以使用 `9021-9030`

### 本地启动

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
```

如果当前还在临时 worktree 里联调，就把目录换成对应的 worktree 路径，例如：

```bash
cd /home/djy/Quant/.worktrees/hardening-phase1
```

API：

```bash
set -a
source .env.quant.local
set +a
/home/djy/Quant/.venv/bin/python -m uvicorn services.api.app.main:app --host 127.0.0.1 --port 9011
```

Web：

```bash
cd apps/web
pnpm build
HOSTNAME=127.0.0.1 PORT=9012 pnpm start
```

## 部署方式

### 代码基线

- GitHub 仓库是唯一代码基线
- 真实部署放在阿里云服务器
- 如果要临时联调，使用 `Quant-Debug-N` 端口段

### 云上部署

当前云上统一部署已经具备：

- API
- WebUI
- Freqtrade
- Mihomo

当前公开行情优先走：

- `data-api.binance.vision`

签名账户和真实下单继续走：

- `api.binance.com`

更详细的部署说明见：

- [docs/deployment-handbook.md](/home/djy/Quant/docs/deployment-handbook.md)
- [docs/ops-freqtrade.md](/home/djy/Quant/docs/ops-freqtrade.md)

## 测试方式

后端：

```bash
cd /home/djy/Quant
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/api/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s services/worker/tests -v
/home/djy/Quant/.venv/bin/python -m unittest discover -s tests -v
```

前端构建：

```bash
cd /home/djy/Quant/apps/web
pnpm build
```

浏览器测试：

```bash
cd /home/djy/Quant/apps/web
QUANT_WEB_BASE_URL=http://127.0.0.1:9012 QUANT_API_BASE_URL=http://127.0.0.1:9011 pnpm exec playwright test
```

说明：

- `pnpm test:ui` 只是一组基础 smoke
- 合并前以前面这条全量 `Playwright` 命令为准

## 研究层运行痕迹

研究层当前会写出这些文件，方便回放和排查：

- `dataset/latest_dataset_snapshot.json`
- `runs/experiment_index.json`

统一复盘接口：

- `GET /api/v1/tasks/validation-review`

## 最小演示与验收

固定演示脚本：

- [infra/scripts/demo_flow.ps1](/home/djy/Quant/infra/scripts/demo_flow.ps1)

相关说明：

- [docs/ops.md](/home/djy/Quant/docs/ops.md)

主链语义：

- `signal -> risk -> execution -> monitoring`

## 搜索记录

- 本轮没有新增外部方案搜索
- 本轮重点是文档整理、归档旧规划和补齐接手手册

## 当前规划入口

- [docs/roadmap.md](/home/djy/Quant/docs/roadmap.md)
- [plan.md](/home/djy/Quant/plan.md)

## 归档说明

早期阶段性 spec / plan 已移到：

- [docs/archive/README.md](/home/djy/Quant/docs/archive/README.md)

主入口不再直接引用 4 月 1 日到 4 月 4 日那批阶段文档，避免新的会话被旧计划干扰。
