"use client";

import { Loader2 } from "lucide-react";

export function LoadingBanner() {
  return (
    <div className="mb-4 flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>正在加载数据...</span>
    </div>
  );
}
