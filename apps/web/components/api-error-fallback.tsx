import { AlertCircle } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type ApiErrorFallbackProps = {
  title?: string;
  message?: string;
  detail?: string;
};

export function ApiErrorFallback({
  title = "数据加载失败",
  message = "后端 API 暂时不可用",
  detail = "当前显示的是降级数据，请稍后刷新页面重试。",
}: ApiErrorFallbackProps) {
  return (
    <Card className="border-amber-500/50 bg-amber-500/5">
      <CardHeader>
        <div className="flex items-center gap-3">
          <AlertCircle className="size-4 text-amber-500" />
          <p className="eyebrow text-amber-500">降级模式</p>
        </div>
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{message}</CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}
