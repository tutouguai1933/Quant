#!/usr/bin/env python3
"""
CCXT Async 代理配置测试脚本

测试 mihomo 代理 (127.0.0.1:7890) 与 Binance API 的连接

用法:
    python test_proxy.py              # 测试默认代理
    python test_proxy.py --no-proxy   # 测试无代理直连
    python test_proxy.py --proxy socks5://127.0.0.1:1080  # 测试指定代理
"""

import asyncio
import argparse
import ccxt.async_support as ccxt
from datetime import datetime


async def test_connection(proxy: str = None, exchange_name: str = "binance"):
    """
    测试交易所连接

    Args:
        proxy: 代理地址，如 "http://127.0.0.1:7890"
        exchange_name: 交易所名称
    """
    print(f"\n{'='*60}")
    print(f"CCXT Async 代理测试")
    print(f"{'='*60}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"交易所: {exchange_name.upper()}")
    print(f"代理: {proxy or '无（直连）'}")
    print(f"{'='*60}\n")

    # 构建配置
    config = {
        'enableRateLimit': True,
    }

    if proxy:
        config['aiohttp_proxy'] = proxy

    # 创建交易所实例
    exchange = getattr(ccxt, exchange_name)(config)

    results = {
        'passed': 0,
        'failed': 0,
        'errors': []
    }

    try:
        # 测试1: 加载市场数据
        print("[1/4] 测试加载市场数据...")
        try:
            markets = await exchange.load_markets()
            print(f"      ✅ 成功 - 获取到 {len(markets)} 个交易对")
            results['passed'] += 1
        except Exception as e:
            print(f"      ❌ 失败 - {type(e).__name__}: {e}")
            results['failed'] += 1
            results['errors'].append(f"load_markets: {e}")

        # 测试2: 获取服务器时间
        print("[2/4] 测试获取服务器时间...")
        try:
            time_result = await exchange.fetch_time()
            server_time = datetime.fromtimestamp(time_result / 1000)
            print(f"      ✅ 成功 - 服务器时间: {server_time}")
            results['passed'] += 1
        except Exception as e:
            print(f"      ❌ 失败 - {type(e).__name__}: {e}")
            results['failed'] += 1
            results['errors'].append(f"fetch_time: {e}")

        # 测试3: 获取 BTC/USDT 行情
        print("[3/4] 测试获取 BTC/USDT 行情...")
        try:
            ticker = await exchange.fetch_ticker('BTC/USDT')
            print(f"      ✅ 成功 - BTC/USDT 价格: ${ticker['last']:,.2f}")
            results['passed'] += 1
        except Exception as e:
            print(f"      ❌ 失败 - {type(e).__name__}: {e}")
            results['failed'] += 1
            results['errors'].append(f"fetch_ticker: {e}")

        # 测试4: 获取 K 线数据
        print("[4/4] 测试获取 BTC/USDT 1小时 K 线...")
        try:
            ohlcv = await exchange.fetch_ohlcv('BTC/USDT', '1h', limit=5)
            print(f"      ✅ 成功 - 获取到 {len(ohlcv)} 根 K 线")
            results['passed'] += 1
        except Exception as e:
            print(f"      ❌ 失败 - {type(e).__name__}: {e}")
            results['failed'] += 1
            results['errors'].append(f"fetch_ohlcv: {e}")

    finally:
        await exchange.close()

    # 打印结果摘要
    print(f"\n{'='*60}")
    print("测试结果摘要")
    print(f"{'='*60}")
    print(f"通过: {results['passed']}/4")
    print(f"失败: {results['failed']}/4")

    if results['errors']:
        print("\n错误详情:")
        for err in results['errors']:
            print(f"  - {err}")

    if results['failed'] == 0:
        print("\n✅ 所有测试通过！代理配置正确。")
        return True
    else:
        print("\n❌ 部分测试失败，请检查代理配置。")
        return False


async def test_env_proxy():
    """测试环境变量代理"""
    import os

    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

    if http_proxy or https_proxy:
        print("\n检测到环境变量代理配置:")
        if http_proxy:
            print(f"  HTTP_PROXY: {http_proxy}")
        if https_proxy:
            print(f"  HTTPS_PROXY: {https_proxy}")
        return True
    return False


async def test_freqtrade_config():
    """测试 Freqtrade 配置文件"""
    import json
    from pathlib import Path

    config_paths = [
        "/home/djy/Quant/infra/freqtrade/user_data/config.proxy.mihomo.json",
        "/home/djy/Quant/infra/freqtrade/user_data/config.private.json",
    ]

    print("\nFreqtrade 代理配置检查:")
    print("-" * 40)

    for path in config_paths:
        p = Path(path)
        if p.exists():
            with open(p) as f:
                config = json.load(f)

            exchange = config.get('exchange', {})
            ccxt_config = exchange.get('ccxt_config', {})
            ccxt_async_config = exchange.get('ccxt_async_config', {})

            # 检查 aiohttp_proxy (正确配置)
            aiohttp_proxy = ccxt_async_config.get('aiohttp_proxy')
            if aiohttp_proxy:
                print(f"✅ {p.name}: aiohttp_proxy = {aiohttp_proxy}")

            # 检查 proxies (错误配置 - sync 格式)
            proxies = ccxt_async_config.get('proxies')
            if proxies:
                print(f"⚠️  {p.name}: 使用了 sync 格式的 proxies 配置")
                print(f"   应改为: 'aiohttp_proxy': 'http://...'")


def main():
    parser = argparse.ArgumentParser(description='测试 CCXT Async 代理配置')
    parser.add_argument('--proxy', '-p', type=str, default=None,
                        help='代理地址，如 http://127.0.0.1:7890')
    parser.add_argument('--no-proxy', '-n', action='store_true',
                        help='不使用代理（直连）')
    parser.add_argument('--exchange', '-e', type=str, default='binance',
                        help='交易所名称（默认: binance）')
    parser.add_argument('--check-config', '-c', action='store_true',
                        help='检查 Freqtrade 配置文件')

    args = parser.parse_args()

    # 检查配置文件
    if args.check_config:
        asyncio.run(test_freqtrade_config())
        return

    # 确定代理
    proxy = None
    if args.no_proxy:
        proxy = None
    elif args.proxy:
        proxy = args.proxy
    else:
        # 默认使用 mihomo 代理
        proxy = "http://127.0.0.1:7890"

    # 运行测试
    success = asyncio.run(test_connection(proxy, args.exchange))

    # 如果使用代理失败，提示尝试无代理
    if not success and proxy:
        print("\n💡 提示: 如果在中国大陆，可能需要代理访问 Binance")
        print("   请检查代理是否正常运行: curl -x http://127.0.0.1:7890 https://api.binance.com/api/v3/ping")

    return 0 if success else 1


if __name__ == '__main__':
    exit(main())