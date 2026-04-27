"use client";

/* 这个文件负责显示研究任务状态，通过 WebSocket 接收实时推送，并在连接失败时降级为轮询。 */

import Link from "next/link";
import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import type { ResearchRunRecord, ResearchRuntimeStatusModel } from "../lib/api";
import { useResearchRuntimeStatus } from "../lib/use-realtime-status";
import { FullScreenModal } from "./full-screen-modal";
import { Button } from "./ui/button";

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

const PAGE_SIZE = 5;

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

  // 历史记录展示
  const history = status.history || {};
  const hasHistory = Object.keys(history).some(key => Array.isArray(history[key]) && history[key].length > 0);

  // 分页状态：每个动作类型独立分页
  const [pageByAction, setPageByAction] = useState<Record<string, number>>({});

  // 是否正在运行
  const isRunning = status.status === "running";

  return (
    <section className="rounded-2xl border border-border/70 bg-card/90 p-5 shadow-[0_24px_60px_rgba(0,0,0,0.28)] backdrop-blur">
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <p className="eyebrow">研究运行状态</p>
          {isRunning && (
            <div className="flex items-center gap-2 text-primary">
              <Loader2 className="size-4 animate-spin" />
              <span className="text-xs font-medium">正在运行</span>
            </div>
          )}
        </div>
        <h3 className="text-lg font-semibold tracking-tight text-foreground">
          {isRunning ? `${actionLabel} - ${stageLabel}` : "当前没有研究任务在运行"}
        </h3>
        <p className="text-sm leading-6 text-muted-foreground">{status.message}</p>
        {isPollingFallback && (
          <p className="text-xs text-muted-foreground/60">WebSocket 断开，已切换为轮询模式</p>
        )}
      </div>

      {/* 运行中显示进度 */}
      {isRunning && (
        <div className="mt-5 space-y-3">
          <div className="flex items-center justify-between gap-3 text-sm">
            <span className="text-muted-foreground">进度</span>
            <span className="font-medium text-foreground">{Math.max(0, Math.min(100, status.progress_pct))}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-muted/30">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${Math.max(0, Math.min(100, status.progress_pct))}%` }}
            />
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <InfoBlock label="当前动作" value={actionLabel} />
            <InfoBlock label="当前阶段" value={stageLabel} />
            <InfoBlock label="预计时长" value={currentEstimate > 0 ? `${currentEstimate} 秒左右` : "暂时未知"} />
            <InfoBlock label="上次完成" value={status.last_completed_action ? `${ACTION_LABELS[status.last_completed_action] ?? status.last_completed_action}` : "还没有"} />
          </div>
        </div>
      )}

      {/* 运行历史记录 */}
      {hasHistory && (
        <div className="mt-5 rounded-2xl border border-border/60 bg-[color:var(--panel-strong)]/80 p-4">
          <p className="eyebrow">运行历史</p>
          <div className="mt-3 grid gap-4">
            {Object.entries(history).map(([action, records]) => {
              if (!Array.isArray(records) || records.length === 0) return null;

              const actionLabel = ACTION_LABELS[action] ?? action;
              const currentPage = pageByAction[action] || 1;
              const totalPages = Math.ceil(records.length / PAGE_SIZE);
              const startIndex = (currentPage - 1) * PAGE_SIZE;
              const endIndex = startIndex + PAGE_SIZE;
              const pageRecords = records.slice().reverse().slice(startIndex, endIndex);

              return (
                <div key={action} className="space-y-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm font-medium text-foreground">{actionLabel}</p>
                    <p className="text-xs text-muted-foreground">共 {records.length} 条记录</p>
                  </div>

                  <div className="grid gap-2">
                    {pageRecords.map((record, index) => (
                      <RunHistoryItem
                        key={`${action}-${startIndex + index}`}
                        record={record}
                        actionLabel={actionLabel}
                      />
                    ))}
                  </div>

                  {/* 分页控制 */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-center gap-2 pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPage <= 1}
                        onClick={() => setPageByAction(prev => ({ ...prev, [action]: currentPage - 1 }))}
                      >
                        上一页
                      </Button>
                      <p className="text-sm text-muted-foreground">
                        第 {currentPage} 页 / 共 {totalPages} 页
                      </p>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={currentPage >= totalPages}
                        onClick={() => setPageByAction(prev => ({ ...prev, [action]: currentPage + 1 }))}
                      >
                        下一页
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

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

/* 渲染单条运行历史记录。 */
function RunHistoryItem({ record, actionLabel }: { record: ResearchRunRecord; actionLabel: string }) {
  const finishedTime = record.finished_at ? formatTimestamp(record.finished_at) : "未知时间";
  const duration = record.duration_seconds ? `${record.duration_seconds} 秒` : "未知时长";
  const statusLabel = record.status === "succeeded" ? "成功" : record.status === "failed" ? "失败" : "未知状态";
  const statusColor = record.status === "succeeded" ? "text-green-600" : record.status === "failed" ? "text-red-600" : "text-muted-foreground";

  return (
    <FullScreenModal
      triggerLabel={`${finishedTime} · ${statusLabel} · ${duration}`}
      title={`${actionLabel} 运行详情`}
      description={`查看 ${finishedTime} 完成的 ${actionLabel} 任务详情`}
      triggerVariant="outline"
      triggerSize="sm"
    >
      <div className="space-y-5">
        {/* 运行元数据 */}
        <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
          <p className="eyebrow">运行元数据</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <DetailItem label="开始时间" value={record.started_at ? formatTimestamp(record.started_at) : "未记录"} />
            <DetailItem label="完成时间" value={finishedTime} />
            <DetailItem label="运行时长" value={duration} />
            <DetailItem label="状态" value={statusLabel} valueClassName={statusColor} />
          </div>
        </div>

        {/* 运行消息 */}
        {record.message && (
          <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
            <p className="eyebrow">运行消息</p>
            <p className="mt-3 text-sm leading-6 text-foreground">{record.message}</p>
          </div>
        )}

        {/* 运行结果快照 */}
        {record.result_snapshot && (
          <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
            <p className="eyebrow">运行结果快照</p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <DetailItem
                label="推荐币种"
                value={record.result_snapshot.recommended_symbol || "无推荐"}
                valueClassName={record.result_snapshot.recommended_symbol ? "text-primary font-semibold" : ""}
              />
              <DetailItem
                label="推荐策略"
                value={record.result_snapshot.recommended_strategy_id ? `策略 #${record.result_snapshot.recommended_strategy_id}` : "无推荐"}
              />
              <DetailItem
                label="Top 候选"
                value={record.result_snapshot.top_candidates.length > 0 ? record.result_snapshot.top_candidates.join(" / ") : "无候选"}
              />
              <DetailItem
                label="模型版本"
                value={record.result_snapshot.model_version || "未记录"}
              />
              <DetailItem
                label="研究模板"
                value={record.result_snapshot.research_template || "未记录"}
              />
              <DetailItem
                label="信号数量"
                value={record.result_snapshot.signal_count > 0 ? `${record.result_snapshot.signal_count} 个` : "未生成"}
              />
            </div>
          </div>
        )}

        {/* 快捷跳转 */}
        <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
          <p className="eyebrow">快捷跳转</p>
          <div className="mt-4 flex flex-wrap gap-3">
            <Button asChild variant="terminal" size="sm">
              <Link href="/signals">去信号页看候选排行</Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/evaluation">去评估页看决策中心</Link>
            </Button>
          </div>
        </div>
      </div>
    </FullScreenModal>
  );
}

/* 渲染详情项。 */
function DetailItem({ label, value, valueClassName = "" }: { label: string; value: string; valueClassName?: string }) {
  return (
    <div className="space-y-1">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={`text-sm leading-6 text-foreground ${valueClassName}`}>{value}</p>
    </div>
  );
}

/* 格式化时间戳为本地时间字符串。 */
function formatTimestamp(timestamp: string): string {
  if (!timestamp) return "未知时间";
  try {
    const date = new Date(timestamp);
    return date.toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return timestamp;
  }
}