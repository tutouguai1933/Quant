# Freqtrade Spot Dry-Run

这个目录负责给 Quant 提供一套最小可落地的 `WSL + Docker + Binance Spot + dry-run` 部署骨架。

## 当前用途

- 用 Docker 在 WSL 里跑一台真实的 Freqtrade
- 交易模式固定为 `Spot`
- 当前只做 `dry-run`
- REST API 默认只监听本机 `127.0.0.1:8080`
- Docker 继续使用 `host` 网络，方便复用这台环境的本机代理
- 第一批交易对白名单固定为：
  - `BTC/USDT`
  - `ETH/USDT`
  - `SOL/USDT`
  - `DOGE/USDT`

## 目录说明

- `docker-compose.yml`
  - 负责启动 Freqtrade 容器
- `.env.example`
  - 负责给 Docker Compose 提供可修改的启动参数样板
- `user_data/config.base.json`
  - 负责存放可提交的公开 dry-run 配置
- `user_data/config.private.json.example`
  - 负责告诉你私密配置该怎么写，但不会提交真实密钥

## 启动前你要准备什么

- Docker 和 Docker Compose 已可用
- 一组 Binance API Key
- 后续如果 dry-run 联调要求更完整权限，再把该 Key 调整为专用 `Spot Trading` Key

## 本地最小步骤

1. 复制环境变量样板
2. 复制私密配置样板
3. 把 Binance Key、REST 用户名和密码填进去
4. 启动 Freqtrade 容器
5. 把控制平面的 `QUANT_FREQTRADE_API_URL / USERNAME / PASSWORD` 指向它

## 推荐命令

```bash
cd /home/djy/Quant/infra/freqtrade
cp .env.example .env
cp user_data/config.private.json.example user_data/config.private.json
docker compose up -d
```

预期结果：

- 本机 `127.0.0.1:8080` 会有一台 Freqtrade REST API
- 控制平面补齐 REST 配置后，会从 `memory` 切到 `rest`
