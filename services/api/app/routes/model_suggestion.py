"""Model Suggestion routes for edge case decision support."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from services.api.app.services.auth_service import auth_service
from services.api.app.services.model_suggestion_service import model_suggestion_service


try:
    from fastapi import APIRouter, Header
except ImportError:
    class APIRouter:  # pragma: no cover - lightweight local fallback
        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def get(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def post(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    def Header(default: str = "") -> str:  # pragma: no cover - fallback stub
        return default


router = APIRouter(prefix="/api/v1/model", tags=["model-suggestion"])


def _success(data: dict, meta: dict | None = None) -> dict:
    return {"data": data, "error": None, "meta": meta or {}}


def _unauthorized() -> dict:
    return {
        "data": None,
        "error": {"code": "unauthorized", "message": "authentication required"},
        "meta": {"source": "control-plane-api"},
    }


def _error(code: str, message: str, meta: dict | None = None) -> dict:
    return {
        "data": None,
        "error": {"code": code, "message": message},
        "meta": meta or {"source": "control-plane-api"},
    }


@router.get("/status")
def get_model_status(token: str = "", authorization: str = Header("")) -> dict:
    """Get model suggestion service status and configuration.

    Requires authentication for admin access.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    stats = model_suggestion_service.get_statistics()
    return _success(
        {"status": stats},
        {"source": "control-plane-api", "action": "model-status"},
    )


@router.post("/suggestion")
def request_model_suggestion(
    payload: dict,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """Request a model suggestion for an edge case decision.

    Payload should include:
    - symbol: Trading symbol (e.g., "BTCUSDT")
    - score: Current decision score (0-1)
    - threshold: Decision threshold (default: 0.7)
    - action_type: Type of decision ("entry", "exit", "position_adjust")
    - side: Trade side ("long", "short")
    - trend_confirmed: Whether trend is confirmed (bool)
    - research_aligned: Whether research aligns with trade direction (bool)
    - volatility: Estimated volatility (optional)
    - market_signals: Additional market signals (optional)
    - conflicting_signals: List of conflicting signals (optional)

    Requires authentication.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    # Validate required fields
    symbol_value = payload.get("symbol")
    if not isinstance(symbol_value, str) or not symbol_value.strip():
        return _error("invalid_request", "symbol is required")

    score_value = payload.get("score")
    if score_value is None:
        return _error("invalid_request", "score is required")

    try:
        score = Decimal(str(score_value))
    except (InvalidOperation, ValueError):
        return _error("invalid_request", "score must be a valid number")

    # Parse optional fields
    threshold_value = payload.get("threshold")
    try:
        threshold = Decimal(str(threshold_value)) if threshold_value is not None else Decimal("0.7")
    except (InvalidOperation, ValueError):
        threshold = Decimal("0.7")

    # Build context data
    context_data = {
        "symbol": symbol_value.strip().upper(),
        "score": float(score),
        "threshold": float(threshold),
        "action_type": payload.get("action_type", "entry"),
        "side": payload.get("side", "long"),
        "trend_confirmed": payload.get("trend_confirmed", False),
        "research_aligned": payload.get("research_aligned", True),
        "volatility": float(payload.get("volatility", 0)),
        "market_signals": payload.get("market_signals", {}),
        "conflicting_signals": payload.get("conflicting_signals", []),
    }

    # First analyze edge case
    edge_analysis = model_suggestion_service.analyze_edge_case(
        score=score,
        threshold=threshold,
    )

    # Get model suggestion
    suggestion = model_suggestion_service.get_model_suggestion(context_data)

    if suggestion is None:
        # Model suggestion disabled or failed
        return _success(
            {
                "edge_case_analysis": edge_analysis.to_dict(),
                "suggestion": None,
                "reason": "Model suggestion disabled or unavailable",
            },
            {
                "source": "control-plane-api",
                "action": "model-suggestion",
                "enabled": model_suggestion_service.enabled,
            },
        )

    return _success(
        {
            "edge_case_analysis": edge_analysis.to_dict(),
            "suggestion": suggestion.to_dict(),
        },
        {
            "source": "control-plane-api",
            "action": "model-suggestion",
            "suggestion_id": suggestion.suggestion_id,
            "action": suggestion.action,
            "confidence": suggestion.confidence,
        },
    )


@router.post("/suggestion/{suggestion_id}/outcome")
def log_suggestion_outcome(
    suggestion_id: str,
    payload: dict,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """Log the outcome of a model suggestion.

    Payload should include:
    - outcome: "success", "failure", or "partial"
    - actual_result: Optional result data (dict)

    Requires authentication.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    outcome = payload.get("outcome")
    if outcome not in ("success", "failure", "partial"):
        return _error("invalid_request", "outcome must be 'success', 'failure', or 'partial'")

    actual_result = payload.get("actual_result")

    success = model_suggestion_service.log_suggestion(
        suggestion_id=suggestion_id,
        outcome=outcome,
        actual_result=actual_result,
    )

    if not success:
        return _error(
            "suggestion_not_found",
            f"Suggestion {suggestion_id} not found",
            {"suggestion_id": suggestion_id},
        )

    return _success(
        {"logged": True, "suggestion_id": suggestion_id, "outcome": outcome},
        {"source": "control-plane-api", "action": "log-outcome"},
    )


@router.get("/history")
def get_suggestion_history(
    limit: int = 100,
    outcome: str | None = None,
    action: str | None = None,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """Get history of model suggestions.

    Query parameters:
    - limit: Maximum number of records (default: 100)
    - outcome: Filter by outcome (optional)
    - action: Filter by action (optional)

    Requires authentication.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    history = model_suggestion_service.get_suggestion_history(
        limit=limit,
        outcome=outcome,
        action=action,
    )

    return _success(
        {"items": history, "count": len(history)},
        {
            "source": "control-plane-api",
            "action": "model-history",
            "limit": limit,
            "outcome_filter": outcome,
            "action_filter": action,
        },
    )


@router.get("/suggestion/{suggestion_id}")
def get_suggestion_by_id(
    suggestion_id: str,
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """Get a specific suggestion by ID.

    Requires authentication.
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    record = model_suggestion_service.get_suggestion(suggestion_id)

    if record is None:
        return _error(
            "suggestion_not_found",
            f"Suggestion {suggestion_id} not found",
            {"suggestion_id": suggestion_id},
        )

    return _success(
        {"item": record},
        {
            "source": "control-plane-api",
            "action": "get-suggestion",
            "suggestion_id": suggestion_id,
        },
    )


@router.post("/analyze")
def analyze_edge_case(
    payload: dict,
) -> dict:
    """Analyze if a score is in the edge case zone near a threshold.

    This endpoint is publicly accessible (no authentication required)
    as it only performs analysis without calling the model API.

    Payload should include:
    - score: The score to analyze (0-1)
    - threshold: The decision threshold (default: 0.7)
    - threshold_range: Optional custom range for edge case detection (default: 0.05)
    """
    score_value = payload.get("score")
    if score_value is None:
        return _error("invalid_request", "score is required")

    try:
        score = Decimal(str(score_value))
    except (InvalidOperation, ValueError):
        return _error("invalid_request", "score must be a valid number")

    threshold_value = payload.get("threshold")
    try:
        threshold = Decimal(str(threshold_value)) if threshold_value is not None else Decimal("0.7")
    except (InvalidOperation, ValueError):
        threshold = Decimal("0.7")

    range_value = payload.get("threshold_range")
    try:
        threshold_range = Decimal(str(range_value)) if range_value is not None else None
    except (InvalidOperation, ValueError):
        threshold_range = None

    analysis = model_suggestion_service.analyze_edge_case(
        score=score,
        threshold=threshold,
        threshold_range=threshold_range,
    )

    return _success(
        {"analysis": analysis.to_dict()},
        {
            "source": "control-plane-api",
            "action": "analyze-edge-case",
            "is_edge_case": analysis.is_edge_case,
        },
    )


@router.delete("/history")
def clear_history(
    token: str = "",
    authorization: str = Header(""),
) -> dict:
    """Clear model suggestion history.

    Requires authentication (admin only).
    """
    try:
        auth_service.require_control_plane_access(
            auth_service.resolve_access_token(token, authorization)
        )
    except PermissionError:
        return _unauthorized()

    count = model_suggestion_service.clear_history()

    return _success(
        {"cleared": count},
        {"source": "control-plane-api", "action": "clear-history"},
    )