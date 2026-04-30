"""仓位管理API路由。"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

try:
    from fastapi import APIRouter, HTTPException, Query
    from pydantic import BaseModel, Field
except ImportError:
    APIRouter = None  # type: ignore[misc,assignment]
    HTTPException = Exception  # type: ignore[misc,assignment]
    Query = None  # type: ignore[misc,assignment]
    BaseModel = object  # type: ignore[misc,assignment]
    Field = None  # type: ignore[misc,assignment]

from services.api.app.services.position_management_service import (
    PositionManagementService,
    RiskLevel,
    position_management_service,
)


if APIRouter is not None:
    router = APIRouter(prefix="/api/v1/position", tags=["position_management"])
else:
    router = None


class PositionCalculateRequest(BaseModel):
    """仓位计算请求。"""

    symbol: str = Field(..., description="交易标的")
    entry_price: str | None = Field(None, description="入场价格")
    stop_loss_price: str | None = Field(None, description="止损价格")
    risk_level: str | None = Field(None, description="风险等级: low, medium, high")
    method: str = Field("fixed_ratio", description="计算方法: fixed_ratio, kelly")


class UpdateCapitalRequest(BaseModel):
    """更新资金请求。"""

    new_capital: str = Field(..., description="新的账户资金")


class RecordTradeRequest(BaseModel):
    """记录交易结果请求。"""

    symbol: str = Field(..., description="交易标的")
    pnl: str = Field(..., description="盈亏金额")
    position_size: str | None = Field(None, description="仓位大小")


class AddPositionRequest(BaseModel):
    """添加仓位请求。"""

    symbol: str = Field(..., description="交易标的")
    size: str = Field(..., description="仓位大小")
    entry_price: str = Field(..., description="入场价格")
    stop_loss: str | None = Field(None, description="止损价格")


class RemovePositionRequest(BaseModel):
    """移除仓位请求。"""

    symbol: str = Field(..., description="交易标的")


class SetRiskLevelRequest(BaseModel):
    """设置风险等级请求。"""

    level: str = Field(..., description="风险等级: low, medium, high")


def _parse_decimal(value: str | None, field_name: str) -> Decimal | None:
    """解析Decimal值。"""
    if value is None:
        return None
    try:
        parsed = Decimal(value.strip())
        if parsed < Decimal("0"):
            raise HTTPException(status_code=400, detail=f"{field_name} must be positive")
        return parsed
    except InvalidOperation:
        raise HTTPException(status_code=400, detail=f"Invalid decimal value for {field_name}: {value}")


def _parse_risk_level(value: str | None) -> RiskLevel | None:
    """解析风险等级。"""
    if value is None:
        return None
    try:
        return RiskLevel(value.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid risk level: {value}. Must be one of: low, medium, high",
        )


if router is not None:

    @router.get("/status")
    def get_position_status() -> dict:
        """获取当前仓位状态。

        Returns:
            仓位状态汇总，包括：
            - status: 仓位状态 (normal, warning, drawdown_limit, trading_paused)
            - current_positions: 当前持仓数量
            - max_positions: 最大持仓数量
            - available_slots: 可用仓位槽位
            - total_capital: 总资金
            - used_capital: 已用资金
            - available_capital: 可用资金
            - drawdown_state: 回撤状态
            - risk_level: 当前风险等级
            - can_open_new: 是否可以开新仓
        """
        status = position_management_service.get_position_status()
        return status.to_dict()

    @router.post("/calculate")
    def calculate_position(request: PositionCalculateRequest) -> dict:
        """计算建议仓位大小。

        支持两种计算方法：
        - fixed_ratio: 固定比例法，默认使用2%风险
        - kelly: Kelly Criterion，基于历史胜率和盈亏比

        Args:
            symbol: 交易标的
            entry_price: 入场价格（可选）
            stop_loss_price: 止损价格（可选）
            risk_level: 风险等级 (low, medium, high)
            method: 计算方法 (fixed_ratio, kelly)

        Returns:
            仓位建议，包括：
            - suggested_size: 建议仓位大小
            - risk_amount: 风险金额
            - position_pct: 仓位百分比
            - method: 使用的计算方法
            - reason: 计算原因说明
        """
        entry_price = _parse_decimal(request.entry_price, "entry_price")
        stop_loss_price = _parse_decimal(request.stop_loss_price, "stop_loss_price")
        risk_level = _parse_risk_level(request.risk_level)

        suggestion = position_management_service.calculate_position(
            symbol=request.symbol,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_level=risk_level,
            method=request.method,
        )

        return suggestion.to_dict()

    @router.get("/drawdown")
    def get_drawdown_status() -> dict:
        """获取回撤状态。

        Returns:
            回撤状态，包括：
            - current_drawdown_pct: 当前回撤百分比
            - peak_capital: 峰值资金
            - current_capital: 当前资金
            - triggered: 是否触发回撤限制
            - triggered_at: 触发时间
            - trading_paused: 是否暂停交易
            - alert_sent: 是否已发送预警
        """
        state = position_management_service.get_drawdown_status()
        return state.to_dict()

    @router.post("/capital/update")
    def update_capital(request: UpdateCapitalRequest) -> dict:
        """更新账户资金。

        用于手动同步账户资金状态，触发回撤检查。

        Args:
            new_capital: 新的账户资金

        Returns:
            更新结果，包括峰值、当前资金和回撤百分比
        """
        new_capital = _parse_decimal(request.new_capital, "new_capital")
        if new_capital is None:
            raise HTTPException(status_code=400, detail="new_capital is required")

        return position_management_service.update_capital(new_capital)

    @router.post("/trade/record")
    def record_trade_result(request: RecordTradeRequest) -> dict:
        """记录交易结果。

        用于Kelly Criterion计算所需的历史数据。

        Args:
            symbol: 交易标的
            pnl: 盈亏金额（正数为盈利，负数为亏损）
            position_size: 仓位大小（可选）

        Returns:
            交易统计数据，包括胜率、平均盈利/亏损等
        """
        pnl = _parse_decimal(request.pnl, "pnl")
        if pnl is None:
            raise HTTPException(status_code=400, detail="pnl is required")

        position_size = _parse_decimal(request.position_size, "position_size")

        return position_management_service.record_trade_result(
            symbol=request.symbol,
            pnl=pnl,
            position_size=position_size,
        )

    @router.post("/add")
    def add_position(request: AddPositionRequest) -> dict:
        """添加仓位。

        Args:
            symbol: 交易标的
            size: 仓位大小
            entry_price: 入场价格
            stop_loss: 止损价格（可选）

        Returns:
            操作结果，包括当前持仓数量和可用槽位
        """
        size = _parse_decimal(request.size, "size")
        if size is None:
            raise HTTPException(status_code=400, detail="size is required")

        entry_price = _parse_decimal(request.entry_price, "entry_price")
        if entry_price is None:
            raise HTTPException(status_code=400, detail="entry_price is required")

        stop_loss = _parse_decimal(request.stop_loss, "stop_loss")

        return position_management_service.add_position(
            symbol=request.symbol,
            size=size,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

    @router.post("/remove")
    def remove_position(request: RemovePositionRequest) -> dict:
        """移除仓位。

        Args:
            symbol: 交易标的

        Returns:
            操作结果，包括移除的仓位详情
        """
        return position_management_service.remove_position(symbol=request.symbol)

    @router.post("/drawdown/reset")
    def reset_drawdown_trigger() -> dict:
        """重置回撤触发状态，恢复交易。

        当回撤限制触发后，可使用此端点重置状态，恢复交易。

        Returns:
            重置结果，包括新的回撤状态
        """
        return position_management_service.reset_drawdown_trigger()

    @router.post("/risk-level/set")
    def set_risk_level(request: SetRiskLevelRequest) -> dict:
        """手动设置风险等级。

        Args:
            level: 风险等级 (low, medium, high)

        Returns:
            设置结果，包括最大仓位数和风险乘数
        """
        risk_level = _parse_risk_level(request.level)
        if risk_level is None:
            raise HTTPException(status_code=400, detail="level is required")

        return position_management_service.set_risk_level(risk_level)

    @router.get("/statistics")
    def get_trade_statistics() -> dict:
        """获取交易统计数据。

        Returns:
            交易统计，包括：
            - total_trades: 总交易次数
            - win_count: 盈利次数
            - loss_count: 亏损次数
            - win_rate: 胜率
            - avg_win: 平均盈利
            - avg_loss: 平均亏损
            - net_pnl: 净盈亏
        """
        return position_management_service.get_trade_statistics()

    @router.get("/config")
    def get_position_config() -> dict:
        """获取当前仓位管理配置。

        Returns:
            配置参数，包括最大回撤、风险百分比等
        """
        config = position_management_service._config
        return {
            "max_drawdown_pct": str(config.max_drawdown_pct),
            "position_risk_pct": str(config.position_risk_pct),
            "max_position_count": config.max_position_count,
            "base_capital": str(config.base_capital),
            "kelly_enabled": config.kelly_enabled,
            "kelly_fraction": str(config.kelly_fraction),
            "trading_paused_on_drawdown": config.trading_paused_on_drawdown,
            "drawdown_alert_threshold": str(config.drawdown_alert_threshold),
            "risk_levels": config.risk_levels,
        }