/* 这个文件负责提供根级 404 页面，避免生产构建缺少 /_not-found。 */

import Link from "next/link";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

export default function NotFound() {
  return (
    <main className="min-h-screen bg-background px-6 py-10 text-foreground">
      <div className="mx-auto flex max-w-4xl items-center justify-center">
        <Card className="w-full max-w-2xl">
          <CardHeader>
            <p className="text-xs uppercase tracking-[0.28em] text-muted-foreground">404</p>
            <CardTitle>未找到对应页面</CardTitle>
            <CardDescription>
              当前地址没有可用内容。你可以回到驾驶舱继续查看研究、市场和执行状态。
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/">返回驾驶舱</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href="/signals">查看信号页</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
