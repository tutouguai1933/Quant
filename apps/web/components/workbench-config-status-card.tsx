/* 这个文件提供工作台配置状态卡，统一展示配置与实际结果的对齐信息。 */

import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type WorkbenchConfigStatusCardProps = {
  scope: string;
  status: string;
  note?: string;
  staleFields?: Array<string | undefined | null>;
  editable?: boolean;
};

const STATUS_VARIANT_MAP: Record<string, "success" | "warning" | "danger"> = {
  aligned: "success",
  ready: "success",
  available: "success",
  degraded: "warning",
  unavailable: "warning",
  stale: "danger",
  blocked: "warning",
  attention_required: "warning",
  waiting_research: "warning",
  no_execution: "warning",
  attention: "warning",
};

const STATUS_LABEL_MAP: Record<string, string> = {
  aligned: "配置已对齐",
  ready: "已准备",
  available: "可用",
  degraded: "已降级",
  unavailable: "暂不可用",
  stale: "可能过期",
  blocked: "被阻塞",
  attention_required: "需人工关注",
  waiting_research: "等待研究",
  no_execution: "未派发",
  attention: "待关注",
};

function resolveVariant(status: string) {
  const normalized = status.trim().toLowerCase();
  return STATUS_VARIANT_MAP[normalized] ?? "warning";
}

function resolveLabel(status: string, editable?: boolean) {
  const normalized = status.trim().toLowerCase();
  if (STATUS_LABEL_MAP[normalized]) {
    return STATUS_LABEL_MAP[normalized];
  }
  if (!editable) {
    return "配置被锁定";
  }
  return status ? `状态：${status}` : "状态未知";
}

export function WorkbenchConfigStatusCard({
  scope,
  status,
  note,
  staleFields,
  editable = true,
}: WorkbenchConfigStatusCardProps) {
  const variant = resolveVariant(status || "");
  const label = resolveLabel(status || "", editable);
  const sanitizedFields = (staleFields ?? []).filter((item): item is string => Boolean(item?.toString().trim()));

  return (
    <Card className="bg-card/95">
      <CardHeader>
        <CardTitle>{scope} 配置状态</CardTitle>
        <CardDescription>
          {editable ? "当前可以调整配置，系统会把下一轮研究按新口径跑。" : "当前配置被锁止，稍后再试。"}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Badge variant={variant}>{label}</Badge>
          <p className="text-sm leading-6 text-muted-foreground">{note || "当前没有额外说明。"} </p>
        </div>
        {sanitizedFields.length ? (
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-muted-foreground">变更字段</p>
            <div className="flex flex-wrap gap-2">
              {sanitizedFields.map((field) => (
                <Badge key={field} variant="outline">
                  {field}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
