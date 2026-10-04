"""汇总完整现货与U本位合约权益，供余额页面使用；不改变交易策略。"""
from __future__ import annotations

import copy
import logging
import os
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal

from services.api.app.adapters.binance.account_client import binance_account_client
from services.api.app.adapters.binance.market_client import BinanceMarketClient
from services.api.app.core.settings import DEFAULT_BALANCE_EQUITY_CACHE_SECONDS

logger = logging.getLogger(__name__)


def _number(value) -> Decimal:
    """拒绝缺失和非有限金额，防止未知账户被估作零。"""
    if value is None or value == "":
        raise ValueError("金额字段缺失")
    amount = Decimal(str(value))
    if not amount.is_finite():
        raise ValueError("金额字段无效")
    return amount


def _text(value: Decimal) -> str:
    """不经浮点舍入返回金额。"""
    return format(value, "f")


class BalanceEquityService:
    """仅保存一个短期账户快照，并合并并发刷新。"""

    def __init__(self, account_client=None, market_client=None, cache_seconds=None):
        """注入只读客户端及缓存时间，便于验证异常和余额换算。"""
        self._account = account_client or binance_account_client
        self._market = market_client or BinanceMarketClient()
        self._ttl = float(cache_seconds if cache_seconds is not None else os.getenv("QUANT_BALANCE_EQUITY_CACHE_SECONDS", DEFAULT_BALANCE_EQUITY_CACHE_SECONDS))
        if not 0 <= self._ttl <= 60:
            raise ValueError("账户权益缓存时间应介于0和60秒")
        self._lock = threading.Lock()
        self._cache = None
        self._expires = 0.0

    def get_summary(self):
        """返回完整权益；已有刷新在途时不创建更多外部请求。"""
        if self._cache is not None and time.monotonic() < self._expires:
            return copy.deepcopy(self._cache)
        if not self._lock.acquire(timeout=1):
            return {"status": "unavailable", "total_equity": None, "spot_equity": None,
                    "futures_equity": None, "assets": [], "issues": ["账户权益正在刷新，请稍后重试"],
                    "scope": "现货 + U本位合约"}
        try:
            if self._cache is not None and time.monotonic() < self._expires:
                return copy.deepcopy(self._cache)
            snapshot = self._read_summary()
            self._cache = snapshot
            self._expires = time.monotonic() + self._ttl
            return copy.deepcopy(snapshot)
        finally:
            self._lock.release()

    def _read_summary(self):
        """独立读取两类账户，任一缺失时不返回误导性的总额。"""
        issues, assets = [], []
        spot, futures, unrealized = None, None, None
        try:
            account = self._account.get_spot_account()
            if not isinstance(account.get("balances"), list):
                raise ValueError("现货账户响应不完整")
            for row in account["balances"]:
                free, locked = _number(row.get("free")), _number(row.get("locked"))
                quantity = free + locked
                if quantity > 0:
                    asset = str(row.get("asset") or "").upper()
                    if not asset:
                        raise ValueError("现货资产名称缺失")
                    assets.append({"asset": asset, "available": _text(free), "locked": _text(locked),
                                   "price_usdt": None, "equity_usdt": None})
            prices = {}
            if any(row["asset"] != "USDT" for row in assets):
                for row in self._market.get_prices():
                    price = _number(row.get("price"))
                    if price > 0:
                        prices[str(row.get("symbol"))] = price
            spot = Decimal("0")
            for row in assets:
                price = Decimal("1") if row["asset"] == "USDT" else prices.get(row["asset"] + "USDT")
                if price is None:
                    issues.append(f'{row["asset"]}缺少现价，现货总额暂不可用')
                    continue
                value = (_number(row["available"]) + _number(row["locked"])) * price
                row.update(price_usdt=_text(price), equity_usdt=_text(value))
                spot += value
            if issues:
                spot = None
        except Exception as exc:
            spot = None
            issues.append("现货余额或价格读取失败，无法计算完整现货权益")
            logger.warning("账户现货权益读取失败：%s", type(exc).__name__)
        try:
            account = self._account.get_futures_account()
            # 合约保证金权益已经包含浮盈，不能在合计时再次加入。
            futures = _number(account.get("totalMarginBalance"))
            unrealized = _number(account.get("totalUnrealizedProfit"))
        except Exception as exc:
            futures = None
            issues.append("合约账户读取失败，请检查网络和读取权限")
            logger.warning("账户合约权益读取失败：%s", type(exc).__name__)
        total = spot + futures if spot is not None and futures is not None else None
        return {"status": "available" if total is not None else "unavailable",
                "total_equity": _text(total) if total is not None else None,
                "spot_equity": _text(spot) if spot is not None else None,
                "futures_equity": _text(futures) if futures is not None else None,
                "futures_unrealized_pnl": _text(unrealized) if unrealized is not None else None,
                "assets": assets, "issues": issues, "scope": "现货 + U本位合约",
                "generated_at": datetime.now(timezone.utc).isoformat()}


balance_equity_service = BalanceEquityService()
