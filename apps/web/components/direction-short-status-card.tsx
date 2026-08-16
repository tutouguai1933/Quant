"use client";

/**
 * 方向做空（模拟盘）状态卡
 * 显示：模型 16 币平均分数、做空状态（已开空/等待中/已平仓）、
 * 开空时间与模拟盘盈亏。数据来自 /signals/research/direction-short-status，
 * 默认每 60 秒自动刷新，供观察期随时查看。
 */

import { useEffect, useState } from "react";
import { TerminalCard, InfoBlock } from "./terminal";
import {
  DEFAULT_API_TIMEOUT,
  getDirectionShortStatus,
  getDirectionShortStatusFallback,
  type DirectionShortStatusModel,
  type DirectionShortTrade,
} from "../lib/api";

interface DirectionShortStatusCardProps {
  token?: string | null;
  refreshInterval?: number;
}

type PositionView = {
  label: string;
  tone: "positive" | "negative" | "neutral" | "warning";
};

export function DirectionShortStatusCard({ token, refreshInterval = 60_000 }: DirectionShortStatusCardProps) {
  const [data, setData] = useState<DirectionShortStatusModel>(getDirectionShortStatusFallback());
  const [isLoading, setIsLoading] = useState(true);
  const [degraded, setDegraded] = useState(false);
  const [updatedAt, setUpdatedAt] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), DEFAULT_API_TIMEOUT);
      try {
        const response = await getDirectionShortStatus(token ?? undefined, controller.signal);
        if (cancelled) return;
        if (response.error) {
          setDegraded(true);
        } else {
          setDegraded(false);
          setData(response.data);
        }
        setUpdatedAt(
          new Date().toLocaleTimeString("zh-CN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          })
        );
      } catch {
        if (!cancelled) setDegraded(true);
      } finally {
        clearTimeout(timeoutId);
        if (!cancelled) setIsLoading(false);
      }
    }

    fetchData();
    const intervalId = setInterval(fetchData, refreshInterval);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [token, refreshInterval]);

  const { market, state, simulation } = data;
  const openPosition = simulation.open_position;

  /* 以模拟盘真实持仓为准推导展示状态；状态文件与持仓不一致时明确提示 */
  const positionView = resolvePositionView(data);

  return (
    <TerminalCard title="方向做空（模拟盘）">
      <div className="space-y-3 text-sm">
        {/* 状态不一致提示：状态文件说已开空但模拟盘实际无空仓 */}
        {data.position_state_mismatch && (
          <div className="rounded border border-[var(--terminal-yellow)]/40 bg-[var(--terminal-yellow)]/10 p-2 text-xs text-[var(--terminal-yellow)]">
            状态记录为已开空，但模拟盘当前无空仓（可能已被止损/策略平仓），调度状态待同步。
          </div>
        )}

        {/* 模拟盘接口不可达提示 */}
        {degraded && (
          <div className="rounded border border-[var(--terminal-red)]/40 bg-[var(--terminal-red)]/10 p-2 text-xs text-[var(--terminal-red)]">
            状态数据暂不可用，可能后端正在更新，请稍后刷新。
          </div>
        )}

        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <InfoBlock label="模型平均分数" value={market.avg_score !== null ? market.avg_score.toFixed(4) : "--"} />
          <InfoBlock label="做空状态" value={positionView.label} />
          <InfoBlock label="开空时间" value={formatOpenTime(openPosition, state.opened_at)} />
          <InfoBlock label="模拟盈亏" value={formatProfit(openPosition, simulation.last_closed_trade)} />
        </div>

        {/* 补充信息：信号方向 / 持仓详情 / 最近决策 */}
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 text-xs">
          <div className="rounded border border-[var(--terminal-border)] p-2">
            <span className="text-[var(--terminal-dim)]">信号方向 </span>
            <span className={directionColor(market.direction)}>{directionLabel(market.direction, market.short_trigger, market.flat_trigger)}</span>
            <span className="ml-1 text-[var(--terminal-dim)]">（阈值：&lt;0.38 开空，&gt;0.45 平空）</span>
          </div>
          <div className="rounded border border-[var(--terminal-border)] p-2">
            <span className="text-[var(--terminal-dim)]">模型版本 </span>
            <span className="text-[var(--terminal-text)] font-mono">{market.model_version || "--"}</span>
            <span className="ml-1 text-[var(--terminal-dim)]">{market.signal_count > 0 ? `${market.signal_count} 币` : "暂无推理"}</span>
          </div>
          <div className="rounded border border-[var(--terminal-border)] p-2">
            <span className="text-[var(--terminal-dim)]">最近决策 </span>
            <span className="text-[var(--terminal-text)]">{formatDateTime(state.last_decision_at) || "--"}</span>
            {state.last_avg_score !== null && (
              <span className="ml-1 text-[var(--terminal-dim)]">分数 {state.last_avg_score.toFixed(4)}</span>
            )}
          </div>
        </div>

        {/* 已平仓时展示最近一笔成交结果，观察期复盘更直观 */}
        {!openPosition && simulation.last_closed_trade && (
          <div className="rounded border border-[var(--terminal-border)] p-2 text-xs">
            <span className="text-[var(--terminal-dim)]">最近一笔已平仓：</span>
            <span className="font-mono text-[var(--terminal-text)]">
              {formatTradeResult(simulation.last_closed_trade)}
            </span>
            {simulation.last_closed_trade.exit_reason && (
              <span className="ml-1 text-[var(--terminal-dim)]">（{exitReasonLabel(simulation.last_closed_trade.exit_reason)}）</span>
            )}
          </div>
        )}

        {/* 底部：连接状态与刷新时间 */}
        <div className="flex items-center justify-between border-t border-[var(--terminal-border)]/30 pt-2 text-[11px] text-[var(--terminal-dim)]">
          <span>
            模拟盘连接：
            {isLoading ? (
              <span className="text-[var(--terminal-muted)]">检查中</span>
            ) : simulation.connected ? (
              <span className="text-[var(--terminal-green)]">正常</span>
            ) : (
              <span className="text-[var(--terminal-red)]">不可用</span>
            )}
          </span>
          {updatedAt && <span>更新于 {updatedAt}</span>}
        </div>
      </div>
    </TerminalCard>
  );
}

/* 根据状态文件与模拟盘真实持仓推导页面展示状态 */
function resolvePositionView(data: DirectionShortStatusModel): PositionView {
  if (data.simulation.open_position) {
    return { label: "已开空", tone: "positive" };
  }
  if (data.position_state_mismatch) {
    return { label: "已平仓（状态待同步）", tone: "warning" };
  }
  if (data.state.has_short_position && !data.simulation.connected) {
    return { label: "已开空（模拟盘暂不可用）", tone: "neutral" };
  }
  return { label: "等待中", tone: "neutral" };
}

/* 开空时间：优先持仓开盘时间，其次状态文件记录 */
function formatOpenTime(openPosition: DirectionShortTrade | null, stateOpenedAt: string): string {
  if (openPosition?.open_date) {
    return formatDateTime(openPosition.open_date);
  }
  return formatDateTime(stateOpenedAt) || "--";
}

/* 模拟盈亏：有持仓显示浮盈，无持仓显示最近一笔已实现盈亏 */
function formatProfit(openPosition: DirectionShortTrade | null, lastClosed: DirectionShortTrade | null): string {
  if (openPosition) {
    const abs = openPosition.profit_abs;
    const pct = openPosition.profit_pct;
    if (abs === null && pct === null) return "--";
    return `${signed(abs, 3)} USDT${pct !== null ? ` (${signed(pct, 2)}%)` : ""}`;
  }
  if (lastClosed) {
    const abs = lastClosed.realized_profit ?? lastClosed.profit_abs;
    const pct = lastClosed.realized_profit_ratio ?? lastClosed.profit_pct;
    if (abs === null && pct === null) return "暂无盈亏";
    return `已平仓 ${signed(abs, 3)} USDT${pct !== null ? ` (${signed(pct, 2)}%)` : ""}`;
  }
  return "暂无盈亏";
}

/* 已平仓交易的格式化结果（盈亏 + 比率） */
function formatTradeResult(trade: DirectionShortTrade): string {
  const abs = trade.realized_profit ?? trade.profit_abs;
  const pct = trade.realized_profit_ratio ?? trade.profit_pct;
  if (abs === null && pct === null) return "--";
  return `${signed(abs, 3)} USDT${pct !== null ? ` (${signed(pct, 2)}%)` : ""}`;
}

/* 带正负号的数值格式化，空值返回 -- */
function signed(value: number | null, digits: number): string {
  if (value === null || value === undefined) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

/* 把后端时间字符串截成易读的 YYYY-MM-DD HH:mm */
function formatDateTime(value: string): string {
  if (!value) return "";
  const normalized = value.replace("T", " ").replace("Z", "").slice(0, 16);
  return normalized;
}

function directionLabel(direction: string, shortTrigger: boolean, flatTrigger: boolean): string {
  if (shortTrigger) return "极度看跌（做空信号）";
  if (flatTrigger) return "转暖（平空信号）";
  if (direction === "bearish") return "看跌";
  if (direction === "bullish") return "看涨";
  if (direction === "neutral") return "中性";
  return "未知";
}

function directionColor(direction: string): string {
  if (direction === "bearish") return "text-[var(--terminal-red)]";
  if (direction === "bullish") return "text-[var(--terminal-green)]";
  return "text-[var(--terminal-muted)]";
}

function exitReasonLabel(reason: string): string {
  const labels: Record<string, string> = {
    stop_loss: "止损",
    trailing_stop_loss: "移动止损",
    exit_signal: "平仓信号",
    roi: "达到目标收益",
    force_exit: "手动平仓",
  };
  return labels[reason] || reason || "正常平仓";
}
