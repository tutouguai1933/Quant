"use client";

/**
 * 实时状态订阅 Hooks。
 *
 * useResearchRuntimeStatus - 研究运行时状态（WebSocket + 轮询降级）
 * useAutomationStatus - 自动化周期状态（WebSocket + 轮询降级）
 */

import { useEffect, useState } from "react";
import { useWebSocket } from "./websocket-context";
import type { ResearchResultSnapshot, ResearchRunRecord, ResearchRuntimeStatusModel } from "./api";

// WebSocket 通道名称
const CHANNEL_RESEARCH_RUNTIME = "research_runtime";
const CHANNEL_AUTOMATION_STATUS = "automation_status";

// 轮询配置
const POLL_INTERVAL_RESEARCH = 2000; // 研究运行时轮询间隔
const POLL_INTERVAL_AUTOMATION = 3000; // 自动化状态轮询间隔

/**
 * 研究运行时实时状态 Hook
 *
 * 当 WebSocket 连接时，使用实时推送；
 * 当 WebSocket 断开且 running 状态时，降级为轮询。
 */
export function useResearchRuntimeStatus(
  initialStatus: ResearchRuntimeStatusModel
): {
  status: ResearchRuntimeStatusModel;
  isWebSocketConnected: boolean;
  isPollingFallback: boolean;
} {
  const { status: wsStatus, channelMessages, subscribe, unsubscribe } = useWebSocket();
  const [currentStatus, setCurrentStatus] = useState<ResearchRuntimeStatusModel>(initialStatus);
  const [isPollingFallback, setIsPollingFallback] = useState(false);

  // WebSocket 连接时订阅通道
  useEffect(() => {
    if (wsStatus === "connected") {
      subscribe(CHANNEL_RESEARCH_RUNTIME);
    }

    return () => {
      if (wsStatus === "connected") {
        unsubscribe(CHANNEL_RESEARCH_RUNTIME);
      }
    };
  }, [wsStatus, subscribe, unsubscribe]);

  // 处理 WebSocket 推送消息
  useEffect(() => {
    const message = channelMessages[CHANNEL_RESEARCH_RUNTIME];
    if (!message || wsStatus !== "connected") return;

    const data = message.data as Record<string, unknown>;
    if (data && typeof data === "object") {
      setCurrentStatus(normalizeResearchRuntimeStatus(data));
      setIsPollingFallback(false);
    }
  }, [channelMessages, wsStatus]);

  // 降级轮询：仅在 WebSocket 断开且 running 状态时激活
  useEffect(() => {
    if (wsStatus === "connected") return;
    if (currentStatus.status !== "running") return;

    setIsPollingFallback(true);

    const timer = window.setInterval(async () => {
      try {
        const response = await fetch("/api/control/signals/research/runtime", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const payload = await response.json();
        const item = payload?.data?.item;
        if (item && typeof item === "object") {
          setCurrentStatus(normalizeResearchRuntimeStatus(item as Record<string, unknown>));
        }
      } catch {
        // 保留当前状态，避免页面闪烁
      }
    }, POLL_INTERVAL_RESEARCH);

    return () => window.clearInterval(timer);
  }, [wsStatus, currentStatus.status]);

  return {
    status: currentStatus,
    isWebSocketConnected: wsStatus === "connected",
    isPollingFallback,
  };
}

/**
 * 自动化状态实时 Hook
 *
 * 当 WebSocket 连接时，使用实时推送；
 * 当 WebSocket 断开时，降级为轮询。
 */
export function useAutomationStatus(
  initialCycle: Record<string, unknown>
): {
  cycle: Record<string, unknown>;
  isWebSocketConnected: boolean;
  isPollingFallback: boolean;
} {
  const { status: wsStatus, channelMessages, subscribe, unsubscribe } = useWebSocket();
  const [cycle, setCycle] = useState<Record<string, unknown>>(initialCycle);
  const [isPollingFallback, setIsPollingFallback] = useState(false);

  // WebSocket 连接时订阅通道
  useEffect(() => {
    if (wsStatus === "connected") {
      subscribe(CHANNEL_AUTOMATION_STATUS);
    }

    return () => {
      if (wsStatus === "connected") {
        unsubscribe(CHANNEL_AUTOMATION_STATUS);
      }
    };
  }, [wsStatus, subscribe, unsubscribe]);

  // 处理 WebSocket 推送消息
  useEffect(() => {
    const message = channelMessages[CHANNEL_AUTOMATION_STATUS];
    if (!message || wsStatus !== "connected") return;

    const data = message.data as Record<string, unknown>;
    if (data && typeof data === "object") {
      if (data.type === "alert") {
        // 告警类型：可以触发 UI 提示
        setCycle((prev) => ({
          ...prev,
          latest_alert: data,
        }));
      } else {
        // 状态更新
        setCycle(normalizeAutomationStatus(data));
      }
      setIsPollingFallback(false);
    }
  }, [channelMessages, wsStatus]);

  // 降级轮询：WebSocket 断开时始终激活
  useEffect(() => {
    if (wsStatus === "connected") return;

    setIsPollingFallback(true);

    const timer = window.setInterval(async () => {
      try {
        const response = await fetch("/api/control/tasks/automation", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const payload = await response.json();
        const item = payload?.data?.item;
        const state = item?.state;
        const nextCycle = normalizeAutomationStatus(state?.last_cycle ?? {});
        setCycle(nextCycle);
      } catch {
        // 保留当前状态
      }
    }, POLL_INTERVAL_AUTOMATION);

    return () => window.clearInterval(timer);
  }, [wsStatus]);

  return {
    cycle,
    isWebSocketConnected: wsStatus === "connected",
    isPollingFallback,
  };
}

// 辅助函数：规范化研究运行时状态
function normalizeResearchRuntimeStatus(item: Record<string, unknown>): ResearchRuntimeStatusModel {
  const estimatedSeconds = item.estimated_seconds as Record<string, unknown> | undefined;
  return {
    status: String(item.status ?? "idle"),
    action: String(item.action ?? ""),
    current_stage: String(item.current_stage ?? "idle"),
    progress_pct: Number(item.progress_pct ?? 0),
    started_at: String(item.started_at ?? ""),
    finished_at: String(item.finished_at ?? ""),
    message: String(item.message ?? "当前没有研究任务在运行。"),
    last_completed_action: String(item.last_completed_action ?? ""),
    last_finished_at: String(item.last_finished_at ?? ""),
    result_paths: Array.isArray(item.result_paths)
      ? item.result_paths.map((v) => String(v ?? ""))
      : ["/research", "/evaluation", "/signals"],
    history: normalizeHistoryRecord(item.history),
    estimated_seconds: {
      training: Number(estimatedSeconds?.training ?? 25),
      inference: Number(estimatedSeconds?.inference ?? 12),
      pipeline: Number(estimatedSeconds?.pipeline ?? 40),
    },
    current_estimate_seconds: Number(item.current_estimate_seconds ?? 0),
  };
}

// 辅助函数：规范化历史记录
function normalizeHistoryRecord(value: unknown): Record<string, ResearchRunRecord[]> {
  if (!isPlainObject(value)) return {};
  const obj = value as Record<string, unknown>;
  const result: Record<string, ResearchRunRecord[]> = {};

  for (const [key, arr] of Object.entries(obj)) {
    if (!Array.isArray(arr)) continue;

    const validRecords: ResearchRunRecord[] = [];
    for (const v of arr) {
      if (isPlainObject(v)) {
        const record = v as Record<string, unknown>;
        // 只保留有时间戳的记录
        if (record.started_at && record.finished_at) {
          const snapshot = record.result_snapshot;
          validRecords.push({
            started_at: String(record.started_at ?? ""),
            finished_at: String(record.finished_at ?? ""),
            duration_seconds: Number(record.duration_seconds ?? 0),
            status: String(record.status ?? "unknown"),
            message: String(record.message ?? ""),
            result_snapshot: normalizeResultSnapshot(snapshot),
          });
        }
      }
    }

    if (validRecords.length > 0) {
      result[key] = validRecords;
    }
  }

  return result;
}

// 辅助函数：规范化结果快照
function normalizeResultSnapshot(value: unknown): ResearchResultSnapshot | null {
  if (!isPlainObject(value)) return null;
  const snapshot = value as Record<string, unknown>;
  const candidates = snapshot.top_candidates;
  return {
    recommended_symbol: String(snapshot.recommended_symbol ?? ""),
    recommended_strategy_id: String(snapshot.recommended_strategy_id ?? ""),
    top_candidates: Array.isArray(candidates) ? candidates.map((c) => String(c ?? "")) : [],
    model_version: String(snapshot.model_version ?? ""),
    research_template: String(snapshot.research_template ?? ""),
    signal_count: Number(snapshot.signal_count ?? 0),
  };
}

// 辅助函数：规范化自动化状态
function normalizeAutomationStatus(value: Record<string, unknown>): Record<string, unknown> {
  const dispatch = asRecord(value.dispatch);
  const dispatchMeta = asRecord(dispatch.meta);
  const dispatchItem = asRecord(dispatch.item);
  const dispatchOrder = asRecord(dispatchItem.order);
  return {
    source: readText(value.source),
    recommendedSymbol: readText(value.recommended_symbol),
    recommendedStrategyId: readText(value.recommended_strategy_id),
    dispatchStatus: readText(dispatch.status),
    orderSymbol: readText(dispatchOrder.symbol),
    orderStatus: readText(dispatchOrder.status),
    failureReason: readText(value.failure_reason),
    message: readText(value.message),
    nextAction: readText(value.next_action),
    triggerSource: readText(dispatchMeta.source),
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  return value as Record<string, unknown>;
}

function isPlainObject(value: unknown): boolean {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function readText(value: unknown): string {
  return typeof value === "string" ? value : "";
}