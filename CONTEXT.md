# 当前进度

- 当前正在做：补 `WSL + Docker + Binance Spot + dry-run` 的 Freqtrade 真实接入骨架，并把默认白名单切到 `BTC / ETH / SOL / DOGE`。
- 上次停留位置：刚完成 Freqtrade 的 `memory / rest` 双后端和市场页、单币页的真实页面验收。
- 近期关键决定：
  - 当前继续采用多 session 分工：
    - 这个 session 负责 `Freqtrade` 执行层和 Docker 实接位
    - 另一个 session 负责 `Qlib` 研究层
  - 当前已经完成：
    - 默认市场白名单切到 `BTCUSDT / ETHUSDT / SOLUSDT / DOGEUSDT`
    - 仓库内新增 `infra/freqtrade` Docker 部署骨架
    - 已把公开配置、私密配置样板和最小 README 分开
  - 当前真实联调还差：
    - 真正把 Freqtrade 容器拉起来
    - 在本地补 `QUANT_FREQTRADE_API_URL / USERNAME / PASSWORD`
    - 用控制平面完成最终 dry-run 验收
  - 当前下一步已经收敛为：
    - 先让 Docker 里的 Freqtrade 真正启动
    - 再把控制平面从 `memory` 切到 `rest`
