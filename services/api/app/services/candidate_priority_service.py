"""候选优先级服务。

这个文件负责把研究候选整理成统一优先级队列，并按自动化模式给出当前推进对象。
"""

from __future__ import annotations


class CandidatePriorityService:
    """统一生成候选优先级和调度摘要。"""

    def build_priority_queue(
        self,
        *,
        report: dict[str, object],
        candidate_scope: dict[str, object],
    ) -> dict[str, object]:
        """把研究报告整理成统一优先级队列。"""

        candidate_by_symbol = {
            str(item.get("symbol", "")).strip().upper(): dict(item)
            for item in list(report.get("candidates") or [])
            if isinstance(item, dict) and str(item.get("symbol", "")).strip()
        }
        source_items = self._resolve_source_items(report=report, candidate_by_symbol=candidate_by_symbol)
        queue_items: list[dict[str, object]] = []
        first_ready_symbol = ""

        for index, row in enumerate(source_items, start=1):
            item = self._build_queue_item(
                row=row,
                priority_rank=index,
                candidate_scope=candidate_scope,
            )
            if item["queue_status"] == "ready" and not first_ready_symbol:
                first_ready_symbol = str(item.get("symbol", ""))
            queue_items.append(item)

        if first_ready_symbol:
            for item in queue_items:
                if item["queue_status"] != "ready":
                    continue
                symbol = str(item.get("symbol", ""))
                if symbol == first_ready_symbol:
                    continue
                item["skip_reason"] = f"前面还有更高优先级候选 {first_ready_symbol}。"

        return {
            "items": queue_items,
            "summary": self._build_priority_summary(queue_items=queue_items),
        }

    def build_dispatch_queue(
        self,
        *,
        priority_queue: dict[str, object],
        mode: str,
        armed_symbol: str,
    ) -> dict[str, object]:
        """按当前自动化模式，把优先级队列转换成可执行调度队列。"""

        normalized_mode = str(mode or "manual").strip().lower()
        target_armed_symbol = str(armed_symbol or "").strip().upper()
        source_items = [
            dict(item)
            for item in list(priority_queue.get("items") or [])
            if isinstance(item, dict)
        ]
        dispatch_items: list[dict[str, object]] = []
        active_symbol = ""

        for item in source_items:
            row = dict(item)
            dispatch_status = "blocked"
            dispatch_code = "candidate_blocked"
            dispatch_reason = str(row.get("why_blocked", "") or row.get("skip_reason", "") or "当前候选还不能继续推进。")
            recommended_stage = str(row.get("recommended_stage", "research") or "research")
            symbol = str(row.get("symbol", "")).strip().upper()

            if normalized_mode == "manual":
                if row.get("queue_status") == "ready":
                    dispatch_status = "skipped"
                    dispatch_code = "manual_mode"
                    dispatch_reason = "当前仍在手动模式，需要先人工确认。"
            elif normalized_mode == "auto_live":
                if row.get("queue_status") != "ready":
                    dispatch_status = "blocked"
                    dispatch_code = "candidate_blocked"
                elif recommended_stage != "live":
                    dispatch_status = "skipped"
                    dispatch_code = "candidate_not_live_ready"
                    dispatch_reason = "当前还没放行到 live，先留在 dry-run。"
                elif not target_armed_symbol:
                    dispatch_status = "skipped"
                    dispatch_code = "awaiting_dry_run_confirmation"
                    dispatch_reason = "当前候选还没有完成上一轮 dry-run 验证"
                elif symbol != target_armed_symbol:
                    dispatch_status = "skipped"
                    dispatch_code = "armed_symbol_mismatch"
                    dispatch_reason = f"当前已完成 dry-run 验证的是 {target_armed_symbol}，这一轮不能直接切到 {symbol}。"
                elif not active_symbol:
                    dispatch_status = "active"
                    dispatch_code = "dispatch_ready"
                    dispatch_reason = "当前先推进这个候选。"
                    active_symbol = symbol
                else:
                    dispatch_status = "standby"
                    dispatch_code = "waiting_higher_priority"
                    dispatch_reason = f"前面还有更高优先级候选 {active_symbol}。"
            else:
                if row.get("queue_status") != "ready":
                    dispatch_status = "blocked"
                    dispatch_code = "candidate_blocked"
                elif not active_symbol:
                    dispatch_status = "active"
                    dispatch_code = "dispatch_ready"
                    dispatch_reason = "当前先推进这个候选。"
                    active_symbol = symbol
                else:
                    dispatch_status = "standby"
                    dispatch_code = "waiting_higher_priority"
                    dispatch_reason = f"前面还有更高优先级候选 {active_symbol}。"

            row["dispatch_status"] = dispatch_status
            row["dispatch_code"] = dispatch_code
            row["dispatch_reason"] = dispatch_reason
            dispatch_items.append(row)

        return {
            "items": dispatch_items,
            "summary": self._build_dispatch_summary(
                items=dispatch_items,
                mode=normalized_mode,
                armed_symbol=target_armed_symbol,
            ),
        }

    def _resolve_source_items(
        self,
        *,
        report: dict[str, object],
        candidate_by_symbol: dict[str, dict[str, object]],
    ) -> list[dict[str, object]]:
        """把 leaderboard 和 candidate 明细合并成稳定排序源。"""

        items: list[dict[str, object]] = []
        used_symbols: set[str] = set()

        for row in list(report.get("leaderboard") or []):
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            items.append(
                {
                    **candidate_by_symbol.get(symbol, {}),
                    **dict(row),
                    "symbol": symbol,
                    "rank": row.get("rank", len(items) + 1),
                    "execution_priority": (
                        dict(row).get("execution_priority")
                        if dict(row).get("execution_priority") is not None
                        else candidate_by_symbol.get(symbol, {}).get("execution_priority", len(items))
                    ),
                }
            )
            used_symbols.add(symbol)

        remaining_candidates = [
            {
                **dict(item),
                "rank": dict(item).get("rank", len(items) + index + 1),
                "execution_priority": (
                    dict(item).get("execution_priority")
                    if dict(item).get("execution_priority") is not None
                    else len(items) + index
                ),
            }
            for index, (symbol, item) in enumerate(candidate_by_symbol.items())
            if symbol not in used_symbols
        ]
        remaining_candidates.sort(key=self._sort_key)
        items.extend(remaining_candidates)
        items.sort(key=self._sort_key)
        return items

    def _build_queue_item(
        self,
        *,
        row: dict[str, object],
        priority_rank: int,
        candidate_scope: dict[str, object],
    ) -> dict[str, object]:
        """生成单个候选的统一队列说明。"""

        symbol = str(row.get("symbol", "")).strip().upper()
        next_action = str(row.get("next_action", "") or "").strip() or (
            "enter_dry_run" if bool(row.get("allowed_to_dry_run")) else "continue_research"
        )
        requested_stage = self._resolve_requested_stage(next_action=next_action, symbol=symbol)
        resolved_stage, queue_status, blocked_by, detail = self._resolve_stage_and_reason(
            row=row,
            candidate_scope=candidate_scope,
            requested_stage=requested_stage,
        )
        return {
            "priority_rank": priority_rank,
            "symbol": symbol,
            "score": str(row.get("score", "") or ""),
            "strategy_template": str(row.get("strategy_template", "") or ""),
            "research_template": str(row.get("research_template", "") or ""),
            "execution_priority": self._parse_int(row.get("execution_priority"), default=999999),
            "review_status": str(row.get("review_status", "") or ""),
            "forced_for_validation": bool(row.get("forced_for_validation")),
            "forced_reason": str(row.get("forced_reason", "") or ""),
            "requested_stage": requested_stage,
            "recommended_stage": resolved_stage,
            "queue_status": queue_status,
            "next_action": next_action,
            "target_page": "/strategies" if resolved_stage in {"dry_run", "live"} else "/research",
            "allowed_to_dry_run": bool(row.get("allowed_to_dry_run")),
            "allowed_to_live": bool(row.get("allowed_to_live")),
            "dry_run_gate": dict(row.get("dry_run_gate") or {}),
            "live_gate": dict(row.get("live_gate") or {}),
            "failure_reasons": [
                str(reason).strip()
                for reason in list(row.get("failure_reasons") or [])
                if str(reason).strip()
            ],
            "why_selected": detail if queue_status == "ready" else "",
            "why_blocked": detail if queue_status == "blocked" else "",
            "blocked_by": blocked_by,
            "skip_reason": "",
        }

    def _resolve_stage_and_reason(
        self,
        *,
        row: dict[str, object],
        candidate_scope: dict[str, object],
        requested_stage: str,
    ) -> tuple[str, str, str, str]:
        """根据范围契约和门控结果，判断候选现在该落在哪一层。"""

        symbol = str(row.get("symbol", "")).strip().upper()
        allowed_to_dry_run = bool(row.get("allowed_to_dry_run"))
        allowed_to_live = bool(row.get("allowed_to_live"))
        scope_reason_live = self._candidate_scope_block_reason(candidate_scope=candidate_scope, stage="live", symbol=symbol)
        scope_reason_dry_run = self._candidate_scope_block_reason(candidate_scope=candidate_scope, stage="dry_run", symbol=symbol)
        dry_run_reason = self._first_reason(dict(row.get("dry_run_gate") or {}), list(row.get("failure_reasons") or []))
        live_reason = self._first_reason(dict(row.get("live_gate") or {}), [])

        if requested_stage == "live":
            if allowed_to_live and not scope_reason_live:
                return "live", "ready", "", f"{symbol} 当前已经满足 live 条件。"
            if allowed_to_dry_run and not scope_reason_dry_run:
                detail = scope_reason_live or live_reason or f"{symbol} 当前先留在 dry-run，等 live 条件补齐。"
                return "dry_run", "ready", "live_guard", detail
            detail = scope_reason_live or scope_reason_dry_run or live_reason or dry_run_reason or f"{symbol} 当前还不能继续推进。"
            return "research", "blocked", "live_guard", detail

        if requested_stage == "dry_run":
            if allowed_to_dry_run and not scope_reason_dry_run:
                return "dry_run", "ready", "", f"{symbol} 当前优先进入 dry-run。"
            detail = scope_reason_dry_run or dry_run_reason or f"{symbol} 当前还没通过 dry-run 门。"
            return "research", "blocked", "dry_run_gate", detail

        detail = dry_run_reason or self._raw_reason(row) or f"{symbol} 当前还需要继续研究。"
        return "research", "blocked", "research", detail

    def _build_priority_summary(self, *, queue_items: list[dict[str, object]]) -> dict[str, object]:
        """生成基础优先级摘要。"""

        ready_items = [item for item in queue_items if item.get("queue_status") == "ready"]
        blocked_items = [item for item in queue_items if item.get("queue_status") == "blocked"]
        active_symbol = str((ready_items[0] or {}).get("symbol", "") if ready_items else "")
        next_symbol = str((ready_items[1] or {}).get("symbol", "") if len(ready_items) > 1 else "")
        focus_item = dict((ready_items[0] if ready_items else blocked_items[0]) or {}) if (ready_items or blocked_items) else {}
        detail = str(focus_item.get("why_selected", "") or focus_item.get("why_blocked", "") or "当前还没有可推进候选。")
        headline = (
            f"当前先推进 {active_symbol}"
            if active_symbol
            else f"{str(focus_item.get('symbol', '') or '当前候选')} 还需要继续补研究"
            if focus_item
            else "当前还没有可推进候选"
        )
        return {
            "headline": headline,
            "detail": detail,
            "focus_symbol": str(focus_item.get("symbol", "") or ""),
            "active_symbol": active_symbol,
            "next_symbol": next_symbol,
            "ready_count": len(ready_items),
            "blocked_count": len(blocked_items),
        }

    def _build_dispatch_summary(
        self,
        *,
        items: list[dict[str, object]],
        mode: str,
        armed_symbol: str,
    ) -> dict[str, object]:
        """生成按当前模式可直接消费的调度摘要。"""

        active_items = [item for item in items if item.get("dispatch_status") == "active"]
        standby_items = [item for item in items if item.get("dispatch_status") == "standby"]
        skipped_items = [item for item in items if item.get("dispatch_status") == "skipped"]
        blocked_items = [item for item in items if item.get("dispatch_status") == "blocked"]
        candidate_items = active_items + standby_items + skipped_items
        focus_item = dict((active_items[0] if active_items else skipped_items[0] if skipped_items else blocked_items[0]) or {}) if (active_items or skipped_items or blocked_items) else {}
        headline = (
            f"当前先推进 {str(active_items[0].get('symbol', '') or '')}"
            if active_items
            else f"{str(focus_item.get('symbol', '') or '当前候选')} 还不能直接推进"
            if focus_item
            else "当前还没有可推进候选"
        )
        detail = str(focus_item.get("dispatch_reason", "") or "当前还没有可推进候选。")
        if mode == "auto_live" and armed_symbol and not active_items and detail:
            detail = f"{detail} 当前已确认 dry-run 的币是 {armed_symbol}。"
        return {
            "headline": headline,
            "detail": detail,
            "active_symbol": str((active_items[0] or {}).get("symbol", "") if active_items else (candidate_items[0] or {}).get("symbol", "") if candidate_items else ""),
            "next_symbol": str((standby_items[0] or {}).get("symbol", "") if standby_items else (candidate_items[1] or {}).get("symbol", "") if len(candidate_items) > 1 else ""),
            "focus_symbol": str(focus_item.get("symbol", "") or ""),
            "ready_count": len(candidate_items),
            "skipped_count": len(skipped_items),
            "blocked_count": len(blocked_items),
            "mode": mode,
        }

    @staticmethod
    def _candidate_scope_block_reason(
        *,
        candidate_scope: dict[str, object],
        stage: str,
        symbol: str,
    ) -> str:
        """按范围契约返回候选为什么不能推进。"""

        target_symbol = str(symbol or "").strip().upper()
        status = str(candidate_scope.get("status", "candidate_pool_missing") or "candidate_pool_missing")
        candidate_symbols = {
            str(item).strip().upper()
            for item in list(candidate_scope.get("candidate_symbols") or [])
            if str(item).strip()
        }
        live_symbols = {
            str(item).strip().upper()
            for item in list(candidate_scope.get("live_allowed_symbols") or [])
            if str(item).strip()
        }
        removed_symbols = [
            str(item).strip().upper()
            for item in list(candidate_scope.get("live_removed_symbols") or [])
            if str(item).strip()
        ]
        if stage == "live":
            if status == "candidate_pool_missing":
                return "当前还没有统一候选池，先固定研究 / dry-run 范围。"
            if status == "live_subset_missing":
                return "当前 live 子集还没放行，先决定哪些币允许继续进入 live。"
            if status == "live_subset_out_of_scope":
                removed_summary = " / ".join(removed_symbols) if removed_symbols else "原 live 子集"
                return f"当前 live 子集已经和候选池脱节，先把 {removed_summary} 收回到当前候选池内。"
            if target_symbol not in candidate_symbols:
                return f"{target_symbol} 当前不在统一候选池内。"
            if target_symbol not in live_symbols:
                return f"{target_symbol} 当前不在 live 子集内，先留在 dry-run。"
            return ""
        if status == "candidate_pool_missing":
            return "当前还没有统一候选池，先在数据工作台选好研究 / dry-run 候选池。"
        if target_symbol not in candidate_symbols:
            return f"{target_symbol} 当前不在统一候选池内。"
        return ""

    @staticmethod
    def _resolve_requested_stage(*, next_action: str, symbol: str) -> str:
        """按下一步动作判断候选当前目标阶段。"""

        if not symbol.strip():
            return "research"
        action = str(next_action or "").strip().lower()
        if action in {"go_live", "enter_live"}:
            return "live"
        if action in {"go_dry_run", "enter_dry_run"}:
            return "dry_run"
        return "research"

    @staticmethod
    def _first_reason(gate: dict[str, object], fallback: list[object]) -> str:
        """优先取门控原因，没有时回退到已有失败原因。"""

        reasons = [str(reason).strip() for reason in list(gate.get("reasons") or []) if str(reason).strip()]
        if reasons:
            return reasons[0]
        fallback_reasons = [str(reason).strip() for reason in list(fallback or []) if str(reason).strip()]
        return fallback_reasons[0] if fallback_reasons else ""

    @classmethod
    def _raw_reason(cls, row: dict[str, object]) -> str:
        """读取候选已有的人话理由。"""

        for key in ("recommendation_reason", "elimination_reason", "review_status"):
            value = str(row.get(key, "") or "").strip()
            if value:
                return value
        return cls._first_reason(dict(row.get("dry_run_gate") or {}), list(row.get("failure_reasons") or []))

    @staticmethod
    def _sort_key(item: dict[str, object]) -> tuple[int, int, str]:
        """稳定排序：先执行优先级，再 rank，再 symbol。"""

        execution_priority = CandidatePriorityService._parse_int(item.get("execution_priority"), default=999999)
        rank = CandidatePriorityService._parse_int(item.get("rank"), default=999999)
        return execution_priority, rank, str(item.get("symbol", "")).strip().upper()

    @staticmethod
    def _parse_int(value: object, *, default: int) -> int:
        """安全把值转成整数。"""

        try:
            return int(value)
        except (TypeError, ValueError):
            return default


candidate_priority_service = CandidatePriorityService()
