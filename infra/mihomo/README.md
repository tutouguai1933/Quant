# Mihomo 代理说明

这个目录只负责阿里云上的代理入口。

当前约定：

- 使用 `Mihomo` 兼容现有的 Clash 配置文件
- 运行时配置文件放在：
  - `infra/mihomo/config.yaml`
- 这个文件不进 Git，只保留在本机或服务器

推荐做法：

- 不要用“自动选择”或“故障转移”
- 固定选择一个稳定节点
- 让 Binance 白名单只认这一条固定出口 IP

服务器默认端口：

- `9016`：Mihomo 混合代理端口
- `9017`：Mihomo 控制器端口

最小用法：

1. 准备一份可用的 Clash / Mihomo 配置
2. 放到 `infra/mihomo/config.yaml`
3. 在 `infra/deploy/.env` 里启用 `QUANT_MIHOMO_*` 变量
4. 在 `infra/deploy/api.env` 和 `infra/freqtrade/.env` 里把代理地址指向 `http://mihomo:7890`

说明：

- 市场公开行情可以直接走 `data-api.binance.vision`
- 余额、订单、真实下单和 Freqtrade 仍然依赖 `api.binance.com`
- 这部分如果不走代理，在中国大陆服务器上经常会超时
