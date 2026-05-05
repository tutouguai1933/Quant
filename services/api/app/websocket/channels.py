"""WebSocket channel constants for real-time push."""

# 研究运行时状态推送通道
CHANNEL_RESEARCH_RUNTIME = "research_runtime"

# 自动化周期状态推送通道
CHANNEL_AUTOMATION_STATUS = "automation_status"

# 健康状态推送通道
CHANNEL_HEALTH_STATUS = "health_status"

# 所有可用通道
ALL_CHANNELS = [
    CHANNEL_RESEARCH_RUNTIME,
    CHANNEL_AUTOMATION_STATUS,
    CHANNEL_HEALTH_STATUS,
]
