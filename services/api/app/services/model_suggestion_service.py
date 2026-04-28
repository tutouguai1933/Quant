"""Model Suggestion Service for Edge Case Decision Making.

This service handles edge case scenarios where the trading system's judgment is uncertain:
- Score near threshold boundaries
- Conflicting market signals
- Ambiguous trend confirmation

When these situations occur, it calls the Claude API (via anthropic SDK) or OpenAI API
to get a recommendation for the trading decision.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
import uuid

logger = logging.getLogger(__name__)

# Configuration constants with environment variable support
MODEL_SUGGESTION_ENABLED = os.getenv("QUANT_MODEL_SUGGESTION_ENABLED", "false").strip().lower() == "true"
MODEL_API_KEY = os.getenv("QUANT_MODEL_API_KEY", "").strip()
MODEL_THRESHOLD_RANGE = Decimal(os.getenv("QUANT_MODEL_THRESHOLD_RANGE", "0.05"))
MODEL_PROVIDER = os.getenv("QUANT_MODEL_PROVIDER", "anthropic").strip().lower()
MODEL_TIMEOUT_SECONDS = int(os.getenv("QUANT_MODEL_TIMEOUT_SECONDS", "30"))
MODEL_MAX_TOKENS = int(os.getenv("QUANT_MODEL_MAX_TOKENS", "1024"))


@dataclass(slots=True)
class EdgeCaseAnalysis:
    """Result of edge case analysis."""
    is_edge_case: bool
    reason: str
    score_distance: Decimal
    threshold_range: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_edge_case": self.is_edge_case,
            "reason": self.reason,
            "score_distance": str(self.score_distance),
            "threshold_range": str(self.threshold_range),
        }


@dataclass(slots=True)
class ModelSuggestion:
    """Model suggestion result."""
    suggestion_id: str
    action: str  # "proceed", "hold", "reject"
    confidence: str  # "low", "medium", "high"
    reasoning: str
    risk_factors: list[str]
    timestamp: datetime
    model_used: str
    provider: str
    context_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "action": self.action,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "risk_factors": self.risk_factors,
            "timestamp": self.timestamp.isoformat(),
            "model_used": self.model_used,
            "provider": self.provider,
            "context_hash": self.context_hash,
        }


@dataclass(slots=True)
class SuggestionRecord:
    """Record of a suggestion and its outcome."""
    suggestion: ModelSuggestion
    context_data: dict[str, Any]
    outcome: str | None  # "success", "failure", "partial", None if not resolved
    outcome_timestamp: datetime | None
    actual_result: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "suggestion": self.suggestion.to_dict(),
            "context_data": self.context_data,
            "outcome": self.outcome,
            "outcome_timestamp": self.outcome_timestamp.isoformat() if self.outcome_timestamp else None,
            "actual_result": self.actual_result,
        }


class ModelSuggestionService:
    """Service for handling edge case decisions using AI model suggestions."""

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        api_key: str | None = None,
        threshold_range: Decimal | None = None,
        provider: str | None = None,
    ) -> None:
        """Initialize the model suggestion service.

        Args:
            enabled: Whether to enable model suggestions. Defaults to env var.
            api_key: API key for the model provider. Defaults to env var.
            threshold_range: Range around threshold to consider edge case.
            provider: Model provider ("anthropic" or "openai").
        """
        self._enabled = enabled if enabled is not None else MODEL_SUGGESTION_ENABLED
        self._api_key = api_key if api_key is not None else MODEL_API_KEY
        self._threshold_range = threshold_range if threshold_range is not None else MODEL_THRESHOLD_RANGE
        self._provider = provider if provider is not None else MODEL_PROVIDER
        self._timeout_seconds = MODEL_TIMEOUT_SECONDS
        self._max_tokens = MODEL_MAX_TOKENS

        # In-memory storage for suggestion history
        self._suggestion_history: dict[str, SuggestionRecord] = {}
        self._history_limit = 1000

        # Statistics
        self._stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "edge_cases_detected": 0,
        }

    @property
    def enabled(self) -> bool:
        """Check if model suggestion is enabled."""
        return self._enabled and bool(self._api_key)

    @property
    def threshold_range(self) -> Decimal:
        """Get the threshold range for edge case detection."""
        return self._threshold_range

    def analyze_edge_case(
        self,
        score: Decimal,
        threshold: Decimal,
        *,
        threshold_range: Decimal | None = None,
    ) -> EdgeCaseAnalysis:
        """Analyze if a score is in the edge case zone near a threshold.

        Args:
            score: The score to analyze.
            threshold: The decision threshold.
            threshold_range: Optional custom range for edge case detection.

        Returns:
            EdgeCaseAnalysis with details about whether it's an edge case.
        """
        effective_range = threshold_range if threshold_range is not None else self._threshold_range
        score_distance = abs(score - threshold)

        # Determine if score is within the edge case range
        is_edge_case = score_distance <= effective_range

        # Build reason message
        if is_edge_case:
            if score >= threshold:
                reason = f"Score {score:.4f} is within {effective_range:.4f} above threshold {threshold:.4f}"
            else:
                reason = f"Score {score:.4f} is within {effective_range:.4f} below threshold {threshold:.4f}"
            self._stats["edge_cases_detected"] += 1
        else:
            reason = f"Score {score:.4f} is clearly {'above' if score >= threshold else 'below'} threshold {threshold:.4f}"

        return EdgeCaseAnalysis(
            is_edge_case=is_edge_case,
            reason=reason,
            score_distance=score_distance,
            threshold_range=effective_range,
        )

    def get_model_suggestion(
        self,
        context_data: dict[str, Any],
        *,
        prompt_template: str | None = None,
    ) -> ModelSuggestion | None:
        """Get a suggestion from the AI model for an edge case decision.

        Args:
            context_data: Context data including score, signals, market data, etc.
            prompt_template: Optional custom prompt template.

        Returns:
            ModelSuggestion or None if disabled/failed.
        """
        if not self.enabled:
            logger.debug("Model suggestion is disabled")
            return None

        self._stats["total_requests"] += 1
        suggestion_id = str(uuid.uuid4())[:8]
        context_hash = self._compute_context_hash(context_data)

        try:
            if self._provider == "anthropic":
                result = self._call_anthropic_api(context_data, prompt_template)
            elif self._provider == "openai":
                result = self._call_openai_api(context_data, prompt_template)
            else:
                logger.warning("Unknown model provider: %s", self._provider)
                self._stats["failed_requests"] += 1
                return None

            if result is None:
                self._stats["failed_requests"] += 1
                return None

            suggestion = ModelSuggestion(
                suggestion_id=suggestion_id,
                action=result["action"],
                confidence=result["confidence"],
                reasoning=result["reasoning"],
                risk_factors=result.get("risk_factors", []),
                timestamp=datetime.now(timezone.utc),
                model_used=result.get("model", "unknown"),
                provider=self._provider,
                context_hash=context_hash,
            )

            # Store in history
            record = SuggestionRecord(
                suggestion=suggestion,
                context_data=context_data,
                outcome=None,
                outcome_timestamp=None,
                actual_result=None,
            )
            self._suggestion_history[suggestion_id] = record
            self._trim_history()

            self._stats["successful_requests"] += 1
            logger.info(
                "Model suggestion generated: id=%s action=%s confidence=%s",
                suggestion_id,
                suggestion.action,
                suggestion.confidence,
            )
            return suggestion

        except Exception as exc:
            logger.error("Failed to get model suggestion: %s", exc)
            self._stats["failed_requests"] += 1
            return None

    def log_suggestion(
        self,
        suggestion_id: str,
        outcome: str,
        actual_result: dict[str, Any] | None = None,
    ) -> bool:
        """Log the outcome of a suggestion.

        Args:
            suggestion_id: The ID of the suggestion to update.
            outcome: The outcome ("success", "failure", "partial").
            actual_result: Optional actual result data.

        Returns:
            True if the suggestion was found and updated, False otherwise.
        """
        record = self._suggestion_history.get(suggestion_id)
        if record is None:
            logger.warning("Suggestion not found: %s", suggestion_id)
            return False

        record.outcome = outcome
        record.outcome_timestamp = datetime.now(timezone.utc)
        record.actual_result = actual_result

        logger.info(
            "Suggestion outcome logged: id=%s outcome=%s",
            suggestion_id,
            outcome,
        )
        return True

    def get_suggestion_history(
        self,
        *,
        limit: int = 100,
        outcome: str | None = None,
        action: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get history of suggestions.

        Args:
            limit: Maximum number of records to return.
            outcome: Filter by outcome (optional).
            action: Filter by action (optional).

        Returns:
            List of suggestion records as dictionaries.
        """
        results = []

        for record in reversed(list(self._suggestion_history.values())):
            # Apply filters
            if outcome is not None and record.outcome != outcome:
                continue
            if action is not None and record.suggestion.action != action:
                continue

            results.append(record.to_dict())

            if len(results) >= limit:
                break

        return results

    def get_suggestion(self, suggestion_id: str) -> dict[str, Any] | None:
        """Get a specific suggestion by ID.

        Args:
            suggestion_id: The suggestion ID.

        Returns:
            Suggestion record or None if not found.
        """
        record = self._suggestion_history.get(suggestion_id)
        return record.to_dict() if record else None

    def get_statistics(self) -> dict[str, Any]:
        """Get statistics about the suggestion service."""
        return {
            **self._stats,
            "enabled": self.enabled,
            "provider": self._provider,
            "threshold_range": str(self._threshold_range),
            "history_count": len(self._suggestion_history),
        }

    def clear_history(self) -> int:
        """Clear suggestion history.

        Returns:
            Number of records cleared.
        """
        count = len(self._suggestion_history)
        self._suggestion_history.clear()
        logger.info("Cleared %d suggestion records", count)
        return count

    def _call_anthropic_api(
        self,
        context_data: dict[str, Any],
        prompt_template: str | None = None,
    ) -> dict[str, Any] | None:
        """Call Anthropic API for suggestion.

        Args:
            context_data: Context data for the decision.
            prompt_template: Optional custom prompt template.

        Returns:
            Parsed suggestion result or None on failure.
        """
        try:
            import anthropic
        except ImportError:
            logger.error("anthropic package not installed")
            return None

        prompt = self._build_prompt(context_data, prompt_template)

        try:
            client = anthropic.Anthropic(api_key=self._api_key)

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=self._max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            content = response.content[0].text if response.content else ""
            return self._parse_model_response(content)

        except Exception as exc:
            logger.error("Anthropic API call failed: %s", exc)
            return None

    def _call_openai_api(
        self,
        context_data: dict[str, Any],
        prompt_template: str | None = None,
    ) -> dict[str, Any] | None:
        """Call OpenAI API for suggestion.

        Args:
            context_data: Context data for the decision.
            prompt_template: Optional custom prompt template.

        Returns:
            Parsed suggestion result or None on failure.
        """
        try:
            import openai
        except ImportError:
            logger.error("openai package not installed")
            return None

        prompt = self._build_prompt(context_data, prompt_template)

        try:
            client = openai.OpenAI(api_key=self._api_key)

            response = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=self._max_tokens,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a trading decision assistant. Analyze the given context and provide a trading recommendation in JSON format.",
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            content = response.choices[0].message.content if response.choices else ""
            return self._parse_model_response(content)

        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            return None

    def _build_prompt(
        self,
        context_data: dict[str, Any],
        prompt_template: str | None = None,
    ) -> str:
        """Build the prompt for the model.

        Args:
            context_data: Context data for the decision.
            prompt_template: Optional custom prompt template.

        Returns:
            Formatted prompt string.
        """
        if prompt_template:
            return prompt_template.format(**context_data)

        # Default prompt template
        symbol = context_data.get("symbol", "unknown")
        score = context_data.get("score", 0)
        threshold = context_data.get("threshold", 0.7)
        action_type = context_data.get("action_type", "entry")
        trend_confirmed = context_data.get("trend_confirmed", False)
        research_aligned = context_data.get("research_aligned", True)
        volatility = context_data.get("volatility", 0)
        market_signals = context_data.get("market_signals", {})
        conflicting_signals = context_data.get("conflicting_signals", [])

        prompt = f"""You are a trading decision assistant. Analyze the following edge case scenario and provide a recommendation.

CONTEXT:
- Symbol: {symbol}
- Decision Type: {action_type}
- Score: {score:.4f}
- Threshold: {threshold:.4f}
- Trend Confirmed: {trend_confirmed}
- Research Aligned: {research_aligned}
- Volatility: {volatility:.4f}

MARKET SIGNALS:
{json.dumps(market_signals, indent=2) if market_signals else 'No additional market signals'}

CONFLICTING SIGNALS:
{json.dumps(conflicting_signals, indent=2) if conflicting_signals else 'No conflicting signals'}

This is an edge case where the score is near the decision threshold. The trading system is uncertain and needs your analysis.

Provide your recommendation as a JSON object with the following structure:
{{
    "action": "proceed" | "hold" | "reject",
    "confidence": "low" | "medium" | "high",
    "reasoning": "Brief explanation of your recommendation",
    "risk_factors": ["list of identified risk factors"]
}}

Only respond with the JSON object, no additional text."""

        return prompt

    def _parse_model_response(self, content: str) -> dict[str, Any] | None:
        """Parse the model's response into a structured suggestion.

        Args:
            content: The raw response content from the model.

        Returns:
            Parsed suggestion dictionary or None on failure.
        """
        if not content:
            return None

        # Try to extract JSON from the response
        try:
            # Remove any markdown code blocks if present
            cleaned = content.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            result = json.loads(cleaned)

            # Validate required fields
            action = result.get("action", "").lower()
            if action not in ("proceed", "hold", "reject"):
                logger.warning("Invalid action in model response: %s", action)
                action = "hold"

            confidence = result.get("confidence", "").lower()
            if confidence not in ("low", "medium", "high"):
                confidence = "low"

            return {
                "action": action,
                "confidence": confidence,
                "reasoning": result.get("reasoning", ""),
                "risk_factors": result.get("risk_factors", []),
                "model": "claude-sonnet-4-20250514" if self._provider == "anthropic" else "gpt-4o",
            }

        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse model response as JSON: %s", exc)

            # Try to extract action from text
            content_lower = content.lower()
            if "proceed" in content_lower:
                action = "proceed"
            elif "reject" in content_lower:
                action = "reject"
            else:
                action = "hold"

            return {
                "action": action,
                "confidence": "low",
                "reasoning": content[:500],  # Truncate long responses
                "risk_factors": [],
                "model": "claude-sonnet-4-20250514" if self._provider == "anthropic" else "gpt-4o",
            }

    def _compute_context_hash(self, context_data: dict[str, Any]) -> str:
        """Compute a hash of the context data for caching/deduplication.

        Args:
            context_data: Context data to hash.

        Returns:
            Hash string.
        """
        # Create a deterministic string representation
        relevant_keys = ["symbol", "score", "threshold", "action_type", "trend_confirmed", "research_aligned"]
        values = [str(context_data.get(k, "")) for k in relevant_keys]
        combined = "|".join(values)
        return str(hash(combined))

    def _trim_history(self) -> None:
        """Trim history to the configured limit."""
        if len(self._suggestion_history) > self._history_limit:
            # Remove oldest entries
            excess = len(self._suggestion_history) - self._history_limit
            oldest_ids = list(self._suggestion_history.keys())[:excess]
            for sid in oldest_ids:
                del self._suggestion_history[sid]


# Singleton instance
model_suggestion_service = ModelSuggestionService()