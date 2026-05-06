/* 这个文件负责承接控制面按钮操作并回写统一反馈。 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { buildAutomationHandoffSummary } from "../../lib/automation-handoff";
import { buildAuthHeaders, buildUpstreamApiUrl, fetchJson, getAdminSession, getAutomationStatus, type AutomationStatusModel } from "../../lib/api";
import { buildRedirectUrl } from "../../lib/redirect";
import { normalizeAppPath, SESSION_COOKIE_NAME } from "../../lib/session";


type ActionConfig = {
  path: string;
  method: "POST";
  requiresToken: boolean;
  successTitle: string;
  successMessage: string;
};

/* GET 请求重定向到任务页面，显示错误提示。 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const returnTo = normalizeAppPath(url.searchParams.get("returnTo")?.toString(), "/tasks");
  return NextResponse.redirect(
    buildRedirectUrl(
      request,
      `${returnTo}?tone=error&title=${encodeURIComponent("操作失败")}&message=${encodeURIComponent("请通过页面按钮执行操作，不要直接访问此链接。")}`,
    ),
    303,
  );
}

/* 处理控制面动作提交。 */
export async function POST(request: Request) {
  const params = new URLSearchParams(await request.text());
  const action = String(params.get("action") ?? "");
  const strategyId = String(params.get("strategyId") ?? "1");
  const returnTo = normalizeAppPath(params.get("returnTo")?.toString(), "/");
  const cookieStore = await cookies();
  const token = String(cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "");

  if (action === "update_workbench_config") {
    return handleWorkbenchConfigUpdate({ request, params, returnTo, token, cookieStore });
  }

  const config = resolveActionConfig(action, strategyId, params);

  if (!config) {
    return redirectAfterPost(request, `${returnTo}?tone=error&title=动作反馈&message=未识别的操作请求。`);
  }

  if (config.requiresToken && !token) {
    return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=请先登录后再执行受保护操作。`);
  }

  if (config.requiresToken) {
    try {
        const session = await getAdminSession(token);
      if (session.error) {
        cookieStore.delete(SESSION_COOKIE_NAME);
        return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话已失效，请重新登录。`);
      }
    } catch {
      cookieStore.delete(SESSION_COOKIE_NAME);
      return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话校验失败，请重新登录。`);
    }
  }

  try {
    const response = await fetch(buildActionUpstreamUrl(request, config.path), {
      method: config.method,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      cache: "no-store",
    });
    const payload = (await response.json()) as Awaited<ReturnType<typeof fetchJson>>;

    if (payload.error) {
      return NextResponse.redirect(
        buildRedirectUrl(
          request,
          `${returnTo}?tone=error&title=${encodeURIComponent("动作反馈")}&message=${encodeURIComponent(payload.error.message)}`,
        ),
        303,
      );
    }

    const feedback = await resolveActionFeedback(action, payload, config, token);
    if (feedback) {
      return NextResponse.redirect(
        buildRedirectUrl(
          request,
          `${returnTo}?tone=${encodeURIComponent(feedback.tone)}&title=${encodeURIComponent(feedback.title)}&message=${encodeURIComponent(feedback.message)}`,
        ),
        303,
      );
    }

    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${returnTo}?tone=success&title=${encodeURIComponent(config.successTitle)}&message=${encodeURIComponent(config.successMessage)}`,
      ),
      303,
    );
  } catch {
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${returnTo}?tone=error&title=${encodeURIComponent("动作反馈")}&message=${encodeURIComponent("控制平面暂时不可达，请稍后重试。")}`,
      ),
      303,
    );
  }
}

async function handleWorkbenchConfigUpdate({
  request,
  params,
  returnTo,
  token,
  cookieStore,
}: {
  request: Request;
  params: URLSearchParams;
  returnTo: string;
  token: string;
  cookieStore: Awaited<ReturnType<typeof cookies>>;
}) {
  if (!token) {
    return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=请先登录后再保存工作台配置。`);
  }

  try {
    const session = await getAdminSession(token);
    if (session.error) {
      cookieStore.delete(SESSION_COOKIE_NAME);
      return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话已失效，请重新登录。`);
    }
  } catch {
    cookieStore.delete(SESSION_COOKIE_NAME);
    return redirectAfterPost(request, `/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话校验失败，请重新登录。`);
  }

  const section = String(params.get("section") ?? "").trim();
  const values = serializeWorkbenchValues(params);

  try {
    const response = await fetch(buildActionUpstreamUrl(request, "/workbench/config"), {
      method: "POST",
      headers: {
        ...buildAuthHeaders(token),
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ section, values }),
      cache: "no-store",
    });
    const payload = (await response.json()) as Awaited<ReturnType<typeof fetchJson>>;
    if (payload.error) {
      return NextResponse.redirect(
        buildRedirectUrl(
          request,
          `${returnTo}?tone=error&title=${encodeURIComponent("配置反馈")}&message=${encodeURIComponent(payload.error.message)}`,
        ),
        303,
      );
    }
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${returnTo}?tone=success&title=${encodeURIComponent("配置反馈")}&message=${encodeURIComponent("工作台配置已更新，当前页面和后续研究链都会按新配置刷新。")}`,
      ),
      303,
    );
  } catch {
    return NextResponse.redirect(
      buildRedirectUrl(
        request,
        `${returnTo}?tone=error&title=${encodeURIComponent("配置反馈")}&message=${encodeURIComponent("工作台配置暂时保存失败，请稍后重试。")}`,
      ),
      303,
    );
  }
}

/* 服务端动作直接连控制面 API，避免再绕一层前端代理。 */
function buildProxyUrl(request: Request, path: string): string {
  const [pathname, search = ""] = path.split("?", 2);
  const upstreamUrl = new URL(buildUpstreamApiUrl(pathname, request));
  if (search) {
    upstreamUrl.search = search;
  }
  return upstreamUrl.toString();
}

function buildActionUpstreamUrl(request: Request, path: string): string {
  return buildProxyUrl(request, path);
}

function redirectAfterPost(request: Request, targetPath: string) {
  return NextResponse.redirect(buildRedirectUrl(request, targetPath), 303);
}

async function resolveActionFeedback(
  action: string,
  payload: Awaited<ReturnType<typeof fetchJson>>,
  config: ActionConfig,
  token: string,
): Promise<{ tone: "success" | "warning"; title: string; message: string } | null> {
  if (!action.startsWith("automation_")) {
    return null;
  }

  const statusFeedback = token ? await buildAutomationStatusFeedback(token, config) : null;
  if (statusFeedback) {
    return statusFeedback;
  }

  const data = isPlainRecord(payload.data) ? payload.data : {};
  const item = isPlainRecord(data.item) ? data.item : {};
  const workflowResult = isPlainRecord(item.result) ? item.result : item;
  const workflowStatus = String(workflowResult.status ?? item.status ?? "").trim().toLowerCase();
  const nextAction = String(workflowResult.next_action ?? "").trim();
  const message = String(workflowResult.message ?? "").trim();
  const pendingItems = Array.isArray(item.pending_items)
    ? item.pending_items
        .map((entry) => (isPlainRecord(entry) ? String(entry.label ?? "") : ""))
        .filter((entry) => entry.length > 0)
    : [];

  if (action === "automation_resume" && workflowStatus === "blocked") {
    const blockedReason = String(item.blocked_reason ?? "").trim();
    const blockedDetail = pendingItems.length
      ? `当前还不能恢复，先处理：${pendingItems.join(" / ")}。`
      : "当前还不能恢复，先完成恢复清单后再继续自动化。";
    return {
      tone: "warning",
      title: "自动化反馈",
      message: blockedReason === "resume_checklist_pending" ? blockedDetail : (message || blockedDetail),
    };
  }

  if (workflowStatus === "succeeded") {
    return {
      tone: "success",
      title: "自动化反馈",
      message: config.successMessage,
    };
  }

  const actionCopy = nextAction ? `下一步：${nextAction}` : "请先查看统一复盘，再决定下一步。";
  return {
    tone: "warning",
    title: "自动化反馈",
    message: message || `本轮自动化已运行，但当前状态是 ${workflowStatus || "waiting"}。${actionCopy}`,
  };
}

async function buildAutomationStatusFeedback(
  token: string,
  config: ActionConfig,
): Promise<{ tone: "success" | "warning"; title: string; message: string } | null> {
  try {
    const response = await getAutomationStatus(token);
    if (response.error) {
      return null;
    }
    return summarizeAutomationFeedback(response.data.item, config);
  } catch {
    return null;
  }
}

function summarizeAutomationFeedback(
  automation: AutomationStatusModel,
  config: ActionConfig,
): { tone: "success" | "warning"; title: string; message: string } {
  const handoff = buildAutomationHandoffSummary({
    automation,
    tasksHref: "/tasks",
    fallbackTargetHref: "/tasks",
    fallbackTargetLabel: "去任务页处理自动化",
    fallbackHeadline: "自动化状态已更新",
    fallbackDetail: config.successMessage,
  });
  const runtimeGuard = isPlainRecord(automation.runtimeGuard) ? automation.runtimeGuard : {};
  const recoveryReview = isPlainRecord(automation.recoveryReview) ? automation.recoveryReview : {};
  const routeTasks = isTasksTargetPath(handoff.targetHref)
    || isTasksTargetPath(String(runtimeGuard.operator_route ?? ""));
  const status = String(runtimeGuard.status ?? handoff.status ?? "").trim().toLowerCase();
  const warningStatus = ["attention_required", "degraded", "waiting", "blocked"].includes(status);
  const reasonLabel = String(recoveryReview.reason_label ?? "").trim();
  const detail = handoff.detail || String(runtimeGuard.detail ?? "").trim() || config.successMessage;
  const messageParts = warningStatus
    ? [reasonLabel || handoff.headline, detail, routeTasks ? "先去任务页看当前恢复建议和人工接管状态。" : ""]
    : [handoff.headline || "自动化状态已更新", detail];

  return {
    tone: warningStatus ? "warning" : "success",
    title: "自动化反馈",
    message: joinFeedbackParts(messageParts),
  };
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isTasksTargetPath(value: string): boolean {
  const normalized = value.trim();
  return normalized === "/tasks" || normalized === "/login?next=%2Ftasks";
}

function joinFeedbackParts(parts: string[]): string {
  return parts
    .map((part) => part.trim().replace(/[。]+$/u, ""))
    .filter((part) => part.length > 0)
    .join("。") + "。";
}

function serializeWorkbenchValues(params: URLSearchParams): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  const explicitFields = new Set<string>();
  const touchedFields = new Set<string>();
  for (const [key, rawValue] of params.entries()) {
    if (key === "action" || key === "section" || key === "returnTo") {
      continue;
    }
    if (key.startsWith("__present__")) {
      explicitFields.add(key.replace(/^__present__/, ""));
      continue;
    }
    touchedFields.add(key);
    const value = String(rawValue ?? "").trim();
    if (!value) {
      continue;
    }
    const current = result[key];
    if (current === undefined) {
      result[key] = value;
      continue;
    }
    if (Array.isArray(current)) {
      current.push(value);
      result[key] = current;
      continue;
    }
    result[key] = [String(current), value];
  }
  for (const key of explicitFields) {
    if (result[key] === undefined) {
      result[key] = [];
    }
  }
  for (const key of touchedFields) {
    if (result[key] === undefined) {
      result[key] = "";
    }
  }
  return result;
}

/* 将表单动作映射到控制平面 API。 */
function resolveActionConfig(action: string, strategyId: string, params: URLSearchParams): ActionConfig | null {
  const alertId = String(params.get("alert_id") ?? "").trim();
  const alertLevels = String(params.get("levels") ?? "").trim();
  const alertLevelQuery = alertLevels ? `?levels=${encodeURIComponent(alertLevels)}` : "";
  const map: Record<string, ActionConfig> = {
    run_pipeline: {
      path: "/signals/pipeline/run?source=qlib",
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "Qlib 信号流水线已进入后台，可在信号页、研究页和评估页查看进度与结果。",
    },
    run_mock_pipeline: {
      path: "/signals/pipeline/run?source=mock",
      method: "POST",
      requiresToken: false,
      successTitle: "动作反馈",
      successMessage: "演示信号流水线已运行，页面已刷新为最新结果。",
    },
    start_strategy: {
      path: `/strategies/${strategyId}/start`,
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "策略已启动，可以继续派发最新信号。",
    },
    pause_strategy: {
      path: `/strategies/${strategyId}/pause`,
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "策略已暂停，执行链路已收紧。",
    },
    stop_strategy: {
      path: `/strategies/${strategyId}/stop`,
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "策略已停止，后续派发会进入风控拒绝路径。",
    },
    dispatch_latest_signal: {
      path: `/strategies/${strategyId}/dispatch-latest-signal`,
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "最新信号已派发，订单和持仓状态已刷新。",
    },
    run_research_training: {
      path: "/signals/research/train",
      method: "POST",
      requiresToken: true,
      successTitle: "研究反馈",
      successMessage: "研究训练已进入后台，可在研究页查看进度，完成后再去评估页看结果。",
    },
    run_research_inference: {
      path: "/signals/research/infer",
      method: "POST",
      requiresToken: true,
      successTitle: "研究反馈",
      successMessage: "研究推理已进入后台，可在研究页查看进度，完成后再去信号页和评估页看结果。",
    },
    trigger_train: {
      path: "/tasks/train",
      method: "POST",
      requiresToken: true,
      successTitle: "研究反馈",
      successMessage: "研究训练任务已进入统一调度。",
    },
    trigger_sync: {
      path: "/tasks/sync",
      method: "POST",
      requiresToken: true,
      successTitle: "任务反馈",
      successMessage: "同步任务已执行，页面数据已更新。",
    },
    trigger_reconcile_failure: {
      path: "/tasks/reconcile?simulate_failure=true",
      method: "POST",
      requiresToken: true,
      successTitle: "任务反馈",
      successMessage: "失败任务场景已制造，可直接观察异常可见性。",
    },
    trigger_archive: {
      path: "/tasks/archive",
      method: "POST",
      requiresToken: true,
      successTitle: "任务反馈",
      successMessage: "归档任务已执行。",
    },
    automation_mode_manual: {
      path: "/tasks/automation/configure?mode=manual",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化模式已切到手动。",
    },
    automation_mode_auto_dry_run: {
      path: "/tasks/automation/configure?mode=auto_dry_run",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化模式已切到自动 dry-run。",
    },
    automation_mode_auto_live: {
      path: "/tasks/automation/configure?mode=auto_live",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化模式已切到自动小额 live。",
    },
    automation_pause: {
      path: "/tasks/automation/pause?reason=manual_pause",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化已暂停，后续不会再自动推进。",
    },
    automation_manual_takeover: {
      path: "/tasks/automation/manual-takeover?reason=manual_takeover",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "系统已进入人工接管，自动执行链已暂停。",
    },
    automation_resume: {
      path: "/tasks/automation/resume",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化已恢复，可以继续跑完整工作流。",
    },
    automation_dry_run_only: {
      path: "/tasks/automation/dry-run-only",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "系统已切到 dry-run only。",
    },
    automation_kill_switch: {
      path: "/tasks/automation/kill-switch",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "Kill Switch 已触发，自动化已停机。",
    },
    automation_confirm_alert: {
      path: alertId ? `/tasks/automation/alerts/${alertId}/confirm` : "",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "头号告警已确认，任务页会按最新状态刷新。",
    },
    automation_clear_non_error_alerts: {
      path: `/tasks/automation/alerts/clear${alertLevelQuery}`,
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "非错误告警已清理，当前风险摘要已刷新。",
    },
    automation_run_cycle: {
      path: "/tasks/automation/run",
      method: "POST",
      requiresToken: true,
      successTitle: "自动化反馈",
      successMessage: "自动化工作流已触发，本轮训练、推理、执行和复盘会按当前模式推进。",
    },
  };

  const item = map[action] ?? null;
  if (!item || !item.path) {
    return null;
  }
  return item;
}
