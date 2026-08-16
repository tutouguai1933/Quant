"""OpenClaw 定时巡检服务。

按固定间隔检查系统状态并执行安全动作。
遵循三条铁规则：
1. 只能做白名单动作
2. 只能降风险，不能放大风险
3. 高风险场景收口到人工处理
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import json
import logging
import threading
import concurrent.futures

from services.api.app.services.alert_push_service import (
    AlertEventType,
    AlertLevel,
    AlertMessage,
    alert_push_service,
)
from services.api.app.services.auto_dispatch_service import auto_dispatch_service
from services.api.app.services.openclaw_snapshot_service import OpenclawSnapshotService
from services.api.app.services.openclaw_action_service import OpenclawActionService
from services.api.app.services.openclaw_action_policy_service import openclaw_action_policy_service
from services.api.app.services.service_health_service import ServiceHealthService, service_health_service
from services.api.app.services.vpn_switch_service import vpn_switch_service, NodeHealthStatus
from services.api.app.services.feishu_push_service import (
    feishu_push_service,
    FeishuAlertLevel,
    AlertCardMessage,
)

logger = logging.getLogger(__name__)


class OpenclawPatrolService:
    """定时巡检服务，按固定间隔检查系统状态并执行安全动作。"""

    PATROL_INTERVALS = {
        "health_check": 60,      # 每分钟健康检查
        "state_sync": 300,       # 每5分钟状态同步
        "cycle_check": 900,      # 每15分钟周期检查
        "vpn_check": 60,         # 每分钟VPN检查
        "auto_dispatch": 300,    # 每5分钟自动派发检查（可通过 QUANT_AUTO_DISPATCH_INTERVAL 配置）
    }

    # 节流配置
    THROTTLE_WINDOW_SECONDS = 3600  # 1小时窗口
    MAX_ACTION_COUNT_PER_WINDOW = 3  # 同一动作每小时最多执行3次
    MAX_CONSECUTIVE_FAILURES = 2     # 连续失败2次后停止自动执行

    # 动作执行超时配置
    # 60天 + 多币种训练约需 70-120 秒，加上数据获取和特征计算
    ACTION_TIMEOUT_SECONDS = 300  # 单个动作最长执行时间 5 分钟

    # 告警阈值
    ALERT_THRESHOLD = 5               # 告警数超过5条触发清理
    SYNC_STALE_THRESHOLD_MINUTES = 10  # 同步超过10分钟视为过期

    MAX_PATROL_RECORDS = 50

    # VPN切换节流（独立于动作节流）
    VPN_SWITCH_WINDOW_SECONDS = 300   # VPN切换窗口5分钟
    MAX_VPN_SWITCH_PER_WINDOW = 3     # 窗口内最多切换3次

    def __init__(
        self,
        snapshot_service: OpenclawSnapshotService,
        action_service: OpenclawActionService,
        health_service: ServiceHealthService | None = None,
        state_path: Path | None = None,
    ):
        """初始化巡检服务。

        Args:
            snapshot_service: 快照服务
            action_service: 动作执行服务
            health_service: 服务健康检查服务
            state_path: 存储巡检记录的文件路径
        """
        self._snapshot_service = snapshot_service
        self._action_service = action_service
        self._health_service = health_service or service_health_service
        self._state_path = state_path or Path(".runtime/openclaw_patrol_records.json")
        self._records: list[dict[str, Any]] = []
        self._action_counters: dict[str, dict[str, Any]] = {}  # 动作节流计数器
        self._vpn_switch_counter: dict[str, Any] = {}  # VPN切换节流计数器
        self._freqtrade_paused_count: int = 0  # freqtrade 连续 PAUSED 轮次（方案 B）
        self._lock = threading.Lock()
        self._background_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="openclaw-action",
        )
        self._background_actions: dict[str, concurrent.futures.Future] = {}
        self._load()

    def _load(self) -> None:
        """从文件加载巡检记录。"""
        if self._state_path.exists():
            try:
                with open(self._state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._records = list(data.get("records", []))
                    self._action_counters = dict(data.get("action_counters", {}))
                    self._vpn_switch_counter = dict(data.get("vpn_switch_counter", {}))
            except (json.JSONDecodeError, IOError):
                self._records = []
                self._action_counters = {}
                self._vpn_switch_counter = {}
        else:
            self._records = []
            self._action_counters = {}
            self._vpn_switch_counter = {}

    def _save(self) -> None:
        """保存巡检记录到文件。"""
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump({
                "records": self._records,
                "action_counters": self._action_counters,
                "vpn_switch_counter": self._vpn_switch_counter,
            }, f, ensure_ascii=False, indent=2)

    def patrol(self, patrol_type: str = "full") -> dict[str, Any]:
        """执行一轮巡检。

        Args:
            patrol_type: 巡检类型，可选 "health_check", "state_sync", "cycle_check", "vpn_check", "full"

        Returns:
            巡检结果，包含 actions_taken 列表
        """
        now = datetime.now(timezone.utc)
        executed_at = now.isoformat()

        # 获取当前快照
        snapshot = self._snapshot_service.get_snapshot()
        snapshot_id = str(snapshot.get("snapshot_id", ""))

        actions_taken: list[dict[str, Any]] = []
        patrol_status = "normal"
        patrol_message = "巡检正常，无需执行动作"

        # 0. VPN健康检查（health_check, vpn_check, full 都执行）
        if patrol_type in ("health_check", "vpn_check", "full"):
            vpn_result = self._check_vpn_health()
            if vpn_result.get("action_taken"):
                actions_taken.append(vpn_result)
                # VPN切换失败不阻止其他检查，但记录状态
                if vpn_result.get("success"):
                    patrol_status = vpn_result.get("patrol_status", patrol_status)
                    patrol_message = vpn_result.get("message", patrol_message)

        # 1. 健康检查（所有类型都执行）
        health_result = self._check_service_health(snapshot)
        if health_result.get("action_taken"):
            actions_taken.append(health_result)
            patrol_status = health_result.get("patrol_status", patrol_status)
            patrol_message = health_result.get("message", patrol_message)

        # 2. 周期就绪检查（cycle_check 或 full）
        if patrol_type in ("cycle_check", "full") and patrol_status == "normal":
            cycle_result = self._check_cycle_ready(snapshot)
            if cycle_result.get("action_taken"):
                actions_taken.append(cycle_result)
                patrol_status = cycle_result.get("patrol_status", patrol_status)
                patrol_message = cycle_result.get("message", patrol_message)

        # 3. 告警清理检查（full）
        if patrol_type == "full" and patrol_status == "normal":
            alert_result = self._check_alert_cleanup(snapshot)
            if alert_result.get("action_taken"):
                actions_taken.append(alert_result)
                patrol_status = alert_result.get("patrol_status", patrol_status)
                patrol_message = alert_result.get("message", patrol_message)

        # 4. 自动派发检查（auto_dispatch 或 full）
        if patrol_type in ("auto_dispatch", "full") and patrol_status == "normal":
            dispatch_result = self._check_auto_dispatch(snapshot)
            if dispatch_result.get("action_taken"):
                actions_taken.append(dispatch_result)
                patrol_status = dispatch_result.get("patrol_status", patrol_status)
                patrol_message = dispatch_result.get("message", patrol_message)

        # 5. 方向做空检查（cycle_check 或 full；模型极度看跌时做空 BTC 的调度）
        if patrol_type in ("cycle_check", "full"):
            try:
                direction_result = self._check_direction_short()
                if direction_result.get("action_taken"):
                    actions_taken.append(direction_result)
            except Exception as exc:
                logger.warning("方向做空检查失败: %s", exc)

        # 记录巡检结果
        patrol_record = {
            "patrol_type": patrol_type,
            "executed_at": executed_at,
            "snapshot_id": snapshot_id,
            "status": patrol_status,
            "message": patrol_message,
            "actions_taken": actions_taken,
            "actions_count": len(actions_taken),
        }

        with self._lock:
            self._records.append(patrol_record)
            if len(self._records) > self.MAX_PATROL_RECORDS:
                self._records = self._records[-self.MAX_PATROL_RECORDS:]
            self._save()

        # 推送巡检结果到飞书（仅当有动作执行或状态异常时）
        if actions_taken or patrol_status != "normal":
            self._push_patrol_result_to_feishu(patrol_record)

        return {
            "patrolled": True,
            "patrol_type": patrol_type,
            "executed_at": executed_at,
            "status": patrol_status,
            "message": patrol_message,
            "actions_taken": actions_taken,
            "snapshot_id": snapshot_id,
        }

    def _push_patrol_result_to_feishu(self, patrol_record: dict[str, Any]) -> None:
        """推送巡检结果到飞书。

        Args:
            patrol_record: 巡检记录
        """
        try:
            if not feishu_push_service.enabled:
                return

            patrol_status = str(patrol_record.get("status", "normal"))
            patrol_type = str(patrol_record.get("patrol_type", "full"))
            patrol_message = str(patrol_record.get("message", ""))
            actions_taken = list(patrol_record.get("actions_taken", []))

            # 根据状态确定告警级别
            level_map = {
                "normal": FeishuAlertLevel.INFO,
                "action_taken": FeishuAlertLevel.WARNING,
                "throttled": FeishuAlertLevel.WARNING,
                "vpn_switched": FeishuAlertLevel.WARNING,
                "vpn_switch_failed": FeishuAlertLevel.ERROR,
                "vpn_throttled": FeishuAlertLevel.WARNING,
                "vpn_error": FeishuAlertLevel.ERROR,
            }
            feishu_level = level_map.get(patrol_status, FeishuAlertLevel.INFO)

            # 构建详情
            details = {
                "巡检类型": patrol_type,
                "状态": patrol_status,
                "动作数": len(actions_taken),
            }
            if actions_taken:
                action_names = [str(a.get("action", "unknown")) for a in actions_taken[:3]]
                details["执行动作"] = ", ".join(action_names)

            # 构建消息
            title = "系统巡检结果"
            if patrol_status == "normal":
                title = "巡检正常"
            elif actions_taken:
                title = "巡检执行动作"
            elif patrol_status.startswith("vpn"):
                title = "VPN巡检结果"

            message = patrol_message
            if not message:
                if actions_taken:
                    message = f"巡检执行了 {len(actions_taken)} 个动作"
                else:
                    message = "巡检完成，状态正常"

            alert = AlertCardMessage(
                level=feishu_level,
                title=title,
                message=message,
                details=details,
                timestamp=str(patrol_record.get("executed_at", "")),
            )

            success = feishu_push_service.send_alert(alert)
            if success:
                logger.info("巡检结果已推送到飞书")
            else:
                logger.warning("巡检结果推送飞书失败")

        except Exception as e:
            logger.warning("推送巡检结果到飞书异常: %s", e)

    def _check_service_health(self, snapshot: dict) -> dict[str, Any]:
        """检查服务健康状态。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        runtime_guard = dict(snapshot.get("runtime_guard") or {})
        execution_health = dict(snapshot.get("execution_health") or {})
        connection_status = str(execution_health.get("connection_status", "connected"))

        # 真实连通性检测：快照 connection_status 有缓存降级（容器死时仍可能显示
        # connected），直接用 REST ping 确认，避免漏检
        ping_ok = self._freqtrade_ping_ok()

        # 执行器连接异常时，切到 dry_run_only + 自动恢复 freqtrade 容器
        if connection_status == "error" or not ping_ok:
            action = "automation_dry_run_only"
            can_execute, reason = self._can_execute_action(action)

            # 自动恢复：freqtrade 进程死亡/连接异常时重启容器（带冷却和次数保护）
            try:
                recovery = self._get_recovery_service()
                if recovery is not None:
                    record = recovery.attempt_recovery("quant-freqtrade")
                    if record and record.status == "success":
                        logger.info("freqtrade 连接异常，已自动重启容器 (冷却/次数保护生效)")
                    else:
                        logger.warning(
                            "freqtrade 自动恢复未执行或未成功: %s",
                            getattr(record, "status", "unknown"),
                        )
            except Exception as recovery_exc:
                logger.warning("freqtrade 自动恢复异常: %s", recovery_exc)

            # 推送执行器异常告警
            try:
                alert_push_service.push_sync(
                    AlertMessage(
                        event_type=AlertEventType.NODE_FAILURE,
                        level=AlertLevel.ERROR,
                        title="执行器连接异常",
                        message=f"Freqtrade 执行器连接状态异常 ({connection_status})",
                        details={
                            "connection_status": connection_status,
                            "suggested_action": action,
                            "can_execute": can_execute,
                        },
                    )
                )
            except Exception as alert_exc:
                logger.warning("告警推送失败: %s", alert_exc)

            if can_execute:
                result = self._action_service.execute_action(action)
                success = bool(result.get("success"))
                self._record_action_result(action, success)
                return {
                    "action_taken": True,
                    "action": action,
                    "success": success,
                    "message": f"执行器异常，已切换到 dry-run only",
                    "patrol_status": "action_taken",
                }
            else:
                return {
                    "action_taken": False,
                    "action": action,
                    "blocked_reason": reason,
                    "message": f"执行器异常但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "服务健康检查正常",
            "patrol_status": "normal",
        }

    def _check_cycle_ready(self, snapshot: dict) -> dict[str, Any]:
        """检查周期就绪状态。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        runtime_guard = dict(snapshot.get("runtime_guard") or {})
        suggested_action = dict(snapshot.get("suggested_action") or {})

        # 自动化暂停时尝试自动恢复（基础设施类失败且连续失败<=3 时恢复，
        # 恢复后 suggested_action 会变为 run_cycle，下一轮巡检自然触发周期）
        try:
            from services.api.app.services.automation_service import automation_service

            auto_resume = automation_service.maybe_auto_resume()
            if str(auto_resume.get("status", "")) == "succeeded":
                logger.info("自动恢复自动化成功（周期检查入口触发）")
                # 刷新快照，重新取 suggested_action
                snapshot = self._snapshot_service.get_snapshot()
                suggested_action = dict(snapshot.get("suggested_action") or {})
        except Exception as exc:
            logger.warning("周期检查入口自动恢复尝试失败: %s", exc)

        # 检查是否建议运行周期
        action = str(suggested_action.get("action", ""))
        auto_run_allowed = bool(suggested_action.get("auto_run_allowed", False))

        # 只有当 suggested_action 是 run_cycle 且 auto_run_allowed=True 时才自动执行
        if action == "run_cycle" and auto_run_allowed:
            can_execute, reason = self._can_execute_action("automation_run_cycle")
            if can_execute:
                queued, queue_reason = self._queue_background_action("automation_run_cycle")
                if queued:
                    return {
                        "action_taken": True,
                        "action": "automation_run_cycle",
                        "success": True,
                        "message": "周期就绪，已排队后台执行自动化周期",
                        "patrol_status": "queued",
                    }
                return {
                    "action_taken": False,
                    "action": "automation_run_cycle",
                    "blocked_reason": queue_reason,
                    "message": f"周期就绪但动作未排队: {queue_reason}",
                    "patrol_status": "running",
                }
            else:
                return {
                    "action_taken": False,
                    "action": "automation_run_cycle",
                    "blocked_reason": reason,
                    "message": f"周期就绪但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "周期未就绪或禁止自动运行",
            "patrol_status": "normal",
        }

    def _queue_background_action(self, action: str) -> tuple[bool, str]:
        """把耗时动作放入后台执行，避免巡检 HTTP 请求等待完整周期。"""
        with self._lock:
            existing = self._background_actions.get(action)
            if existing is not None and not existing.done():
                return False, "action_already_running"
            future = self._background_executor.submit(self._execute_background_action, action)
            self._background_actions[action] = future
        return True, "queued"

    def _execute_background_action(self, action: str) -> None:
        """执行后台动作并记录结果。"""
        success = False
        try:
            result = self._action_service.execute_action(action)
            success = bool(result.get("success"))
        except Exception as e:
            logger.exception("%s 后台执行异常: %s", action, e)
        finally:
            self._record_action_result(action, success)

    def _check_alert_cleanup(self, snapshot: dict) -> dict[str, Any]:
        """检查告警堆积。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        automation_state = dict(snapshot.get("automation_state") or {})
        alerts = list(automation_state.get("alerts", []))

        # 统计非错误级告警数
        non_error_alerts = [
            a for a in alerts
            if str(a.get("level", "")) in ("info", "warning")
        ]

        if len(non_error_alerts) > self.ALERT_THRESHOLD:
            action = "automation_clear_non_error_alerts"
            can_execute, reason = self._can_execute_action(action)
            if can_execute:
                result = self._action_service.execute_action(action)
                success = bool(result.get("success"))
                self._record_action_result(action, success)
                return {
                    "action_taken": True,
                    "action": action,
                    "success": success,
                    "message": f"告警堆积（{len(non_error_alerts)}条），已清理非错误告警",
                    "patrol_status": "action_taken",
                }
            else:
                return {
                    "action_taken": False,
                    "action": action,
                    "blocked_reason": reason,
                    "message": f"告警堆积但动作被节流: {reason}",
                    "patrol_status": "throttled",
                }

        return {
            "action_taken": False,
            "message": "告警数量正常",
            "patrol_status": "normal",
        }

    def _check_vpn_health(self) -> dict[str, Any]:
        """检查VPN节点健康状态。

        优先使用主备策略（若已配置），否则降级到原有自动切换逻辑。
        额外检测 freqtrade 是否卡在 PAUSED（exchange 连续失败导致），
        连续 N 轮仍 PAUSED 时主动强制 failover（方案 B）。

        Returns:
            检查结果
        """
        try:
            # 优先使用主备故障切换策略
            controller = self._get_failover_controller()

            # freqtrade PAUSED 强信号检测：连续 2 轮（每轮 60s）仍 PAUSED
            # 说明出口节点大概率有问题（即使 delay 探测显示健康），强制切换
            freqtrade_paused = self._freqtrade_is_paused()
            if freqtrade_paused:
                self._freqtrade_paused_count += 1
            else:
                self._freqtrade_paused_count = 0

            if self._freqtrade_paused_count >= 2:
                logger.warning(
                    "freqtrade 连续 %d 轮 PAUSED，强制执行 VPN 故障切换",
                    self._freqtrade_paused_count,
                )
                if controller is not None and controller.enabled:
                    forced = controller.failover(from_node=controller.primary_name)
                    return {
                        "action_taken": True,
                        "action": "vpn_failover",
                        "success": bool(forced.get("success")),
                        "message": f"freqtrade 卡 PAUSED，强制故障切换: {forced.get('message')}",
                        "patrol_status": "vpn_switched" if forced.get("success") else "vpn_switch_failed",
                        "policy_action": "forced_failover",
                    }
                return {
                    "action_taken": True,
                    "action": "vpn_failover",
                    "success": False,
                    "message": "freqtrade 卡 PAUSED 但主备策略未配置，无法自动切换",
                    "patrol_status": "vpn_switch_failed",
                }

            if controller is not None and controller.enabled:
                return self._check_vpn_with_policy(controller)

            # 降级到原有逻辑
            return self._check_vpn_legacy()

        except Exception as e:
            logger.exception("VPN健康检查异常: %s", e)
            return {
                "action_taken": False,
                "message": f"VPN健康检查异常: {e}",
                "patrol_status": "vpn_error",
                "error": str(e),
            }

    @staticmethod
    def _freqtrade_is_paused() -> bool:
        """查询 freqtrade 是否处于 PAUSED 状态。

        Returns:
            True 表示 freqtrade 处于 PAUSED（exchange 连接异常暂停）
        """
        try:
            from services.api.app.adapters.freqtrade.client import freqtrade_client

            runtime = dict(freqtrade_client.get_runtime_snapshot())
            if str(runtime.get("backend", "")) != "rest":
                return False
            return str(runtime.get("bot_state", "")).lower() == "paused"
        except Exception as e:
            logger.warning("查询 freqtrade 状态失败: %s", e)
            return False

    @staticmethod
    def _get_failover_controller():
        """获取故障切换控制器（延迟导入避免循环依赖）。"""
        try:
            from services.api.app.services.vpn_failover_controller import (
                get_failover_controller,
            )
            return get_failover_controller()
        except Exception:
            return None

    @staticmethod
    def _get_recovery_service():
        """获取自动恢复服务（延迟导入避免循环依赖）。"""
        try:
            from services.api.app.services.auto_recovery_service import (
                auto_recovery_service,
            )
            return auto_recovery_service
        except Exception:
            return None

    @staticmethod
    def _freqtrade_ping_ok() -> bool:
        """真实检测 freqtrade REST 连通性（ping 9013，绕过快照缓存降级）。"""
        try:
            from services.api.app.adapters.freqtrade.client import FreqtradeClient
            from services.api.app.core.settings import Settings

            client = FreqtradeClient(Settings.from_env())
            backend = getattr(client, "_backend", None)
            if backend is None or not hasattr(backend, "ping"):
                return True  # 无 REST 后端（内存态），不视为异常
            backend.ping()
            return True
        except Exception:
            return False

    def _check_vpn_with_policy(self, controller) -> dict[str, Any]:
        """使用主备策略检查VPN。"""
        result = controller.check_primary()
        action = result.get("action", "unknown")

        if action == "healthy":
            return {
                "action_taken": False,
                "message": f"VPN主节点健康，IP: {result.get('ip', 'N/A')}",
                "patrol_status": "normal",
                "policy_action": action,
                "vpn_details": result,
            }

        if action == "failover":
            # 主节点故障，已选出备选 — 需要实际执行切换
            to_node = result.get("to", "")
            if to_node:
                switch_result = vpn_switch_service.switch_node_sync(to_node)
                self._record_vpn_switch_result(switch_result.success)
                return {
                    "action_taken": True,
                    "action": "vpn_failover",
                    "success": switch_result.success,
                    "message": (
                        f"VPN故障切换到 {switch_result.current_node}, IP: {switch_result.exit_ip}"
                        if switch_result.success
                        else f"VPN故障切换失败: {switch_result.error_message}"
                    ),
                    "patrol_status": "vpn_switched" if switch_result.success else "vpn_switch_failed",
                    "vpn_switch": switch_result.to_dict(),
                    "policy_action": action,
                }
            return {
                "action_taken": False,
                "message": "VPN故障切换：备选节点名称为空",
                "patrol_status": "vpn_switch_failed",
                "policy_action": action,
            }

        if action == "failback":
            # 回切到主节点
            switch_result = vpn_switch_service.switch_node_sync(controller.primary_name)
            self._record_vpn_switch_result(switch_result.success)
            return {
                "action_taken": True,
                "action": "vpn_failback",
                "success": switch_result.success,
                "message": (
                    f"VPN回切到主节点 {switch_result.current_node}"
                    if switch_result.success
                    else f"VPN回切失败: {switch_result.error_message}"
                ),
                "patrol_status": "vpn_switched" if switch_result.success else "vpn_switch_failed",
                "vpn_switch": switch_result.to_dict(),
                "policy_action": action,
            }

        if action == "failover_failed":
            return {
                "action_taken": True,
                "action": "vpn_failover_failed",
                "success": False,
                "message": result.get("message", "故障切换失败"),
                "patrol_status": "vpn_switch_failed",
                "policy_action": action,
            }

        # probing / observing / disabled
        return {
            "action_taken": False,
            "message": result.get("message", "VPN策略等待中"),
            "patrol_status": "normal",
            "policy_action": action,
        }

    def _check_vpn_legacy(self) -> dict[str, Any]:
        """原有VPN检查逻辑（降级路径）。"""
        # 检查当前节点健康状态
        health_result = vpn_switch_service.check_node_health_sync()

        logger.info(
            "VPN健康检查: 节点=%s, 状态=%s, IP=%s, 白名单=%s, 延迟=%.2fms",
            health_result.node_name,
            health_result.status.value,
            health_result.exit_ip,
            health_result.is_whitelisted,
            health_result.latency_ms or 0,
        )

        # 如果节点健康且在白名单，无需切换
        if health_result.status == NodeHealthStatus.HEALTHY and health_result.is_whitelisted:
            return {
                "action_taken": False,
                "message": f"VPN节点健康，IP在白名单: {health_result.exit_ip}",
                "patrol_status": "normal",
                "vpn_health": health_result.to_dict(),
            }

        # 节点不健康或IP不在白名单，尝试自动切换
        can_switch, reason = self._can_switch_vpn()
        if not can_switch:
            logger.warning("VPN切换被节流: %s", reason)
            return {
                "action_taken": False,
                "blocked_reason": reason,
                "message": f"VPN异常但切换被节流: {reason}",
                "patrol_status": "vpn_throttled",
                "vpn_health": health_result.to_dict(),
            }

        # 执行自动切换
        switch_result = vpn_switch_service.auto_switch_to_healthy_node_sync()
        self._record_vpn_switch_result(switch_result.success)

        return {
            "action_taken": True,
            "action": "vpn_auto_switch",
            "success": switch_result.success,
            "message": (
                f"VPN节点切换成功: {switch_result.current_node}, IP: {switch_result.exit_ip}"
                if switch_result.success
                else f"VPN节点切换失败: {switch_result.error_message}"
            ),
            "patrol_status": "vpn_switched" if switch_result.success else "vpn_switch_failed",
            "vpn_health": health_result.to_dict(),
            "vpn_switch": switch_result.to_dict(),
        }

    def _can_switch_vpn(self) -> tuple[bool, str]:
        """检查是否可以执行VPN切换（节流校验）。

        Returns:
            (是否可切换, 原因)
        """
        now = datetime.now(timezone.utc)

        counter = self._vpn_switch_counter
        window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None
        count_in_window = int(counter.get("count", 0))
        consecutive_failures = int(counter.get("consecutive_failures", 0))

        # 如果窗口过期，重置计数器
        if window_start and (now - window_start).total_seconds() > self.VPN_SWITCH_WINDOW_SECONDS:
            count_in_window = 0
            consecutive_failures = 0
            window_start = None

        # 检查连续失败次数（超过2次后停止自动切换）
        if consecutive_failures >= 2:
            return False, f"VPN切换连续失败 {consecutive_failures} 次，已停止自动切换"

        # 检查窗口内切换次数
        if count_in_window >= self.MAX_VPN_SWITCH_PER_WINDOW:
            return False, f"VPN切换在窗口内已执行 {count_in_window} 次，已达上限"

        return True, "允许切换"

    def _record_vpn_switch_result(self, success: bool) -> None:
        """记录VPN切换结果用于节流计算。

        Args:
            success: 是否成功
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            counter = self._vpn_switch_counter
            window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None

            # 如果窗口过期或不存在，重置窗口
            if not window_start or (now - window_start).total_seconds() > self.VPN_SWITCH_WINDOW_SECONDS:
                window_start = now
                counter = {
                    "window_start": window_start.isoformat(),
                    "count": 0,
                    "consecutive_failures": 0,
                }

            # 更新计数
            counter["count"] = int(counter.get("count", 0)) + 1
            if success:
                counter["consecutive_failures"] = 0
            else:
                counter["consecutive_failures"] = int(counter.get("consecutive_failures", 0)) + 1

            self._vpn_switch_counter = counter
            self._save()

    def get_vpn_switch_counter(self) -> dict[str, Any]:
        """获取VPN切换计数器状态。

        Returns:
            VPN切换计数器状态
        """
        with self._lock:
            return dict(self._vpn_switch_counter)

    def reset_vpn_switch_counter(self) -> None:
        """重置VPN切换计数器。"""
        with self._lock:
            self._vpn_switch_counter = {}
            self._save()

    def _check_direction_short(self) -> dict[str, Any]:
        """方向做空检查：模型极度看跌时做空 BTCUSDT（futures 模拟盘）。

        决策来自 direction_short_service（阈值来自 OOS 验证：<0.38 开空、>0.45 平空）。
        执行通过独立的 freqtrade 客户端（指向模拟盘 9014，与实盘 9013 完全隔离）。
        QUANT_DIRECTION_SHORT_FREQTRADE_URL 可切换（实盘时改为实盘地址）。

        Returns:
            {action_taken, action, message}
        """
        import os

        from services.api.app.services.direction_short_service import build_sim_client, direction_short_service
        from services.api.app.services.research_service import research_service

        # 1. 读取模型平均分数（最近一次推理）
        latest = research_service.get_latest_result()
        inference = dict(latest.get("latest_inference") or {})
        signals = list(inference.get("signals") or [])
        if not signals:
            return {"action_taken": False, "action": "direction_short", "message": "无推理信号，跳过方向做空"}
        avg_score = sum(float(str(s.get("score", "0"))) for s in signals) / len(signals)

        # 2. 构建独立客户端（默认模拟盘 9014，与实盘隔离），
        #    并在决策前先用真实持仓对齐状态文件（自愈：止损平仓后状态文件残留会僵死观察期）
        sim_url = os.getenv("QUANT_DIRECTION_SHORT_FREQTRADE_URL", "http://127.0.0.1:9014").strip()
        sim_client = build_sim_client()
        try:
            trades = sim_client.list_trades(limit=5)
            direction_short_service.reconcile_with_trades(trades)
        except Exception as exc:
            # 查询失败时沿用内部状态决策，避免误改状态文件
            logger.warning("方向做空状态同步查询失败，沿用内部状态: %s", exc)

        # 3. 决策（内部状态已按真实持仓对齐）
        decision = direction_short_service.decide(avg_score=avg_score)
        action = str(decision.get("action", "hold"))

        if action == "open_short":
            try:
                sim_client.submit_execution_action({
                    "symbol": "BTC/USDT:USDT",
                    "side": "short",
                    "quantity": 1,
                })
                direction_short_service.mark_short_open(symbol="BTCUSDT")
                logger.info("方向做空开仓(模拟盘 %s): avg=%.4f", sim_url, avg_score)
                return {
                    "action_taken": True,
                    "action": "direction_short_open",
                    "message": f"模型极度看跌（avg={avg_score:.3f}<0.38），已开空 BTCUSDT（模拟盘）",
                }
            except Exception as exc:
                # forceenter 可能超时但订单实际成交：查询实际持仓确认真实状态
                try:
                    trades = sim_client.list_open_trades()
                    has_short = any(str(t.get("is_short", "")).lower() == "true" for t in trades)
                    if has_short:
                        direction_short_service.mark_short_open(symbol="BTCUSDT")
                        logger.info("方向做空开仓确认（forceenter 超时但持仓已存在）")
                        return {
                            "action_taken": True,
                            "action": "direction_short_open",
                            "message": f"开空确认成功（avg={avg_score:.3f}，forceenter 超时但持仓已开）",
                        }
                except Exception:
                    pass
                logger.warning("方向做空开仓失败: %s", exc)
                return {"action_taken": False, "action": "direction_short", "message": f"开空失败: {exc}"}

        if action == "close_short":
            try:
                sim_client.submit_execution_action({
                    "symbol": "BTCUSDT",
                    "side": "flat",
                })
                direction_short_service.mark_short_closed()
                logger.info("方向做空平仓(模拟盘 %s): avg=%.4f", sim_url, avg_score)
                return {
                    "action_taken": True,
                    "action": "direction_short_close",
                    "message": f"模型转暖（avg={avg_score:.3f}>0.45），已平空 BTCUSDT（模拟盘）",
                }
            except Exception as exc:
                logger.warning("方向做空平仓失败: %s", exc)
                return {"action_taken": False, "action": "direction_short", "message": f"平空失败: {exc}"}

        return {"action_taken": False, "action": "direction_short", "message": f"方向做空保持（avg={avg_score:.3f}）"}

    def _check_auto_dispatch(self, snapshot: dict) -> dict[str, Any]:
        """检查是否需要自动派发信号。

        Args:
            snapshot: 当前快照

        Returns:
            检查结果
        """
        # 获取自动派发配置
        auto_dispatch_config = auto_dispatch_service.get_config()

        # 检查自动派发是否启用
        if not auto_dispatch_config.get("enabled"):
            return {
                "action_taken": False,
                "message": "自动派发功能未启用",
                "patrol_status": "normal",
                "config": auto_dispatch_config,
            }

        # 执行自动派发流程
        try:
            dispatch_result = auto_dispatch_service.run_auto_dispatch_cycle()
            dispatched = bool(dispatch_result.get("dispatched"))

            if dispatched:
                symbol = str(dispatch_result.get("symbol", ""))
                logger.info("自动派发成功: %s", symbol)
                return {
                    "action_taken": True,
                    "action": "auto_dispatch",
                    "success": True,
                    "message": f"已自动派发候选 {symbol}",
                    "patrol_status": "action_taken",
                    "dispatch_result": dispatch_result,
                }
            else:
                reason = str(dispatch_result.get("reason", ""))
                logger.info("本轮不执行自动派发: %s", reason)
                return {
                    "action_taken": False,
                    "message": reason,
                    "patrol_status": "normal",
                    "dispatch_result": dispatch_result,
                }

        except Exception as exc:
            logger.warning("自动派发检查异常: %s", exc)
            return {
                "action_taken": False,
                "message": f"自动派发检查异常: {exc}",
                "patrol_status": "normal",
                "error": str(exc),
            }

    def _can_execute_action(self, action: str) -> tuple[bool, str]:
        """检查是否可以执行指定动作（节流校验）。

        Args:
            action: 动作名称

        Returns:
            (是否可执行, 原因)
        """
        now = datetime.now(timezone.utc)

        # 检查动作是否在白名单
        if not openclaw_action_policy_service.is_safe_action(action):
            return False, f"动作 {action} 不在白名单中"

        # 检查窗口内执行次数
        counter = self._action_counters.get(action, {})
        window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None
        count_in_window = int(counter.get("count", 0))
        consecutive_failures = int(counter.get("consecutive_failures", 0))

        # 如果窗口过期，重置计数器
        if window_start and (now - window_start).total_seconds() > self.THROTTLE_WINDOW_SECONDS:
            count_in_window = 0
            consecutive_failures = 0
            window_start = None

        # 检查连续失败次数
        if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            return False, f"动作 {action} 连续失败 {consecutive_failures} 次，已停止自动执行"

        # 检查窗口内执行次数
        if count_in_window >= self.MAX_ACTION_COUNT_PER_WINDOW:
            return False, f"动作 {action} 在窗口内已执行 {count_in_window} 次，已达上限"

        return True, "允许执行"

    def _record_action_result(self, action: str, success: bool) -> None:
        """记录动作执行结果用于节流计算。

        Args:
            action: 动作名称
            success: 是否成功
        """
        now = datetime.now(timezone.utc)

        with self._lock:
            counter = self._action_counters.get(action, {})
            window_start = datetime.fromisoformat(str(counter.get("window_start", ""))) if counter.get("window_start") else None

            # 如果窗口过期或不存在，重置窗口
            if not window_start or (now - window_start).total_seconds() > self.THROTTLE_WINDOW_SECONDS:
                window_start = now
                counter = {
                    "window_start": window_start.isoformat(),
                    "count": 0,
                    "consecutive_failures": 0,
                }

            # 更新计数
            counter["count"] = int(counter.get("count", 0)) + 1
            if success:
                counter["consecutive_failures"] = 0
            else:
                counter["consecutive_failures"] = int(counter.get("consecutive_failures", 0)) + 1

            self._action_counters[action] = counter
            self._save()

    def get_recent_patrols(self, limit: int = 10) -> list[dict]:
        """获取最近的巡检记录。

        Args:
            limit: 返回的最大记录数

        Returns:
            最近的巡检记录列表，按时间倒序
        """
        with self._lock:
            return list(reversed(self._records[-limit:]))

    def get_action_counters(self) -> dict[str, dict[str, Any]]:
        """获取动作计数器状态。

        Returns:
            所有动作的计数器状态
        """
        with self._lock:
            return dict(self._action_counters)

    def reset_action_counter(self, action: str) -> None:
        """重置指定动作的计数器。

        Args:
            action: 动作名称
        """
        with self._lock:
            if action in self._action_counters:
                del self._action_counters[action]
                self._save()


# 默认实例（延迟初始化）
_openclaw_patrol_service: OpenclawPatrolService | None = None


def get_openclaw_patrol_service() -> OpenclawPatrolService:
    """获取默认巡检服务实例。"""
    global _openclaw_patrol_service
    if _openclaw_patrol_service is None:
        from services.api.app.services.openclaw_action_service import OpenclawActionService
        from services.api.app.services.automation_service import AutomationService, automation_service
        from services.api.app.services.automation_workflow_service import AutomationWorkflowService, automation_workflow_service
        from services.api.app.services.strategy_dispatch_service import strategy_dispatch_service

        snapshot_service = OpenclawSnapshotService(
            automation=automation_service,
            strategies=strategy_dispatch_service,
        )
        action_service = OpenclawActionService(
            automation=automation_service,
            snapshot_service=snapshot_service,
            workflow_service=automation_workflow_service,
        )
        _openclaw_patrol_service = OpenclawPatrolService(
            snapshot_service=snapshot_service,
            action_service=action_service,
        )
    return _openclaw_patrol_service


openclaw_patrol_service = get_openclaw_patrol_service()
