import assert from "node:assert/strict";
import test from "node:test";

import { resolveHumanStatus } from "../lib/status-language";

test("maps common legacy statuses into the shared four-state vocabulary", () => {
  assert.equal(resolveHumanStatus("ready").label, "正常");
  assert.equal(resolveHumanStatus("waiting_research").label, "运行中");
  assert.equal(resolveHumanStatus("blocked_by_rule_gate").label, "阻塞");
  assert.equal(resolveHumanStatus("attention_required").label, "需人工处理");
});

test("keeps awaiting and manual review states in the attention bucket", () => {
  assert.equal(resolveHumanStatus("awaiting_manual_review").label, "需人工处理");
  assert.equal(resolveHumanStatus("wait_window").label, "需人工处理");
  assert.equal(resolveHumanStatus("wait_sync").label, "需人工处理");
});

test("preserves detailed labels for accessibility and follow-up text", () => {
  const status = resolveHumanStatus("login required");

  assert.equal(status.label, "需人工处理");
  assert.equal(status.detail, "需要登录");
  assert.equal(status.badgeVariant, "warning");
});
