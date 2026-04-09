"use client";

/* 这个文件负责在任务页刷新最近一轮自动化判断，避免首屏 fallback 把手动流水线结果盖掉。 */

import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type AutomationLastCycleCardProps = {
  initialCycle: Record<string, unknown>;
};

type CycleState = {
  source: string;
  recommendedSymbol: string;
  recommendedStrategyId: string;
  dispatchStatus: string;
  orderSymbol: string;
  orderStatus: string;
  failureReason: string;
  message: string;
  nextAction: string;
  triggerSource: string;
};

export function AutomationLastCycleCard({ initialCycle }: AutomationLastCycleCardProps) {
  const [cycle, setCycle] = useState<CycleState>(() => normalizeCycle(initialCycle));

  useEffect(() => {
    setCycle(normalizeCycle(initialCycle));
  }, [initialCycle]);

  useEffect(() => {
    let cancelled = false;

    async function loadLatestCycle() {
      try {
        const response = await fetch("/api/control/tasks/automation", {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        const payload = await response.json();
        const item = payload?.data?.item;
        const state = item && typeof item === "object" && item.state && typeof item.state === "object"
          ? item.state
          : {};
        const nextCycle = normalizeCycle(
          state && typeof state === "object" && !Array.isArray(state) ? ((state as Record<string, unknown>).last_cycle as Record<string, unknown> | undefined) ?? {} : {},
        );
        if (!cancelled) {
          setCycle(nextCycle);
        }
      } catch {
        // 客户端刷新失败时保留首屏内容，避免界面闪烁。
      }
    }

    void loadLatestCycle();
    const timer = window.setInterval(() => {
      void loadLatestCycle();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const workflowSource = useMemo(() => formatWorkflowSource(cycle.source), [cycle.source]);

  return (
    <Card>
      <CardHeader>
        <p className="eyebrow">本轮自动化判断</p>
        <CardTitle>先看为什么推荐、为什么阻塞、为什么执行</CardTitle>
        <CardDescription>这里直接收口最近一轮自动化工作流的关键判断，不需要自己翻任务列表和复盘结果去拼。</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
        <p>最近工作流来源：{workflowSource}</p>
        <p>推荐标的：{cycle.recommendedSymbol || "n/a"}</p>
        <p>推荐策略实例：{cycle.recommendedStrategyId || "n/a"}</p>
        <p>派发结果：{cycle.dispatchStatus || "waiting"}</p>
        <p>最近订单：{cycle.orderSymbol || "n/a"} / {cycle.orderStatus || "n/a"}</p>
        <p>失败原因：{cycle.failureReason || "当前没有新的失败原因。"}</p>
        <p>本轮说明：{cycle.message || "当前还没有新的自动化判断。"}</p>
        <p>下一步：{cycle.nextAction || "n/a"}</p>
        <p>触发来源：{cycle.triggerSource || "n/a"}</p>
      </CardContent>
    </Card>
  );
}

function normalizeCycle(value: Record<string, unknown>): CycleState {
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
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return value as Record<string, unknown>;
}

function readText(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function formatWorkflowSource(value: string): string {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "自动化工作流";
  }
  if (normalized === "manual_pipeline") {
    return "手动信号流水线";
  }
  if (normalized === "automation") {
    return "自动化工作流";
  }
  return normalized;
}
