/* 这个文件负责把前端散落的原始状态压成统一的四类状态语言。 */

export type HumanStatusCategory = "normal" | "running" | "blocked" | "attention";

export type HumanStatusMeta = {
  category: HumanStatusCategory;
  label: string;
  badgeVariant: "success" | "accent" | "danger" | "warning";
  detail: string;
  raw: string;
};

const CATEGORY_LABEL_MAP: Record<HumanStatusCategory, string> = {
  normal: "正常",
  running: "运行中",
  blocked: "阻塞",
  attention: "需人工处理",
};

const CATEGORY_VARIANT_MAP: Record<HumanStatusCategory, HumanStatusMeta["badgeVariant"]> = {
  normal: "success",
  running: "accent",
  blocked: "danger",
  attention: "warning",
};

const EXACT_CATEGORY_MAP: Record<string, HumanStatusCategory> = {
  aligned: "normal",
  ready: "normal",
  available: "normal",
  healthy: "normal",
  success: "normal",
  completed: "normal",
  complete: "normal",
  filled: "normal",
  ready_for_dry_run: "normal",
  supportive_but_not_triggering: "normal",
  live: "normal",
  dry_run: "normal",
  research: "normal",
  running: "running",
  waiting: "running",
  idle: "running",
  pending: "running",
  queued: "running",
  loading: "running",
  syncing: "running",
  waiting_research: "running",
  continue_research: "running",
  unavailable: "blocked",
  blocked: "blocked",
  blocked_by_rule_gate: "blocked",
  blocked_by_backtest_gate: "blocked",
  no_execution: "blocked",
  stale: "blocked",
  failed: "blocked",
  rejected: "blocked",
  error: "blocked",
  attention_required: "attention",
  attention: "attention",
  warning: "attention",
  manual: "attention",
  manual_mode: "attention",
  manual_takeover: "attention",
  paused: "attention",
  pause: "attention",
  cooldown: "attention",
  resume_review: "attention",
  "login required": "attention",
  wait_window: "attention",
  wait_sync: "attention",
  awaiting_review: "attention",
  awaiting_manual: "attention",
  waiting_manual: "attention",
};

const STATUS_DETAIL_MAP: Record<string, string> = {
  aligned: "配置已对齐",
  ready: "已准备",
  available: "可用",
  healthy: "健康",
  success: "成功",
  completed: "已完成",
  complete: "已完成",
  filled: "已成交",
  ready_for_dry_run: "可进 dry-run",
  supportive_but_not_triggering: "支持但未触发",
  live: "live",
  dry_run: "dry-run",
  research: "研究",
  running: "运行中",
  waiting: "等待中",
  idle: "未运行",
  pending: "处理中",
  queued: "排队中",
  loading: "加载中",
  syncing: "同步中",
  waiting_research: "等待研究",
  continue_research: "继续研究",
  unavailable: "暂不可用",
  blocked: "被阻塞",
  blocked_by_rule_gate: "规则门拦截",
  blocked_by_backtest_gate: "回测门拦截",
  no_execution: "未派发",
  stale: "可能过期",
  failed: "失败",
  rejected: "被拒绝",
  error: "异常",
  attention_required: "需人工关注",
  attention: "待关注",
  warning: "警告",
  manual: "手动模式",
  manual_mode: "手动模式",
  manual_takeover: "人工接管",
  paused: "已暂停",
  pause: "已暂停",
  cooldown: "冷却中",
  resume_review: "等待恢复复核",
  wait_window: "等待窗口",
  wait_sync: "等待同步复核",
  awaiting_review: "等待复核",
  awaiting_manual: "等待人工确认",
  waiting_manual: "等待人工确认",
  "login required": "需要登录",
};

const RUNNING_TOKENS = ["run", "wait", "queue", "pending", "load", "sync", "train", "infer", "progress", "dispatch"];
const BLOCKED_TOKENS = ["fail", "error", "block", "reject", "unavailable", "stale", "missing", "forbidden", "denied", "locked"];
const ATTENTION_TOKENS = ["manual", "pause", "warning", "attention", "takeover", "review", "cooldown", "login", "await"];
const NORMAL_TOKENS = ["success", "ready", "available", "aligned", "healthy", "done", "complete", "fill", "active", "live", "dry_run"];

/* 统一解析原始状态值。 */
export function resolveHumanStatus(value: unknown): HumanStatusMeta {
  const raw = String(value ?? "").trim();
  const normalized = raw.toLowerCase().replaceAll("-", "_");
  const category = resolveCategory(normalized);
  const detail = resolveDetail(raw, normalized);

  return {
    category,
    label: CATEGORY_LABEL_MAP[category],
    badgeVariant: CATEGORY_VARIANT_MAP[category],
    detail,
    raw,
  };
}

/* 根据原始状态值归类到统一四态。 */
function resolveCategory(normalized: string): HumanStatusCategory {
  if (!normalized) {
    return "attention";
  }
  if (EXACT_CATEGORY_MAP[normalized]) {
    return EXACT_CATEGORY_MAP[normalized];
  }
  if (ATTENTION_TOKENS.some((token) => normalized.includes(token))) {
    return "attention";
  }
  if (BLOCKED_TOKENS.some((token) => normalized.includes(token))) {
    return "blocked";
  }
  if (RUNNING_TOKENS.some((token) => normalized.includes(token))) {
    return "running";
  }
  if (NORMAL_TOKENS.some((token) => normalized.includes(token))) {
    return "normal";
  }
  return "attention";
}

/* 生成更适合展示和辅助阅读的细节说明。 */
function resolveDetail(raw: string, normalized: string): string {
  if (STATUS_DETAIL_MAP[normalized]) {
    return STATUS_DETAIL_MAP[normalized];
  }
  if (!raw) {
    return "状态未知";
  }
  return raw.replaceAll("_", " ");
}
