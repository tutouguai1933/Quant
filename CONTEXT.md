# 当前进度

- 当前正在做：`Phase1 / Phase2` 的全面验收已经完成，review、全量后端测试、前端构建、Playwright 全量回归和真实页面联调都已跑通，下一步进入 `Phase3`。
- 上次停留位置：`Phase2` 功能已收口，但还缺一次把代码、测试和页面一起扫完的总验收。

# 关键决定

- 手动接管的状态契约固定为：
  - `mode` 保持当前自动模式
  - `paused` 和 `manual_takeover` 表示进入接管
  - `paused_reason` 记录接管原因
  - 路由测试已经按这个真实语义对齐
- 评估页里 `execution_alignment.status == unavailable` 时，不再因为旧订单 / 旧持仓碰巧同币而误判“研究和执行已对齐”。
- 自动化工作流里“只是等待”的分支不再计入日轮次：
  - 暂停中
  - 连续失败等待人工处理
  - 同步陈旧等待恢复
  - 日内轮次上限
  - 冷却窗口
- 自动化旧状态文件里没有合法 `created_at` 的告警，只算历史告警，不再抬高当前活跃告警和恢复阻塞。
- 研究工作台在 `workspace.status == unavailable` 时会锁住配置保存；信号页“推理摘要”的生成时间优先使用 `latest_inference.generated_at`。
- 本轮验收口径固定为：
  - Python 单测通过：`335`
  - 前端生产构建通过：`1`
  - Playwright 全量回归通过：`42`
  - 真实页面联调已验证：
    - 正常链路下 `/signals`、`/research`、`/evaluation`、`/strategies`、`/tasks` 可正常登录、跳转、提交动作和展示结果
    - 研究接口不可用时，`/research` 会显示“工作台暂时不可用”，并把配置表单锁成 `disabled`

# 下一步

- 正式进入 `Phase3`
- 主线先做：
  - 多模板 + 统一候选池
  - 研究到执行的仲裁层
  - 更稳的长期运行与人工接管
