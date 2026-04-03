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

  return <Badge variant={tone}>{value}</Badge>;
}
