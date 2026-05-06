# 项目部署和开发注意事项

## 核心原则：本地开发 + 服务器部署

### 部署架构
```
本地WSL (代码编辑) --> SSH部署 --> 服务器 (Docker运行)
                                    ├── quant-api (FastAPI)
                                    ├── quant-web (Next.js)
                                    ├── quant-freqtrade
                                    ├── quant-mihomo
                                    └── ...其他服务
```

### 部署命令（必须在服务器执行）

```bash
# SSH到服务器
ssh djy@39.106.11.65

# 进入部署目录
cd /home/djy/Quant/infra/deploy

# 完整重建并部署
docker compose build api web && docker compose up -d api web

# 仅重启API（修改了Python代码时）
docker compose build api && docker compose up -d api

# 仅重启Web（修改了前端代码时）
docker compose build web && docker compose up -d web

# 查看日志
docker logs quant-api --tail 100
docker logs quant-web --tail 100
```

## 常见问题排查

### 1. API返回空数据但代码看起来正确

**原因**: 代码修改后没有重新部署到服务器

**排查步骤**:
```bash
# 1. 检查服务器上的代码是否是最新的
ssh djy@39.106.11.65 "cat /app/services/api/app/routes/market.py | grep -A 5 'def get_rsi_summary'"

# 2. 检查日志是否有异常
ssh djy@39.106.11.65 "docker logs quant-api --tail 50"

# 3. 确认容器已重启
ssh djy@39.106.11.65 "docker ps | grep quant-api"
```

### 2. 前端组件没有显示

**排查步骤**:
```bash
# 1. 确认容器已重建
ssh djy@39.106.11.65 "docker exec quant-web cat /app/apps/web/.next/BUILD_ID"

# 2. 检查构建日志
ssh djy@39.106.11.65 "docker logs quant-web --tail 30"
```

### 3. RSI接口超时（响应时间>60秒）

**原因**: 串行获取16个币种的RSI数据，每个请求可能需要1-2秒

**解决方案**: 使用并发请求（已在market.py中实现ThreadPoolExecutor）

### 4. 线程池中函数无法访问模块级变量

**问题**: 在ThreadPoolExecutor中执行的函数无法访问模块级导入的`timedelta`、`timezone`等

**解决方案**: 在函数内部重新导入所需模块

```python
# 错误写法
from datetime import timedelta, timezone
def _fetch_single_rsi(...):
    # 在线程池中执行时可能找不到timedelta
    shanghai_tz = timezone(timedelta(hours=8))

# 正确写法
def _fetch_single_rsi(...):
    from datetime import timedelta as td, timezone as tz_module
    shanghai_tz = tz_module(td(hours=8))
```

### 5. 切换dry_run模式后实盘连接断开

**检查项**:
```bash
# 1. 确认Freqtrade配置
curl -s http://localhost:8080/api/v1/show_config -u "Freqtrader:jianyu0.0." | python3 -c "import sys,json; print(json.load(sys.stdin).get('dry_run'))"

# 2. 检查config.private.json是否有Binance API Key
cat /home/djy/Quant/infra/freqtrade/user_data/config.private.json | grep -E "key|secret"
```

## 配置文件位置

| 服务 | 配置文件 | 说明 |
|------|----------|------|
| API | `/home/djy/Quant/infra/deploy/api.env` | 环境变量配置 |
| Web | `/home/djy/Quant/infra/deploy/` | 通过api.env配置 |
| Freqtrade | `/home/djy/Quant/infra/freqtrade/user_data/config.*.json` | 多个配置文件 |
| Mihomo | `/home/djy/Quant/infra/mihomo/config.yaml` | 代理配置 |

## 环境变量说明

关键环境变量：
- `QUANT_RUNTIME_MODE`: dry-run / live
- `QUANT_MARKET_SYMBOLS`: 监控的币种列表
- `QUANT_FREQTRADE_API_URL`: Freqtrade API地址
- `BINANCE_API_KEY` / `BINANCE_API_SECRET`: 交易所API密钥