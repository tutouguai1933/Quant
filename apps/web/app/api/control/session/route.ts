/* 这个文件负责返回当前客户端的会话状态。 */

import { NextResponse } from "next/server";
import { getControlSessionState } from "../../../../lib/session";

export async function GET() {
  try {
    const session = await getControlSessionState();
    return NextResponse.json({
      token: session.token,
      isAuthenticated: session.isAuthenticated,
    });
  } catch (error) {
    return NextResponse.json(
      {
        token: null,
        isAuthenticated: false,
        error: "Failed to get session state",
      },
      { status: 500 }
    );
  }
}
