/* 评估与实验中心：精简版 */
"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { AppShell } from "../../components/app-shell";
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
      .catch(() => {
        // Keep default session state
      });
  }, []);

  const params = searchParams ? Object.fromEntries(searchParams.entries()) : {};
  const feedback = readFeedback(params);

  return (
    <AppShell
      title="评估"
      subtitle="评估中心先回答：哪些候选值得推进、为什么推荐、为什么淘汰。"
      currentPath="/evaluation"
      isAuthenticated={session.isAuthenticated}
    >
      <FeedbackBanner feedback={feedback} />
      <EvaluationClient token={session.token} isAuthenticated={session.isAuthenticated} />
    </AppShell>
  );
}
