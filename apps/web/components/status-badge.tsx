/* 这个文件负责统一展示状态徽章。 */

import { Badge } from "./ui/badge";

type StatusBadgeProps = {
  value: string;
};

/* 根据状态值渲染统一徽章。 */
export function StatusBadge({ value }: StatusBadgeProps) {
  const normalized = value.toLowerCase();
  const tone =
    normalized.includes("fail") || normalized.includes("block") || normalized.includes("reject")
      ? "danger"
      : normalized.includes("run") || normalized.includes("fill") || normalized.includes("success")
        ? "success"
        : normalized.includes("pause") || normalized.includes("warn")
          ? "warning"
          : "outline";

  return <Badge variant={tone}>{formatStatusLabel(value, normalized)}</Badge>;
}

/* 把内部状态值压缩成更适合终端界面的短标签。 */
function formatStatusLabel(value: string, normalized: string): string {
  const labels: Record<string, string> = {
    supportive_but_not_triggering: "支持但未触发",
    blocked_by_rule_gate: "规则门拦截",
    blocked_by_backtest_gate: "回测门拦截",
    ready_for_dry_run: "可进 dry-run",
    unavailable: "不可用",
  };

  if (labels[normalized]) {
    return labels[normalized];
  }

  return value.replaceAll("_", " ");
}
