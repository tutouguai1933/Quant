/* 这个文件负责把前端客户端请求代理到本地控制面 API。 */

import { NextResponse } from "next/server";

import { buildApiUrl } from "../../../../lib/api";


type RouteContext = {
  params: Promise<{ path: string[] }>;
};

/* 代理市场和图表等客户端只读请求。 */
export async function GET(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const upstreamUrl = new URL(buildApiUrl(`/${path.join("/")}`));
  upstreamUrl.search = new URL(request.url).search;

  try {
    const response = await fetch(upstreamUrl, {
      headers: {
        Accept: "application/json",
      },
      cache: "no-store",
    });
    const body = await response.text();

    return new NextResponse(body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("Content-Type") ?? "application/json; charset=utf-8",
      },
    });
  } catch {
    return NextResponse.json(
      {
        data: null,
        error: {
          code: "proxy_unavailable",
          message: "客户端代理暂时不可用。",
        },
        meta: {},
      },
      { status: 502 },
    );
  }
}
