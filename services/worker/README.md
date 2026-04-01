# Worker Notes

## 目标

`services/worker` 预留给第一阶段的信号生产与后台任务执行。当前仓库还没有引入任务运行时或调度器，因此这里只记录最小 worker 方向和 `Task 5` 的约束。

## 第一阶段最小信号生产路径

当前优先落地的不是完整研究平台，而是一个可演示的最小流水线：

1. 数据准备
2. 特征生成
3. 训练
4. signal 输出

这条链路在当前代码里由 `services/api/app/services/signal_service.py` 提供最小可运行骨架。

## 当前可执行路径

- 默认执行路径：`mock`
- 可选占位路径：`qlib`
- 兼容来源枚举：`mock | qlib | rule-based`

说明：

- `mock` 路径使用内置样例数据执行完整四阶段，输出与正式 producer 一致的 `signal` 契约
- `qlib` 路径当前只保留接口和阶段定义，等待后续用户批准安装 `qlib` 后再接入真实依赖
- `rule-based` 路径沿用同一输出契约，用于后续补充简化规则策略

## 为什么当前不直接安装 Qlib

当前仓库仍遵守“不自动安装依赖、不自动修改依赖声明”的约束，因此：

- 先把阶段接口、契约和 API 链路固定
- 再在后续需要时由用户批准安装 `qlib`

## 后续接入 Qlib 时需要覆盖的最小阶段

- 初始化数据源
- 准备训练数据集
- 配置特征处理
- 运行模型训练
- 生成标准化 signal
- 把 signal 交给 Control Plane API

## 与控制平面的边界

- worker 不直接操作 WebUI
- worker 不直接操作执行器
- 所有信号都必须通过统一 `SignalContract`
- 所有页面继续通过 Control Plane API 取数
