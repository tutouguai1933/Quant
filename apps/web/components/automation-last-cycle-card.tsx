"use client";

/* 这个文件负责显示自动化周期状态，通过 WebSocket 接收实时推送，并在连接失败时降级为轮询。 */

import { useMemo } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { useAutomationStatus } from "../lib/use-realtime-status";

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
  // 使用 WebSocket 实时状态 Hook（自动降级为轮询）
  const { cycle, isWebSocketConnected, isPollingFallback } = useAutomationStatus(initialCycle);

  // 将 Record 转换为 CycleState
  const cycleState: CycleState = useMemo(() => ({
    source: String(cycle.source ?? ""),
    recommendedSymbol: String(cycle.recommendedSymbol ?? ""),
    recommendedStrategyId: String(cycle.recommendedStrategyId ?? ""),
    dispatchStatus: String(cycle.dispatchStatus ?? ""),
    orderSymbol: String(cycle.orderSymbol ?? ""),
    orderStatus: String(cycle.orderStatus ?? ""),
    failureReason: String(cycle.failureReason ?? ""),
    message: String(cycle.message ?? ""),
    nextAction: String(cycle.nextAction ?? ""),
    triggerSource: String(cycle.triggerSource ?? ""),
  }), [cycle]);

  const workflowSource = useMemo(() => formatWorkflowSource(cycleState.source), [cycleState.source]);

  return (
    <Card>
      <CardHeader>
        <p className="eyebrow">本轮自动化判断</p>
        <CardTitle>先看为什么推荐、为什么阻塞、为什么执行</CardTitle>
        <CardDescription>
          {isPollingFallback
            ? "WebSocket 断开，已切换为轮询模式。"
            : "这里直接收口最近一轮自动化工作流的关键判断，不需要自己翻任务列表和复盘结果去拼。"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
        <p>最近工作流来源：{workflowSource}</p>
        <p>推荐标的：{cycleState.recommendedSymbol || "n/a"}</p>
        <p>推荐策略实例：{cycleState.recommendedStrategyId || "n/a"}</p>
        <p>派发结果：{cycleState.dispatchStatus || "waiting"}</p>
        <p>最近订单：{cycleState.orderSymbol || "n/a"} / {cycleState.orderStatus || "n/a"}</p>
        <p>失败原因：{cycleState.failureReason || "当前没有新的失败原因。"}</p>
        <p>本轮说明：{cycleState.message || "当前还没有新的自动化判断。"}</p>
        <p>下一步：{cycleState.nextAction || "n/a"}</p>
        <p>触发来源：{cycleState.triggerSource || "n/a"}</p>
      </CardContent>
    </Card>
  );
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