"""VPN 故障切换控制器。

集成 NodeRegistry、NodeHealthProbe、PrimaryBackupPolicy，
提供统一的故障切换与回切逻辑。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from services.api.app.services.vpn_failover_policy import (
    FailoverEvent,
    PrimaryBackupPolicy,
)
from services.api.app.services.vpn_health_probe import NodeHealthProbe
from services.api.app.services.vpn_node_registry import NodeRegistry

logger = logging.getLogger(__name__)

# 默认配置
DEFAULT_FAIL_THRESHOLD = 3
DEFAULT_RECOVER_THRESHOLD = 3
DEFAULT_OBSERVE_SECONDS = 300
DEFAULT_STATE_PATH = Path(".runtime/vpn_nodes.json")
DEFAULT_EVENTS_PATH = Path(".runtime/vpn_failover_events.jsonl")


class VPNFailoverController:
    """VPN 故障切换控制器。

    集成注册表、探针和策略，提供统一的切换决策。
    """

    def __init__(
        self,
        primary: str,
        backups: list[str],
        whitelisted_ips: set[str],
        proxy_url: str = "http://127.0.0.1:7890",
        health_check_url: str = "https://api.binance.com/api/v3/ping",
        ip_check_url: str = "https://api.ipify.org?format=json",
        fail_threshold: int = DEFAULT_FAIL_THRESHOLD,
        recover_threshold: int = DEFAULT_RECOVER_THRESHOLD,
        observe_seconds: int = DEFAULT_OBSERVE_SECONDS,
        state_path: Path | None = None,
        events_path: Path | None = None,
        mihomo_api_url: str = "http://127.0.0.1:9090",
        signed_check_url: str = "https://api.binance.com/api/v3/account",
        binance_api_key: str | None = None,
        binance_api_secret: str | None = None,
        probe_cache_ttl: float = 30.0,
        signed_probe_interval: float = 60.0,
    ) -> None:
        """初始化控制器。

        Args:
            primary: 主节点名称
            backups: 备选节点名称列表
            whitelisted_ips: 白名单 IP 集合
            proxy_url: mihomo 代理地址
            health_check_url: Binance 健康检查 URL
            ip_check_url: 出口 IP 检测 URL
            fail_threshold: 连续失败阈值
            recover_threshold: 连续成功阈值
            observe_seconds: 观察期秒数
            state_path: 状态持久化路径
            events_path: 事件记录路径
            mihomo_api_url: mihomo controller 地址
            signed_check_url: 签名实测接口 URL
            binance_api_key: Binance API key（签名实测）
            binance_api_secret: Binance API secret（签名实测）
            probe_cache_ttl: 探测缓存有效期（秒）
            signed_probe_interval: 签名实测最小间隔（秒）
        """
        self._registry = NodeRegistry(
            primary=primary,
            backups=backups,
            whitelisted_ips=whitelisted_ips,
        )
        self._probe = NodeHealthProbe(
            proxy_url=proxy_url,
            health_check_url=health_check_url,
            ip_check_url=ip_check_url,
            whitelisted_ips=whitelisted_ips,
            mihomo_api_url=mihomo_api_url,
            cache_ttl_s=probe_cache_ttl,
            signed_check_url=signed_check_url,
            binance_api_key=binance_api_key,
            binance_api_secret=binance_api_secret,
        )
        self._signed_probe_interval = signed_probe_interval
        self._policy = PrimaryBackupPolicy(
            fail_threshold=fail_threshold,
            recover_threshold=recover_threshold,
            observe_seconds=observe_seconds,
        )
        self._state_path = state_path or DEFAULT_STATE_PATH
        self._events_path = events_path or DEFAULT_EVENTS_PATH
        self._primary = primary
        self._enabled = bool(primary and backups)

        # 启动时恢复状态
        if self._enabled:
            self._registry.load_state(self._state_path)

    @property
    def enabled(self) -> bool:
        """是否启用主备策略。"""
        return self._enabled

    @property
    def registry(self) -> NodeRegistry:
        """返回节点注册表。"""
        return self._registry

    @property
    def probe(self) -> NodeHealthProbe:
        """返回健康探针。"""
        return self._probe

    @property
    def policy(self) -> PrimaryBackupPolicy:
        """返回切换策略。"""
        return self._policy

    @property
    def primary_name(self) -> str:
        """返回主节点名称。"""
        return self._primary

    def check_primary(self) -> dict[str, Any]:
        """探测主节点并驱动故障切换/回切决策。

        除 mihomo delay 探测外，叠加签名接口实测（验证当前出口 IP 是否在
        Binance 白名单）。签名实测失败说明当前出口对签名接口不可用，
        视为主节点故障，尽快切换。

        Returns:
            检查结果字典
        """
        if not self._enabled:
            return {"action": "disabled", "message": "主备策略未配置"}

        # 探测主节点（mihomo delay）
        result = self._probe.check_with_interval(self._primary)
        primary_ok = result.ok

        # 签名接口实测（当前出口）：失败则主节点判为不健康
        signed_result = self._probe.check_signed_exit(
            min_interval_s=self._signed_probe_interval,
        )
        if not signed_result.ok:
            logger.warning(
                "签名接口实测失败（当前出口）: %s，主节点视为不健康",
                signed_result.error,
            )
            primary_ok = False

        self._policy.record_probe(self._primary, primary_ok)

        # 更新注册表
        self._registry.mark_probe(self._primary, primary_ok, result.ip)
        self._registry.save_state(self._state_path)

        if not primary_ok:
            # 主节点不健康，检查是否需要故障切换
            if self._policy.should_failover(self._primary):
                logger.warning(
                    "主节点 %s 连续失败 %d 次，触发故障切换",
                    self._primary,
                    self._policy.fail_threshold,
                )
                return self.failover(from_node=self._primary)

            return {
                "action": "probing",
                "node": self._primary,
                "ok": False,
                "signed_ok": signed_result.ok,
                "message": f"主节点探测失败({result.error or signed_result.error})，等待更多失败确认",
            }

        # 主节点健康
        # 检查是否需要回切
        if self._policy.current_backup is not None:
            if self._policy.should_failback(self._primary):
                logger.info(
                    "主节点 %s 已恢复，触发回切",
                    self._primary,
                )
                back_result = self._switch_back(from_backup=self._policy.current_backup)
                if back_result:
                    self._policy.mark_switched()
                    self._policy.current_backup = None
                    return {
                        "action": "failback",
                        "to": self._primary,
                        "from": self._policy.current_backup,
                        "success": True,
                        "message": f"回切到主节点 {self._primary}",
                    }
            else:
                return {
                    "action": "observing",
                    "node": self._policy.current_backup,
                    "primary_ok": True,
                    "message": "主节点已恢复，等待更多成功确认或观察期结束",
                }

        return {
            "action": "healthy",
            "node": self._primary,
            "ok": True,
            "signed_ok": signed_result.ok,
            "ip": result.ip,
            "message": "主节点健康",
        }

    def failover(self, from_node: str) -> dict[str, Any]:
        """从主节点故障切换，自动找到白名单内第一个健康备选。

        按优先级依次尝试备选：delay 探测健康 → 实际切换 → 出口 IP 在白名单
        才算成功；任一环节不过则试下一个。全部失败返回 failover_failed，
        由上层触发告警（提示用户配新 IP）。

        Args:
            from_node: 切换前节点

        Returns:
            切换结果字典（action=failover / failover_failed）
        """
        from services.api.app.services.vpn_switch_service import vpn_switch_service

        candidates = self._registry.candidates()
        if not candidates:
            logger.error("没有可用的备选节点")
            return {
                "action": "failover_failed",
                "from": from_node,
                "success": False,
                "message": "故障切换失败，所有备选节点不可用",
            }

        for candidate in candidates:
            probe_result = self._probe.check_with_interval(candidate.name)
            if not probe_result.ok:
                logger.warning(
                    "备选节点 %s 探测失败: %s，尝试下一个",
                    candidate.name,
                    probe_result.error,
                )
                continue

            switch_result = vpn_switch_service.switch_node_sync(candidate.name)
            if switch_result.success and switch_result.is_whitelisted:
                # 切换后签名复验：确认新出口对签名接口真实可用
                signed_after = self._probe.check_signed_exit(
                    min_interval_s=0.0,
                    force=True,
                )
                if not signed_after.ok:
                    logger.warning(
                        "备选节点 %s 切换后签名实测失败: %s，尝试下一个",
                        candidate.name,
                        signed_after.error,
                    )
                    event = self._policy.record_event(
                        from_node=from_node,
                        to_node=candidate.name,
                        reason=f"切换后签名实测失败: {signed_after.error}",
                        success=False,
                    )
                    self._write_event(event)
                    continue

                self._policy.mark_switched()
                self._policy.current_backup = candidate.name
                event = self._policy.record_event(
                    from_node=from_node,
                    to_node=candidate.name,
                    reason=f"主节点 {from_node} 连续失败",
                    success=True,
                )
                self._write_event(event)
                logger.info(
                    "VPN 故障切换到 %s（出口 %s，白名单通过，签名实测通过）",
                    candidate.name,
                    switch_result.exit_ip,
                )
                # 切换成功后恢复 freqtrade（方案 B）
                self._recover_freqtrade()
                return {
                    "action": "failover",
                    "from": from_node,
                    "to": candidate.name,
                    "success": True,
                    "exit_ip": switch_result.exit_ip,
                    "is_whitelisted": True,
                    "message": f"故障切换到备选节点 {candidate.name}",
                }

            logger.warning(
                "备选节点 %s 切换成功但出口 IP %s 不在白名单，尝试下一个",
                candidate.name,
                switch_result.exit_ip,
            )
            event = self._policy.record_event(
                from_node=from_node,
                to_node=candidate.name,
                reason=f"出口 IP {switch_result.exit_ip} 不在白名单",
                success=False,
            )
            self._write_event(event)

        event = self._policy.record_event(
            from_node=from_node,
            to_node="",
            reason=f"主节点 {from_node} 故障切换失败，所有备选不可用或不在白名单",
            success=False,
        )
        self._write_event(event)
        return {
            "action": "failover_failed",
            "from": from_node,
            "success": False,
            "message": "故障切换失败，所有备选节点不可用或不在白名单",
        }

    def _switch_back(self, from_backup: str) -> bool:
        """记录回切事件。

        Args:
            from_backup: 当前备选节点

        Returns:
            True
        """
        event = self._policy.record_event(
            from_node=from_backup,
            to_node=self._primary,
            reason=f"主节点 {self._primary} 已恢复",
            success=True,
        )
        self._write_event(event)
        # 回切后也恢复 freqtrade（重新加载配置、解除可能的 PAUSED）
        self._recover_freqtrade()
        return True

    def _recover_freqtrade(self) -> None:
        """切换节点后触发 freqtrade 重载配置，解除可能的 PAUSED 状态。

        freqtrade 在 reload_markets 连续失败后自动暂停（PAUSED），自身重试
        周期约 1 小时。代理已切换后主动触发 reload_config 可立即重连，
        无需干等下一个重试周期。
        """
        try:
            from services.api.app.adapters.freqtrade.client import FreqtradeClient
            from services.api.app.core.settings import Settings

            client = FreqtradeClient(Settings.from_env())
            if not getattr(client, "_backend", None):
                return
            if not Settings.from_env().should_use_freqtrade_rest():
                logger.info("freqtrade 未配置 REST，跳过 reload_config")
                return
            result = client._backend.reload_config()
            logger.info("freqtrade reload_config 已触发: %s", result)
        except Exception as e:
            logger.warning("恢复 freqtrade 失败（不影响切换本身）: %s", e)

    def _write_event(self, event: FailoverEvent) -> None:
        """将切换事件写入 JSONL 文件。

        Args:
            event: 切换事件
        """
        try:
            self._events_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._events_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
            logger.info(
                "VPN 切换事件已记录: %s -> %s (success=%s)",
                event.from_node,
                event.to_node,
                event.success,
            )
        except (OSError, IOError) as e:
            logger.warning("写入切换事件失败: %s", e)

    def get_status(self) -> dict[str, Any]:
        """获取当前状态摘要。"""
        return {
            "enabled": self._enabled,
            "primary": self._primary,
            "current_backup": self._policy.current_backup,
            "in_observation": self._policy.in_observation(
                self._policy.switched_at or 0
            ),
            "switched_at": self._policy.switched_at,
            "events_count": len(self._policy.get_events()),
        }


# 全局单例（延迟初始化）
_failover_controller: VPNFailoverController | None = None


def get_failover_controller() -> VPNFailoverController | None:
    """获取全局故障切换控制器。

    通过环境变量 QUANT_VPN_PRIMARY_NODE 判断是否启用。
    配置完整（有主节点+备选+白名单）时启用。
    """
    global _failover_controller
    if _failover_controller is not None:
        return _failover_controller

    primary = os.getenv("QUANT_VPN_PRIMARY_NODE", "").strip()
    raw_backups = os.getenv("QUANT_VPN_BACKUP_NODES", "")
    raw_ips = os.getenv("QUANT_VPN_WHITELISTED_IPS", "")

    backups = [n.strip() for n in raw_backups.split(",") if n.strip()]
    whitelisted_ips = {ip.strip() for ip in raw_ips.split(",") if ip.strip()}

    if not primary or not backups:
        logger.info("VPN 主备策略未配置（缺少 QUANT_VPN_PRIMARY_NODE 或 QUANT_VPN_BACKUP_NODES），将使用默认自动切换逻辑")
        return None

    proxy_url = os.getenv("QUANT_MIHOMO_PROXY_URL", "http://127.0.0.1:7890")
    health_check_url = os.getenv("QUANT_VPN_HEALTH_CHECK_URL", "https://api.binance.com/api/v3/ping")
    ip_check_url = os.getenv("QUANT_VPN_IP_CHECK_URL", "https://api.ipify.org?format=json")
    mihomo_api_url = os.getenv("QUANT_MIHOMO_API_URL", "http://127.0.0.1:9090")
    signed_check_url = os.getenv(
        "QUANT_VPN_SIGNED_CHECK_URL",
        "https://api.binance.com/api/v3/account",
    )
    binance_api_key = os.getenv("BINANCE_API_KEY", "").strip()
    binance_api_secret = os.getenv("BINANCE_API_SECRET", "").strip()

    fail_threshold = int(os.getenv("QUANT_VPN_FAIL_THRESHOLD", str(DEFAULT_FAIL_THRESHOLD)))
    recover_threshold = int(os.getenv("QUANT_VPN_RECOVER_THRESHOLD", str(DEFAULT_RECOVER_THRESHOLD)))
    observe_seconds = int(os.getenv("QUANT_VPN_OBSERVE_SECONDS", str(DEFAULT_OBSERVE_SECONDS)))
    probe_cache_ttl = float(os.getenv("QUANT_VPN_PROBE_CACHE_TTL", "30.0"))
    signed_probe_interval = float(os.getenv("QUANT_VPN_SIGNED_PROBE_INTERVAL", "60.0"))

    _failover_controller = VPNFailoverController(
        primary=primary,
        backups=backups,
        whitelisted_ips=whitelisted_ips,
        proxy_url=proxy_url,
        health_check_url=health_check_url,
        ip_check_url=ip_check_url,
        fail_threshold=fail_threshold,
        recover_threshold=recover_threshold,
        observe_seconds=observe_seconds,
        mihomo_api_url=mihomo_api_url,
        signed_check_url=signed_check_url,
        binance_api_key=binance_api_key,
        binance_api_secret=binance_api_secret,
        probe_cache_ttl=probe_cache_ttl,
        signed_probe_interval=signed_probe_interval,
    )
    return _failover_controller
