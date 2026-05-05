/**
 * 共享工具函数
 */

/**
 * 将未知值转换为 Record 对象
 */
export function asRecord(value: unknown): Record<string, unknown> {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return {};
}

/**
 * 读取文本值，如果为空则返回默认值
 */
export function readText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}

/**
 * 格式化时间
 */
export function formatTime(value: string): string {
  try {
    const date = new Date(value);
    return date.toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return value;
  }
}

/**
 * 格式化百分比
 */
export function formatPercent(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(num)) return "0.0%";
  return `${(num * 100).toFixed(1)}%`;
}

/**
 * 格式化小数
 */
export function formatDecimal(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(num) || Math.abs(num) < 0.0001) return "0";
  return num.toFixed(8);
}

/**
 * 格式化盈亏值
 */
export function formatPnl(value: string | number): string {
  const num = typeof value === "string" ? parseFloat(value) : value;
  if (!Number.isFinite(num)) return "0";
  const sign = num >= 0 ? "+" : "";
  return `${sign}${num.toFixed(8)}`;
}
