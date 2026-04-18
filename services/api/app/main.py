"""Control Plane API skeleton for Quant phase 1.

This file stays dependency-light so the repository can define the API surface
before the user approves dependency installation.
"""

from __future__ import annotations

try:
    from fastapi import FastAPI
except ImportError:
    class FastAPI:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs
            self.routers = []

        def include_router(self, router) -> None:
            self.routers.append(router)


from services.api.app.routes.accounts import router as accounts_router
from services.api.app.routes.auth import router as auth_router
from services.api.app.routes.backtest_workspace import router as backtest_workspace_router
from services.api.app.routes.balances import router as balances_router
from services.api.app.routes.data_workspace import router as data_workspace_router
from services.api.app.routes.evaluation_workspace import router as evaluation_workspace_router
from services.api.app.routes.feature_workspace import router as feature_workspace_router
from services.api.app.routes.health import router as health_router
from services.api.app.routes.market import router as market_router
from services.api.app.routes.openclaw import router as openclaw_router
from services.api.app.routes.orders import router as orders_router
from services.api.app.routes.positions import router as positions_router
from services.api.app.routes.research_workspace import router as research_workspace_router
from services.api.app.routes.risk_events import router as risk_events_router
from services.api.app.routes.signals import router as signals_router
from services.api.app.routes.strategies import router as strategies_router
from services.api.app.routes.tasks import router as tasks_router
from services.api.app.routes.workbench_config import router as workbench_config_router


app = FastAPI(
    title="Quant Control Plane API",
    version="0.1.0",
    description="Phase-1 skeleton for crypto + Binance + Freqtrade.",
)

if not hasattr(app, "routers"):
    app.routers = []  # type: ignore[attr-defined]

app.include_router(health_router)
app.routers.append(health_router)  # type: ignore[attr-defined]
app.include_router(auth_router)
app.routers.append(auth_router)  # type: ignore[attr-defined]
app.include_router(backtest_workspace_router)
app.routers.append(backtest_workspace_router)  # type: ignore[attr-defined]
app.include_router(evaluation_workspace_router)
app.routers.append(evaluation_workspace_router)  # type: ignore[attr-defined]
app.include_router(accounts_router)
app.routers.append(accounts_router)  # type: ignore[attr-defined]
app.include_router(balances_router)
app.routers.append(balances_router)  # type: ignore[attr-defined]
app.include_router(data_workspace_router)
app.include_router(feature_workspace_router)
app.routers.append(data_workspace_router)  # type: ignore[attr-defined]
app.routers.append(feature_workspace_router)  # type: ignore[attr-defined]
app.include_router(workbench_config_router)
app.routers.append(workbench_config_router)  # type: ignore[attr-defined]
app.include_router(research_workspace_router)
app.routers.append(research_workspace_router)  # type: ignore[attr-defined]
app.include_router(market_router)
app.routers.append(market_router)  # type: ignore[attr-defined]
app.include_router(positions_router)
app.routers.append(positions_router)  # type: ignore[attr-defined]
app.include_router(orders_router)
app.routers.append(orders_router)  # type: ignore[attr-defined]
app.include_router(strategies_router)
app.routers.append(strategies_router)  # type: ignore[attr-defined]
app.include_router(signals_router)
app.routers.append(signals_router)  # type: ignore[attr-defined]
app.include_router(tasks_router)
app.routers.append(tasks_router)  # type: ignore[attr-defined]
app.include_router(risk_events_router)
app.routers.append(risk_events_router)  # type: ignore[attr-defined]
app.include_router(openclaw_router)
app.routers.append(openclaw_router)  # type: ignore[attr-defined]
