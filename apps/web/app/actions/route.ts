/* 这个文件负责承接控制面按钮操作并回写统一反馈。 */

import { cookies } from "next/headers";
import { NextResponse } from "next/server";

import { buildApiUrl, fetchJson, getAdminSession } from "../../lib/api";
import { normalizeAppPath, SESSION_COOKIE_NAME } from "../../lib/session";


type ActionConfig = {
  path: string;
  method: "POST";
  requiresToken: boolean;
  successTitle: string;
  successMessage: string;
};

/* 处理控制面动作提交。 */
export async function POST(request: Request) {
  const formData = await request.formData();
  const action = String(formData.get("action") ?? "");
  const strategyId = String(formData.get("strategyId") ?? "1");
  const returnTo = normalizeAppPath(formData.get("returnTo")?.toString(), "/");
  const cookieStore = await cookies();
  const token = String(cookieStore.get(SESSION_COOKIE_NAME)?.value ?? "");
  const config = resolveActionConfig(action, strategyId);

  if (!config) {
    return NextResponse.redirect(new URL(`${returnTo}?tone=error&title=动作反馈&message=未识别的操作请求。`, request.url));
  }

  if (config.requiresToken && !token) {
    return NextResponse.redirect(new URL(`/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=请先登录后再执行受保护操作。`, request.url));
  }

  if (config.requiresToken) {
    try {
      const session = await getAdminSession(token);
      if (session.error) {
        cookieStore.delete(SESSION_COOKIE_NAME);
        return NextResponse.redirect(new URL(`/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话已失效，请重新登录。`, request.url));
      }
    } catch {
      cookieStore.delete(SESSION_COOKIE_NAME);
      return NextResponse.redirect(new URL(`/login?next=${encodeURIComponent(returnTo)}&tone=warning&title=登录反馈&message=当前会话校验失败，请重新登录。`, request.url));
    }
  }

  try {
    const response = await fetch(buildApiUrl(config.path), {
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
        new URL(
          `${returnTo}?tone=error&title=${encodeURIComponent("动作反馈")}&message=${encodeURIComponent(payload.error.message)}`,
          request.url,
        ),
      );
    }

    return NextResponse.redirect(
      new URL(
        `${returnTo}?tone=success&title=${encodeURIComponent(config.successTitle)}&message=${encodeURIComponent(config.successMessage)}`,
        request.url,
      ),
    );
  } catch {
    return NextResponse.redirect(
      new URL(
        `${returnTo}?tone=error&title=${encodeURIComponent("动作反馈")}&message=${encodeURIComponent("控制平面暂时不可达，请稍后重试。")}`,
        request.url,
      ),
    );
  }
}

/* 将表单动作映射到控制平面 API。 */
function resolveActionConfig(action: string, strategyId: string): ActionConfig | null {
  const map: Record<string, ActionConfig> = {
    run_pipeline: {
      path: "/signals/pipeline/run?source=qlib",
      method: "POST",
      requiresToken: true,
      successTitle: "动作反馈",
      successMessage: "Qlib 信号流水线已运行，页面已刷新为最新结果。",
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
      successMessage: "研究训练已提交，最近研究结果会更新。",
    },
    run_research_inference: {
      path: "/signals/research/infer",
      method: "POST",
      requiresToken: true,
      successTitle: "研究反馈",
      successMessage: "研究推理已提交，最近研究结果会更新。",
    },
    trigger_train: {
      path: "/tasks/train",
      method: "POST",
      requiresToken: true,
      successTitle: "任务反馈",
      successMessage: "训练任务已进入记录流转。",
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
  };

  return map[action] ?? null;
}
