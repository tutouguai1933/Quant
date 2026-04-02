/* 这个文件负责装载专业 K 线图运行时。 */

"use client";

import Script from "next/script";

type ProChartScriptProps = {
  onReady?: () => void;
};

/* 注入 lightweight-charts 的浏览器运行时。 */
export function ProChartScript({ onReady }: ProChartScriptProps) {
  return (
    <Script
      id="lightweight-charts-runtime"
      src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js"
      strategy="afterInteractive"
      onLoad={onReady}
      onReady={onReady}
    />
  );
}
