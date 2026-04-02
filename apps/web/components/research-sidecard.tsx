/* 这个文件负责渲染单币页右侧研究侧卡骨架。 */

import { StatusBadge } from "./status-badge";
import type { ResearchCockpitSummary } from "../lib/api";


type ResearchSidecardProps = {
  cockpit: ResearchCockpitSummary;
  nextStep: string;
};

/* 渲染研究解释和下一步动作侧卡。 */
export function ResearchSidecard({ cockpit, nextStep }: ResearchSidecardProps) {
  const gateStatus = String(cockpit.research_gate.status ?? "unavailable");

  return (
    <aside className="panel">
      <p className="eyebrow">研究侧卡</p>
      <h3>先看研究解释，再决定要不要去策略页</h3>
      <p>研究倾向：{formatText(cockpit.research_bias, "unavailable")}</p>
      <p>推荐策略：{formatText(cockpit.recommended_strategy, "none")}</p>
      <p>判断信心：{formatText(cockpit.confidence, "low")}</p>
      <p>研究门控：<StatusBadge value={gateStatus} /></p>
      <p>研究解释：{formatText(cockpit.research_explanation, "暂无研究解释")}</p>
      <p>模型版本：{formatText(cockpit.model_version, "n/a")}</p>
      <p>生成时间：{formatText(cockpit.generated_at, "n/a")}</p>
      <p>下一步：{formatText(nextStep, "先继续观察。")}</p>
    </aside>
  );
}

/* 把可选文本统一成稳定展示值。 */
function formatText(value: unknown, fallback: string): string {
  const text = String(value ?? "").trim();
  return text.length > 0 ? text : fallback;
}
