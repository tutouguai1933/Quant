"use client";

import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader } from "./ui/card";

export function LoadingBanner() {
  return (
    <Card className="border-accent/30 bg-accent/10">
      <CardHeader className="pb-2">
        <p className="eyebrow">加载状态</p>
      </CardHeader>
      <CardContent className="flex items-center gap-2 text-sm text-accent-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>正在加载数据...</span>
      </CardContent>
    </Card>
  );
}
