/* 这个文件负责统一页面反馈提示的解析和编码。 */

export type FeedbackTone = "success" | "warning" | "error" | "info";

export type FeedbackState = {
  tone: FeedbackTone;
  title: string;
  message: string;
} | null;

/* 从页面查询参数中提取反馈信息。 */
export function readFeedback(value: Record<string, string | string[] | undefined>): FeedbackState {
  const tone = readSingleParam(value.tone) as FeedbackTone;
  const title = decodeURIComponent(readSingleParam(value.title));
  const message = decodeURIComponent(readSingleParam(value.message));

  if (!tone || !title || !message) {
    return null;
  }

  return {
    tone,
    title,
    message,
  };
}

/* 生成带反馈参数的跳转地址。 */
export function withFeedback(path: string, tone: FeedbackTone, title: string, message: string): string {
  const query = new URLSearchParams({
    tone,
    title: encodeURIComponent(title),
    message: encodeURIComponent(message),
  });
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}${query.toString()}`;
}

/* 读取单值参数，避免数组干扰。 */
function readSingleParam(value?: string | string[]): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}
