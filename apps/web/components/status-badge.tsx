/* 这个文件负责统一展示状态徽章。 */

import { resolveHumanStatus } from "../lib/status-language";
import { Badge } from "./ui/badge";

type StatusBadgeProps = {
  value: string;
};

/* 根据状态值渲染统一徽章。 */
export function StatusBadge({ value }: StatusBadgeProps) {
  const status = resolveHumanStatus(value);

  return (
    <Badge variant={status.badgeVariant} title={status.detail} aria-label={`${status.label}：${status.detail}`}>
      {status.label}
    </Badge>
  );
}
