/* 这个文件提供 Next 生产构建需要的最小文档兜底。 */

import { Head, Html, Main, NextScript } from "next/document";


/* 保持 pages 路由层的最小文档结构，不干扰 app router。 */
export default function Document() {
  return (
    <Html lang="zh-CN">
      <Head />
      <body>
        <Main />
        <NextScript />
      </body>
    </Html>
  );
}
