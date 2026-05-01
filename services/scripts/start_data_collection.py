"""AI训练数据采集启动脚本。

定时采集 BTC/USDT 和 ETH/USDT 的市场数据和技术指标，
收集样本用于AI策略训练。

使用方式:
    python services/scripts/start_data_collection.py

停止方式:
    Ctrl+C 或 kill <pid>
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Event

# 添加项目根目录到路径
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    import schedule
except ImportError:
    # 如果没有 schedule 库，使用 threading.Timer 替代
    schedule = None

from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.services.indicator_service import (
    calculate_rsi,
    calculate_macd,
    _ema,
)
from services.api.app.services.ai.training_data_service import training_data_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# 采集配置
COLLECTION_INTERVAL_MINUTES = 5
SYMBOLS = ["BTC/USDT", "ETH/USDT"]
KLINE_INTERVAL = "4h"
KLINE_LIMIT = 100  # 用于计算指标的历史K线数量

# 停止信号
stop_event = Event()


def signal_handler(signum, frame):
    """处理停止信号。"""
    logger.info("收到停止信号，正在退出...")
    stop_event.set()


def get_market_data(symbol: str, client: BinanceMarketClient) -> dict:
    """获取市场数据和技术指标。

    Args:
        symbol: 交易标的符号（如 BTC/USDT）
        client: Binance 市场数据客户端

    Returns:
        包含K线数据和指标的字典
    """
    # 转换符号格式（BTC/USDT -> BTCUSDT）
    binance_symbol = symbol.replace("/", "").upper()

    # 获取K线数据
    rows = client.get_klines(
        symbol=binance_symbol,
        interval=KLINE_INTERVAL,
        limit=KLINE_LIMIT,
    )

    if not rows:
        logger.warning(f"无法获取 {symbol} 的K线数据")
        return {"symbol": symbol, "candles": [], "indicators": {}}

    # 标准化K线数据（数值类型，不是字符串）
    candles = []
    for row in rows:
        try:
            if len(row) < 7:
                continue
            candles.append({
                "open_time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "close_time": int(row[6]),
            })
        except (TypeError, ValueError, IndexError):
            continue

    if not candles:
        logger.warning(f"{symbol} K线数据标准化失败")
        return {"symbol": symbol, "candles": [], "indicators": {}}

    # 计算技术指标
    closes = [Decimal(c["close"]) for c in candles]
    volumes = [Decimal(c["volume"]) for c in candles]

    # RSI
    rsi_value = calculate_rsi(closes, period=14)

    # MACD (服务期望格式: macd.signal)
    macd_result = calculate_macd(closes)
    macd_signal_value = macd_result.get("signal_line") or Decimal(0)
    macd_data = {
        "signal": float(macd_signal_value),  # 服务期望的格式
        "macd_line": float(macd_result.get("macd_line") or Decimal(0)),
        "histogram": float(macd_result.get("histogram") or Decimal(0)),
        "trend": str(macd_result.get("trend") or "neutral"),
    }

    # EMA 距离 (用于 ma_distance)
    ema_fast = _ema(closes, 20)
    ema_slow = _ema(closes, 55)
    ma_distance = float((ema_fast - ema_slow) / ema_slow) if ema_slow != 0 else 0.0

    # 指标结构符合服务期望格式
    indicators = {
        "rsi": float(rsi_value),
        "macd": macd_data,  # 包含 signal 字段
        "bb_position": _calculate_bb_position(candles),
        "ma_distance": ma_distance,
    }

    logger.info(
        f"{symbol} 数据采集完成: "
        f"RSI={float(rsi_value):.2f}, "
        f"MACD趋势={macd_data['trend']}, "
        f"K线数量={len(candles)}"
    )

    return {
        "symbol": symbol,
        "candles": candles,
        "indicators": indicators,
    }


def _calculate_true_ranges(candles: list[dict]) -> list[Decimal]:
    """计算真实波幅序列。"""
    ranges = []
    prev_close = None
    for c in candles:
        high = Decimal(c["high"])
        low = Decimal(c["low"])
        close = Decimal(c["close"])
        current_range = high - low
        if prev_close is not None:
            current_range = max(
                current_range,
                abs(high - prev_close),
                abs(low - prev_close),
            )
        ranges.append(current_range)
        prev_close = close
    return ranges


def _calculate_bb_position(candles: list[dict]) -> float:
    """计算布林带位置（价格相对于中轨的位置）。"""
    if len(candles) < 20:
        return 0.5

    closes = [Decimal(c["close"]) for c in candles[-20:]]
    # 计算SMA
    sma = sum(closes) / Decimal(len(closes))
    current_close = closes[-1]

    # 计算标准差
    variance = sum((c - sma) ** 2 for c in closes) / Decimal(len(closes))
    std = variance.sqrt() if variance > 0 else Decimal(0)

    # 计算BB位置
    if std > 0:
        upper = sma + 2 * std
        lower = sma - 2 * std
        position = (current_close - lower) / (upper - lower)
        return float(position)
    return 0.5


def collect_sample(symbol: str, client: BinanceMarketClient) -> bool:
    """采集单个样本。

    Args:
        symbol: 交易标的符号
        client: 市场数据客户端

    Returns:
        是否成功采集
    """
    try:
        data = get_market_data(symbol, client)

        if not data["candles"]:
            return False

        # 直接调用训练数据服务
        sample = training_data_service.collect_sample(
            symbol=symbol,
            candles=data["candles"],
            indicators=data["indicators"],
            position_info=None,  # 暂无持仓信息
            source_strategy="data_collector",
        )

        total_samples = training_data_service.get_sample_count()
        symbol_samples = training_data_service.get_sample_count(symbol.upper().replace("/", ""))

        logger.info(
            f"样本采集成功: {symbol} "
            f"时间={sample.timestamp.isoformat()}, "
            f"本币种样本={symbol_samples}, "
            f"总样本={total_samples}"
        )

        return True

    except Exception as e:
        logger.error(f"样本采集失败: {symbol} - {e}")
        return False


def collect_all_symbols():
    """采集所有配置的币种。"""
    logger.info(f"开始采集任务: {SYMBOLS}")

    client = BinanceMarketClient()

    success_count = 0
    fail_count = 0

    for symbol in SYMBOLS:
        if stop_event.is_set():
            break

        if collect_sample(symbol, client):
            success_count += 1
        else:
            fail_count += 1

    # 记录统计
    stats = training_data_service.get_statistics()
    logger.info(
        f"采集任务完成: 成功={success_count}, 失败={fail_count}, "
        f"总样本={stats['total_samples']}"
    )

    # 保存采集日志
    save_collection_log(success_count, fail_count, stats)


def save_collection_log(success: int, fail: int, stats: dict):
    """保存采集日志到文件。"""
    log_dir = REPO_ROOT / "services" / "data" / "collection_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "collection_history.json"

    # 读取历史日志
    history = []
    if log_file.exists():
        try:
            with open(log_file, "r") as f:
                history = json.load(f)
        except (json.JSONDecodeError, IOError):
            history = []

    # 添加新记录
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "success_count": success,
        "fail_count": fail,
        "total_samples": stats["total_samples"],
        "symbols": stats["symbols"],
    }
    history.append(record)

    # 保存日志（保留最近1000条）
    if len(history) > 1000:
        history = history[-1000:]

    try:
        with open(log_file, "w") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"保存采集日志失败: {e}")


def run_with_schedule():
    """使用 schedule 库运行定时任务。"""
    logger.info(f"使用 schedule 库，采集间隔: {COLLECTION_INTERVAL_MINUTES} 分钟")

    # 立即执行一次
    collect_all_symbols()

    # 设置定时任务
    schedule.every(COLLECTION_INTERVAL_MINUTES).minutes.do(collect_all_symbols)

    # 运行循环
    while not stop_event.is_set():
        schedule.run_pending()
        time.sleep(1)


def run_with_timer():
    """使用 threading.Timer 运行定时任务（无 schedule 库时）。"""
    logger.info(f"使用 threading.Timer，采集间隔: {COLLECTION_INTERVAL_MINUTES} 分钟")

    def timer_callback():
        if stop_event.is_set():
            return

        collect_all_symbols()

        # 设置下一次定时器
        if not stop_event.is_set():
            timer = threading.Timer(
                COLLECTION_INTERVAL_MINUTES * 60,
                timer_callback,
            )
            timer.daemon = True
            timer.start()

    import threading

    # 立即执行一次
    collect_all_symbols()

    # 启动定时器
    if not stop_event.is_set():
        timer = threading.Timer(
            COLLECTION_INTERVAL_MINUTES * 60,
            timer_callback,
        )
        timer.daemon = True
        timer.start()

        # 保持主线程运行
        while not stop_event.is_set():
            time.sleep(1)


def main():
    """主入口。"""
    logger.info("=" * 50)
    logger.info("AI训练数据采集服务启动")
    logger.info(f"采集币种: {SYMBOLS}")
    logger.info(f"K线周期: {KLINE_INTERVAL}")
    logger.info(f"采集间隔: {COLLECTION_INTERVAL_MINUTES} 分钟")
    logger.info("=" * 50)

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 选择调度方式
    if schedule is not None:
        run_with_schedule()
    else:
        run_with_timer()

    logger.info("AI训练数据采集服务已停止")

    # 打印最终统计
    stats = training_data_service.get_statistics()
    logger.info(f"最终统计: 总样本={stats['total_samples']}, 币种={stats['symbols']}")


if __name__ == "__main__":
    main()