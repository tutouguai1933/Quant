/* 这个文件负责统一展示操作成功、失败或提示信息。 */

import type { FeedbackState } from "../lib/feedback";

import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

type FeedbackBannerProps = {
  feedback: FeedbackState;
  fallbackTitle?: string;
};

/* 渲染反馈条。 */
export function FeedbackBanner({ feedback, fallbackTitle = "动作反馈" }: FeedbackBannerProps) {
  if (!feedback) {
    return null;
  }

  const toneClass =
    feedback.tone === "error"
      ? "border-rose-500/40 bg-rose-500/10"
      : feedback.tone === "warning"
        ? "border-amber-500/40 bg-amber-500/10"
        : "border-emerald-500/30 bg-emerald-500/10";

  return (
    <Card className={toneClass}>
      <CardHeader className="pb-2">
        <p className="eyebrow">{fallbackTitle}</p>
        <CardTitle>{feedback.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-6 text-muted-foreground">{feedback.message}</p>
      </CardContent>
    </Card>
  );
}
