/* 这个文件提供 Next 生产构建需要的最小 pages 兜底入口。 */

import type { AppProps } from "next/app";


/* 保持 pages 路由层的最小渲染能力，不干扰 app router。 */
export default function LegacyApp({ Component, pageProps }: AppProps) {
  return <Component {...pageProps} />;
}
