/* 这个文件负责挂载全局样式和页面元数据。 */

import "./globals.css";

export const metadata = {
  title: "Quant Control Plane",
  description: "Phase-1 crypto control plane for Binance + Freqtrade.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className="dark min-h-screen bg-background text-foreground antialiased">{children}</body>
    </html>
  );
}
