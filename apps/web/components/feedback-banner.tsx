/* 这个文件负责统一展示操作成功、失败或提示信息。 */

import type { FeedbackState } from "../lib/feedback";


type FeedbackBannerProps = {
  feedback: FeedbackState;
  fallbackTitle?: string;
};

/* 渲染反馈条。 */
export function FeedbackBanner({ feedback, fallbackTitle = "动作反馈" }: FeedbackBannerProps) {
  if (!feedback) {
    return null;
  }

  return (
    <section className={`feedback-banner feedback-${feedback.tone}`}>
      <p className="eyebrow">{fallbackTitle}</p>
      <h3>{feedback.title}</h3>
      <p>{feedback.message}</p>
    </section>
  );
}
