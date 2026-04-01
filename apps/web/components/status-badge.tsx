/* 这个文件负责统一展示状态徽章。 */

type StatusBadgeProps = {
  value: string;
};

/* 根据状态值渲染统一徽章。 */
export function StatusBadge({ value }: StatusBadgeProps) {
  const normalized = value.toLowerCase();
  const tone =
    normalized.includes("fail") || normalized.includes("block") || normalized.includes("reject")
      ? "status-danger"
      : normalized.includes("run") || normalized.includes("fill") || normalized.includes("success")
        ? "status-success"
        : normalized.includes("pause") || normalized.includes("warn")
          ? "status-warning"
          : "status-neutral";

  return <span className={`status-badge ${tone}`}>{value}</span>;
}
