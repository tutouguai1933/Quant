"""研究到执行仲裁服务。

这个文件负责把研究推荐、执行状态和运行窗口压成统一的下一步结论。
"""

from __future__ import annotations

from services.api.app.services.evaluation_workspace_service import evaluation_workspace_service


class ResearchExecutionArbitrationService:
    """聚合研究与执行状态，返回单一仲裁结论。"""

    def __init__(self, *, evaluation_reader=None) -> None:
        self._evaluation_reader = evaluation_reader or evaluation_workspace_service

    def build_decision(
        self,
        *,
        automation_status: dict[str, object],
        evaluation_workspace: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """返回当前最适合继续推进的状态与动作建议。"""

        workspace = dict(evaluation_workspace or self._read_evaluation_workspace())
        state = dict(automation_status.get("state") or {})
        runtime_window = dict(automation_status.get("runtime_window") or {})
        resume_status = dict(automation_status.get("resume_status") or {})
        execution_health = dict(automation_status.get("execution_health") or {})
        best_experiment = dict(workspace.get("best_experiment") or {})
        recommendation = dict(workspace.get("recommendation_explanation") or {})
        elimination = dict(workspace.get("elimination_explanation") or {})
        alignment = dict(workspace.get("alignment_details") or {})
        summary = dict(workspace.get("stage_decision_summary") or {})

        symbol = str(best_experiment.get("symbol", "") or alignment.get("research_symbol", "")).strip().upper()
        recommended_stage = self._normalize_stage(best_experiment.get("recommended_stage", "research"))
        research_action = self._normalize_action(best_experiment.get("next_action", "") or "continue_research")
        blocked_reason = self._normalize_token(runtime_window.get("blocked_reason", ""))
        latest_sync_status = self._normalize_token(
            execution_health.get("latest_sync_status", "") or alignment.get("latest_sync_status", "") or "unknown"
        )
        execution_state = self._normalize_state_token(
            dict(execution_health.get("execution_state") or {}).get("state", "") or "unknown"
        )
        recovery_action = self._normalize_token(execution_health.get("recovery_action", ""))
        difference_summary = str(alignment.get("difference_summary", "") or summary.get("execution_gap", "")).strip()
        difference_reasons = [
            str(item).strip()
            for item in list(alignment.get("difference_reasons") or [])
            if str(item).strip()
        ]
        difference_codes = self._resolve_difference_codes(
            alignment=alignment,
            difference_reasons=difference_reasons,
        )

        if bool(state.get("manual_takeover")) or blocked_reason == "manual_takeover_active":
            return self._build_result(
                status="manual_takeover",
                headline="当前仍在人工接管中",
                detail=self._resolve_story_detail(
                    runtime_window=runtime_window,
                    fallback="先把人工接管原因处理完，再决定是否恢复自动链。",
                ),
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=[
                    "人工接管仍在生效",
                    str(state.get("paused_reason", "") or "自动链当前不允许继续推进"),
                ],
                blocking_items=[
                    self._blocking_item(
                        code="manual_takeover",
                        label="人工接管仍在生效",
                        detail=str(state.get("paused_reason", "") or "先处理接管原因"),
                        source="automation",
                    )
                ],
                suggested_action=self._suggested_action(
                    action="review_takeover",
                    label="去任务页处理人工接管",
                    target_page="/tasks",
                ),
                automation_status=automation_status,
            )

        if blocked_reason == "manual_mode" or self._normalize_token(state.get("mode", "")) == "manual":
            return self._build_result(
                status="manual_mode",
                headline="当前仍在手动模式",
                detail="研究层已经给出下一步建议，但自动链现在还是手动模式，先切回自动模式再继续。",
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=["当前还是手动模式", "要继续自动推进前，先切回 dry-run only 或自动模式"],
                blocking_items=[
                    self._blocking_item(
                        code="manual_mode",
                        label="自动链仍在手动模式",
                        detail="先切回 dry-run only 或自动模式。",
                        source="automation",
                    )
                ],
                suggested_action=self._suggested_action(
                    action="switch_auto_mode",
                    label="去任务页切回自动模式",
                    target_page="/tasks",
                ),
                automation_status=automation_status,
            )

        if blocked_reason == "cooldown_active":
            cooldown_minutes = int(runtime_window.get("cooldown_remaining_minutes", 0) or 0)
            return self._build_result(
                status="cooldown",
                headline="当前还在冷却窗口内",
                detail=f"自动链还需要等待约 {cooldown_minutes} 分钟，冷却结束后再继续推进。",
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=["当前运行窗口还没开放", "先不要重复触发同一轮自动化"],
                blocking_items=[
                    self._blocking_item(
                        code="cooldown_active",
                        label="冷却窗口未结束",
                        detail=f"还需等待约 {cooldown_minutes} 分钟。",
                        source="runtime_window",
                    )
                ],
                suggested_action=self._suggested_action(
                    action="wait_cooldown",
                    label="去任务页等待冷却结束",
                    target_page="/tasks",
                ),
                automation_status=automation_status,
            )

        if blocked_reason == "daily_limit_reached":
            return self._build_result(
                status="wait_window",
                headline="今日自动化轮次已经用完",
                detail="当前不是研究不行，而是日内轮次窗口已经打满，等下一日窗口再继续。",
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=["今日轮次上限已经触发"],
                blocking_items=[
                    self._blocking_item(
                        code="daily_limit_reached",
                        label="日内窗口已满",
                        detail="需要等下一日调度窗口。",
                        source="runtime_window",
                    )
                ],
                suggested_action=self._suggested_action(
                    action="wait_next_window",
                    label="去任务页查看下一日窗口",
                    target_page="/tasks",
                ),
                automation_status=automation_status,
            )

        if blocked_reason == "paused_waiting_review":
            return self._build_result(
                status="resume_review",
                headline="当前仍在等待人工复核",
                detail=str(resume_status.get("cannot_resume_reason", "") or "先处理恢复清单，再决定是否继续自动链。"),
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=["自动链当前处于暂停待复核状态"],
                blocking_items=self._resume_blocking_items(resume_status=resume_status),
                suggested_action=self._suggested_action(
                    action="review_resume",
                    label="去任务页完成恢复复核",
                    target_page="/tasks",
                ),
                automation_status=automation_status,
            )

        if recommended_stage == "research" or research_action == "continue_research" or not symbol:
            why_blocked = str(summary.get("why_blocked", "") or elimination.get("detail", "")).strip()
            why_recommended = str(summary.get("why_recommended", "") or recommendation.get("detail", "")).strip()
            detail = why_blocked or why_recommended or "当前还没有稳定候选进入执行层，先继续研究。"
            return self._build_result(
                status="continue_research",
                headline=f"{symbol} 还需要继续研究" if symbol else "当前还需要继续研究",
                detail=detail,
                symbol=symbol,
                recommended_stage="research",
                research_action="continue_research",
                reason_items=[
                    item
                    for item in [why_recommended, why_blocked, difference_summary]
                    if item
                ] or ["当前研究结果还不够稳定"],
                blocking_items=[
                    self._blocking_item(
                        code="research_not_ready",
                        label="研究层还没放行",
                        detail=detail,
                        source="evaluation",
                    )
                ],
                suggested_action=self._suggested_action(
                    action="continue_research",
                    label="去研究页继续训练和推理",
                    target_page="/research",
                ),
                automation_status=automation_status,
            )

        if self._needs_sync_wait(
            recommended_stage=recommended_stage,
            latest_sync_status=latest_sync_status,
            execution_state=execution_state,
            difference_codes=difference_codes,
        ):
            reasons = difference_reasons or [difference_summary or "研究和执行还没完全对齐。"]
            return self._build_result(
                status="wait_sync",
                headline=f"{symbol or '当前候选'} 还需要先收口执行状态",
                detail=difference_summary or "研究结论已经给出，但执行侧还没准备好进入下一步。",
                symbol=symbol,
                recommended_stage=recommended_stage,
                research_action=research_action,
                reason_items=reasons,
                blocking_items=[
                    self._blocking_item(
                        code="execution_not_aligned",
                        label="执行侧还没对齐",
                        detail=item,
                        source="execution",
                    )
                    for item in reasons
                ],
                suggested_action=self._suggested_action(
                    action="review_sync" if recovery_action in {"retry_sync", "resume_after_review", "manual_takeover"} else "check_execution",
                    label="去任务页和策略页处理同步与执行差异",
                    target_page="/tasks" if recovery_action in {"retry_sync", "resume_after_review", "manual_takeover"} else "/strategies",
                ),
                automation_status=automation_status,
            )

        if recommended_stage == "live":
            return self._build_result(
                status="go_live",
                headline=f"{symbol or '当前候选'} 可以准备进入小额 live",
                detail=str(recommendation.get("detail", "") or summary.get("why_recommended", "") or "研究和执行条件已经允许继续推进 live。"),
                symbol=symbol,
                recommended_stage="live",
                research_action=research_action,
                reason_items=[
                    item
                    for item in [
                        str(recommendation.get("headline", "")).strip(),
                        str(summary.get("why_recommended", "")).strip(),
                    ]
                    if item
                ] or ["当前候选已经满足 live 准入条件"],
                blocking_items=[],
                suggested_action=self._suggested_action(
                    action="enter_live",
                    label="去策略页确认小额 live",
                    target_page="/strategies",
                ),
                automation_status=automation_status,
            )

        return self._build_result(
            status="go_dry_run",
            headline=f"{symbol or '当前候选'} 可以先进入 dry-run",
            detail=str(recommendation.get("detail", "") or summary.get("why_recommended", "") or "当前研究候选已经适合先进入 dry-run。"),
            symbol=symbol,
            recommended_stage="dry_run",
            research_action=research_action,
            reason_items=[
                item
                for item in [
                    str(recommendation.get("headline", "")).strip(),
                    str(summary.get("why_recommended", "")).strip(),
                ]
                if item
            ] or ["当前候选已经满足 dry-run 准入条件"],
            blocking_items=[],
            suggested_action=self._suggested_action(
                action="enter_dry_run",
                label="去策略页确认 dry-run",
                target_page="/strategies",
            ),
            automation_status=automation_status,
        )

    def _read_evaluation_workspace(self) -> dict[str, object]:
        """读取当前评估工作台。"""

        reader = self._evaluation_reader
        try:
            if hasattr(reader, "get_workspace"):
                return dict(reader.get_workspace())
            if callable(reader):
                return dict(reader())
        except Exception:
            return {}
        return {}

    @staticmethod
    def _resolve_difference_codes(
        *,
        alignment: dict[str, object],
        difference_reasons: list[str],
    ) -> list[str]:
        """优先读取结构化差异码，没有时再做兼容推断。"""

        raw_codes = [
            ResearchExecutionArbitrationService._normalize_token(item)
            for item in list(alignment.get("difference_codes") or [])
            if ResearchExecutionArbitrationService._normalize_token(item)
        ]
        if raw_codes:
            return raw_codes
        inferred: list[str] = []
        for reason in difference_reasons:
            normalized = str(reason).strip()
            if normalized.startswith("最近订单仍是"):
                inferred.append("order_symbol_mismatch")
            elif normalized.startswith("最近持仓仍是"):
                inferred.append("position_symbol_mismatch")
            elif normalized == "同步失败":
                inferred.append("sync_failed")
            elif "还没进入同一轮" in normalized:
                inferred.append("waiting_same_cycle")
            elif "手动模式" in normalized:
                inferred.append("manual_mode_confirmation_required")
            elif normalized == "当前没有明显差异":
                inferred.append("aligned")
        return inferred

    @staticmethod
    def _needs_sync_wait(
        *,
        recommended_stage: str,
        latest_sync_status: str,
        execution_state: str,
        difference_codes: list[str],
    ) -> bool:
        """判断当前是不是应该先停在执行同步和对齐阶段。"""

        if latest_sync_status not in {"succeeded", "retrying"}:
            return True
        if recommended_stage == "live":
            return execution_state not in {"live", "dry_run"} or any(
                code in {"order_symbol_mismatch", "position_symbol_mismatch", "waiting_same_cycle", "execution_unavailable"}
                for code in difference_codes
            )
        if recommended_stage == "dry_run":
            if execution_state in {"dry_run", "live"}:
                return any(
                    code in {"order_symbol_mismatch", "position_symbol_mismatch"}
                    for code in difference_codes
                )
        return False

    @staticmethod
    def _normalize_stage(value: object) -> str:
        """统一阶段枚举。"""

        normalized = ResearchExecutionArbitrationService._normalize_token(value)
        if normalized in {"dry_run", "dry-run"}:
            return "dry_run"
        if normalized in {"live", "enter_live", "go_live"}:
            return "live"
        return "research"

    @staticmethod
    def _normalize_action(value: object) -> str:
        """统一下一步动作枚举。"""

        normalized = ResearchExecutionArbitrationService._normalize_token(value)
        if normalized in {"go_dry_run", "enter_dry_run", "go-dry-run", "enter-dry-run"}:
            return "go_dry_run"
        if normalized in {"go_live", "enter_live", "go-live", "enter-live"}:
            return "go_live"
        if normalized in {"run_training", "run-training"}:
            return "run_training"
        if normalized in {"run_inference", "run-inference"}:
            return "run_inference"
        if normalized in {"wait_live", "wait-live"}:
            return "wait_live"
        return "continue_research"

    @staticmethod
    def _normalize_state_token(value: object) -> str:
        """统一执行状态枚举。"""

        normalized = ResearchExecutionArbitrationService._normalize_token(value)
        if normalized in {"dry_run", "dry-run"}:
            return "dry_run"
        return normalized

    @staticmethod
    def _normalize_token(value: object) -> str:
        """把枚举 token 压成统一比较格式。"""

        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    @staticmethod
    def _resolve_story_detail(*, runtime_window: dict[str, object], fallback: str) -> str:
        """统一读取运行窗口里的说明文案。"""

        story = runtime_window.get("story")
        if isinstance(story, str):
            cleaned = story.strip()
            return cleaned or fallback
        detail = str(dict(story or {}).get("why_not_resume", "")).strip()
        return detail or fallback

    @staticmethod
    def _resume_blocking_items(*, resume_status: dict[str, object]) -> list[dict[str, object]]:
        """把恢复清单整理成统一阻塞项。"""

        blocked = []
        for item in list(resume_status.get("resume_blockers") or []):
            row = dict(item or {})
            blocked.append(
                ResearchExecutionArbitrationService._blocking_item(
                    code="resume_checklist_pending",
                    label=str(row.get("label", "") or "恢复检查项"),
                    detail=str(row.get("detail", "") or "当前还没有通过恢复检查。"),
                    source="resume_status",
                )
            )
        if blocked:
            return blocked
        reason = str(resume_status.get("cannot_resume_reason", "") or "")
        return [
            ResearchExecutionArbitrationService._blocking_item(
                code="resume_review_pending",
                label="恢复前仍需人工复核",
                detail=reason or "当前还不能直接恢复自动化。",
                source="resume_status",
            )
        ]

    @staticmethod
    def _blocking_item(*, code: str, label: str, detail: str, source: str) -> dict[str, object]:
        """构造统一阻塞项。"""

        return {
            "code": code,
            "label": label,
            "detail": detail,
            "source": source,
            "blocking": True,
        }

    @staticmethod
    def _suggested_action(*, action: str, label: str, target_page: str) -> dict[str, str]:
        """构造统一动作建议。"""

        return {
            "action": action,
            "label": label,
            "target_page": target_page,
        }

    @staticmethod
    def _build_result(
        *,
        status: str,
        headline: str,
        detail: str,
        symbol: str,
        recommended_stage: str,
        research_action: str,
        reason_items: list[str],
        blocking_items: list[dict[str, object]],
        suggested_action: dict[str, str],
        automation_status: dict[str, object],
    ) -> dict[str, object]:
        """整理统一仲裁输出。"""

        state = dict(automation_status.get("state") or {})
        runtime_window = dict(automation_status.get("runtime_window") or {})
        execution_health = dict(automation_status.get("execution_health") or {})
        execution_state = dict(execution_health.get("execution_state") or {})
        return {
            "status": status,
            "headline": headline,
            "detail": detail,
            "symbol": symbol,
            "recommended_stage": recommended_stage,
            "research_action": research_action,
            "reason_items": reason_items,
            "blocking_items": blocking_items,
            "suggested_action": suggested_action,
            "inputs": {
                "mode": str(state.get("mode", "") or ""),
                "manual_takeover": bool(state.get("manual_takeover")),
                "paused": bool(state.get("paused")),
                "runtime_blocked_reason": str(runtime_window.get("blocked_reason", "") or ""),
                "runtime_next_action": str(runtime_window.get("next_action", "") or ""),
                "latest_sync_status": str(execution_health.get("latest_sync_status", "") or ""),
                "execution_state": str(execution_state.get("state", "") or ""),
                "execution_recovery_action": str(execution_health.get("recovery_action", "") or ""),
            },
        }


research_execution_arbitration_service = ResearchExecutionArbitrationService()
