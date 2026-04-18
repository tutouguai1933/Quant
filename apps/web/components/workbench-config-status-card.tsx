/* 这个文件提供工作台配置状态卡，统一展示配置与实际结果的对齐信息。 */

import { resolveHumanStatus } from "../lib/status-language";
import { Badge } from "./ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type WorkbenchConfigStatusCardProps = {
  scope: string;
  status: string;
  note?: string;
  staleFields?: Array<string | undefined | null>;
  editable?: boolean;
};

export function WorkbenchConfigStatusCard({
  scope,
  status,
  note,
  staleFields,
  editable = true,
}: WorkbenchConfigStatusCardProps) {
  const humanStatus = resolveHumanStatus(status || "");
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
          <Badge variant={humanStatus.badgeVariant} title={humanStatus.detail} aria-label={`${humanStatus.label}：${humanStatus.detail}`}>
            {humanStatus.label}
          </Badge>
          <p className="text-sm leading-6 text-muted-foreground">
            {note || (!editable ? `当前配置被锁止，真实状态：${humanStatus.detail}` : humanStatus.detail || "当前没有额外说明。")}
          </p>
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
