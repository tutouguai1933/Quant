/* 这个文件负责把前端客户端请求代理到本地控制面 API。 */

import { NextResponse } from "next/server";

import { buildUpstreamApiUrl } from "../../../../lib/api";
import { SESSION_COOKIE_NAME } from "../../../../lib/session";


type RouteContext = {
  params: Promise<{ path: string[] }>;
};

function resolveAuthorizationHeader(request: Request): string {
  const directHeader = request.headers.get("authorization")?.trim();
  if (directHeader) {
    return directHeader;
  }
  const cookieHeader = request.headers.get("cookie") ?? "";
  const token = cookieHeader
    .split(";")
    .map((item) => item.trim())
    .find((item) => item.startsWith(`${SESSION_COOKIE_NAME}=`))
    ?.split("=", 2)[1];
  return token ? `Bearer ${decodeURIComponent(token)}` : "";
}

/* 代理市场和图表等客户端只读请求。 */
export async function GET(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const upstreamUrl = new URL(buildUpstreamApiUrl(`/${path.join("/")}`, request));
  upstreamUrl.search = new URL(request.url).search;
  const authorization = resolveAuthorizationHeader(request);

  try {
    const response = await fetch(upstreamUrl, {
      headers: {
        Accept: "application/json",
        ...(authorization ? { Authorization: authorization } : {}),
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

/* 代理受保护动作和配置提交。 */
export async function POST(request: Request, context: RouteContext) {
  const { path } = await context.params;
  const upstreamUrl = new URL(buildUpstreamApiUrl(`/${path.join("/")}`, request));
  upstreamUrl.search = new URL(request.url).search;

  try {
    const response = await fetch(upstreamUrl, {
      method: "POST",
      headers: {
        Accept: request.headers.get("accept") ?? "application/json",
        ...(resolveAuthorizationHeader(request)
          ? { Authorization: resolveAuthorizationHeader(request) }
          : {}),
        ...(request.headers.get("content-type")
          ? { "Content-Type": request.headers.get("content-type") as string }
          : {}),
      },
      body: await request.text(),
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
