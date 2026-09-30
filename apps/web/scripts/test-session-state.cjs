/* 用现有TypeScript工具加载会话模块，验证断网与会话失效的区别。 */
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const assert = require("node:assert/strict");
const ts = require("typescript");
const source = fs.readFileSync(path.join(__dirname, "../lib/session.ts"), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;

/* 隔离Next的cookie依赖，执行真实会话判断代码。 */
function loadSession(fetcher, hasCookie = true) {
  const context = {
    exports: {}, fetch: fetcher, AbortSignal,
    process: { env: { QUANT_API_BASE_URL: "http://api/api/v1" } },
    require: name => name === "next/headers"
      ? { cookies: async () => ({ get: () => hasCookie ? { value: "test-token" } : undefined }) }
      : { SESSION_COOKIE_NAME: "quant_admin_token" },
  };
  vm.runInNewContext(compiled, context);
  return context.exports.getControlSessionState;
}

test("后端暂时不可达不是登录过期", async () => {
  const read = loadSession(async () => { throw new Error("网络不可达"); });
  const state = await read();
  assert.equal(state.status, "unavailable");
  assert.equal(state.hasSessionCookie, true);
});

test("失效令牌的HTTP200信封确认为登录过期", async () => {
  const read = loadSession(async () => ({
    ok: true, status: 200, json: async () => ({ error: { code: "session_not_found" } }),
  }));
  assert.equal((await read()).status, "expired");
});

test("后端503不能清掉仍有效的登录", async () => {
  const read = loadSession(async () => ({
    ok: false, status: 503, json: async () => ({ error: null }),
  }));
  assert.equal((await read()).status, "unavailable");
});

test("有效令牌返回已认证状态", async () => {
  const read = loadSession(async () => ({
    ok: true, status: 200, json: async () => ({ error: null, data: { item: { token: "test-token" } } }),
  }));
  assert.equal((await read()).status, "authenticated");
});

test("没有cookie时不调用后端", async () => {
  let calls = 0;
  const read = loadSession(async () => { calls += 1; }, false);
  assert.equal((await read()).status, "anonymous");
  assert.equal(calls, 0);
});
