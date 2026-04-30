# CCXT Async 代理配置方案研究

> 研究日期：2026-04-30
> 目的：解决 Freqtrade Live 模式下的代理连接问题

---

## 1. 问题分析

### 1.1 当前状态
- **环境**：mihomo 代理 `127.0.0.1:7890`（日本节点）
- **Freqtrade 模式**：`dry_run=true` 正常运行
- **Live 模式问题**：ccxt async 需要正确配置代理

### 1.2 核心问题

**Sync vs Async 代理配置差异**：

| 版本 | 配置键 | 后端库 | 格式 |
|------|--------|--------|------|
| Sync | `proxies` | requests | 字典 |
| Async | `aiohttp_proxy` | aiohttp | 字符串 |

**当前错误配置**（`config.private.json`）：
```json
{
  "exchange": {
    "ccxt_config": {
      "proxies": {                          // ❌ 这是 sync 版本格式
        "http": "http://172.21.0.1:7890",
        "https": "http://172.21.0.1:7890"
      }
    },
    "ccxt_async_config": {
      "proxies": {                          // ❌ async 不支持这种格式
        "http": "http://172.21.0.1:7890",
        "https": "http://172.21.0.1:7890"
      }
    }
  }
}
```

**正确配置**（`config.proxy.mihomo.json`）：
```json
{
  "exchange": {
    "ccxt_config": {
      "aiohttp_proxy": "http://127.0.0.1:7890"    // ✅ 字符串格式
    },
    "ccxt_async_config": {
      "aiohttp_proxy": "http://127.0.0.1:7890"    // ✅ 字符串格式
    }
  }
}
```

---

## 2. CCXT Async 代理配置详解

### 2.1 三种配置方式

#### 方式一：构造函数配置（推荐）
```python
import ccxt.async_support as ccxt

# HTTP 代理
exchange = ccxt.binance({
    'aiohttp_proxy': 'http://user:pass@proxy.com:8080'
})

# SOCKS5 代理（需要安装 aiohttp-socks）
exchange = ccxt.binance({
    'aiohttp_proxy': 'socks5://user:pass@proxy.com:1080'
})
```

#### 方式二：运行时配置
```python
exchange = ccxt.binance()
exchange.options['aiohttp_proxy'] = 'http://127.0.0.1:7890'
```

#### 方式三：环境变量
```bash
export HTTP_PROXY="http://proxy.com:8080"
export HTTPS_PROXY="http://proxy.com:8080"
export ALL_PROXY="http://proxy.com:8080"
```

### 2.2 Freqtrade 配置方式

Freqtrade 通过 JSON 配置文件传递 ccxt 参数：

```json
{
  "exchange": {
    "name": "binance",
    "key": "your-api-key",
    "secret": "your-api-secret",
    "ccxt_config": {
      "enableRateLimit": true,
      "aiohttp_proxy": "http://127.0.0.1:7890"
    },
    "ccxt_async_config": {
      "enableRateLimit": true,
      "rateLimit": 200,
      "aiohttp_proxy": "http://127.0.0.1:7890"
    }
  }
}
```

---

## 3. 推荐配置方案

### 3.1 方案概述

使用**配置文件分层** + **环境变量**双重保障：

| 配置文件 | 用途 | 代理配置 |
|----------|------|----------|
| `config.base.json` | 基础配置 | 无代理 |
| `config.private.json` | API密钥 | 无代理 |
| `config.proxy.mihomo.json` | 代理配置 | `aiohttp_proxy` |
| 环境变量 | Docker注入 | `HTTP_PROXY` |

### 3.2 配置文件修改

#### 3.2.1 修复 `config.private.json`

**修改前**：
```json
{
  "exchange": {
    "key": "...",
    "secret": "...",
    "ccxt_config": {
      "proxies": {
        "http": "http://172.21.0.1:7890",
        "https": "http://172.21.0.1:7890"
      }
    },
    "ccxt_async_config": {
      "proxies": {
        "http": "http://172.21.0.1:7890",
        "https": "http://172.21.0.1:7890"
      }
    }
  }
}
```

**修改后**：
```json
{
  "exchange": {
    "key": "...",
    "secret": "..."
  },
  "api_server": {
    "username": "Freqtrader",
    "password": "jianyu0.0.",
    "jwt_secret_key": "...",
    "ws_token": "..."
  }
}
```

**说明**：代理配置移到单独的 `config.proxy.mihomo.json` 文件

#### 3.2.2 确认 `config.proxy.mihomo.json`

```json
{
  "exchange": {
    "ccxt_config": {
      "aiohttp_proxy": "http://127.0.0.1:7890"
    },
    "ccxt_async_config": {
      "aiohttp_proxy": "http://127.0.0.1:7890"
    }
  }
}
```

**说明**：
- Freqtrade 使用 `network_mode: host`，可直接访问 `127.0.0.1:7890`
- 同时配置 `ccxt_config` 和 `ccxt_async_config` 以覆盖所有场景

### 3.3 环境变量配置

`docker-compose.yml` 已配置：
```yaml
environment:
  HTTP_PROXY: ${QUANT_PROXY_HTTP:-}
  HTTPS_PROXY: ${QUANT_PROXY_HTTP:-}
  ALL_PROXY: ${QUANT_PROXY_SOCKS:-}
```

建议在 `.env` 中添加：
```bash
QUANT_PROXY_HTTP=http://127.0.0.1:7890
```

---

## 4. SOCKS5 代理支持（可选）

### 4.1 安装依赖

```bash
pip install aiohttp-socks
```

### 4.2 配置方式

```json
{
  "exchange": {
    "ccxt_async_config": {
      "aiohttp_proxy": "socks5://127.0.0.1:1080"
    }
  }
}
```

**注意**：当前 mihomo 是 HTTP 代理，不需要 SOCKS5

---

## 5. 验证测试步骤

### 5.1 本地 Python 测试

```python
#!/usr/bin/env python3
"""测试 CCXT Async 代理配置"""
import asyncio
import ccxt.async_support as ccxt

async def test_proxy():
    exchange = ccxt.binance({
        'aiohttp_proxy': 'http://127.0.0.1:7890',
        'enableRateLimit': True,
    })

    try:
        # 测试连接
        markets = await exchange.load_markets()
        print(f"✅ 连接成功！获取到 {len(markets)} 个交易对")

        # 测试 ticker
        ticker = await exchange.fetch_ticker('BTC/USDT')
        print(f"✅ BTC/USDT 价格: {ticker['last']}")

    except Exception as e:
        print(f"❌ 连接失败: {e}")
    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(test_proxy())
```

### 5.2 Freqtrade Dry-run 测试

```bash
# 启动 dry-run 模式测试
cd /home/djy/Quant/infra/freqtrade
docker compose up -d

# 查看日志
docker logs -f quant-freqtrade
```

### 5.3 Live 模式测试

```bash
# 修改配置为 live 模式
# 确保 config.proxy.mihomo.json 被加载

# 检查当前代理配置
docker exec quant-freqtrade cat /freqtrade/user_data/config.proxy.mihomo.json

# 测试 API 连接
docker exec quant-freqtrade freqtrade test-pairlist -c /freqtrade/user_data/config.base.json
```

---

## 6. 常见问题排查

### 6.1 连接超时

**症状**：
```
ccxt.NetworkError: binance {}
```

**排查步骤**：
1. 检查代理是否运行：`curl -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping`
2. 检查配置是否加载：查看 Freqtrade 启动日志
3. 检查环境变量：`docker exec quant-freqtrade env | grep -i proxy`

### 6.2 代理认证失败

**症状**：
```
aiohttp.client_exceptions.ClientHttpProxyError: 407 Proxy Authentication Required
```

**解决方案**：
```json
{
  "aiohttp_proxy": "http://user:password@127.0.0.1:7890"
}
```

### 6.3 SSL 证书错误

**症状**：
```
ssl.SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**解决方案**：
```python
# 在 ccxt_config 中添加
{
  "aiohttp_proxy": "http://127.0.0.1:7890",
  "verify": True  # 或 False 跳过验证（不推荐生产环境）
}
```

---

## 7. 配置优先级

Freqtrade 加载顺序（后加载覆盖前加载）：
1. `config.base.json` - 基础配置
2. `config.private.json` - API 密钥
3. `config.proxy.mihomo.json` - 代理配置

**最终生效配置**：合并上述所有配置

---

## 8. 总结

### 8.1 关键修改点

1. **`config.private.json`**：移除错误的 `proxies` 配置
2. **`config.proxy.mihomo.json`**：确保使用 `aiohttp_proxy` 字符串格式
3. **环境变量**：可选，作为备用方案

### 8.2 验证清单

- [ ] mihomo 代理正常运行 (`127.0.0.1:7890`)
- [ ] 本地 Python 脚本测试通过
- [ ] Freqtrade dry-run 模式正常
- [ ] Binance API 可通过代理访问
- [ ] Live 模式启动测试

### 8.3 参考资料

- [CCXT 官方文档 - Proxy Support](https://docs.ccxt.com/#/README?id=proxy-support)
- [CCXT GitHub - Async Configuration](https://github.com/ccxt/ccxt)
- [Freqtrade 配置文档](https://www.freqtrade.io/en/stable/configuration/)