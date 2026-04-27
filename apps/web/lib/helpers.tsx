/* 通用辅助函数，从各页面重复定义中提取。 */

import type { ReactNode } from "react";

/* 安全读取对象。 */
export function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

/* 安全读取字符串数组。 */
export function toStringArray(value: unknown, fallback: string[] = []): string[] {
  if (!Array.isArray(value)) {
    return fallback;
  }
  return value.map((item) => String(item ?? "").trim()).filter(Boolean);
}

/* 安全读取对象数组。 */
export function toRecordArray(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object" && !Array.isArray(item)));
}

/* 读取对象字段的文本值，支持嵌套字段路径。 */
export function readText(value: unknown, fallback: string = ""): string {
  if (typeof value === "string") {
    const text = value.trim();
    return text || fallback;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  return fallback;
}

/* 简单读取文本值。 */
export function readPlainText(value: unknown, fallback: string = ""): string {
  const text = String(value ?? "").trim();
  return text || fallback;
}

/* 格式化显示值，替换术语。 */
export function displayValue(value: unknown, fallback: string = ""): string {
  const text = String(value ?? "").trim();
  if (!text) {
    return fallback;
  }
  return normalizeBasketTerms(text);
}

/* 替换候选池为候选篮子。 */
export function normalizeBasketTerms(value: string): string {
  return value.replaceAll("候选池", "候选篮子");
}

/* 渲染信息块组件。 */
export function InfoBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/60 bg-muted/15 p-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-sm font-medium leading-6 text-foreground break-all">{value}</p>
    </div>
  );
}

/* 渲染详情分组组件。 */
export function DetailSection({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return (
    <section className="rounded-2xl border border-border/60 bg-muted/10 p-4">
      <div className="space-y-2">
        <p className="eyebrow">{title}</p>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}