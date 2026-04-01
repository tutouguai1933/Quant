"""Freqtrade 运行状态服务。

这个文件负责把运行模式、后端类型和连接状态整理成统一视图。
"""

from __future__ import annotations

from services.api.app.adapters.freqtrade.client import freqtrade_client


class FreqtradeRuntimeService:
    """收敛 Freqtrade 运行时状态。"""

    def get_runtime_snapshot(self) -> dict[str, object]:
        """返回最小运行摘要。"""

        return dict(freqtrade_client.get_runtime_snapshot())


freqtrade_runtime_service = FreqtradeRuntimeService()
