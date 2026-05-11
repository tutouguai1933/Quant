"""OpenClaw 定时运维调度器。

按固定间隔调用 Quant API 的 patrol 接口，实现自动化运维。

三条铁规则：
1. 只能做白名单动作 - patrol API 内部校验
2. 只能降风险，不能放大风险 - 不自动切 live
3. 高风险场景收口到人工 - 连续失败后停止
"""

import os
import time
import logging
import requests
from datetime import datetime, timezone

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("openclaw")

# 从环境变量读取配置
QUANT_API_BASE_URL = os.getenv("QUANT_API_BASE_URL", "http://localhost:9011/api/v1")
HEALTH_CHECK_INTERVAL = int(os.getenv("HEALTH_CHECK_INTERVAL", "60"))  # 每分钟
STATE_SYNC_INTERVAL = int(os.getenv("STATE_SYNC_INTERVAL", "300"))     # 每5分钟
CYCLE_CHECK_INTERVAL = int(os.getenv("CYCLE_CHECK_INTERVAL", "900"))   # 每15分钟
HYPEROPT_CHECK_INTERVAL = int(os.getenv("HYPEROPT_CHECK_INTERVAL", "3600"))  # 每小时检查


def call_patrol(patrol_type: str) -> dict:
    """调用 patrol API。

    Args:
        patrol_type: 巡检类型 (health_check, state_sync, cycle_check, full)

    Returns:
        API 响应结果
    """
    url = f"{QUANT_API_BASE_URL}/openclaw/patrol?patrol_type={patrol_type}"

    # cycle_check 和 full 需要更长的超时时间，因为涉及训练和推理
    timeout = 180 if patrol_type in ("cycle_check", "full") else 60

    try:
        response = requests.post(url, timeout=timeout)
        if response.status_code == 200:
            result = response.json()
            logger.info(f"Patrol {patrol_type}: status={result.get('status')}, actions={len(result.get('actions_taken', []))}")
            return result
        else:
            logger.error(f"Patrol {patrol_type} failed: HTTP {response.status_code}")
            return {"patrolled": False, "error": f"HTTP {response.status_code}"}
    except requests.exceptions.Timeout:
        logger.error(f"Patrol {patrol_type} timeout after {timeout}s")
        return {"patrolled": False, "error": "timeout"}
    except requests.exceptions.RequestException as e:
        logger.error(f"Patrol {patrol_type} error: {e}")
        return {"patrolled": False, "error": str(e)}


def check_and_run_hyperopt() -> dict:
    """检查并运行超参数优化。

    每小时检查一次，如果满足条件则启动优化。

    Returns:
        检查结果
    """
    url = f"{QUANT_API_BASE_URL}/ml/hyperopt/status"
    start_url = f"{QUANT_API_BASE_URL}/ml/hyperopt/start"

    try:
        # 检查当前优化状态
        response = requests.get(url, timeout=30)
        if response.status_code != 200:
            logger.warning(f"Hyperopt status check failed: HTTP {response.status_code}")
            return {"checked": False, "error": f"HTTP {response.status_code}"}

        status = response.json().get("data", {})
        current_status = status.get("status", "idle")

        # 如果已有优化在运行，跳过
        if current_status == "running":
            logger.info("Hyperopt already running, skip")
            return {"checked": True, "action": "skip", "reason": "already_running"}

        # 检查是否应该运行（通过 schedule service 判断）
        schedule_url = f"{QUANT_API_BASE_URL}/ml/hyperopt/schedule/check"
        try:
            schedule_response = requests.get(schedule_url, timeout=30)
            if schedule_response.status_code == 200:
                schedule_data = schedule_response.json().get("data", {})
                if not schedule_data.get("should_run", False):
                    logger.debug(f"Hyperopt not needed: {schedule_data.get('reason', '')}")
                    return {"checked": True, "action": "skip", "reason": schedule_data.get("reason", "not_scheduled")}
        except requests.exceptions.RequestException:
            pass  # 如果调度端点不可用，继续执行

        # 启动优化
        logger.info("Starting scheduled hyperopt optimization...")
        start_response = requests.post(start_url, timeout=60)
        if start_response.status_code == 200:
            result = start_response.json()
            logger.info(f"Hyperopt started: {result.get('data', {})}")
            return {"checked": True, "action": "started", "result": result}
        else:
            logger.error(f"Hyperopt start failed: HTTP {start_response.status_code}")
            return {"checked": True, "action": "failed", "error": f"HTTP {start_response.status_code}"}

    except requests.exceptions.RequestException as e:
        logger.error(f"Hyperopt check error: {e}")
        return {"checked": False, "error": str(e)}


def run_scheduler():
    """运行定时调度器。"""
    logger.info("OpenClaw scheduler starting...")
    logger.info(f"API URL: {QUANT_API_BASE_URL}")
    logger.info(f"Intervals: health={HEALTH_CHECK_INTERVAL}s, sync={STATE_SYNC_INTERVAL}s, cycle={CYCLE_CHECK_INTERVAL}s, hyperopt={HYPEROPT_CHECK_INTERVAL}s")

    # 记录上次执行时间
    last_health_check = 0
    last_state_sync = 0
    last_cycle_check = 0
    last_hyperopt_check = 0

    while True:
        now = time.time()

        # 健康检查（每分钟）
        if now - last_health_check >= HEALTH_CHECK_INTERVAL:
            call_patrol("health_check")
            last_health_check = now

        # 状态同步（每5分钟）
        if now - last_state_sync >= STATE_SYNC_INTERVAL:
            call_patrol("state_sync")
            last_state_sync = now

        # 周期检查（每15分钟）
        if now - last_cycle_check >= CYCLE_CHECK_INTERVAL:
            call_patrol("cycle_check")
            last_cycle_check = now

        # 超参数优化检查（每小时）
        if now - last_hyperopt_check >= HYPEROPT_CHECK_INTERVAL:
            check_and_run_hyperopt()
            last_hyperopt_check = now

        # 等待1秒再检查
        time.sleep(1)


if __name__ == "__main__":
    # 启动时执行一次完整巡检
    logger.info("Initial full patrol on startup...")
    call_patrol("full")

    # 进入定时调度循环
    run_scheduler()