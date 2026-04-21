"use client";

/* 这个文件负责显示研究任务状态，通过 WebSocket 接收实时推送，并在连接失败时降级为轮询。 */

import Link from "next/link";
import { useMemo } from "react";

import type { ResearchRuntimeStatusModel } from "../lib/api";
import { useResearchRuntimeStatus } from "../lib/use-realtime-status";

type ResearchRuntimePanelProps = {
  initialStatus: ResearchRuntimeStatusModel;
};

const ACTION_LABELS: Record<string, string> = {
  training: "研究训练",
  inference: "研究推理",
  pipeline: "Qlib 信号流水线",
};

const STAGE_LABELS: Record<string, string> = {
  idle: "未运行",
  queued: "已进入后台",
  preparing_dataset: "准备数据",
  loading_model: "读取模型",
  training_model: "训练模型",
  running_inference: "生成候选",
  writing_signals: "回写信号",
  completed: "已完成",
  failed: "执行失败",
  interrupted: "任务中断",
  invalid_state: "状态异常",
};

export function ResearchRuntimePanel({ initialStatus }: ResearchRuntimePanelProps) {
  // 使用 WebSocket 实时状态 Hook（自动降级为轮询）
  const { status, isWebSocketConnected, isPollingFallback } = useResearchRuntimeStatus(initialStatus);

  const actionLabel = useMemo(() => ACTION_LABELS[status.action] ?? "研究任务", [status.action]);
  const stageLabel = useMemo(
    () => STAGE_LABELS[status.current_stage] ?? (status.current_stage || "未运行"),
    [status.current_stage],
  );
  const currentEstimate = status.current_estimate_seconds || status.estimated_seconds[status.action] || 0;

  // 连接状态提示
  const connectionHint = isWebSocketConnected
    ? "实时推送"
    : isPollingFallback
      ? "轮询模式"
      : "已连接";

  return (
    <section className="rounded-2xl border border-border/70 bg-card/90 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.28)] backdrop-blur">
      <div className="flex flex-col gap-2">
        <p className="eyebrow">研究运行状态</p>
        <h3 className="text-lg font-semibold tracking-tight text-foreground">点了之后，不用再猜系统是不是还在跑</h3>
        <p className="text-sm leading-6 text-muted-foreground">{status.message}</p>
        {isPollingFallback && (
          <p className="text-xs text-muted-foreground/60">WebSocket 断开，已切换为轮询模式</p>
        )}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <InfoBlock label="当前动作" value={actionLabel} />
        <InfoBlock label="当前阶段" value={stageLabel} />
        <InfoBlock label="预计时长" value={currentEstimate > 0 ? `${currentEstimate} 秒左右` : "暂时未知"} />
        <InfoBlock label="上次完成" value={status.last_completed_action ? `${ACTION_LABELS[status.last_completed_action] ?? status.last_completed_action}` : "还没有"} />
      </div>

      <div className="mt-5 space-y-3">
        <div className="flex items-center justify-between gap-3 text-sm text-muted-foreground">
          <span>进度条</span>
          <span>{Math.max(0, Math.min(100, status.progress_pct))}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-muted/30">
          <div
            className="h-full rounded-full bg-primary transition-all duration-500"
            style={{ width: `${Math.max(0, Math.min(100, status.progress_pct))}%` }}
          />
        </div>
      </div>

      <div className="mt-5 rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/80 p-4">
        <p className="eyebrow">完成后去哪里看</p>
        <div className="mt-3 flex flex-wrap gap-3">
          {status.result_paths.map((path) => (
            <Link
              key={path}
              href={path}
              className="inline-flex items-center justify-center rounded-xl border border-border bg-transparent px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
            >
              {path === "/research" ? "研究工作台" : path === "/evaluation" ? "评估与实验中心" : path === "/signals" ? "信号页" : path}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}

function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/80 p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-3 text-base font-semibold text-foreground">{value}</p>
    </div>
  );
}