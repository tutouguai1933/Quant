# Quant 开发手册

这份文档面向新的开发会话。  
目标是让新的 AI 或开发者一进来就知道：

- 先读什么
- 在哪里开发
- 怎么验证
- 怎么避免把前端和文档弄乱

## 1. 接手顺序

先按这个顺序读：

1. `CONTEXT.md`
2. `README.md`
3. `docs/roadmap.md`
4. `docs/architecture.md`
5. `docs/system-flow-guide.md`

如果任务和某一层强相关，再继续读：

- 研究相关：`docs/ops-qlib.md`
- 执行相关：`docs/ops-freqtrade.md`
- 部署相关：`docs/deployment-handbook.md`
- 历史决策：`docs/archive/README.md`

## 2. 当前推荐开发环境

默认在主目录开发：

- `/home/djy/Quant`

如果是临时联调：

- 按 `/home/djy/.port-registry.yaml` 分配 `Quant-Debug-N`
- 例如 `Quant-Debug-1` 可以使用 `9021-9030`

标准主端口仍然是：

- API：`9011`
- Web：`9012`
- Freqtrade：`9013`

## 3. 本地启动

先进入环境：

```bash
source /home/djy/miniforge3/etc/profile.d/conda.sh
conda activate quant
cd /home/djy/Quant
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

## 4. 前端验证规则

这是当前最重要的规则。

只要改了页面、按钮、表单、脚本或接口联动，不能只看代码或接口，必须走这条顺序：

1. `pnpm build`
2. 停掉旧的前端端口
3. 用最新 build 重启当前页面端口
4. 跑浏览器测试
5. 做真实页面回读

原因：

- 旧 build 和新页面混用时，最容易出现“只剩纯文字”“亮底块”“资源 400”
- 这些往往不是代码逻辑问题，而是旧构建产物没有被彻底替换

## 5. 最常用验证命令

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

浏览器：

```bash
cd /home/djy/Quant/apps/web
QUANT_WEB_BASE_URL=http://127.0.0.1:9012 QUANT_API_BASE_URL=http://127.0.0.1:9011 pnpm exec playwright test
```

说明：

- `pnpm test:ui` 只是一组基础 smoke
- 真正的合并门槛仍然是上面这条全量 `Playwright` 命令

真实页面回读：

```bash
curl -s http://127.0.0.1:9012/research
curl -s http://127.0.0.1:9012/evaluation
curl -s http://127.0.0.1:9012/tasks
```

## 6. 文档更新规则

每轮阶段性完成后：

- 必须更新 `CONTEXT.md`
- 如果能力、运行方式、部署方式有变化，还要更新：
  - `README.md`
  - `docs/architecture.md`
  - `docs/roadmap.md`

如果只是阶段性思路和旧计划，不要再继续往主目录堆新 spec / plan。  
优先：

- 更新当前主文档
- 把旧阶段文档放到 `docs/archive/`

## 7. 当前主线在哪里

现在开发重点不是再铺新模块，而是继续推进：

1. 工作台更完整可配置
2. 实验对比和研究 / 执行结果更清楚
3. 长期运行、告警、人工接管更稳

更详细的待办看：

- `docs/roadmap.md`

## 8. 哪些东西不要乱动

- 不要提交 `apps/web/node_modules`
- 不要把旧 spec / plan 再放回主入口
- 不要绕开统一配置中心，单独给工作台各写一套保存逻辑
- 不要跳过真实页面验证就说“修好了”

## 9. 新 AI 接手时最容易踩的坑

### 坑 1：拿旧 build 做验证

结果：

- 页面像纯文字
- 样式乱
- chunk 404

### 坑 2：只看后端成功，不看页面状态

结果：

- 接口成功了，但用户看不到变化

### 坑 3：只看推荐分数，不看门控和执行差异

结果：

- 误以为候选能直接进 `live`

### 坑 4：把历史 spec / plan 当成当前入口

结果：

- 会被 4 月初的阶段文档误导

所以：

- 当前入口只看主文档
- 历史设计只在需要追溯时再去 archive
