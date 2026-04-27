/* 这个文件负责把自动化状态压成首页、评估页、策略页共用的一份承接摘要。 */

import type { AutomationStatusModel } from "./api";

export type AutomationHandoffSummary = {
  status: string;
  headline: string;
  detail: string;
  targetLabel: string;
  targetHref: string;
  runtimeHeadline: string;
  runtimeDetail: string;
  reasonLabel: string;
  alertLevel: string;
  alertCode: string;
  nextCheckAt: string;
  takeoverReviewDueAt: string;
};

type BuildAutomationHandoffSummaryOptions = {
  automation: AutomationStatusModel | Record<string, unknown>;
  tasksHref: string;
  fallbackTargetHref: string;
  fallbackTargetLabel: string;
  fallbackHeadline: string;
  fallbackDetail: string;
};

/* 生成跨页面统一复用的自动化承接摘要。 */
export function buildAutomationHandoffSummary({
  automation,
  tasksHref,
  fallbackTargetHref,
  fallbackTargetLabel,
  fallbackHeadline,
  fallbackDetail,
}: BuildAutomationHandoffSummaryOptions): AutomationHandoffSummary {
  const recoveryReview = asRecord(automation.recoveryReview);
  const runtimeGuard = asRecord(automation.runtimeGuard);
  const arbitration = asRecord(automation.arbitration);
  const suggestedAction = asRecord(arbitration.suggested_action);
  const alertContext = asRecord(runtimeGuard.alert_context);
  const recoveryStatus = readText(recoveryReview.status, "waiting");
  const runtimeStatus = readText(runtimeGuard.status, recoveryStatus);
  const reasonLabel = readText(
    recoveryReview.reason_label,
    readText(runtimeGuard.reason_label, readText(recoveryReview.headline, fallbackHeadline)),
  );
  const headline = readText(
    recoveryReview.headline,
    readText(runtimeGuard.headline, readText(arbitration.headline, fallbackHeadline)),
  );
  const detail = readText(
    recoveryReview.detail,
    readText(runtimeGuard.detail, readText(arbitration.detail, fallbackDetail)),
  );
  const runtimeHeadline = readText(runtimeGuard.reason_label, readText(runtimeGuard.headline, reasonLabel || headline));
  const runtimeDetail = readText(runtimeGuard.detail, detail);
  const alertLevel = readText(alertContext.level, "normal");
  const alertCode = readText(alertContext.code, "");
  const nextCheckAt = readText(runtimeGuard.next_check_at, "");
  const takeoverReviewDueAt = readText(runtimeGuard.takeover_review_due_at, "");
  const shouldRouteTasks = ["attention_required", "degraded", "waiting", "blocked", "running"].includes(runtimeStatus)
    || ["attention_required", "waiting", "blocked", "running"].includes(recoveryStatus);
  let targetHref = readText(suggestedAction.target_page, fallbackTargetHref);
  let targetLabel = readText(
    suggestedAction.label,
    readText(recoveryReview.next_action_label, fallbackTargetLabel),
  );
  if (shouldRouteTasks) {
    targetHref = tasksHref;
    targetLabel = readText(recoveryReview.next_action_label, "去任务页处理自动化");
  }

  return {
    status: runtimeStatus || recoveryStatus,
    headline: headline || fallbackHeadline,
    detail: detail || fallbackDetail,
    targetLabel: targetLabel || fallbackTargetLabel,
    targetHref: targetHref || fallbackTargetHref,
    runtimeHeadline: runtimeHeadline || fallbackHeadline,
    runtimeDetail: runtimeDetail || fallbackDetail,
    reasonLabel: reasonLabel || headline || fallbackHeadline,
    alertLevel,
    alertCode,
    nextCheckAt,
    takeoverReviewDueAt,
  };
}

/* 安全读取对象。 */
function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

/* 安全读取文本。 */
function readText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? normalizeBasketTerms(text) : fallback;
}

/* 保持候选篮子 / 执行篮子口径一致。 */
function normalizeBasketTerms(value: string): string {
  return value.replaceAll("候选池", "候选篮子").replaceAll("live 子集", "执行篮子");
}
