"""WebSocket 通道常量定义。"""

# 研究运行时状态通道
CHANNEL_RESEARCH_RUNTIME = "research_runtime"

# 自动化状态通道
CHANNEL_AUTOMATION_STATUS = "automation_status"

# 系统健康状态通道
CHANNEL_SYSTEM_HEALTH = "system_health"

# 通道白名单（用于验证订阅请求）
VALID_CHANNELS = frozenset([
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
    CHANNEL_SYSTEM_HEALTH,
])


def is_valid_channel(channel: str) -> bool:
    """验证通道名称是否在白名单中。"""
    return channel in VALID_CHANNELS