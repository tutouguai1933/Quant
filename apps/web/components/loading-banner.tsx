"use client";

import { Loader2 } from "lucide-react";

import { Card } from "./ui/card";

export function LoadingBanner() {
  return (
    <Card className="mb-4 flex items-center gap-2 rounded-2xl border-blue-500/30 bg-blue-500/10 px-4 py-3 text-sm text-blue-800">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>正在加载数据...</span>
    </Card>
  );
}
