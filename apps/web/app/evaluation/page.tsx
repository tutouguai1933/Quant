/**
 * 选币回测页面入口
 * 复刻参考图 2 的终端化布局
 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { TerminalShell } from "../../components/terminal";
import { FeedbackBanner } from "../../components/feedback-banner";
import { readFeedback } from "../../lib/feedback";
import { EvaluationClient } from "./evaluation-client";

export default function EvaluationPage() {
  const searchParams = useSearchParams();
  const [session, setSession] = useState<{ token: string | null; isAuthenticated: boolean }>({
    token: null,
    isAuthenticated: false,
  });

  useEffect(() => {
    fetch("/api/control/session")
      .then((res) => res.json())
      .then((data) => {
        setSession({
          token: data.token || null,
          isAuthenticated: Boolean(data.isAuthenticated),
        });
      })
      .catch(() => {});
  }, []);

  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  return (
    <TerminalShell
      breadcrumb="研究 / 选币回测"
      title="选币回测"
      subtitle="多标的 Top-K 组合回测"
      currentPath="/evaluation"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      <EvaluationClient token={session.token} isAuthenticated={session.isAuthenticated} />
    </TerminalShell>
  );
}
