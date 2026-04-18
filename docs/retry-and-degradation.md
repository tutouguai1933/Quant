# 客户端重试和降级策略

## 概述

为 Binance market_client 和 Freqtrade REST client 添加了超时重试和连接失败降级策略，确保在网络不稳定或服务不可用时系统能够优雅降级，而不是直接返回 500 错误。

## 实现的功能

### 1. Binance Market Client

**文件**: `services/api/app/adapters/binance/market_client.py`

**特性**:
- 3 次重试机制（可配置）
- 指数退避策略（基础延迟 0.5 秒，每次重试翻倍）
- 超时配置（默认从环境变量读取）
- 连接失败时返回空结果而非抛异常

**配置参数**:
```python
BinanceMarketClient(
    base_url="https://api.binance.com",
    timeout_seconds=5.0,
    max_retries=3,        # 最大重试次数
    base_delay=0.5,       # 基础延迟（秒）
)
```

**降级行为**:
- `get_tickers()` → 返回 `[]`
- `get_klines()` → 返回 `[]`
- `get_exchange_info()` → 返回 `{"symbols": []}`

### 2. Freqtrade REST Client

**文件**: `services/api/app/adapters/freqtrade/rest_client.py`

**特性**:
- 3 次重试机制（可配置）
- 指数退避策略（基础延迟 0.5 秒）
- 超时配置（默认 10 秒）
- 对 5xx 错误和网络错误进行重试
- 对 401 错误自动刷新 token 并重试一次

**配置参数**:
```python
FreqtradeRestConfig(
    base_url="http://localhost:8080",
    username="bot",
    password="secret",
    timeout_seconds=10.0,
    max_retries=3,        # 最大重试次数
    base_delay=0.5,       # 基础延迟（秒）
)
```

**重试策略**:
- 5xx 服务器错误 → 重试
- 网络连接错误 (URLError) → 重试
- 超时错误 (TimeoutError) → 重试
- 401 未授权 → 刷新 token 后重试一次
- 其他 4xx 错误 → 直接抛异常

**降级行为**:
- 达到最大重试次数后抛出 `FreqtradeRestError`
- 上层服务（如 routes）捕获异常并返回 200 + unavailable 状态

## 重试工具

**文件**: `services/api/app/adapters/retry_utils.py`

提供了通用的重试装饰器和降级响应构建函数（预留给未来使用）。

## 测试覆盖

### 1. 重试和降级测试
**文件**: `services/api/tests/test_retry_and_fallback.py`

测试内容:
- Binance client 超时重试
- Binance client 达到最大重试次数后返回空结果
- Binance client 使用指数退避
- Freqtrade client 5xx 错误重试
- Freqtrade client 达到最大重试次数后抛异常
- Freqtrade client 连接错误重试
- Freqtrade client 使用指数退避

### 2. 优雅降级测试
**文件**: `services/api/tests/test_client_graceful_degradation.py`

测试内容:
- Binance client 连接失败时返回空列表
- Binance client 超时时返回空列表
- Market service 处理空 ticker 列表
- Binance client 连接不可达端点时降级
- Binance client 降级前重试

## 使用示例

### Binance Market Client

```python
from services.api.app.adapters.binance.market_client import BinanceMarketClient

# 使用默认配置
client = BinanceMarketClient()

# 自定义配置
client = BinanceMarketClient(
    base_url="https://api.binance.com",
    timeout_seconds=5.0,
    max_retries=3,
    base_delay=0.5,
)

# 即使网络失败，也会返回空列表而不是抛异常
tickers = client.get_tickers()  # 返回 [] 如果连接失败
```

### Freqtrade REST Client

```python
from services.api.app.adapters.freqtrade.rest_client import (
    FreqtradeRestClient,
    FreqtradeRestConfig,
)

# 创建配置
config = FreqtradeRestConfig(
    base_url="http://localhost:8080",
    username="bot",
    password="secret",
    timeout_seconds=10.0,
    max_retries=3,
    base_delay=0.5,
)

# 创建客户端
client = FreqtradeRestClient(config)

# 会自动重试，失败后抛出 FreqtradeRestError
try:
    snapshot = client.get_snapshot()
except FreqtradeRestError as e:
    # 上层服务捕获并返回 200 + unavailable 状态
    print(f"Freqtrade 不可用: {e}")
```

## 指数退避策略

重试延迟计算公式:
```
delay = base_delay * (2 ** attempt)
```

示例（base_delay=0.5）:
- 第 1 次重试: 0.5 秒后
- 第 2 次重试: 1.0 秒后
- 第 3 次重试: 2.0 秒后

总延迟: 0.5 + 1.0 + 2.0 = 3.5 秒

## API 层面的降级

在 routes 层面，已经有异常捕获机制：

**示例** (`services/api/app/routes/positions.py`):
```python
try:
    items = sync_service.list_positions(limit=limit)
    return _success({"items": items}, _build_freqtrade_meta(limit))
except Exception as exc:
    return _success({"items": []}, _build_freqtrade_meta(limit, str(exc)))
```

这确保了即使底层服务失败，API 也会返回 200 状态码，并在 meta 中标记 `status: "unavailable"`。

## 验证方式

### 1. 临时断开网络
```bash
# 设置错误的 Freqtrade URL
export QUANT_FREQTRADE_API_URL=http://127.0.0.1:9999

# 启动 API
python3 -m services.api.app.main

# 访问接口，应返回 200 + unavailable 状态
curl http://localhost:8000/api/positions
```

### 2. 运行测试
```bash
# 运行所有重试和降级测试
python3 -m pytest services/api/tests/ -k "retry or degradation" -v

# 运行所有 binance 和 freqtrade 相关测试
python3 -m pytest services/api/tests/ -k "binance or freqtrade" -v
```

## 性能影响

- **正常情况**: 无额外开销
- **网络抖动**: 最多增加 3.5 秒延迟（3 次重试）
- **服务不可用**: 快速失败并降级，避免长时间阻塞

## 未来改进

1. 添加断路器模式（Circuit Breaker）
2. 添加请求缓存
3. 添加监控和告警
4. 支持自定义重试策略
5. 添加请求去重
