"use client";

/* 这个文件负责在前端轮询研究任务状态，并把进度、预计时长和结果去向显示出来。 */

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { ResearchRuntimeStatusModel } from "../lib/api";

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
  const [status, setStatus] = useState<ResearchRuntimeStatusModel>(initialStatus);

  useEffect(() => {
    setStatus(initialStatus);
  }, [initialStatus]);

  useEffect(() => {
    if (status.status !== "running") {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const response = await fetch("/api/control/signals/research/runtime", {
          headers: {
            Accept: "application/json",
          },
          cache: "no-store",
        });
        const payload = await response.json();
        const item = payload?.data?.item;
        if (item && typeof item === "object") {
          setStatus({
            status: String(item.status ?? "idle"),
            action: String(item.action ?? ""),
            current_stage: String(item.current_stage ?? "idle"),
            progress_pct: Number(item.progress_pct ?? 0),
            started_at: String(item.started_at ?? ""),
            finished_at: String(item.finished_at ?? ""),
            message: String(item.message ?? "当前没有研究任务在运行。"),
            last_completed_action: String(item.last_completed_action ?? ""),
            last_finished_at: String(item.last_finished_at ?? ""),
            result_paths: Array.isArray(item.result_paths) ? item.result_paths.map((value: unknown) => String(value ?? "")) : ["/research", "/evaluation", "/signals"],
            history: item.history && typeof item.history === "object" && !Array.isArray(item.history) ? item.history : {},
            estimated_seconds: item.estimated_seconds && typeof item.estimated_seconds === "object" && !Array.isArray(item.estimated_seconds)
              ? {
                  training: Number((item.estimated_seconds as Record<string, unknown>).training ?? 25),
                  inference: Number((item.estimated_seconds as Record<string, unknown>).inference ?? 12),
                  pipeline: Number((item.estimated_seconds as Record<string, unknown>).pipeline ?? 40),
                }
              : { training: 25, inference: 12, pipeline: 40 },
            current_estimate_seconds: Number(item.current_estimate_seconds ?? 0),
          });
        }
      } catch {
        // 轮询失败时保留当前状态，避免页面闪烁。
      }
    }, 2000);

    return () => window.clearInterval(timer);
  }, [status.status]);

  const actionLabel = useMemo(() => ACTION_LABELS[status.action] ?? "研究任务", [status.action]);
  const stageLabel = useMemo(
    () => STAGE_LABELS[status.current_stage] ?? (status.current_stage || "未运行"),
    [status.current_stage],
  );
  const currentEstimate = status.current_estimate_seconds || status.estimated_seconds[status.action] || 0;

  return (
    <section className="rounded-2xl border border-border/70 bg-card/90 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.28)] backdrop-blur">
      <div className="flex flex-col gap-2">
        <p className="eyebrow">研究运行状态</p>
        <h3 className="text-lg font-semibold tracking-tight text-foreground">点了之后，不用再猜系统是不是还在跑</h3>
        <p className="text-sm leading-6 text-muted-foreground">{status.message}</p>
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
